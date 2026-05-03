#  Entry point to the project backend 

import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import BackgroundTasks, Depends, FastAPI, File, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import OAuth2PasswordBearer
from lib.core.orm_module import Base, User, Plan, Project, Ouvrage, Question, Material, PlanBatiment, LigneDeCalcul, NoteDeCalcul, get_engine, get_db
from sqlalchemy.orm import Session
from lib.core.security import SECRET_KEY, ALGORITHM, authenticate_admin, decode_access_token, hash_password, CustomOAuth2Form, authenticate_user, create_access_token, Token, ACCESS_TOKEN_EXPIRE_MINUTES
from lib.core.exeption_module import CustomException
from lib.core.knowledge_base_module import add_document, delete_document, get_document, list_documents, search_documents
from lib.core import user_knowledge_base_module as user_kb
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from lib.model import (
    LoginPayload, MeAdminResponse, MeResponse, PlanResponse,
    PublicDocumentDetailResponse, PublicDocumentResponse,
    SearchRequest, VectorSearchResponse,
    UserDocumentResponse, UserDocumentDetailResponse, UserVectorSearchResponse,
    QuestionResponse, QuestionCreateRequest, AnswerRequest,
    MaterialCreateRequest, MaterialResponse, PlanBatimentResponse,
    LigneDeCalculResponse, OuvrageResponse,
    ProjectSummaryResponse, ProjectDetailResponse,
    ProjectCreateRequest, ProjectUpdateRequest,
    WorkflowStatusResponse, ResumeWorkflowRequest,
)
from lib.smart_btp_agent import run_project_workflow, resume_project_workflow

logger = logging.getLogger(__name__)
from typing import Annotated
import re
from datetime import datetime, timedelta, timezone


# ──────────────────────────────────────────────────────────────
# BUS D'ÉVÉNEMENTS SSE (par project_id)
# ──────────────────────────────────────────────────────────────
# Chaque projet possède une liste de queues asyncio (une par client connecté).
# Les événements sont publiés via `_publish_event` et consommés par le générateur SSE.

_sse_subscribers: dict[int, list[asyncio.Queue]] = {}


async def _publish_event(project_id: int, event_type: str, data: dict) -> None:
    """Publie un événement SSE à tous les clients connectés sur ce projet."""
    payload = json.dumps({"type": event_type, **data}, ensure_ascii=False)
    for q in _sse_subscribers.get(project_id, []):
        await q.put(payload)


async def _sse_generator(project_id: int, queue: asyncio.Queue) -> AsyncGenerator[str, None]:
    """Générateur asynchrone qui écoute la queue et envoie les événements SSE."""
    try:
        while True:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"data: {payload}\n\n"
            except asyncio.TimeoutError:
                # Keepalive : empêche la déconnexion du client
                yield ": keepalive\n\n"
    finally:
        subs = _sse_subscribers.get(project_id, [])
        if queue in subs:
            subs.remove(queue)


# ---- Configuration ----- #

