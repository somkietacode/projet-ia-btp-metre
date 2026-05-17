from pydantic import BaseModel


class LoginPayload(BaseModel):
    email: str
    password: str

class MeResponse(BaseModel):
    username: str
    email: str
    plan_id: int
    quota_used: int
    plan_quota: int

class MeAdminResponse(BaseModel):
    email: str
    



class PlanResponse(BaseModel):
    id: int
    name: str
    description: str
    quota: int
    price: float


class PublicDocumentResponse(BaseModel):
    """Métadonnées d'un document de la base de connaissance publique.
    Le contenu binaire est exclu pour ne pas surcharger les réponses réseau.
    """
    id: int
    filename: str
    extension: str
    upload_date: str
    indexation_status: str  # "pending" | "indexing" | "indexed" | "failed"


class PublicDocumentDetailResponse(PublicDocumentResponse):
    """Métadonnées + contenu textuel extrait (sans le binaire)."""
    text_content: str | None  # None si l'indexation a échoué


class VectorSearchChunkResult(BaseModel):
    """Un résultat de recherche vectorielle : chunk + document source."""
    score: float                    # similarité cosinus [0, 1]
    chunk: str                      # passage de texte correspondant
    description: str                # première phrase du chunk
    keywords: list[str]             # mots-clés NLP (YAKE)
    chunk_index: int                # position du chunk dans le document
    total_chunks: int               # nombre total de chunks du document
    document: PublicDocumentDetailResponse  # document source complet (PostgreSQL)


class VectorSearchResponse(BaseModel):
    """Réponse complète d'une recherche vectorielle."""
    query: str
    total_results: int
    results: list[VectorSearchChunkResult]

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


# ─── Base de connaissance privée (utilisateur) ────────────────────────────────

class UserDocumentResponse(BaseModel):
    """Métadonnées d'un document de la base de connaissance privée.
    Le contenu binaire est exclu pour ne pas surcharger les réponses réseau.
    """
    id: int
    filename: str
    extension: str
    upload_date: str
    indexation_status: str  # "pending" | "indexing" | "indexed" | "failed"


class UserDocumentDetailResponse(UserDocumentResponse):
    """Métadonnées + contenu textuel extrait (sans le binaire)."""
    text_content: str | None  # None si l'indexation a échoué


class UserVectorSearchChunkResult(BaseModel):
    """Un résultat de recherche vectorielle privée : chunk + document source."""
    score: float                       # similarité cosinus [0, 1]
    chunk: str                         # passage de texte correspondant
    description: str                   # première phrase du chunk
    keywords: list[str]                # mots-clés NLP (YAKE)
    chunk_index: int                   # position du chunk dans le document
    total_chunks: int                  # nombre total de chunks du document
    document: UserDocumentDetailResponse  # document source complet (PostgreSQL)


class UserVectorSearchResponse(BaseModel):
    """Réponse complète d'une recherche vectorielle privée."""
    query: str
    total_results: int
    results: list[UserVectorSearchChunkResult]


# ──────────────────────────────────────────────────────────────
# Questions système → utilisateur
# ──────────────────────────────────────────────────────────────

class QuestionResponse(BaseModel):
    """Question posée par le système à l'utilisateur."""
    id: int
    project_id: int
    project_name: str
    ouvrage_id: int | None
    ouvrage_name: str | None
    question_text: str
    answer_text: str | None
    status: str          # "pending" | "answered"
    asked_date: str
    answered_date: str | None


class QuestionCreateRequest(BaseModel):
    """Payload pour créer une question (appelé par le système / agent)."""
    project_id: int
    ouvrage_id: int | None = None
    question_text: str


class AnswerRequest(BaseModel):
    """Payload pour soumettre une réponse à une question."""
    answer_text: str


# ──────────────────────────────────────────────────────────────
# Projets
# ──────────────────────────────────────────────────────────────

class MaterialCreateRequest(BaseModel):
    """Payload pour créer un matériau dans le catalogue global (admin)."""
    name: str
    description: str | None = None
    unite_defaut: str
    unite_commerciale: str | None = None
    conditionnement: str | None = None
    facteur_conversion: float | None = None


class MaterialResponse(BaseModel):
    """Représentation d'un matériau du catalogue global."""
    id: int
    name: str
    description: str | None
    unite_defaut: str
    unite_commerciale: str | None
    conditionnement: str | None
    facteur_conversion: float | None


class MaterialImportResult(BaseModel):
    """Résultat d'un import de catalogue depuis un fichier Excel."""
    created: int
    updated: int
    errors: list[str]


class PlanBatimentResponse(BaseModel):
    """Représentation d'un plan de bâtiment (métadonnées, sans le binaire)."""
    id: int
    name: str
    description: str | None
    upload_date: str
    extension: str
    project_id: int


class LigneDeCalculResponse(BaseModel):
    """Ligne de calcul associée à un ouvrage."""
    id: int
    description: str
    quantity: float
    unit: str
    commercial_quantity: float | None
    commercial_unit: str | None
    position: int
    material: MaterialResponse


class OuvrageResponse(BaseModel):
    """Ouvrage d'un projet avec ses lignes de calcul."""
    id: int
    name: str
    categorie: str
    description: str | None
    position: int
    lignes_de_calcul: list[LigneDeCalculResponse]


class ProjectSummaryResponse(BaseModel):
    """Résumé d'un projet (vue liste)."""
    id: int
    name: str
    description: str | None
    creation_date: str
    status: str
    current_step: str | None
    error_message: str | None
    last_updated: str
    ouvrages_count: int
    questions_pending_count: int
    plans_count: int
    materials_count: int


class ProjectDetailResponse(ProjectSummaryResponse):
    """Détail complet d'un projet."""
    materials: list[MaterialResponse]
    ouvrages: list[OuvrageResponse]
    questions: list[QuestionResponse]
    plans_batiment: list[PlanBatimentResponse]


class ProjectCreateRequest(BaseModel):
    """Payload pour créer un nouveau projet."""
    name: str
    description: str | None = None


class ProjectUpdateRequest(BaseModel):
    """Payload pour mettre à jour les infos d'un projet."""
    name: str | None = None
    description: str | None = None


# ──────────────────────────────────────────────────────────────
# Workflow agentique
# ──────────────────────────────────────────────────────────────

class WorkflowQuestionResponse(BaseModel):
    """Question posée par le workflow et en attente de réponse."""
    id: int | None
    text: str
    ouvrage_id: int | None


class WorkflowStatusResponse(BaseModel):
    """
    Réponse retournée par les endpoints /run et /resume du workflow agentique.
    """
    status: str
    """
    Statut courant :
        "calcul_running" — le workflow tourne en arrière-plan (ne devrait pas arriver en sync)
        "waiting_user"   — le workflow est suspendu, une question attend une réponse
        "done"           — tous les ouvrages ont été calculés avec succès
        "error"          — une erreur s'est produite (voir le champ error_message du projet)
    """
    question: WorkflowQuestionResponse | None = None
    message: str


class ResumeWorkflowRequest(BaseModel):
    """Payload pour reprendre le workflow après la réponse de l'utilisateur."""
    answer: str
