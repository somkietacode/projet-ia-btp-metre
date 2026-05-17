from dotenv import load_dotenv
from sqlalchemy import create_engine, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from typing import List, Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
import os


# ---- Configuration ----- #

load_dotenv()
DB_URL = os.getenv("DB_URL")



# ---- Base de données ----- #

class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    # Définition des colonnes de la table "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(nullable=False)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(nullable=False)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"), nullable=False) # Clé étrangère vers la table "plans"
    quota_used: Mapped[int] = mapped_column(nullable=False, default=0) # Nombre de tokens utilisés ce mois-ci
    role: Mapped[str] = mapped_column(nullable=False, default="user") # Rôle de l'utilisateur ("user" ou "admin")
    
    plan: Mapped["Plan"] = relationship("Plan", back_populates="users") # Relation avec la table "plans"
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="user", cascade="all, delete-orphan") # Relation avec la table "documents"
    projects: Mapped[List["Project"]] = relationship("Project", back_populates="user", cascade="all, delete-orphan") # Relation avec la table "projects"


    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}', plan_id={self.plan_id}, quota_used={self.quota_used})>"

class Plan(Base):
    __tablename__ = "plans"

    # Définition des colonnes de la table "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[Optional[str]] = mapped_column(nullable=True)
    quota: Mapped[int] = mapped_column(nullable=False) # Nombre de tokens autorisés par mois
    price: Mapped[float] = mapped_column(nullable=False) # Prix du plan en euros

    users: Mapped[List["User"]] = relationship("User", back_populates="plan", cascade="all, delete-orphan") # Relation avec la table "users"

    def __repr__(self):
        return f"<Plan(id={self.id}, name='{self.name}', description='{self.description}', quota={self.quota}, price={self.price})>"

class Document(Base):
    __tablename__ = "documents"

    # Définition des colonnes de la table "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False) # ID de l'utilisateur auquel appartient le document 
    filename: Mapped[str] = mapped_column(nullable=False)
    content: Mapped[bytes] = mapped_column(nullable=False) # Contenu du document stocké en binaire
    text_content: Mapped[Optional[str]] = mapped_column(nullable=True) # Contenu textuel extrait du document (pour les recherches textuelles)
    upload_date: Mapped[str] = mapped_column(nullable=False) # Date de téléchargement du document
    extension: Mapped[str] = mapped_column(nullable=False) # Extension du fichier (ex: .pdf, .docx, etc.)
    indexation_status: Mapped[str] = mapped_column(nullable=False, default="pending") # Statut d'indexation : "pending" | "indexing" | "indexed" | "failed"

    user: Mapped["User"] = relationship("User", back_populates="documents") # Relation avec la table "users" (clé étrangère vers "users.id")

    def __repr__(self):
        return f"<Document(id={self.id}, filename='{self.filename}', upload_date='{self.upload_date}', extension='{self.extension}')>"

class PublicDocument(Base):
    __tablename__ = "public_documents"

    # Définition des colonnes de la table "public_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(nullable=False)
    content: Mapped[bytes] = mapped_column(nullable=False) # Contenu du document stocké en binaire
    text_content: Mapped[Optional[str]] = mapped_column(nullable=True) # Contenu textuel extrait du document (pour les recherches textuelles)
    upload_date: Mapped[str] = mapped_column(nullable=False) # Date de téléchargement du document
    extension: Mapped[str] = mapped_column(nullable=False) # Extension du fichier (ex: .pdf, .docx, etc.)
    indexation_status: Mapped[str] = mapped_column(nullable=False, default="pending") # Statut d'indexation : "pending" | "indexing" | "indexed" | "failed"

    def __repr__(self):
        return f"<PublicDocument(id={self.id}, filename='{self.filename}', upload_date='{self.upload_date}', extension='{self.extension}', indexation_status='{self.indexation_status}')>"