app = FastAPI(
    title="kube API",
    description="API pour la gestion des utilisateurs, des projets, des documents et des calculs de métrés dans le cadre du projet kube",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    tags_metadata=[
        { "name" : "Greeting", "description": "Endpoint de test pour vérifier que l'API fonctionne correctement" },
        { "name": "Auth", "description": "Opérations d'authentification et de gestion des utilisateurs" },
        { "name" : "Info", "description": "Endpoints pour récupérer des informations sur les plans d'abonnement et les quotas" },
        { "name" : "Knowledge Base", "description": "Base de connaissance privée de l'utilisateur (documents personnels, recherche vectorielle)" },
        { "name" : "Questions", "description": "Questions posées par le système à l'utilisateur, liées à un projet et un ouvrage" },
        { "name" : "Projects", "description": "Gestion des projets de calcul de métrés" },
        { "name" : "Admin", "description": "Endpoints pour les opérations réservées aux administrateurs" },
    ],
    favicon="./static/favicon.ico"
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", scheme_name="JWT")

USER_ALLREADY_EXISTS_EXCEPTION = CustomException("Un utilisateur avec cet email existe déjà", status_code=400)
EMAIL_INVALID_EXCEPTION = CustomException("Email invalide", status_code=400)


# ---- Middleware ----- #

@app.exception_handler(CustomException)
async def custom_exception_handler(request: Request, exc: CustomException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Autorise toutes les origines (à restreindre en production)
    allow_credentials=True,
    allow_methods=["*"],  # Autorise toutes les méthodes HTTP
    allow_headers=["*"],  # Autorise tous les en-têtes
)

# --- Role Utility function --- #

def require_role(*roles: str):
    def dependency(token: str = Depends(oauth2_scheme)):
        payload = decode_access_token(token)
        if payload.get("role") not in roles:
            raise CustomException("Accès interdit", status_code=403)
        return payload
    return dependency


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Dépendance FastAPI : décode le JWT et retourne l'utilisateur connecté."""
    payload = decode_access_token(token)
    email: str | None = payload.get("sub")
    if not email:
        raise CustomException("Token invalide : champ 'sub' manquant", status_code=401)
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise CustomException("Utilisateur non trouvé", status_code=404)
    return user


# ---- Routes ----- #


# --- Event de démarrage de l'application --- #

@app.on_event("startup")
async def startup_event():
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    try:
        plans = [
            {"name": "Gratuit", "description": "Plan de base gratuit avec un quota limité de tokens par mois", "quota": 10000, "price": 0.0},
            {"name": "Standard", "description": "Plan standard avec un quota plus élevé de tokens par mois", "quota": 100000, "price": 9.99},
            {"name": "Premium", "description": "Plan premium avec un quota très élevé de tokens par mois et des fonctionnalités supplémentaires", "quota": 1000000, "price": 49.99},
        ]
        for plan_data in plans:
            existing_plan = db.query(Plan).filter(Plan.name == plan_data["name"]).first()
            if not existing_plan:
                new_plan = Plan(name=plan_data["name"], description=plan_data["description"], quota=plan_data["quota"], price=plan_data["price"])
                db.add(new_plan)
        db.commit()
    finally:
        db.close()
    return {"message": "Application démarrée avec succès"}

# --- Endpoint de test pour vérifier que l'API fonctionne correctement --- #

@app.get("/", tags=["Greeting"])
async def root():
    return {"message": "Bienvenue sur l'API du projet kube !"}

# --- Endpoint d'authentification --- #

@app.post("/auth/login", tags=["Auth"], response_model=Token)
async def get_token(form_data: Annotated[CustomOAuth2Form, Depends()], db: Annotated[Session, Depends(get_db)]):
    try :
      form_data_dict = form_data.__dict__
      email = form_data_dict.get("username")
      password = form_data_dict.get("password")
      user = authenticate_user(db, email, password)
      access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
      access_token = create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)
      return {"access_token": access_token, "token_type": "bearer"}
    except CustomException as e:
      raise CustomException(e.message, status_code=e.status_code)

@app.get("/auth/me", tags=["Auth"], response_model=MeResponse)
async def read_users_me(token: Annotated[str, Depends(oauth2_scheme)], db: Annotated[Session, Depends(get_db)]):
    try:
        payload = decode_access_token(token)
        email: str = payload.get("sub")
        if email is None:
            raise CustomException("Token invalide : champ 'sub' manquant", status_code=401)
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            raise CustomException("Utilisateur non trouvé", status_code=404)
        return MeResponse(username=user.username, email=user.email, plan_id=user.plan_id, quota_used=user.quota_used, plan_quota=user.plan.quota)
    except CustomException as e:
        raise CustomException(e.message, status_code=e.status_code)

@app.post("/auth/register", tags=["Auth"], response_model=Token)
async def register_user(payload: LoginPayload, db: Annotated[Session, Depends(get_db)]):
    def is_valid_email(email: str) -> bool:
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_regex, email) is not None
    try:
        existing_user = db.query(User).filter(User.email == payload.email).first()
        if existing_user:
            raise USER_ALLREADY_EXISTS_EXCEPTION
        hashed_password = hash_password(payload.password)
        if not is_valid_email(payload.email):
            raise EMAIL_INVALID_EXCEPTION
        new_user = User(username=payload.email.split("@")[0], email=payload.email, password_hash=hashed_password, plan_id=1, quota_used=0)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(data={"sub": new_user.email, "role": new_user.role}, expires_delta=access_token_expires)
        return {"access_token": access_token, "token_type": "bearer"}
    except CustomException as e:
        raise CustomException(e.message, status_code=e.status_code)


@app.post("/auth/admin", tags=["Auth"])
async def authenticate_admin_endpoint(form_data: Annotated[CustomOAuth2Form, Depends()], db: Annotated[Session, Depends(get_db)]):
    form_data_dict = form_data.__dict__
    email = form_data_dict.get("username")
    password = form_data_dict.get("password")
    if authenticate_admin(db, email, password):
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(data={"sub": email, "role": "admin"}, expires_delta=access_token_expires)
        return {"access_token": access_token, "token_type": "bearer"}
    else:
        raise CustomException("Email ou mot de passe administrateur invalide", status_code=401)


@app.get("/plans", tags=["Info"], response_model=list[PlanResponse])
async def get_plans(db: Annotated[Session, Depends(get_db)]):
    plans = db.query(Plan).all()
    return [PlanResponse(id=plan.id, name=plan.name, description=plan.description, quota=plan.quota, price=plan.price) for plan in plans]


