"""

smart_btp_agent.py — Système multi-agent LangGraph pour le calcul automatique de métrés BTP.



Architecture

────────────

Deux agents Gemini orchestrés via LangGraph :



  • Chef de Projet  (GEMINI_CHEF_MODEL)     : lit les plans de bâtiment, orchestre les

                                              calculs, interagit avec l'utilisateur.

  • Mettreur        (GEMINI_METTREUR_MODEL) : calcule les quantités de matériaux, crée

                                              les entrées en base de données.



Graphe principal (Chef de Projet) :



    START ──► [chef_node] ──► (outil appelé ?) ──► [chef_tools_node]

                  ▲                                        │

                  └────────────────────────────────────────┘

                  │ (plus aucun outil)

                  ▼

                 END



Outil spécial « delegate_to_mettreur » :

    Lance le sous-graphe Mettreur de manière asynchrone,

    attend sa complétion, retourne le rapport au Chef.



Outil spécial « ask_user_question » :

    Persiste la question en BDD, appelle interrupt() → le graphe

    se met en pause. À la reprise, retourne la réponse au Chef.



Variables d'environnement nécessaires :

    GEMINI_API_KEY          — Clé API Google Gemini (obligatoire)

    GEMINI_CHEF_MODEL       — Nom du modèle chef   (défaut : gemini-2.5-flash-preview-05-20)

    GEMINI_METTREUR_MODEL   — Nom du modèle mettreur (défaut : gemini-2.5-flash-8b-001)

"""



from __future__ import annotations



import ast

import asyncio

import math

import os

import tempfile

from datetime import datetime, timezone

from typing import Annotated, Any, Awaitable, Callable, TypedDict



from dotenv import load_dotenv

from langchain_core.callbacks import BaseCallbackHandler

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from langchain_core.outputs import LLMResult

from langchain_core.tools import tool

from langchain_google_genai import ChatGoogleGenerativeAI

from langgraph.checkpoint.memory import MemorySaver

from langgraph.graph import END, START, StateGraph

from langgraph.graph.message import add_messages

from langgraph.prebuilt import ToolNode, tools_condition

from langgraph.types import Command as LGCommand

from langgraph.types import interrupt

from sqlalchemy.orm import Session



from lib.core.content_extractor import extract_content

from lib.core.exeption_module import CustomException

from lib.core.orm_module import (

    LigneDeCalcul,

    Material,

    NoteDeCalcul,

    Ouvrage,

    Plan,

    PlanBatiment,

    Project,

    Question,

    User,

)

from lib.core import vector_store_module as vector_store



load_dotenv()

def _extract_text_content(content) -> str:
    """Extrait le texte d'un AIMessage.content (str ou list de dicts)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return str(content)







# ──────────────────────────────────────────────────────────────

# CONFIGURATION

# ──────────────────────────────────────────────────────────────



_GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")

_CHEF_MODEL: str = os.getenv("GEMINI_CHEF_MODEL", "gemini-2.5-flash-preview-05-20")

_METTREUR_MODEL: str = os.getenv("GEMINI_METTREUR_MODEL", "gemini-2.5-flash-8b-001")



# Extensions image passées directement à Gemini Vision (inline base64).

# Les PDF sont traités séparément via _pdf_pages_to_vision_parts().

_VISION_MIME: dict[str, str] = {

    ".png":  "image/png",

    ".jpg":  "image/jpeg",

    ".jpeg": "image/jpeg",

    ".bmp":  "image/bmp",

    ".tiff": "image/tiff",

    ".tif":  "image/tiff",

    ".webp": "image/webp",

    ".gif":  "image/gif",

}



# Type alias pour le callback SSE (event_type, data) → Awaitable

EventCallback = Callable[[str, dict], Awaitable[None]]





def _noop_event_callback(_type: str, _data: dict) -> Awaitable[None]:

    """Callback vide utilisé quand aucun callback SSE n'est fourni."""

    async def _noop():

        pass

    return _noop()





def _fire_event(callback: EventCallback, event_type: str, data: dict) -> None:

    """

    Planifie l'émission d'un événement SSE de manière thread-safe.

    - Contexte asyncio direct (outil async ou code async) → create_task.

    - Contexte thread d'exécuteur (outils @tool sync, run_in_executor) →

      run_coroutine_threadsafe sur la boucle principale capturée au démarrage.

    """

    coro = callback(event_type, data)

    try:

        # On est dans la boucle asyncio principale (ex: outil async)

        loop = asyncio.get_running_loop()

        loop.create_task(coro)

    except RuntimeError:

        # On est dans un thread d'exécuteur (outil @tool sync via LangGraph)

        global _main_event_loop

        target = _main_event_loop

        if target and target.is_running():

            asyncio.run_coroutine_threadsafe(coro, target)

        else:

            coro.close()  # Évite le warning "coroutine never awaited"





# ──────────────────────────────────────────────────────────────

# SUIVI DU QUOTA DE TOKENS

# ──────────────────────────────────────────────────────────────



class _TokenTracker(BaseCallbackHandler):

    """

    Callback LangChain qui compte les tokens consommés par chaque appel LLM

    et met à jour ``User.quota_used`` en base de données.

    """



    def __init__(

        self,

        db: Session,

        user_id: int,

        project_id: int,

        event_callback: EventCallback,

    ) -> None:

        super().__init__()

        self.db = db

        self.user_id = user_id

        self.project_id = project_id

        self.event_callback = event_callback



    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:  # noqa: ANN401

        """Appelé par LangChain après chaque réponse LLM."""

        total_tokens = 0

        for generations in response.generations:

            for gen in generations:

                usage = getattr(gen, "generation_info", {}) or {}

                usage_meta = usage.get("usage_metadata") or {}

                total_tokens += (

                    usage_meta.get("total_token_count")

                    or usage_meta.get("total_tokens")

                    or 0

                )

        if total_tokens <= 0:

            # Fallback : llm_output niveau réponse

            lo = response.llm_output or {}

            usage_meta = lo.get("usage_metadata") or lo.get("token_usage") or {}

            total_tokens = (

                usage_meta.get("total_token_count")

                or usage_meta.get("total_tokens")

                or 0

            )



        if total_tokens <= 0:

            return



        # Session dédiée pour éviter les conflits de thread avec la session partagée
        from lib.core.orm_module import get_engine
        from sqlalchemy.orm import sessionmaker as _SM
        _factory = _SM(autocommit=False, autoflush=False, bind=get_engine())
        token_db = _factory()
        try:
            user = token_db.query(User).filter(User.id == self.user_id).first()

            if not user:
                return

            user.quota_used = (user.quota_used or 0) + total_tokens
            new_quota_used = user.quota_used
            plan_quota = user.plan.quota if user.plan else 0
            token_db.commit()
        finally:
            token_db.close()

        _fire_event(
            self.event_callback,
            "quota",
            {"quota_used": new_quota_used, "plan_quota": plan_quota},
        )



# Checkpointer global partagé entre tous les projets.

# NOTE : MemorySaver est en mémoire vive ; il est réinitialisé au redémarrage

# du serveur. Pour une persistance totale, remplacer par PostgresSaver (langgraph-checkpoint-postgres).

_checkpointer = MemorySaver()

# Référence à la boucle asyncio principale, capturée dans run_project_workflow.
# Nécessaire pour que _fire_event fonctionne depuis les threads d'exécuteur LangGraph
# (les @tool sync sont exécutés via run_in_executor → pas de running loop dans le thread).
_main_event_loop: asyncio.AbstractEventLoop | None = None





# ──────────────────────────────────────────────────────────────

# ÉTAT DU GRAPHE

# ──────────────────────────────────────────────────────────────



class BTPAgentState(TypedDict):

    """État partagé du graphe Chef de Projet."""



    project_id: int

    user_id: int

    messages: Annotated[list[BaseMessage], add_messages]





# ──────────────────────────────────────────────────────────────

# CALCULATEUR PYTHON SÉCURISÉ

# ──────────────────────────────────────────────────────────────