class Project(Base):
    __tablename__ = "projects"

    # Définition des colonnes de la table "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False) # ID de l'utilisateur auquel appartient le projet
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[Optional[str]] = mapped_column(nullable=True)
    creation_date: Mapped[str] = mapped_column(nullable=False) # Date de création du projet

    # Suivi de l'état du workflow multi-agent
    status: Mapped[str] = mapped_column(nullable=False, default="pending") # "pending" | "vision_running" | "vision_done" | "extraction_running" | "waiting_user" | "calcul_running" | "done" | "error"
    current_step: Mapped[Optional[str]] = mapped_column(nullable=True) # Étape en cours (ex: "Analyse plan RDC.pdf")
    error_message: Mapped[Optional[str]] = mapped_column(nullable=True) # Message d'erreur si status="error"
    last_updated: Mapped[str] = mapped_column(nullable=False) # Dernière mise à jour du workflow

    user: Mapped["User"] = relationship("User", back_populates="projects") # Relation avec la table "users" (clé étrangère vers "users.id")
    plans_batiment: Mapped[List["PlanBatiment"]] = relationship("PlanBatiment", back_populates="project", cascade="all, delete-orphan") # Relation avec la table "plans_batiment"
    ouvrages: Mapped[List["Ouvrage"]] = relationship("Ouvrage", back_populates="project", cascade="all, delete-orphan") # Relation avec la table "ouvrages"
    questions: Mapped[List["Question"]] = relationship("Question", back_populates="project", cascade="all, delete-orphan") # Relation avec la table "questions"

    def __repr__(self):
        return f"<Project(id={self.id}, name='{self.name}', status='{self.status}')>"

class PlanBatiment(Base):
    __tablename__ = "plans_batiment"

    # Définition des colonnes de la table "plans_batiment"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[Optional[str]] = mapped_column(nullable=True)
    content: Mapped[bytes] = mapped_column(nullable=False) # Contenu du plan stocké en binaire
    upload_date: Mapped[str] = mapped_column(nullable=False) # Date de téléchargement du plan
    extension: Mapped[str] = mapped_column(nullable=False) # Extension du fichier (ex: .pdf, .dwg, etc.)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False) # ID du projet auquel appartient le plan de bâtiment

    project: Mapped["Project"] = relationship("Project", back_populates="plans_batiment") # Relation avec la table "projects" (clé étrangère vers "projects.id")

    def __repr__(self):
        return f"<PlanBatiment(id={self.id}, name='{self.name}', description='{self.description}')>"

class NoteDeCalcul(Base):
    __tablename__ = "notes_de_calcul"

    # Note de calcul justifiant les quantités d'un ouvrage

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(nullable=False) # Titre de la note de calcul
    contenu: Mapped[str] = mapped_column(nullable=False) # Détail du calcul effectué par l'agent (raisonnement, formules, hypothèses)
    ouvrage_id: Mapped[int] = mapped_column(ForeignKey("ouvrages.id"), nullable=False) # ID de l'ouvrage auquel appartient la note de calcul
    calculation_date: Mapped[str] = mapped_column(nullable=False) # Date du calcul

    ouvrage: Mapped["Ouvrage"] = relationship("Ouvrage", back_populates="notes_de_calcul") # Relation avec la table "ouvrages"

    def __repr__(self):
        return f"<NoteDeCalcul(id={self.id}, title='{self.title}', ouvrage_id={self.ouvrage_id})>"

class Material(Base):
    __tablename__ = "materials"

    # Catalogue global de matériaux de construction (géré par l'admin)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False) # Nom du matériau (ex: "Brique", "Ciment", etc.)
    description: Mapped[Optional[str]] = mapped_column(nullable=True) # Description du matériau (ex: "Brique creuse 20x20x50")
    unite_defaut: Mapped[str] = mapped_column(nullable=False) # Unité technique de calcul (ex: "U", "kg", "sac", "m³")
    unite_commerciale: Mapped[Optional[str]] = mapped_column(nullable=True) # Unité commerciale fournisseur (ex: "palette", "big-bag")
    conditionnement: Mapped[Optional[str]] = mapped_column(nullable=True) # Description du conditionnement (ex: "1 palette = 500 U", "sac 50 kg")
    facteur_conversion: Mapped[Optional[float]] = mapped_column(nullable=True) # Facteur technique → commercial (ex: 500 pour U→palette)

    def __repr__(self):
        return f"<Material(id={self.id}, name='{self.name}', unite_defaut='{self.unite_defaut}')>"