@app.get("/admin/users", tags=["Admin"])
async def get_all_users(payload: Annotated[dict, Depends(require_role("admin"))], db: Annotated[Session, Depends(get_db)]):
    users = db.query(User).all()
    return [{"id": user.id, "username": user.username, "email": user.email, "plan_id": user.plan_id, "quota_used": user.quota_used} for user in users]

@app.patch("/admin/users/{user_id}/plan", tags=["Admin"])
async def update_user_plan(
    user_id: int,
    plan_id: int,
    payload: Annotated[dict, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
):
    """Change le plan d'abonnement d'un utilisateur (admin seulement)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise CustomException("Utilisateur non trouvé", status_code=404)
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise CustomException("Plan non trouvé", status_code=404)
    user.plan_id = plan_id
    db.commit()
    db.refresh(user)
    return {"id": user.id, "username": user.username, "email": user.email, "plan_id": user.plan_id, "quota_used": user.quota_used}


@app.get("/admin/me", tags=["Admin"], response_model=MeAdminResponse)
async def read_admin_me(payload: Annotated[dict, Depends(require_role("admin"))], db: Annotated[Session, Depends(get_db)]):
    email = payload.get("sub")
    return MeAdminResponse(email=email)


# ──────────────────────────────────────────────────────────────
# Base de connaissance publique (admin)
# ──────────────────────────────────────────────────────────────

@app.get(
    "/admin/knowledge-base",
    tags=["Admin"],
    response_model=list[PublicDocumentResponse],
    summary="Lister les documents de la base de connaissance",
)
async def get_knowledge_base(
    payload: Annotated[dict, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
):
    """Retourne les métadonnées de tous les documents publics (sans le contenu binaire)."""
    return list_documents(db)


@app.post(
    "/admin/knowledge-base",
    tags=["Admin"],
    response_model=PublicDocumentResponse,
    status_code=201,
    summary="Ajouter un document dans la base de connaissance",
)
async def upload_to_knowledge_base(
    payload: Annotated[dict, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
):
    """
    Upload un fichier, extrait son contenu via OCR / parsing,
    puis l'enregistre dans la table `public_documents`.

    Formats supportés : .pdf, .docx, .xlsx, .xls, .pptx, .csv, .mp4, .mp3, .wav, .m4a
    """
    try:
        content_bytes = await file.read()
        filename = file.filename or "document_inconnu"

        # Déduction de l'extension depuis le nom de fichier
        from pathlib import Path
        extension = Path(filename).suffix or ""

        doc = add_document(
            db=db,
            filename=filename,
            content_bytes=content_bytes,
            extension=extension,
        )
        return PublicDocumentResponse(
            id=doc.id,
            filename=doc.filename,
            extension=doc.extension,
            upload_date=doc.upload_date,
            indexation_status=doc.indexation_status,
        )
    except CustomException as exc:
        raise CustomException(exc.message, status_code=exc.status_code)


@app.post(
    "/admin/knowledge-base/search",
    tags=["Admin"],
    response_model=VectorSearchResponse,
    summary="Recherche sémantique dans la base de connaissance",
)
async def search_knowledge_base(
    request: SearchRequest,
    payload: Annotated[dict, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Recherche sémantique vectorielle dans la base de connaissance publique.

    Retourne les passages les plus proches de la requête de `request`,
    enrichis des métadonnées et du texte complet de leur document source
    (récupéré depuis PostgreSQL via le `doc_id`).

    Paramètres (JSON) :
    - **query** : question ou texte en langage naturel
    - **top_k** : nombre maximal de résultats (défaut : 5, max recommandé : 20)
    """
    try:
        return search_documents(db, request.query, top_k=min(request.top_k, 20))
    except CustomException as exc:
        raise CustomException(exc.message, status_code=exc.status_code)


@app.get(
    "/admin/knowledge-base/{doc_id}",
    tags=["Admin"],
    response_model=PublicDocumentDetailResponse,
    summary="Détail d'un document de la base de connaissance",
)
async def get_knowledge_base_document(
    doc_id: int,
    payload: Annotated[dict, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
):
    """Retourne les métadonnées et le contenu textuel extrait d'un document (sans le binaire)."""
    try:
        doc = get_document(db, doc_id)
        return PublicDocumentDetailResponse(
            id=doc.id,
            filename=doc.filename,
            extension=doc.extension,
            upload_date=doc.upload_date,
            indexation_status=doc.indexation_status,
            text_content=doc.text_content,
        )
    except CustomException as exc:
        raise CustomException(exc.message, status_code=exc.status_code)


@app.get(
    "/admin/knowledge-base/{doc_id}/content",
    tags=["Admin"],
    response_class=Response,
    summary="Contenu textuel brut d'un document indexé",
)
async def get_knowledge_base_document_content(
    doc_id: int,
    payload: Annotated[dict, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Retourne le contenu textuel extrait (OCR / parsing) d'un document
    sous forme de texte brut (`text/plain`).

    Retourne 204 No Content si le document n'a pas de texte indexé.
    """
    try:
        doc = get_document(db, doc_id)
        if not doc.text_content or not doc.text_content.strip():
            return Response(status_code=204)
        return Response(
            content=doc.text_content.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
        )
    except CustomException as exc:
        raise CustomException(exc.message, status_code=exc.status_code)


@app.get(
    "/admin/knowledge-base/{doc_id}/download",
    tags=["Admin"],
    response_class=Response,
    summary="Télécharger le fichier original d'un document",
)
async def download_knowledge_base_document(
    doc_id: int,
    payload: Annotated[dict, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
):
    """Retourne le contenu binaire original du document avec les bons en-têtes de téléchargement."""
    try:
        doc = get_document(db, doc_id)
        return Response(
            content=doc.content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{doc.filename}"',
            },
        )
    except CustomException as exc:
        raise CustomException(exc.message, status_code=exc.status_code)


@app.delete(
    "/admin/knowledge-base/{doc_id}",
    tags=["Admin"],
    status_code=204,
    summary="Supprimer un document de la base de connaissance",
)
async def remove_from_knowledge_base(
    doc_id: int,
    payload: Annotated[dict, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
):
    """Supprime définitivement un document de la base de connaissance par son ID."""
    try:
        delete_document(db, doc_id)
    except CustomException as exc:
        raise CustomException(exc.message, status_code=exc.status_code)


# ──────────────────────────────────────────────────────────────
# Base de connaissance privée (utilisateur)
# ──────────────────────────────────────────────────────────────

@app.get(
    "/knowledge-base",
    tags=["Knowledge Base"],
    response_model=list[UserDocumentResponse],
    summary="Lister mes documents",
)
async def get_user_knowledge_base(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Retourne les métadonnées de tous les documents de l'utilisateur connecté."""
    return user_kb.list_documents(db, current_user.id)


@app.post(
    "/knowledge-base",
    tags=["Knowledge Base"],
    response_model=UserDocumentResponse,
    status_code=201,
    summary="Ajouter un document dans ma base de connaissance",
)
async def upload_to_user_knowledge_base(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
):
    """
    Upload un fichier, extrait son contenu via OCR / parsing et l'enregistre
    dans la base de connaissance privée de l'utilisateur connecté.

    Formats supportés : .pdf, .docx, .xlsx, .xls, .pptx, .csv, .mp4, .mp3, .wav, .m4a
    """
    try:
        content_bytes = await file.read()
        filename = file.filename or "document_inconnu"

        from pathlib import Path
        extension = Path(filename).suffix or ""

        doc = user_kb.add_document(
            db=db,
            user_id=current_user.id,
            filename=filename,
            content_bytes=content_bytes,
            extension=extension,
        )
        return UserDocumentResponse(
            id=doc.id,
            filename=doc.filename,
            extension=doc.extension,
            upload_date=doc.upload_date,
            indexation_status=doc.indexation_status,
        )
    except CustomException as exc:
        raise CustomException(exc.message, status_code=exc.status_code)


@app.post(
    "/knowledge-base/search",
    tags=["Knowledge Base"],
    response_model=UserVectorSearchResponse,
    summary="Recherche sémantique dans ma base de connaissance",
)
async def search_user_knowledge_base(
    request: SearchRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Recherche sémantique vectorielle dans la base de connaissance privée
    de l'utilisateur connecté. Les résultats sont strictement isolés par utilisateur.

    Paramètres (JSON) :
    - **query** : question ou texte en langage naturel
    - **top_k** : nombre maximal de résultats (défaut : 5, max recommandé : 20)
    """
    try:
        return user_kb.search_documents(
            db, current_user.id, request.query, top_k=min(request.top_k, 20)
        )
    except CustomException as exc:
        raise CustomException(exc.message, status_code=exc.status_code)


@app.get(
    "/knowledge-base/{doc_id}",
    tags=["Knowledge Base"],
    response_model=UserDocumentDetailResponse,
    summary="Détail d'un de mes documents",
)
async def get_user_knowledge_base_document(
    doc_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Retourne les métadonnées et le contenu textuel extrait d'un document (sans le binaire)."""
    try:
        doc = user_kb.get_document(db, current_user.id, doc_id)
        return UserDocumentDetailResponse(
            id=doc.id,
            filename=doc.filename,
            extension=doc.extension,
            upload_date=doc.upload_date,
            indexation_status=doc.indexation_status,
            text_content=doc.text_content,
        )
    except CustomException as exc:
        raise CustomException(exc.message, status_code=exc.status_code)


@app.get(
    "/knowledge-base/{doc_id}/content",
    tags=["Knowledge Base"],
    response_class=Response,
    summary="Contenu textuel brut d'un de mes documents indexés",
)
async def get_user_knowledge_base_document_content(
    doc_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Retourne le contenu textuel extrait (OCR / parsing) d'un document
    sous forme de texte brut (`text/plain`).

    Retourne 204 No Content si le document n'a pas de texte indexé.
    """
    try:
        doc = user_kb.get_document(db, current_user.id, doc_id)
        if not doc.text_content or not doc.text_content.strip():
            return Response(status_code=204)
        return Response(
            content=doc.text_content.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
        )
    except CustomException as exc:
        raise CustomException(exc.message, status_code=exc.status_code)


@app.get(
    "/knowledge-base/{doc_id}/download",
    tags=["Knowledge Base"],
    response_class=Response,
    summary="Télécharger un de mes fichiers originaux",
)
async def download_user_knowledge_base_document(
    doc_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Retourne le contenu binaire original du document avec les bons en-têtes de téléchargement."""
    try:
        doc = user_kb.get_document(db, current_user.id, doc_id)
        return Response(
            content=doc.content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{doc.filename}"',
            },
        )
    except CustomException as exc:
        raise CustomException(exc.message, status_code=exc.status_code)


@app.delete(
    "/knowledge-base/{doc_id}",
    tags=["Knowledge Base"],
    status_code=204,
    summary="Supprimer un de mes documents",
)
async def remove_from_user_knowledge_base(
    doc_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Supprime définitivement un document de la base de connaissance privée."""
    try:
        user_kb.delete_document(db, current_user.id, doc_id)
    except CustomException as exc:
        raise CustomException(exc.message, status_code=exc.status_code)


# ──────────────────────────────────────────────────────────────
# Questions système → utilisateur
# ──────────────────────────────────────────────────────────────

def _build_question_response(q: Question) -> QuestionResponse:
    return QuestionResponse(
        id=q.id,
        project_id=q.project_id,
        project_name=q.project.name if q.project else "",
        ouvrage_id=q.ouvrage_id,
        ouvrage_name=q.ouvrage.name if q.ouvrage else None,
        question_text=q.question_text,
        answer_text=q.answer_text,
        status=q.status,
        asked_date=q.asked_date,
        answered_date=q.answered_date,
    )


@app.get(
    "/questions",
    tags=["Questions"],
    response_model=list[QuestionResponse],
    summary="Lister toutes mes questions",
)
async def list_questions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    status: str | None = None,
):
    """
    Retourne toutes les questions adressées à l'utilisateur connecté.
    Filtre optionnel par `status` : `pending` ou `answered`.
    """
    query = (
        db.query(Question)
        .join(Question.project)
        .filter(Project.user_id == current_user.id)
    )
    if status:
        query = query.filter(Question.status == status)
    questions = query.order_by(Question.asked_date.desc()).all()
    return [_build_question_response(q) for q in questions]


@app.post(
    "/questions",
    tags=["Questions"],
    response_model=QuestionResponse,
    status_code=201,
    summary="Créer une question (système / agent)",
)
async def create_question(
    payload: QuestionCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Crée une question liée à un projet (et optionnellement un ouvrage).
    Le projet doit appartenir à l'utilisateur connecté.
    """
    project = db.query(Project).filter(
        Project.id == payload.project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise CustomException("Projet introuvable ou accès refusé", status_code=404)
    if payload.ouvrage_id is not None:
        ouvrage = db.query(Ouvrage).filter(
            Ouvrage.id == payload.ouvrage_id,
            Ouvrage.project_id == payload.project_id,
        ).first()
        if not ouvrage:
            raise CustomException("Ouvrage introuvable", status_code=404)
    new_question = Question(
        project_id=payload.project_id,
        ouvrage_id=payload.ouvrage_id,
        question_text=payload.question_text,
        status="pending",
        asked_date=datetime.now(timezone.utc).isoformat(),
    )
    db.add(new_question)
    db.commit()
    db.refresh(new_question)
    return _build_question_response(new_question)


@app.patch(
    "/questions/{question_id}/answer",
    tags=["Questions"],
    response_model=QuestionResponse,
    summary="Répondre à une question",
)
async def answer_question(
    question_id: int,
    payload: AnswerRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Soumet la réponse de l'utilisateur à une question en attente."""
    question = (
        db.query(Question)
        .join(Question.project)
        .filter(Question.id == question_id, Project.user_id == current_user.id)
        .first()
    )
    if not question:
        raise CustomException("Question introuvable ou accès refusé", status_code=404)
    if question.status == "answered":
        raise CustomException("Cette question a déjà été répondue", status_code=400)
    question.answer_text = payload.answer_text
    question.status = "answered"
    question.answered_date = datetime.now(timezone.utc).isoformat()
    db.commit()
    db.refresh(question)
    return _build_question_response(question)


@app.delete(
    "/questions/{question_id}",
    tags=["Questions"],
    status_code=204,
    summary="Supprimer une question",
)
async def delete_question(
    question_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Supprime une question (seulement si elle appartient à l'utilisateur)."""
    question = (
        db.query(Question)
        .join(Question.project)
        .filter(Question.id == question_id, Project.user_id == current_user.id)
        .first()
    )
    if not question:
        raise CustomException("Question introuvable ou accès refusé", status_code=404)
    db.delete(question)
    db.commit()


# ──────────────────────────────────────────────────────────────
# Projets
# ──────────────────────────────────────────────────────────────

def _build_material_response(m: Material) -> MaterialResponse:
    return MaterialResponse(
        id=m.id,
        name=m.name,
        description=m.description,
        unite_defaut=m.unite_defaut,
        project_id=m.project_id,
    )


def _build_plan_batiment_response(p: PlanBatiment) -> PlanBatimentResponse:
    return PlanBatimentResponse(
        id=p.id,
        name=p.name,
        description=p.description,
        upload_date=p.upload_date,
        extension=p.extension,
        project_id=p.project_id,
    )


def _build_ouvrage_response(o: Ouvrage) -> OuvrageResponse:
    lignes = [
        LigneDeCalculResponse(
            id=l.id,
            description=l.description,
            quantity=l.quantity,
            unit=l.unit,
            position=l.position,
            material=_build_material_response(l.material),
        )
        for l in sorted(o.lignes_de_calcul, key=lambda x: x.position)
    ]
    return OuvrageResponse(
        id=o.id,
        name=o.name,
        categorie=o.categorie,
        description=o.description,
        position=o.position,
        lignes_de_calcul=lignes,
    )


def _build_project_summary(p: Project) -> ProjectSummaryResponse:
    pending_questions = sum(1 for q in p.questions if q.status == "pending")
    return ProjectSummaryResponse(
        id=p.id,
        name=p.name,
        description=p.description,
        creation_date=p.creation_date,
        status=p.status,
        current_step=p.current_step,
        error_message=p.error_message,
        last_updated=p.last_updated,
        ouvrages_count=len(p.ouvrages),
        questions_pending_count=pending_questions,
        plans_count=len(p.plans_batiment),
        materials_count=len(p.materials),
    )


def _build_project_detail(p: Project) -> ProjectDetailResponse:
    summary = _build_project_summary(p)
    materials = [_build_material_response(m) for m in p.materials]
    ouvrages = [_build_ouvrage_response(o) for o in sorted(p.ouvrages, key=lambda x: x.position)]
    questions = [_build_question_response(q) for q in p.questions]
    plans = [_build_plan_batiment_response(pb) for pb in p.plans_batiment]
    return ProjectDetailResponse(
        **summary.model_dump(),
        materials=materials,
        ouvrages=ouvrages,
        questions=questions,
        plans_batiment=plans,
    )


@app.get(
    "/projects",
    tags=["Projects"],
    response_model=list[ProjectSummaryResponse],
    summary="Lister mes projets",
)
async def list_projects(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Retourne la liste des projets de l'utilisateur connecté, du plus récent au plus ancien."""
    projects = (
        db.query(Project)
        .filter(Project.user_id == current_user.id)
        .order_by(Project.last_updated.desc())
        .all()
    )
    return [_build_project_summary(p) for p in projects]


@app.post(
    "/projects",
    tags=["Projects"],
    response_model=ProjectDetailResponse,
    status_code=201,
    summary="Créer un nouveau projet",
)
async def create_project(
    payload: ProjectCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Crée un nouveau projet pour l'utilisateur connecté.
    Les matériaux peuvent être fournis directement dans le payload.
    """
    now = datetime.now(timezone.utc).isoformat()
    project = Project(
        user_id=current_user.id,
        name=payload.name,
        description=payload.description,
        creation_date=now,
        status="pending",
        last_updated=now,
    )
    db.add(project)
    db.flush()  # Obtenir l'ID avant le commit

    for mat in payload.materials:
        material = Material(
            name=mat.name,
            description=mat.description,
            unite_defaut=mat.unite_defaut,
            project_id=project.id,
        )
        db.add(material)

    db.commit()
    db.refresh(project)
    detail = _build_project_detail(project)

    # Le workflow est déclenché manuellement via POST /projects/{id}/workflow
    # après que l'utilisateur a uploadé ses plans de bâtiment.

    return detail


async def _make_db_session():
    """Crée et retourne une session BDD indépendante (pour les tâches de fond)."""
    from sqlalchemy.orm import sessionmaker as _SM
    engine = get_engine()
    SessionLocal = _SM(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


async def _run_workflow_background(project_id: int, user_id: int) -> None:
    """
    Tâche de fond lancée dès la création du projet.
    Ouvre sa propre session BDD, exécute le workflow et publie les événements SSE.
    """
    db = await _make_db_session()

    async def on_event(event_type: str, data: dict) -> None:
        await _publish_event(project_id, event_type, data)

    logger.info("Workflow start project_id=%s user_id=%s", project_id, user_id)
    try:
        await run_project_workflow(
            project_id=project_id,
            user_id=user_id,
            db=db,
            event_callback=on_event,
        )
        logger.info("Workflow done project_id=%s", project_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Workflow error project_id=%s: %s", project_id, exc)
        await _publish_event(project_id, "error", {"message": str(exc)})
    finally:
        db.close()


@app.get(
    "/projects/materials",
    tags=["Projects"],
    response_model=list[MaterialResponse],
    summary="Lister tous mes matériaux (tous projets confondus)",
)
async def list_all_user_materials(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Retourne tous les matériaux utilisés dans les projets de l'utilisateur.
    Utile pour proposer une réutilisation lors de la création d'un nouveau projet.
    """
    materials = (
        db.query(Material)
        .join(Material.project)
        .filter(Project.user_id == current_user.id)
        .all()
    )
    return [_build_material_response(m) for m in materials]


@app.get(
    "/projects/{project_id}",
    tags=["Projects"],
    response_model=ProjectDetailResponse,
    summary="Détail d'un projet",
)
async def get_project(
    project_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Retourne le détail complet d'un projet (ouvrages, matériaux, questions, plans)."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise CustomException("Projet introuvable ou accès refusé", status_code=404)
    return _build_project_detail(project)


@app.patch(
    "/projects/{project_id}",
    tags=["Projects"],
    response_model=ProjectDetailResponse,
    summary="Mettre à jour un projet",
)
async def update_project(
    project_id: int,
    payload: ProjectUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Met à jour le nom et/ou la description d'un projet."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise CustomException("Projet introuvable ou accès refusé", status_code=404)
    if payload.name is not None:
        project.name = payload.name
    if payload.description is not None:
        project.description = payload.description
    project.last_updated = datetime.now(timezone.utc).isoformat()
    db.commit()
    db.refresh(project)
    return _build_project_detail(project)


@app.delete(
    "/projects/{project_id}",
    tags=["Projects"],
    status_code=204,
    summary="Supprimer un projet",
)
async def delete_project(
    project_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Supprime définitivement un projet et toutes ses données associées (cascade)."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise CustomException("Projet introuvable ou accès refusé", status_code=404)
    db.delete(project)
    db.commit()


@app.post(
    "/projects/{project_id}/plans",
    tags=["Projects"],
    response_model=PlanBatimentResponse,
    status_code=201,
    summary="Ajouter un plan de bâtiment",
)
async def upload_plan_batiment(
    project_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
    name: str = "",
    description: str | None = None,
):
    """
    Upload un plan de bâtiment (PDF, image, DWG...) attaché au projet.
    Le nom par défaut est le nom du fichier si `name` est vide.
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise CustomException("Projet introuvable ou accès refusé", status_code=404)

    from pathlib import Path
    content_bytes = await file.read()
    filename = file.filename or "plan_inconnu"
    extension = Path(filename).suffix or ""
    plan_name = name.strip() if name.strip() else filename

    plan = PlanBatiment(
        name=plan_name,
        description=description,
        content=content_bytes,
        upload_date=datetime.now(timezone.utc).isoformat(),
        extension=extension,
        project_id=project.id,
    )
    db.add(plan)
    project.last_updated = datetime.now(timezone.utc).isoformat()
    db.commit()
    db.refresh(plan)
    return _build_plan_batiment_response(plan)


@app.delete(
    "/projects/{project_id}/plans/{plan_id}",
    tags=["Projects"],
    status_code=204,
    summary="Supprimer un plan de bâtiment",
)
async def delete_plan_batiment(
    project_id: int,
    plan_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Supprime un plan de bâtiment appartenant au projet de l'utilisateur."""
    plan = (
        db.query(PlanBatiment)
        .join(PlanBatiment.project)
        .filter(
            PlanBatiment.id == plan_id,
            PlanBatiment.project_id == project_id,
            Project.user_id == current_user.id,
        )
        .first()
    )
    if not plan:
        raise CustomException("Plan introuvable ou accès refusé", status_code=404)
    db.delete(plan)
    db.commit()


# ──────────────────────────────────────────────────────────────
# Workflow agentique
# ──────────────────────────────────────────────────────────────

@app.post(
    "/projects/{project_id}/run",
    tags=["Projects"],
    response_model=WorkflowStatusResponse,
    summary="Lancer le calcul automatique de métrés d'un projet",
)
async def start_project_workflow(
    project_id: int,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Lance le workflow en arrière-plan et retourne immédiatement.
    Utiliser ``GET /projects/{project_id}/stream`` pour suivre la progression en temps réel.
    """
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise CustomException("Projet introuvable ou accès refusé", status_code=404)

    background_tasks.add_task(_run_workflow_background, project_id, current_user.id)
    return WorkflowStatusResponse(status="calcul_running", message="Workflow démarré en arrière-plan.")


@app.post(
    "/projects/{project_id}/resume",
    tags=["Projects"],
    response_model=WorkflowStatusResponse,
    summary="Reprendre le workflow après la réponse à une question",
)
async def resume_workflow(
    project_id: int,
    payload: ResumeWorkflowRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Soumet la réponse de l'utilisateur et reprend le workflow en arrière-plan.
    La suite de la progression est transmise via le flux SSE.
    """
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise CustomException("Projet introuvable ou accès refusé", status_code=404)
    if project.status != "waiting_user":
        raise CustomException(
            f"Le projet n'est pas en attente de réponse (statut : {project.status}).",
            status_code=400,
        )

    # Mise à jour de la question en BDD
    pending_q = (
        db.query(Question)
        .filter(Question.project_id == project_id, Question.status == "pending")
        .order_by(Question.asked_date.desc())
        .first()
    )
    if pending_q:
        pending_q.answer_text = payload.answer
        pending_q.status = "answered"
        pending_q.answered_date = datetime.now(timezone.utc).isoformat()
        db.commit()

    await _publish_event(project_id, "answer_received", {"answer": payload.answer})

    background_tasks.add_task(_resume_workflow_background, project_id, current_user.id, payload.answer)
    return WorkflowStatusResponse(status="calcul_running", message="Réponse reçue, reprise du workflow.")


async def _resume_workflow_background(project_id: int, user_id: int, answer: str) -> None:
    """Reprend le workflow dans un thread de fond après la réponse utilisateur."""
    db = await _make_db_session()

    async def on_event(event_type: str, data: dict) -> None:
        await _publish_event(project_id, event_type, data)

    try:
        await resume_project_workflow(
            project_id=project_id,
            user_id=user_id,
            answer=answer,
            db=db,
            event_callback=on_event,
        )
    except Exception as exc:  # noqa: BLE001
        await _publish_event(project_id, "error", {"message": str(exc)})
    finally:
        db.close()


@app.get(
    "/projects/{project_id}/stream",
    tags=["Projects"],
    summary="Flux SSE temps réel de l'avancement du workflow",
)
async def stream_project_events(
    project_id: int,
    token: str,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Flux Server-Sent Events (SSE) pour suivre en temps réel l'avancement
    du workflow agentique d'un projet.

    Authentification : passer le JWT en query param ``?token=…``
    (les EventSource navigateur ne supportent pas les headers custom).

    **Types d'événements émis** :
    - ``step``       — étape en cours (message + ouvrage courant)
    - ``ouvrage``    — nouvel ouvrage créé
    - ``calcul``     — ligne de calcul ajoutée
    - ``question``   — question posée à l'utilisateur (workflow suspendu)
    - ``answer_received`` — réponse utilisateur reçue
    - ``quota``      — quota tokens mis à jour ``{quota_used, plan_quota}``
    - ``done``       — workflow terminé avec succès
    - ``error``      — erreur inattendue
    """
    from lib.core.security import decode_access_token

    payload = decode_access_token(token)
    email = payload.get("sub")
    if not email:
        return JSONResponse(status_code=401, content={"detail": "Token invalide"})

    user = db.query(User).filter(User.email == email).first()
    if not user:
        return JSONResponse(status_code=401, content={"detail": "Utilisateur inconnu"})

    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == user.id)
        .first()
    )
    if not project:
        return JSONResponse(status_code=404, content={"detail": "Projet introuvable ou accès refusé"})

    queue: asyncio.Queue = asyncio.Queue()
    _sse_subscribers.setdefault(project_id, []).append(queue)

    return StreamingResponse(
        _sse_generator(project_id, queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