_ALLOWED_AST_NODES = (

    ast.Expression,

    ast.BinOp,

    ast.UnaryOp,

    ast.Constant,

    ast.Add,

    ast.Sub,

    ast.Mult,

    ast.Div,

    ast.FloorDiv,

    ast.Mod,

    ast.Pow,

    ast.USub,

    ast.UAdd,

    ast.Name,

    ast.Call,

    ast.Load,

)



_ALLOWED_NAMES: dict[str, Any] = {

    "abs": abs,

    "round": round,

    "min": min,

    "max": max,

    "int": int,

    "float": float,

    **{k: v for k, v in vars(math).items() if not k.startswith("_")},

}





def _safe_eval(expression: str) -> float:

    """

    Évalue une expression mathématique Python de manière sécurisée.



    Seules les opérations arithmétiques et les fonctions du module ``math``

    sont autorisées. Toute tentative d'accès à des builtins arbitraires

    ou à des modules externes est bloquée au niveau AST.



    Args:

        expression: Expression Python valide (ex: ``"3.14 * 5**2 * 2.5"``).



    Returns:

        Résultat numérique sous forme de ``float``.



    Raises:

        ValueError: Si l'expression est syntaxiquement invalide ou contient

                    des constructions non autorisées.

    """

    try:

        tree = ast.parse(expression.strip(), mode="eval")

    except SyntaxError as exc:

        raise ValueError(f"Expression mathématique invalide : {exc}") from exc



    for node in ast.walk(tree):

        if not isinstance(node, _ALLOWED_AST_NODES):

            raise ValueError(

                f"Opération non autorisée : '{type(node).__name__}' "

                f"dans l'expression '{expression}'"

            )

        if isinstance(node, ast.Name) and node.id not in _ALLOWED_NAMES:

            raise ValueError(

                f"Identifiant non autorisé : '{node.id}'. "

                "Seules les fonctions math.* sont permises."

            )



    code = compile(tree, "<calcul_metre>", "eval")

    result = eval(code, {"__builtins__": {}}, _ALLOWED_NAMES)  # noqa: S307

    return float(result)





# ──────────────────────────────────────────────────────────────

# ANALYSE VISION DES PLANS IMAGE (Gemini multimodal)

# ──────────────────────────────────────────────────────────────



def _pdf_pages_to_vision_parts(pdf_bytes: bytes, dpi: int = 200) -> list[dict]:

    """

    Convertit chaque page d'un PDF en image PNG haute résolution (200 DPI par défaut)

    puis retourne une liste de parts « image_url » pour Gemini Vision.



    Avantages vs passage du PDF en base64 :

    - Contrôle précis de la résolution (cotes lisibles à 200 DPI)

    - Aucune limite de format ou de codec PDF

    - Gemini reçoit exactement le rendu visuel final, page par page



    Args:

        pdf_bytes: Contenu brut du fichier PDF.

        dpi:       Résolution de rendu (200 DPI = bon équilibre qualité/taille).



    Returns:

        Liste de dicts image_url prêts pour HumanMessage.content, ou liste vide si erreur.

    """

    import base64

    try:

        import pymupdf  # PyMuPDF ≥ 1.23



        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")

        matrix = pymupdf.Matrix(dpi / 72, dpi / 72)  # facteur d'échelle = DPI / 72 (pt → px)

        parts: list[dict] = []



        for page in doc:

            pix = page.get_pixmap(matrix=matrix, colorspace=pymupdf.csRGB, alpha=False)

            img_b64 = base64.b64encode(pix.tobytes("png")).decode()

            parts.append({

                "type": "image_url",

                "image_url": {"url": f"data:image/png;base64,{img_b64}"},

            })



        doc.close()

        print(f"  [PDF→IMG] {len(parts)} page(s) converties en PNG {dpi} DPI")

        return parts



    except ImportError:

        print("  [PDF→IMG] pymupdf non installé")

        return []

    except Exception as exc:

        print(f"  [PDF→IMG] Erreur conversion : {exc}")

        return []