class Ouvrage(Base):
    __tablename__ = "ouvrages"

    # Définition d'un ouvrage (gros œuvre ou second œuvre)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False) # Nom de l'ouvrage (ex: "Fondations semelles filantes", "Carrelage salle de bain")
    categorie: Mapped[str] = mapped_column(nullable=False) # Catégorie de l'ouvrage (ex: "gros_oeuvre", "second_oeuvre")
    description: Mapped[Optional[str]] = mapped_column(nullable=True) # Description de l'ouvrage
    position: Mapped[int] = mapped_column(nullable=False, default=0) # Ordre d'affichage
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False) # ID du projet auquel appartient l'ouvrage

    project: Mapped["Project"] = relationship("Project", back_populates="ouvrages") # Relation avec la table "projects"
    lignes_de_calcul: Mapped[List["LigneDeCalcul"]] = relationship("LigneDeCalcul", back_populates="ouvrage", cascade="all, delete-orphan") # Relation avec la table "lignes_de_calcul"
    notes_de_calcul: Mapped[List["NoteDeCalcul"]] = relationship("NoteDeCalcul", back_populates="ouvrage", cascade="all, delete-orphan") # Relation avec la table "notes_de_calcul"

    def __repr__(self):
        return f"<Ouvrage(id={self.id}, name='{self.name}', categorie='{self.categorie}')>"


class LigneDeCalcul(Base):
    __tablename__ = "lignes_de_calcul"

    # Définition d'une ligne de calcul pour un ouvrage

    id: Mapped[int] = mapped_column(primary_key=True)
    ouvrage_id: Mapped[int] = mapped_column(ForeignKey("ouvrages.id"), nullable=False) # ID de l'ouvrage auquel appartient la ligne de calcul
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False) # ID du matériau utilisé dans la ligne de calcul
    description: Mapped[str] = mapped_column(nullable=False) # Description de la ligne (ex: "Briques mur façade nord RDC")
    quantity: Mapped[float] = mapped_column(nullable=False) # Quantité technique calculée (ex: 450 briques, 12 sacs)
    unit: Mapped[str] = mapped_column(nullable=False) # Unité technique (ex: "U", "kg", "sac", "m³")
    commercial_quantity: Mapped[Optional[float]] = mapped_column(nullable=True) # Quantité commerciale (convertie via facteur_conversion)
    commercial_unit: Mapped[Optional[str]] = mapped_column(nullable=True) # Unité commerciale (ex: "palette", "big-bag")
    position: Mapped[int] = mapped_column(nullable=False, default=0) # Ordre d'affichage

    ouvrage: Mapped["Ouvrage"] = relationship("Ouvrage", back_populates="lignes_de_calcul") # Relation avec la table "ouvrages"
    material: Mapped["Material"] = relationship("Material") # Relation avec la table "materials"

    def __repr__(self):
        return f"<LigneDeCalcul(id={self.id}, description='{self.description}', quantity={self.quantity}, unit='{self.unit}')>"


class Question(Base):
    __tablename__ = "questions"

    # Question posée par le système à l'utilisateur, liée à un projet et optionnellement à un ouvrage

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False) # ID du projet concerné
    ouvrage_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ouvrages.id"), nullable=True) # ID de l'ouvrage concerné (optionnel)
    question_text: Mapped[str] = mapped_column(nullable=False) # Texte de la question posée par le système
    answer_text: Mapped[Optional[str]] = mapped_column(nullable=True) # Réponse de l'utilisateur
    status: Mapped[str] = mapped_column(nullable=False, default="pending") # "pending" | "answered"
    asked_date: Mapped[str] = mapped_column(nullable=False) # Date à laquelle la question a été posée
    answered_date: Mapped[Optional[str]] = mapped_column(nullable=True) # Date à laquelle la question a été répondue

    project: Mapped["Project"] = relationship("Project", back_populates="questions")
    ouvrage: Mapped[Optional["Ouvrage"]] = relationship("Ouvrage")

    def __repr__(self):
        return f"<Question(id={self.id}, project_id={self.project_id}, status='{self.status}')>"


# ---- Fonctions utilitaires ----- #

def get_engine():
    # Fonction pour créer une connexion à la base de données
    return create_engine(DB_URL)

def get_db():
    # Générateur de session pour l'injection de dépendances FastAPI
    engine = get_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