def _analyze_plan_with_vision(file_bytes: bytes, mime_type: str, plan_name: str) -> str:

    """

    Analyse un plan de bâtiment (image ou PDF) avec Gemini Vision.



    Méthode :

    - PDF   → chaque page est rendue en PNG 200 DPI via PyMuPDF, puis toutes les

              pages sont envoyées en une seule requête Gemini (contexte complet).

              Équivalent à attacher toutes les pages comme images dans l'app Gemini.

    - Image → passée directement en base64 inline à Gemini Vision.



    Gemini voit le rendu VISUEL réel du plan (cotes, hachures, symboles, légendes)

    et non un texte OCR reconstruit.



    Args:

        file_bytes: Contenu brut du fichier (PDF, PNG, JPG, etc.).

        mime_type:  Type MIME (ex: 'application/pdf', 'image/png').

        plan_name:  Nom du plan (pour l'en-tête du rapport).



    Returns:

        Rapport structuré extrait par Gemini Vision.

    """

    import base64



    if not _GEMINI_API_KEY:

        return "Erreur : GEMINI_API_KEY non configurée."



    llm_vision = ChatGoogleGenerativeAI(

        model=_CHEF_MODEL,

        google_api_key=_GEMINI_API_KEY,

        temperature=0,

    )



    # ── Construction des parts visuelles ──

    _is_pdf = mime_type == "application/pdf"

    if _is_pdf:

        image_parts = _pdf_pages_to_vision_parts(file_bytes)

        if not image_parts:

            # Fallback : PDF inline si la conversion échoue

            b64 = base64.b64encode(file_bytes).decode()

            image_parts = [{"type": "image_url", "image_url": {"url": f"data:application/pdf;base64,{b64}"}}]

    else:

        b64 = base64.b64encode(file_bytes).decode()

        image_parts = [{"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}}]



    nb_pages = len(image_parts)

    _VISION_PROMPT = (

        "Tu es un expert en lecture de plans architecturaux BTP. "

        + (f"Ce document contient {nb_pages} page(s) — analyse-les TOUTES. " if _is_pdf else "Analyse ce plan. ")

        + "Fournis une description EXHAUSTIVE incluant :\n"

        "1. TYPE DE PLAN : façade, coupe, plan de masse, plan de niveau, plan de toiture, etc.\n"

        "   (précise la page concernée pour un document multi-pages)\n"

        "2. DIMENSIONS : TOUTES les cotes visibles avec leur emplacement exact\n"

        "   (longueurs de murs, hauteurs sous plafond, épaisseurs, distances entre axes,\n"

        "    dimensions L × l de chaque pièce, dimensions L × H des ouvertures)\n"

        "3. PIÈCES / ZONES : nom, superficie estimée, dimensions de chaque pièce\n"

        "4. OUVERTURES : chaque porte et fenêtre — dimensions (L × H), type, sens d'ouverture\n"

        "5. ANNOTATIONS TECHNIQUES : matériaux, revêtements, DTU, isolants, épaisseurs\n"

        "6. TABLEAUX / NOMENCLATURES : tableaux de menuiserie, légendes, nomenclatures\n"

        "7. ALTIMÉTRIE : cotes NGF, niveaux de sol fini, hauteurs de bâtiment, pentes toiture\n"

        "Sois EXHAUSTIF sur tous les chiffres. Format : [localisation précise] = valeur unité."

    )



    msg = HumanMessage(content=[

        {"type": "text", "text": _VISION_PROMPT},

        *image_parts,

    ])



    try:

        response = llm_vision.invoke([msg])

        suffix = f"{nb_pages} page(s)" if _is_pdf else mime_type

        return f"=== Analyse Gemini du plan \'{plan_name}\' ({suffix}) ===\n{_extract_text_content(response.content)}"

    except Exception as exc:  # noqa: BLE001

        return f"Erreur analyse Gemini du plan \'{plan_name}\' : {exc}"





# ──────────────────────────────────────────────────────────────

# PROMPTS SYSTÈME

# ──────────────────────────────────────────────────────────────



_CHEF_SYSTEM_PROMPT = """Tu es le Chef de Projet d'une plateforme intelligente de calcul de métrés BTP.



MISSION

Analyser les plans de bâtiment d'un projet de construction et orchestrer le calcul

complet des quantités de matériaux nécessaires pour chaque ouvrage identifié.

L'objectif final est de produire des quantités commerciales exploitables pour passer

une commande fournisseur.



MÉTHODE DE TRAVAIL

1. Commence par lister et lire TOUS les plans de bâtiment disponibles.

2. Identifie l'ensemble des ouvrages à calculer (terrassement, fondations, maçonnerie,

   chape/dalle, carrelage, toiture, enduit/crépi, plâtrerie, menuiserie…).

3. Consulte les bases de connaissance (publique et privée) si tu as besoin de normes,

   de DTU, de CCTP ou de ratios techniques.

4. Pour chaque ouvrage identifié, dans l'ordre :

   a. Crée l'ouvrage en base (create_ouvrage).

   b. Fournis au Mettreur toutes les dimensions mesurées sur les plans :

      surfaces, longueurs, largeurs, hauteurs, volumes, nombre de baies, etc.

   c. Liste EXPLICITEMENT dans la tâche les matériaux du CATALOGUE GLOBAL

      (issus de list_project_materials) qui s'appliquent à cet ouvrage, avec leurs IDs.

      IMPORTANT : tu ne peux utiliser QUE les matériaux présents dans le catalogue —

      n'invente pas de matériaux inexistants.

   d. Délègue le calcul au Mettreur (delegate_to_mettreur).

   e. Lis le rapport du Mettreur. Si des matériaux attendus sont absents,

      relance le Mettreur avec une instruction correctrice.

5. Si des informations CRUCIALES sont illisibles ou absentes des plans (dimensions

   clés, choix de matériau non précisé), pose une question à l'utilisateur

   (ask_user_question) — 3 questions maximum sur tout le projet.

6. Une fois TOUS les ouvrages calculés, appelle mark_project_complete avec un résumé

   incluant les quantités commerciales totales par matériau (palettes, big-bags, sacs…).



FORMAT DE DÉLÉGATION AU METTREUR (obligatoire)

Chaque tâche delegate_to_mettreur DOIT contenir :

  DIMENSIONS :

    - Surface nette : X m²   (après déduction des baies si applicable)

    - Périmètre     : X ml

    - Hauteur       : X m

    - Volume        : X m³   (si applicable)

    - Autre         : ...



  MATÉRIAUX À CALCULER (avec leur ID du catalogue global) :

    - [ID=n] Nom du matériau → formule ou méthode à appliquer

    - [ID=n] Nom du matériau → formule ou méthode à appliquer

    ... (TOUS les matériaux applicables du catalogue, aucun ne doit être omis)



  CONTEXTE : localisation de l'ouvrage, remarques sur les plans, hypothèses.



RÈGLES STRICTES

- Tu ne calcules JAMAIS les quantités toi-même : tu délègues TOUJOURS au Mettreur.

- Fournis des dimensions précises — jamais de valeurs approximatives sans explication.

- Travaille de manière séquentielle : crée l'ouvrage → délègue → lis le rapport → suivant.

- Un ouvrage est valide uniquement si le Mettreur a produit une ligne par matériau listé.

- Utilise UNIQUEMENT les matériaux du catalogue global (list_project_materials).

  Ne demande pas au Mettreur de créer des matériaux — seul l'admin peut le faire.



CATÉGORIES D'OUVRAGES RECONNUES

"terrassement", "fondations", "maçonnerie", "chape_dalle", "carrelage",

"toiture", "enduit_crepi", "platerie_placo", "menuiserie", "autre"

"""



_METTREUR_SYSTEM_PROMPT = """Tu es le Mettreur d'une plateforme intelligente de calcul de métrés BTP.



MISSION

Calculer TOUTES les quantités de matériaux pour l'ouvrage confié par le Chef de Projet,

en produisant une ligne de calcul (add_ligne_de_calcul) pour CHAQUE matériau listé dans

la tâche. Zéro omission est acceptable.

La quantité commerciale (unité fournisseur) est calculée automatiquement à partir du

facteur_conversion de chaque matériau lors de l'appel à add_ligne_de_calcul.



MÉTHODE DE TRAVAIL

1. Lis la tâche : relève chaque dimension (surface, longueur, hauteur, volume).

2. Consulte le catalogue global (list_project_materials) pour identifier les matériaux

   disponibles et leurs IDs. Tu ne peux PAS créer de nouveaux matériaux — utilise

   uniquement ceux du catalogue. Si un matériau listé dans la tâche est absent du

   catalogue, indique-le dans le rapport au lieu de le créer.

3. Pour CHAQUE matériau listé dans la tâche ET présent dans le catalogue :

   a. Calcule la quantité technique via run_calculation avec la formule exacte.

   b. Applique le coefficient de perte correspondant.

   c. Arrondis au nombre entier supérieur pour les unités discrètes (U, sac).

   d. Enregistre la ligne (add_ligne_de_calcul) — la quantité commerciale sera

      calculée automatiquement si le matériau a un facteur_conversion défini.

4. Rédige une note de calcul détaillée (create_note_de_calcul).

5. Rédige le rapport de synthèse pour le Chef, incluant pour chaque matériau :

   - Quantité technique (avec unité)

   - Quantité commerciale (avec unité commerciale) si disponible

   - Conditionnement applicable (ex : "12 palettes de 500 U")



═══════════════════════════════════════════════════════════════════

FORMULES ET MÉTHODES PAR CATÉGORIE

═══════════════════════════════════════════════════════════════════



── TERRASSEMENT ──────────────────────────────────────────────────

  Remblai (m³)          = longueur × largeur × profondeur × 0.75

  Géotextile (m²)       = (longueur × largeur) × 1.10  [recouvrement 10%]

  Grillage avertisseur (ml) = périmètre total des tranchées

  Sable de remblai (m³) = volume fond de fouille × 0.10



── FONDATIONS ────────────────────────────────────────────────────

  Béton de fondation (m³) = section × longueur totale

                             ex : semelle 0.50×0.30 : 0.50×0.30×L

  Acier HA (kg)           = volume béton × 100  [100 kg/m³ moyen]

  Treillis soudé (m²)     = surface dalle fond × 1.10

  Coffrage (m²)           = 2 × hauteur semelle × longueur totale

  Parpaing plein (U)      = surface soubassement × 10 × 1.05



── MAÇONNERIE ────────────────────────────────────────────────────

  Surface brute murs (m²) = périmètre × hauteur sous-plafond

  Surface nette (m²)      = surface brute − Σ(largeur×hauteur de chaque baie)

  Parpaing creux (U)      = surface nette × 10 × 1.05  [10 par m², perte 5%]

  Brique creuse (U)       = surface nette × 16 × 1.05  [16 par m², perte 5%]

  Mortier de montage (sac 35kg) = CEIL(parpaings / 10)

                                   [1 sac pour 10 parpaings]

  Ciment CEM II (sac 50kg)= CEIL(surface nette / 5)

  Sable (m³)              = surface nette × 0.03

  Linteau préfabriqué (U) = nombre total de baies (fenêtres + portes)



── CHAPE / DALLE ─────────────────────────────────────────────────

  Béton prêt à l'emploi (m³) = surface × épaisseur_dalle  [min 0.12 m]

  Treillis soudé ST25 (m²)   = surface × 1.10

  Film polyane (m²)           = surface × 1.10

  Isolant sous-chape (m²)     = surface × 1.05

  Ciment de chape (sac 35kg)  = CEIL(surface × 85 / 35)

                                  [85 kg/m² pour 5 cm d'épaisseur]

  Sable de chape (m³)         = surface × 0.05  [chape 5 cm]



── CARRELAGE ─────────────────────────────────────────────────────

  Carrelage sol (m²)      = surface_sol × 1.10  [perte 10%]

  Carrelage mur (m²)      = surface_murs_carrelés × 1.15  [perte 15%]

  Colle à carrelage (sac 25kg) = CEIL(surface_totale_collée / 4)

                                   [1 sac pour 4 m²]

  Joint de carrelage (sac 5kg) = CEIL(surface_totale_collée / 20)

                                   [1 sac pour 20 m²]

  Plinthes (ml)           = périmètre_pièce × 1.05



── TOITURE ───────────────────────────────────────────────────────

  Coefficient de pente    : pente 30° → ×1.15 ; 35° → ×1.22 ; 45° → ×1.41

  Surface réelle toiture  = surface projetée × coeff_pente

  Tuile terre cuite (U)   = CEIL(surface_réelle × 15 × 1.10)

                              [15 tuiles/m², perte 10%]

  Ardoise (U)             = CEIL(surface_réelle × 22 × 1.10)

  Chevron 60×80 (ml)      = nb_travées × longueur_rampant × 1.05

                              [nb_travées = largeur / 0.60]

  Latte 40×25 (ml)        = (surface_réelle / pureau_m) × longueur_rive × 1.05

                              [pureau moyen : tuile canal = 0.22 m]

  Sous-toiture HPV (m²)   = surface_réelle × 1.05

  Faitage (ml)            = longueur_faîtage × 1.10

  Gouttière PVC (ml)      = longueur_rive_basse × 1.05



── ENDUIT / CRÉPI ────────────────────────────────────────────────

  Surface façade nette    = surface brute façades − baies

  Enduit de façade (sac 25kg)  = CEIL(surface × 15 / 25)

                                   [15 kg/m² à 15 mm d'épaisseur]

  Crépi minéral (sac 25kg)     = CEIL(surface / 7)

                                   [1 sac pour 7 m²]

  Sous-enduit (sac 25kg)       = CEIL(surface × 5 / 25)

                                   [5 kg/m² couche accrochage]

  Grillage de façade (m²)      = surface × 1.05



── PLÂTRERIE / PLACO ─────────────────────────────────────────────

  Surface cloisons        = périmètre_intérieur × hauteur × 2 faces

  Plaque BA13 (m²)        = surface_cloisons × 1.10  [chutes 10%]

  Rail R48 (ml)           = (surface_cloisons / hauteur) × 2 × 1.05

                              [1 rail sol + 1 rail plafond par travée]

  Montant M48 (ml)        = CEIL(surface_cloisons / 0.60) × hauteur × 1.05

                              [montant tous les 60 cm]

  Vis TF 25 (boîte 500)   = CEIL(surface_cloisons / 20)

                              [1 boîte pour 20 m²]

  Bande à joint (ml)      = surface_cloisons × 3

                              [3 ml de joint par m² de plaque]

  Enduit de finition (sac 20kg) = CEIL(surface_cloisons / 10)

                              [1 sac pour 10 m²]



═══════════════════════════════════════════════════════════════════

COEFFICIENTS DE PERTE (à appliquer sur TOUTES les quantités)

═══════════════════════════════════════════════════════════════════

  Carrelage sol      : +10%    Carrelage mural   : +15%

  Maçonnerie (U)     : +5%     Ferraillage béton : +10%

  Enduit/crépi       : +5%     Tuiles/ardoises   : +10%

  Bois charpente     : +5%     Placo (m²)        : +10%



RÈGLES ABSOLUES

- Utilise TOUJOURS run_calculation pour les calculs — jamais de valeur inventée.

- Produis une ligne add_ligne_de_calcul pour CHAQUE matériau du catalogue applicable.

- Ne crée JAMAIS de matériau : le catalogue est géré exclusivement par l'administrateur.

- Les quantités doivent être cohérentes avec les dimensions : si surface = 20 m²

  et carrelage = 22 m², c'est correct (coeff 1.10) ; si carrelage = 5 m², c'est faux.

- Si un matériau listé dans la tâche est absent du catalogue, signale-le dans le rapport.

- Arrondis toujours au sac/unité supérieur pour les conditionnements discrets.

- Documente CHAQUE formule dans la note de calcul (create_note_de_calcul).

"""





# ──────────────────────────────────────────────────────────────

# UTILITAIRES BASE DE DONNÉES

# ──────────────────────────────────────────────────────────────



def _update_project_status(

    db: Session,

    project_id: int,

    status: str,

    step: str,

) -> None:

    project = db.query(Project).filter(Project.id == project_id).first()

    if project:

        project.status = status

        project.current_step = step[:255]

        project.last_updated = datetime.now(timezone.utc).isoformat()

        db.commit()





def _update_project_step(db: Session, project_id: int, step: str) -> None:

    project = db.query(Project).filter(Project.id == project_id).first()

    if project:

        project.current_step = step[:255]

        project.last_updated = datetime.now(timezone.utc).isoformat()

        db.commit()





# ──────────────────────────────────────────────────────────────

# OUTILS DU CHEF DE PROJET

# ──────────────────────────────────────────────────────────────



def _make_chef_tools(

    db: Session,

    project_id: int,

    user_id: int,

    event_callback: EventCallback,

) -> list:

    """

    Fabrique les outils LangChain du Chef de Projet.

    Toutes les fonctions sont des fermetures capturant le contexte (db, project_id, user_id).

    """

    # Chaque appel d'outil crée sa propre session SQLAlchemy isolée pour éviter
    # les conflits de thread quand LangGraph exécute plusieurs outils en parallèle
    # via asyncio.gather (ToolNode._afunc, tool_node.py:857).
    from sqlalchemy.orm import sessionmaker as _SM
    from lib.core.orm_module import get_engine as _get_engine
    _SessionFactory = _SM(autocommit=False, autoflush=False, bind=_get_engine())

    def _new_db():
        return _SessionFactory()



    @tool

    def list_building_plans() -> list[dict]:

        """Liste tous les plans de bâtiment attachés au projet courant."""

        _db = _new_db()

        try:

            plans = (

                _db.query(PlanBatiment)

                .filter(PlanBatiment.project_id == project_id)

                .all()

            )

            return [

                {

                    "id": p.id,

                    "name": p.name,

                    "description": p.description,

                    "extension": p.extension,

                    "upload_date": p.upload_date,

                    "has_content": bool(p.content),

                    "needs_vision": (p.extension.lower().lstrip(".")) in {

                        "png", "jpg", "jpeg", "bmp", "tiff", "tif", "webp", "gif", "pdf"

                    },

                }

                for p in plans

            ]

        finally:

            _db.close()



    @tool

    def read_building_plan(plan_id: int) -> str:

        """

        Lit et retourne le contenu textuel extrait d'un plan de bâtiment.

        Supporte PDF (avec OCR), DOCX, XLSX, images et autres formats indexés.



        Args:

            plan_id: Identifiant du plan de bâtiment.



        Returns:

            Texte extrait du plan, ou message d'erreur si illisible.

        """

        _db = _new_db()

        try:

            plan = (

                _db.query(PlanBatiment)

                .filter(PlanBatiment.id == plan_id, PlanBatiment.project_id == project_id)

                .first()

            )

            if not plan:

                return f"Erreur : plan {plan_id} introuvable pour ce projet."

            # Lire les colonnes avant de fermer la session

            plan_content = plan.content

            plan_name = plan.name

            plan_extension = plan.extension

        finally:

            _db.close()

        if not plan_content:

            return f"Le plan '{plan_name}' n'a pas de contenu binaire enregistré."



        # ── Gemini Vision : PDF (pages → PNG 200 DPI) ou image (inline) ──

        # Le plan est analysé visuellement par Gemini — cotes, hachures, symboles,

        # légendes — sans passer par un OCR intermédiaire.

        _ext = plan_extension.lower()

        if not _ext.startswith("."):

            _ext = f".{_ext}"

        _mime = _VISION_MIME.get(_ext)

        if _mime:

            _fire_event(event_callback, "step", {"message": "Analyse visuelle du plan : " + plan_name + "..."})

            return _analyze_plan_with_vision(plan_content, _mime, plan_name)

        if _ext == ".pdf":

            _fire_event(event_callback, "step", {"message": "Analyse PDF du plan : " + plan_name + "..."})

            return _analyze_plan_with_vision(plan_content, "application/pdf", plan_name)



        tmp_path: str | None = None

        try:

            with tempfile.NamedTemporaryFile(

                delete=False, suffix=plan_extension

            ) as tmp:

                tmp.write(plan_content)

                tmp_path = tmp.name

            text = extract_content(tmp_path, extension=plan_extension)

        except Exception as exc:  # noqa: BLE001

            return f"Erreur lors de la lecture du plan '{plan_name}' : {exc}"

        finally:

            if tmp_path and os.path.exists(tmp_path):

                os.unlink(tmp_path)



        if not text:

            return (

                f"Le plan '{plan_name}' n'a pas pu être extrait "

                "(format non supporté ou plan illisible)."

            )

        return f"=== Contenu du plan '{plan_name}' ===\n{text}"



    @tool

    def search_plan_for_term(plan_id: int, term: str) -> list[dict]:

        """

        Recherche un terme dans un plan de bâtiment (équivalent Ctrl+F).

        Retourne les occurrences avec leur contexte (±100 caractères).



        Args:

            plan_id: Identifiant du plan.

            term:    Terme à rechercher (insensible à la casse).



        Returns:

            Liste de dict ``{position: int, context: str}``, max 20 résultats.

        """

        _db = _new_db()

        try:

            plan = (

                _db.query(PlanBatiment)

                .filter(PlanBatiment.id == plan_id, PlanBatiment.project_id == project_id)

                .first()

            )

            if not plan or not plan.content:

                return []

            _plan_content = plan.content

            _plan_extension = plan.extension

        finally:

            _db.close()

        tmp_path: str | None = None

        try:

            with tempfile.NamedTemporaryFile(

                delete=False, suffix=_plan_extension

            ) as tmp:

                tmp.write(_plan_content)

                tmp_path = tmp.name

            text = extract_content(tmp_path, extension=plan.extension) or ""

        except Exception:  # noqa: BLE001

            return []

        finally:

            if tmp_path and os.path.exists(tmp_path):

                os.unlink(tmp_path)



        text_lower = text.lower()

        term_lower = term.lower()

        results: list[dict] = []

        pos = 0



        while True:

            idx = text_lower.find(term_lower, pos)

            if idx == -1:

                break

            start = max(0, idx - 100)

            end = min(len(text), idx + len(term) + 100)

            results.append({"position": idx, "context": text[start:end]})

            pos = idx + 1

            if len(results) >= 20:

                break



        return results



    @tool

    def read_plan_range(plan_id: int, start_char: int, end_char: int) -> str:

        """

        Lit une plage précise du texte d'un plan par offset de caractères.

        À utiliser après search_plan_for_term pour lire un passage en contexte élargi.



        Args:

            plan_id:    Identifiant du plan.

            start_char: Indice de début (0-based, inclus).

            end_char:   Indice de fin (exclusif).



        Returns:

            Portion de texte demandée.

        """

        _db = _new_db()

        try:

            plan = (

                _db.query(PlanBatiment)

                .filter(PlanBatiment.id == plan_id, PlanBatiment.project_id == project_id)

                .first()

            )

            if not plan or not plan.content:

                return "Plan introuvable ou sans contenu."

            _plan_content = plan.content

            _plan_extension = plan.extension

        finally:

            _db.close()

        tmp_path: str | None = None

        try:

            with tempfile.NamedTemporaryFile(

                delete=False, suffix=_plan_extension

            ) as tmp:

                tmp.write(_plan_content)

                tmp_path = tmp.name

            text = extract_content(tmp_path, extension=plan.extension) or ""

        except Exception as exc:  # noqa: BLE001

            return f"Erreur de lecture : {exc}"

        finally:

            if tmp_path and os.path.exists(tmp_path):

                os.unlink(tmp_path)



        return text[start_char:end_char]



    @tool

    def search_public_knowledge_base(query: str, top_k: int = 5) -> str:

        """

        Recherche sémantique dans la base de connaissance publique

        (normes, DTU, CCTP, catalogues techniques…).



        Args:

            query:  Question ou terme de recherche en langage naturel.

            top_k:  Nombre de résultats souhaités (max 10).



        Returns:

            Passages pertinents formatés en texte brut.

        """

        top_k = min(int(top_k), 10)

        try:

            hits = vector_store.search(query, top_k=top_k)

        except Exception as exc:  # noqa: BLE001

            return f"Erreur recherche KB publique : {exc}"



        if not hits:

            return "Aucun résultat dans la base de connaissance publique."



        lines = [f"=== Résultats KB publique — '{query}' ==="]

        for i, hit in enumerate(hits, 1):

            lines.append(

                f"\n[{i}] Score : {hit.get('score', 0):.2f}  |  {hit.get('filename', '?')}\n"

                f"{hit.get('chunk', '')}"

            )

        return "\n".join(lines)



    @tool

    def search_private_knowledge_base(query: str, top_k: int = 5) -> str:

        """

        Recherche sémantique dans la base de connaissance privée de l'utilisateur

        (devis, CCTP, plans techniques personnels uploadés).



        Args:

            query:  Question ou terme de recherche en langage naturel.

            top_k:  Nombre de résultats souhaités (max 10).



        Returns:

            Passages pertinents formatés en texte brut.

        """

        top_k = min(int(top_k), 10)

        try:

            hits = vector_store.search_private(query, user_id=user_id, top_k=top_k)

        except Exception as exc:  # noqa: BLE001

            return f"Erreur recherche KB privée : {exc}"



        if not hits:

            return "Aucun résultat dans la base de connaissance privée."



        lines = [f"=== Résultats KB privée — '{query}' ==="]

        for i, hit in enumerate(hits, 1):

            lines.append(

                f"\n[{i}] Score : {hit.get('score', 0):.2f}  |  {hit.get('filename', '?')}\n"

                f"{hit.get('chunk', '')}"

            )

        return "\n".join(lines)



    @tool

    def create_ouvrage(

        name: str,

        categorie: str,

        description: str | None = None,

    ) -> dict:

        """

        Crée un nouvel ouvrage dans le projet courant.



        Args:

            name:        Nom de l'ouvrage (ex: "Fondations semelles filantes RDC").

            categorie:   Catégorie parmi : terrassement, fondations, maçonnerie,

                         chape_dalle, carrelage, toiture, enduit_crepi,

                         platerie_placo, menuiserie, autre.

            description: Description complémentaire (optionnel).



        Returns:

            Dictionnaire ``{id, name, categorie, description}``.

        """

        _db = _new_db()

        try:

            position = _db.query(Ouvrage).filter(Ouvrage.project_id == project_id).count()

            ouvrage = Ouvrage(

                name=name,

                categorie=categorie,

                description=description,

                position=position,

                project_id=project_id,

            )

            _db.add(ouvrage)

            _db.commit()

            _db.refresh(ouvrage)

            _update_project_step(_db, project_id, f"Ouvrage créé : {name}")

            result = {

                "id": ouvrage.id,

                "name": ouvrage.name,

                "categorie": ouvrage.categorie,

                "description": ouvrage.description,

            }

            _fire_event(event_callback, "ouvrage", result)

            return result

        except Exception:

            _db.rollback()

            raise

        finally:

            _db.close()



    @tool

    def list_ouvrages() -> list[dict]:

        """Liste tous les ouvrages créés pour le projet courant avec leur état."""

        _db = _new_db()

        try:

            ouvrages = (

                _db.query(Ouvrage)

                .filter(Ouvrage.project_id == project_id)

                .order_by(Ouvrage.position)

                .all()

            )

            return [

                {

                    "id": o.id,

                    "name": o.name,

                    "categorie": o.categorie,

                    "description": o.description,

                    "lignes_count": len(o.lignes_de_calcul),

                }

                for o in ouvrages

            ]

        finally:

            _db.close()



    @tool

    def ask_user_question(

        question_text: str,

        ouvrage_id: int | None = None,

    ) -> str:

        """

        Pose une question à l'utilisateur et suspend le workflow jusqu'à sa réponse.

        À utiliser UNIQUEMENT pour des informations CRUCIALES manquantes dans les plans

        (dimensions illisibles, choix de matériau non précisé, etc.).



        Args:

            question_text: Question claire et précise en français.

            ouvrage_id:    ID de l'ouvrage concerné (optionnel, pour le contexte).



        Returns:

            Réponse de l'utilisateur.

        """

        # Idempotence : ne pas créer deux fois la même question en cas de reprise

        # Session 1 : avant interrupt() — écriture de la question en BDD

        _db1 = _new_db()

        try:

            existing = (

                _db1.query(Question)

                .filter(

                    Question.project_id == project_id,

                    Question.question_text == question_text,

                )

                .first()

            )

            if existing is None:

                q = Question(

                    project_id=project_id,

                    ouvrage_id=ouvrage_id,

                    question_text=question_text,

                    status="pending",

                    asked_date=datetime.now(timezone.utc).isoformat(),

                )

                _db1.add(q)

                _db1.commit()

                _db1.refresh(q)

                question_id = q.id

            else:

                question_id = existing.id

            _update_project_status(_db1, project_id, "waiting_user", question_text[:120])

        except Exception:

            _db1.rollback()

            raise

        finally:

            _db1.close()

        # ── Émission SSE avant la pause ──

        _fire_event(

            event_callback,

            "question",

            {

                "id": question_id,

                "text": question_text,

                "ouvrage_id": ouvrage_id,

            },

        )



        # ── Pause du graphe : retourne le contrôle à l'API ──

        # LangGraph sauvegarde l'état complet ; l'exécution reprend ici

        # quand l'API appelle resume_project_workflow(answer=…).

        answer = interrupt({"question_id": question_id, "question_text": question_text})



        # ── Reprise : Session 2 — mise à jour de la réponse ──

        _db2 = _new_db()

        try:

            q_resume = _db2.query(Question).filter(Question.id == question_id).first()

            if q_resume and q_resume.status != "answered":

                q_resume.answer_text = str(answer)

                q_resume.status = "answered"

                q_resume.answered_date = datetime.now(timezone.utc).isoformat()

                _db2.commit()

            _update_project_status(_db2, project_id, "calcul_running", "Reprise après réponse utilisateur")

        except Exception:

            _db2.rollback()

            raise

        finally:

            _db2.close()

        return f"Réponse de l'utilisateur : {answer}"



    @tool

    async def delegate_to_mettreur(ouvrage_id: int, task_description: str) -> str:

        """

        Délègue le calcul des quantités d'un ouvrage au Mettreur (agent spécialisé).

        Le Mettreur créera les matériaux, lignes de calcul et note de calcul en BDD.



        Args:

            ouvrage_id:       ID de l'ouvrage cible (doit exister en BDD).

            task_description: Description complète de la tâche : dimensions mesurées

                              sur les plans, matériaux envisagés, méthode de calcul,

                              tout contexte utile pour le Mettreur.



        Returns:

            Rapport de synthèse du Mettreur (quantités calculées, matériaux créés).

        """

        _db = _new_db()

        try:

            ouvrage = (

                _db.query(Ouvrage)

                .filter(Ouvrage.id == ouvrage_id, Ouvrage.project_id == project_id)

                .first()

            )

            if not ouvrage:

                return f"Erreur : ouvrage {ouvrage_id} introuvable dans ce projet."

            _ouvrage_name = ouvrage.name

            _ouvrage_cat = ouvrage.categorie

            _ouvrage_desc = ouvrage.description

            _update_project_step(_db, project_id, f"Calcul métré : {_ouvrage_name}")

            _nb_mat = _db.query(Material).count()

        except Exception:

            _db.rollback()

            raise

        finally:

            _db.close()

        _fire_event(

            event_callback,

            "step",

            {"message": f"Calcul métré : {_ouvrage_name}", "ouvrage_id": ouvrage_id},

        )



        # Construction et exécution du sous-graphe Mettreur

        mettreur_graph = _build_mettreur_graph(db, project_id, user_id, ouvrage_id, event_callback)

        # Limite intelligente : chaque matériau nécessite ~8 steps dans le Mettreur

        _mettreur_limit = max(60, _nb_mat * 8 + 20)

        config = {

            "configurable": {"thread_id": f"{project_id}-mettreur-{ouvrage_id}"},

            "recursion_limit": _mettreur_limit,

        }

        initial = HumanMessage(

            content=(

                f"Tâche de métré\n"

                f"Ouvrage ID={ouvrage_id} : {_ouvrage_name} ({_ouvrage_cat})"

                + (f"\nDescription : {_ouvrage_desc}" if _ouvrage_desc else "")

                + f"\n\n{task_description}"

            )

        )



        result = await mettreur_graph.ainvoke(

            {

                "messages": [initial],

                "ouvrage_id": ouvrage_id,

                "project_id": project_id,

            },

            config=config,

        )



        last = result["messages"][-1]

        report = _extract_text_content(last.content) if isinstance(last, AIMessage) else str(last)

        return f"[Rapport Mettreur — {_ouvrage_name}]\n{report}"



    @tool

    def mark_project_complete(summary: str) -> str:

        """

        Marque le projet comme terminé et enregistre un résumé final.

        À appeler UNIQUEMENT lorsque TOUS les ouvrages ont été calculés.



        Args:

            summary: Résumé de synthèse (ouvrages traités, totaux estimés, remarques).



        Returns:

            Message de confirmation.

        """

        _db = _new_db()

        try:

            _update_project_status(_db, project_id, "done", "Calculs terminés")

        except Exception:

            _db.rollback()

            raise

        finally:

            _db.close()

        _fire_event(event_callback, "done", {"message": summary[:300]})

        print(f"  [BTPAgent] Projet {project_id} terminé. Résumé : {summary[:200]}")

        return f"Projet {project_id} marqué comme terminé. {summary}"



    @tool

    def list_project_materials() -> list[dict]:

        """Liste tous les materiaux du catalogue global disponibles pour le calcul."""

        _db = _new_db()

        try:

            materials = _db.query(Material).order_by(Material.name).all()

            return [

                {

                    "id": m.id,

                    "name": m.name,

                    "description": m.description,

                    "unite_defaut": m.unite_defaut,

                    "unite_commerciale": m.unite_commerciale,

                    "conditionnement": m.conditionnement,

                    "facteur_conversion": m.facteur_conversion,

                }

                for m in materials

            ]

        finally:

            _db.close()



    return [

        list_building_plans,

        read_building_plan,

        search_plan_for_term,

        read_plan_range,

        search_public_knowledge_base,

        search_private_knowledge_base,

        create_ouvrage,

        list_ouvrages,

        list_project_materials,

        ask_user_question,

        delegate_to_mettreur,

        mark_project_complete,

    ]





# ──────────────────────────────────────────────────────────────

# OUTILS DU METTREUR

# ──────────────────────────────────────────────────────────────



def _make_mettreur_tools(

    db: Session,

    project_id: int,

    user_id: int,  # noqa: ARG001

    ouvrage_id: int,

    event_callback: EventCallback,

) -> list:

    """

    Fabrique les outils LangChain du Mettreur.

    Toutes les fonctions sont des fermetures capturant le contexte BDD.

    """

    # Session isolée par appel d'outil
    from sqlalchemy.orm import sessionmaker as _SM
    from lib.core.orm_module import get_engine as _get_engine
    _SessionFactory = _SM(autocommit=False, autoflush=False, bind=_get_engine())

    def _new_db():
        return _SessionFactory()



    @tool

    def run_calculation(expression: str) -> str:

        """

        Évalue une expression mathématique Python en environnement sécurisé.

        Utilise cette fonction pour TOUS les calculs numériques de métrés.



        Opérateurs disponibles : +, -, *, /, //, %, **

        Fonctions disponibles  : toutes les fonctions du module ``math``,

                                 plus abs, round, min, max, int, float.



        Exemples :

            "3.14159 * 5.5**2"                   → surface d'un cercle

            "14.5 * 2.80 * 1.10"                 → surface avec coeff de perte 10 %

            "round(math.ceil(45.3 / 0.33**2), 0)"→ nombre de briques



        Args:

            expression: Expression Python valide (sans variables, sans import).



        Returns:

            Résultat numérique sous forme de chaîne.

        """

        try:

            result = _safe_eval(expression)

            return f"{result:.6g}"

        except ValueError as exc:

            return f"Erreur de calcul : {exc}"



    @tool

    def list_project_materials() -> list[dict]:

        """Liste tous les matériaux du catalogue global disponibles pour le calcul."""

        _db = _new_db()

        try:

            materials = _db.query(Material).order_by(Material.name).all()

            return [

                {

                    "id": m.id,

                    "name": m.name,

                    "description": m.description,

                    "unite_defaut": m.unite_defaut,

                    "unite_commerciale": m.unite_commerciale,

                    "conditionnement": m.conditionnement,

                    "facteur_conversion": m.facteur_conversion,

                }

                for m in materials

            ]

        finally:

            _db.close()



    @tool

    def add_ligne_de_calcul(

        material_id: int,

        description: str,

        quantity: float,

        unit: str,

    ) -> dict:

        """

        Ajoute une ligne de calcul à l'ouvrage courant.

        Représente la quantité d'un matériau pour cet ouvrage.



        Args:

            material_id:  ID du matériau (obtenu via list_project_materials).

            description:  Libellé de la ligne (ex: "Parpaings mur façade nord RDC").

            quantity:     Quantité technique calculée (valeur numérique positive).

            unit:         Unité technique (U, m², m³, ml, kg, sac, t).



        Returns:

            Dictionnaire ``{id, description, quantity, unit, commercial_quantity, commercial_unit}``.

        """

        import math as _imath

        _db = _new_db()

        try:

            position = (

                _db.query(LigneDeCalcul)

                .filter(LigneDeCalcul.ouvrage_id == ouvrage_id)

                .count()

            )

            # Calcul de la quantité commerciale via facteur_conversion du catalogue

            mat = _db.query(Material).filter(Material.id == material_id).first()

            commercial_quantity: float | None = None

            commercial_unit: str | None = None

            if mat and mat.facteur_conversion and mat.facteur_conversion > 0:

                commercial_quantity = float(_imath.ceil(quantity / mat.facteur_conversion))

                commercial_unit = mat.unite_commerciale or mat.unite_defaut

            ligne = LigneDeCalcul(

                ouvrage_id=ouvrage_id,

                material_id=material_id,

                description=description,

                quantity=quantity,

                unit=unit,

                commercial_quantity=commercial_quantity,

                commercial_unit=commercial_unit,

                position=position,

            )

            _db.add(ligne)

            _db.commit()

            _db.refresh(ligne)

            result = {

                "id": ligne.id,

                "description": ligne.description,

                "quantity": ligne.quantity,

                "unit": ligne.unit,

                "ouvrage_id": ouvrage_id,

            }

            result["commercial_quantity"] = ligne.commercial_quantity

            result["commercial_unit"] = ligne.commercial_unit

            _fire_event(event_callback, "calcul", result)

            return {k: v for k, v in result.items() if k != "ouvrage_id"}

        except Exception:

            _db.rollback()

            raise

        finally:

            _db.close()



    @tool

    def create_note_de_calcul(title: str, contenu: str) -> dict:

        """

        Crée une note de calcul pour l'ouvrage courant.

        Documente la démarche (formules, hypothèses, résultats intermédiaires).



        Args:

            title:   Titre de la note (ex: "Calcul surface carrelage salle de bain").

            contenu: Contenu détaillé (formules, raisonnement, résultats).



        Returns:

            Dictionnaire ``{id, title}``.

        """

        _db = _new_db()

        try:

            note = NoteDeCalcul(

                title=title,

                contenu=contenu,

                ouvrage_id=ouvrage_id,

                calculation_date=datetime.now(timezone.utc).isoformat(),

            )

            _db.add(note)

            _db.commit()

            _db.refresh(note)

            return {"id": note.id, "title": note.title}

        except Exception:

            _db.rollback()

            raise

        finally:

            _db.close()



    @tool

    def get_ouvrage_info() -> dict:

        """

        Retourne les détails de l'ouvrage courant avec ses lignes de calcul existantes.

        Utile pour vérifier ce qui a déjà été saisi avant d'ajouter des lignes.

        """

        _db = _new_db()

        try:

            ouvrage = _db.query(Ouvrage).filter(Ouvrage.id == ouvrage_id).first()

            if not ouvrage:

                return {"error": f"Ouvrage {ouvrage_id} introuvable."}

            return {

                "id": ouvrage.id,

                "name": ouvrage.name,

                "categorie": ouvrage.categorie,

                "description": ouvrage.description,

                "lignes_de_calcul": [

                    {

                        "id": l.id,

                        "description": l.description,

                        "quantity": l.quantity,

                        "unit": l.unit,

                        "material_name": l.material.name if l.material else "?",

                    }

                    for l in ouvrage.lignes_de_calcul

                ],

            }

        finally:

            _db.close()



    return [

        run_calculation,

        list_project_materials,

        add_ligne_de_calcul,

        create_note_de_calcul,

        get_ouvrage_info,

    ]





# ──────────────────────────────────────────────────────────────

# CONSTRUCTION DU SOUS-GRAPHE METTREUR

# ──────────────────────────────────────────────────────────────



class _MettreurState(TypedDict):

    """État interne du sous-graphe Mettreur (sans persistence)."""



    messages: Annotated[list[BaseMessage], add_messages]

    ouvrage_id: int

    project_id: int





def _build_mettreur_graph(

    db: Session,

    project_id: int,

    user_id: int,

    ouvrage_id: int,

    event_callback: EventCallback,

) -> Any:

    """

    Construit et retourne le sous-graphe LangGraph du Mettreur.



    Le sous-graphe est autonome (sans checkpointer) et s'exécute jusqu'à

    complétion avant de retourner le rapport au Chef de Projet.

    """

    if not _GEMINI_API_KEY:

        raise CustomException("GEMINI_API_KEY non configurée.", status_code=500)



    mettreur_tools = _make_mettreur_tools(db, project_id, user_id, ouvrage_id, event_callback)

    token_tracker = _TokenTracker(db, user_id, project_id, event_callback)

    llm_mettreur = ChatGoogleGenerativeAI(

        model=_METTREUR_MODEL,

        google_api_key=_GEMINI_API_KEY,

        temperature=0.1,

        callbacks=[token_tracker],

    ).bind_tools(mettreur_tools)



    tool_node = ToolNode(mettreur_tools)



    def mettreur_node(state: _MettreurState) -> dict:

        response = llm_mettreur.invoke(

            [SystemMessage(content=_METTREUR_SYSTEM_PROMPT)] + state["messages"]

        )

        return {"messages": [response]}



    builder: StateGraph = StateGraph(_MettreurState)

    builder.add_node("mettreur", mettreur_node)

    builder.add_node("mettreur_tools", tool_node)

    builder.add_edge(START, "mettreur")

    builder.add_conditional_edges("mettreur", tools_condition, {"tools": "mettreur_tools", "__end__": END})

    builder.add_edge("mettreur_tools", "mettreur")



    return builder.compile()





# ──────────────────────────────────────────────────────────────

# CONSTRUCTION DU GRAPHE PRINCIPAL (CHEF DE PROJET)

# ──────────────────────────────────────────────────────────────



def _build_chef_graph(

    db: Session,

    project_id: int,

    user_id: int,

    event_callback: EventCallback,

) -> Any:

    """

    Construit le graphe LangGraph principal du Chef de Projet.



    Utilise ``_checkpointer`` (MemorySaver global) pour persister l'état

    entre les appels HTTP ``run`` et ``resume``.

    """

    if not _GEMINI_API_KEY:

        raise CustomException("GEMINI_API_KEY non configurée.", status_code=500)



    chef_tools = _make_chef_tools(db, project_id, user_id, event_callback)

    token_tracker = _TokenTracker(db, user_id, project_id, event_callback)

    llm_chef = ChatGoogleGenerativeAI(

        model=_CHEF_MODEL,

        google_api_key=_GEMINI_API_KEY,

        temperature=0.2,

        callbacks=[token_tracker],

    ).bind_tools(chef_tools)



    tool_node = ToolNode(chef_tools)



    def chef_node(state: BTPAgentState) -> dict:

        # Gemini rejette les AIMessage avec content vide meme quand tool_calls
        # est present (erreur "contents are required" apres interrupt/resume).
        # On remplace le contenu vide par un espace pour eviter ce bug.
        sanitized: list[BaseMessage] = []
        for msg in state["messages"]:
            if (
                isinstance(msg, AIMessage)
                and getattr(msg, "tool_calls", None)
                and not _extract_text_content(msg.content).strip()
            ):
                msg = AIMessage(
                    content=" ",
                    tool_calls=msg.tool_calls,
                    id=msg.id,
                )
            sanitized.append(msg)

        response = llm_chef.invoke(

            [SystemMessage(content=_CHEF_SYSTEM_PROMPT)] + sanitized

        )

        return {"messages": [response]}



    builder: StateGraph = StateGraph(BTPAgentState)

    builder.add_node("chef", chef_node)

    builder.add_node("chef_tools", tool_node)

    builder.add_edge(START, "chef")

    builder.add_conditional_edges("chef", tools_condition, {"tools": "chef_tools", "__end__": END})

    builder.add_edge("chef_tools", "chef")



    return builder.compile(checkpointer=_checkpointer)





# ──────────────────────────────────────────────────────────────

# HELPERS D'INSPECTION DU GRAPHE

# ──────────────────────────────────────────────────────────────



def _thread_config(project_id: int) -> dict:

    """Retourne la configuration de thread LangGraph pour un projet donné."""

    return {"configurable": {"thread_id": str(project_id)}}





async def _inspect_state(

    graph: Any,

    config: dict,

    db: Session,

    project_id: int,

) -> dict:

    """

    Inspecte l'état du graphe après un invoke pour détecter un interrupt ou une complétion.



    Returns:

        Dictionnaire ``{status, question, message}`` transmis à l'API.

    """

    state = await graph.aget_state(config)



    if state.next:

        for task in state.tasks:

            if task.interrupts:

                iv = task.interrupts[0].value

                question_id = iv.get("question_id") if isinstance(iv, dict) else None

                question_text = (

                    iv.get("question_text", "") if isinstance(iv, dict) else str(iv)

                )

                q = (

                    db.query(Question).filter(Question.id == question_id).first()

                    if question_id

                    else None

                )

                return {

                    "status": "waiting_user",

                    "question": {

                        "id": question_id,

                        "text": question_text,

                        "ouvrage_id": q.ouvrage_id if q else None,

                    },

                    "message": "Le workflow est suspendu et attend une réponse de l'utilisateur.",

                }



    project = db.query(Project).filter(Project.id == project_id).first()

    final_status = project.status if project else "done"

    return {

        "status": final_status,

        "question": None,

        "message": (

            "Workflow terminé avec succès."

            if final_status == "done"

            else f"Statut du projet : {final_status}"

        ),

    }





# ──────────────────────────────────────────────────────────────

# API PUBLIQUE

# ──────────────────────────────────────────────────────────────



async def run_project_workflow(

    project_id: int,

    user_id: int,

    db: Session,

    event_callback: EventCallback | None = None,

) -> dict:

    """

    Démarre le workflow agentique d'analyse et de calcul de métrés pour un projet.



    Si un workflow précédent existe déjà pour ce projet (dans le checkpointer),

    l'appel le reprend depuis son dernier état sauvegardé.



    Args:

        project_id: Identifiant du projet à traiter.

        user_id:    Identifiant de l'utilisateur propriétaire (contrôle d'accès).

        db:         Session SQLAlchemy active (injectée par FastAPI).



    Returns:

        Dict ``{status, question, message}`` :

            - ``status="waiting_user"`` → question posée, reprendre avec resume_project_workflow.

            - ``status="done"``         → workflow terminé avec succès.

            - ``status="error"``        → erreur inattendue (détails dans le projet BDD).



    Raises:

        CustomException(404) — projet introuvable ou accès refusé.

        CustomException(500) — erreur interne lors de l'exécution du workflow.

    """

    project = (

        db.query(Project)

        .filter(Project.id == project_id, Project.user_id == user_id)

        .first()

    )

    if not project:

        raise CustomException("Projet introuvable ou accès refusé.", status_code=404)



    # ── Capture de la boucle asyncio pour _fire_event (thread-safe) ──
    global _main_event_loop
    _main_event_loop = asyncio.get_running_loop()

    # ── Vérification du quota de tokens ──

    _cb = event_callback or _noop_event_callback

    user = db.query(User).filter(User.id == user_id).first()

    if user and user.plan:

        if (user.quota_used or 0) >= user.plan.quota:

            await _cb(

                "error",

                {"message": "Quota mensuel de tokens épuisé. Veuillez mettre à niveau votre abonnement."},

            )

            raise CustomException(

                "Quota mensuel de tokens épuisé.", status_code=429

            )



    plans = db.query(PlanBatiment).filter(PlanBatiment.project_id == project_id).all()

    plans_info = (

        ", ".join(f"'{p.name}' (ID={p.id})" for p in plans)

        if plans

        else "aucun plan fourni"

    )



    _update_project_status(db, project_id, "calcul_running", "Démarrage de l'analyse")

    await _cb("step", {"message": "Démarrage de l'analyse du projet..."})



    graph = _build_chef_graph(db, project_id, user_id, _cb)

    config = _thread_config(project_id)

    # Limite intelligente : nb_materiaux catalogue x 30 steps chef + 6 steps/plan + base 100

    _nb_mat_run = db.query(Material).count()

    config["recursion_limit"] = max(200, _nb_mat_run * 30 + len(plans) * 6 + 100)



    initial = HumanMessage(

        content=(

            f"Démarre l'analyse du projet ID={project_id} : '{project.name}'.\n"

            + (f"Description : {project.description}\n" if project.description else "")

            + f"Plans de bâtiment disponibles : {plans_info}.\n"

            "Lis les plans, identifie chaque ouvrage, délègue les calculs au Mettreur, "

            "puis marque le projet comme terminé une fois tous les ouvrages traités."

        )

    )



    try:

        await graph.ainvoke(

            {

                "project_id": project_id,

                "user_id": user_id,

                "messages": [initial],

            },

            config=config,

        )

    except Exception as exc:  # noqa: BLE001

        _update_project_status(db, project_id, "error", str(exc)[:255])

        raise CustomException(

            f"Erreur lors de l'exécution du workflow : {exc}", status_code=500

        ) from exc



    return await _inspect_state(graph, config, db, project_id)





async def resume_project_workflow(

    project_id: int,

    user_id: int,

    answer: str,

    db: Session,

    event_callback: EventCallback | None = None,

) -> dict:

    """

    Reprend le workflow agentique après la réponse de l'utilisateur à une question.



    Args:

        project_id: Identifiant du projet.

        user_id:    Identifiant de l'utilisateur propriétaire (contrôle d'accès).

        answer:     Réponse de l'utilisateur à la question en attente.

        db:         Session SQLAlchemy active.



    Returns:

        Même structure que ``run_project_workflow``.



    Raises:

        CustomException(404) — projet introuvable ou accès refusé.

        CustomException(400) — projet non en attente de réponse.

        CustomException(500) — erreur interne.

    """

    project = (

        db.query(Project)

        .filter(Project.id == project_id, Project.user_id == user_id)

        .first()

    )

    if not project:

        raise CustomException("Projet introuvable ou accès refusé.", status_code=404)

    if project.status != "waiting_user":

        raise CustomException(

            f"Le projet n'est pas en attente de réponse (statut : {project.status}).",

            status_code=400,

        )



    # Mise à jour de la question pendante en BDD (avant la reprise du graphe)

    pending_q = (

        db.query(Question)

        .filter(Question.project_id == project_id, Question.status == "pending")

        .order_by(Question.asked_date.desc())

        .first()

    )

    if pending_q:

        pending_q.answer_text = answer

        pending_q.status = "answered"

        pending_q.answered_date = datetime.now(timezone.utc).isoformat()

        db.commit()



    _update_project_status(db, project_id, "calcul_running", "Reprise après réponse utilisateur")



    _cb2 = event_callback or _noop_event_callback

    graph = _build_chef_graph(db, project_id, user_id, _cb2)

    config = _thread_config(project_id)

    # Limite intelligente : meme formule que run (catalogue global)

    _nb_mat_res = db.query(Material).count()

    config["recursion_limit"] = max(200, _nb_mat_res * 30 + 100)



    try:

        await graph.ainvoke(LGCommand(resume=answer), config=config)

    except Exception as exc:  # noqa: BLE001

        _update_project_status(db, project_id, "error", str(exc)[:255])

        raise CustomException(

            f"Erreur lors de la reprise du workflow : {exc}", status_code=500

        ) from exc



    return await _inspect_state(graph, config, db, project_id)

