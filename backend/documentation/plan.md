# 📐 Plan d'Exécution — Plateforme IA Agentique BTP Métré

## 1. Analyse du Problème & Hypothèses Fondamentales

### 1.1 Décomposition logique du problème

Le cahier des charges se réduit à une **chaîne de transformation formelle** :

```
Entrée (Plan PDF/Image + Paramètres Utilisateur) → Extraction (Vision IA) → Structuration (Graphe d'éléments) → Calcul (Moteur métier) → Sortie (Quantités)
```

**Preuve par algèbre de Bool — Faisabilité de l'automatisation :**

Soit les propositions :
- **A** = "La cote est lisible sur le plan"
- **B** = "L'élément est identifiable graphiquement"
- **C** = "Le paramètre est fourni par l'utilisateur"
- **Q** = "La quantité est calculable"

Alors : **Q = (A ∧ B) ∨ (C ∧ B) ∨ (A ∧ C)**

Pour produire une quantité, il faut **au minimum deux sources d'information parmi trois**. Si une seule source est disponible, la quantité est **indéterminée** → le système doit demander les données manquantes.

**Table de vérité :**

| A | B | C | Q | Niveau |
|---|---|---|---|--------|
| 1 | 1 | 1 | 1 | Automatique + validé |
| 1 | 1 | 0 | 1 | Automatique |
| 1 | 0 | 1 | 1 | Semi-automatique |
| 0 | 1 | 1 | 1 | Semi-automatique |
| 1 | 0 | 0 | 0 | Insuffisant |
| 0 | 1 | 0 | 0 | Insuffisant |
| 0 | 0 | 1 | 0 | Insuffisant |
| 0 | 0 | 0 | 0 | Impossible |

**Conséquence architecturale** : le système doit implémenter un **graphe de dépendances** entre données et résultats, capable d'identifier les données manquantes et de les demander à l'utilisateur.

### 1.2 Modèle mathématique des calculs métier

Tous les calculs du cahier des charges se ramènent à **4 opérations fondamentales** :

| Opération | Formule | Exemple |
|-----------|---------|---------|
| **Surface** | S = L × l | Murs, carrelage, toiture, crépi |
| **Volume** | V = S × e | Béton fondation, chape, terrassement |
| **Comptage** | N = S / (s_unitaire) × (1 + τ_perte) | Briques, parpaings, plaques, tuiles |
| **Linéaire** | L_total = Σ segments | Fondations, chaînages, arêtiers |

Avec :
- τ_perte = coefficient de perte paramétrable (typiquement 5-10%)
- s_unitaire = surface unitaire d'un élément (ex: brique 20×50 = 0.1 m²)

**Il n'y a aucun calcul complexe** — la complexité réside dans l'**extraction** (vision IA), pas dans le calcul.

---

## 2. Architecture Technique

### 2.1 Schéma d'architecture globale

> 📎 Diagramme : [architecture-globale.mmd](architecture-globale.mmd)

### 2.2 Flux agentique LangGraph — Graphe d'états

> 📎 Diagramme : [flux-agentique-langgraph.mmd](flux-agentique-langgraph.mmd)

### 2.3 Modèle de données PostgreSQL

> 📎 Diagramme : [modele-donnees-postgresql.mmd](modele-donnees-postgresql.mmd)

---

## 3. Structure du Dépôt & Stack Technique

```
projet-ia-btp-metre/
├── docker-compose.yml
├── .env.example
├── frontend/                    # Angular 17+
│   ├── src/app/
│   │   ├── modules/
│   │   │   ├── auth/
│   │   │   ├── upload/
│   │   │   ├── parametrage/
│   │   │   ├── projet/
│   │   │   └── resultats/
│   │   └── shared/
│   └── Dockerfile
├── backend/                     # FastAPI
│   ├── app/
│   │   ├── api/                 # Routes REST + WebSocket
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── services/
│   │   │   ├── auth.py
│   │   │   ├── quota.py
│   │   │   └── export.py
│   │   ├── agents/              # LangGraph
│   │   │   ├── graph.py         # Graphe principal
│   │   │   ├── nodes/
│   │   │   │   ├── vision.py
│   │   │   │   ├── detection.py
│   │   │   │   ├── calcul.py
│   │   │   │   └── validation.py
│   │   │   └── tools/
│   │   │       ├── pdf_converter.py
│   │   │       ├── ocr_tool.py
│   │   │       ├── geometry.py
│   │   │       └── metre_calculator.py
│   │   └── db/
│   └── Dockerfile
├── qdrant/                      # Config Qdrant
│   └── init_collections.py
├── docs/
│   ├── cahier_des_charges.md
│   └── api_spec.yaml
└── monitoring/                  # Arize Phoenix
    └── phoenix_config.yaml
```

---

## 4. Composants Clés — Décisions Techniques Justifiées

| Composant | Choix | Justification |
|-----------|-------|---------------|
| **Vision IA** | Claude 3.5 Sonnet / GPT-4o via API | Seuls modèles prouvés pour extraction structurée depuis plans architecturaux |
| **Orchestration** | LangGraph | Graphe d'états avec boucles conditionnelles (données manquantes → demande user → recalcul) |
| **Base vectorielle** | Qdrant | Stockage des embeddings de livres BTP + normes + données utilisateur pour RAG |
| **BDD relationnelle** | PostgreSQL | Paramètres métier, projets, résultats, utilisateurs, quotas |
| **Conversion PDF** | pdf2image (poppler) | Service Docker isolé, conversion PDF → PNG haute résolution |
| **Monitoring** | Arize Phoenix | Traçabilité des appels LLM, coûts tokens, latence, qualité |
| **Export** | openpyxl + reportlab | Génération Excel et PDF côté serveur |
| **Quotas** | Middleware FastAPI | Token counting par requête, plafond mensuel lié à l'abonnement 20€ |

---

## 5. Contenu de la Base Vectorielle Qdrant

| Collection | Contenu | Usage |
|------------|---------|-------|
| `btp_references` | Livres de métré, DTU, normes construction | RAG pour règles de calcul métier |
| `plan_patterns` | Exemples annotés de plans + éléments détectés | Few-shot learning pour la détection |
| `user_knowledge` | Paramètres et historique par utilisateur | Personnalisation des calculs |

---

## 6. Calendrier d'Exécution — 16 Semaines (4 Sprints de 4 semaines)

> 📎 Diagramme : [calendrier-execution.mmd](calendrier-execution.mmd)

| Sprint | Durée | Livrable |
|--------|-------|----------|
| **Sprint 1** (S1-S4) | 4 sem. | Infrastructure, Auth, BDD, Qdrant peuplé |
| **Sprint 2** (S5-S8) | 4 sem. | Pipeline Vision fonctionnel, détection éléments |
| **Sprint 3** (S9-S12) | 4 sem. | Moteur de calcul complet, paramétrage, résultats |
| **Sprint 4** (S13-S16) | 4 sem. | Export, tests terrain, déploiement |

---

## 7. Gestion des Risques

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| Plans de mauvaise qualité (photos floues) | Haute | Élevé | Pré-traitement image + message d'avertissement qualité + saisie manuelle fallback |
| Variabilité extrême des conventions de plans | Haute | Moyen | Prompts adaptatifs + RAG sur conventions + validation utilisateur |
| Dépassement quota tokens | Moyenne | Moyen | Compteur strict middleware + alerte à 80% |
| Erreurs de calcul métier | Moyenne | Élevé | Chaque résultat porte sa `justification` (source, formule, données) — auditabilité totale |

---

## 8. Résumé Exécutif

**Problème** : Le métré BTP est manuel, lent, coûteux et réservé aux experts.

**Solution** : Une plateforme SaaS agentique à 20€/mois qui transforme un plan PDF en quantités chantier exploitables via une chaîne LangGraph (Vision → Détection → Calcul → Export).

**Faisabilité prouvée** :
- Les calculs sont des opérations arithmétiques simples (S, V, N, L)
- La complexité réside dans l'extraction, couverte par les LLM vision de dernière génération
- Le modèle économique tient : ~0.12$/projet × 50 projets = 6$ de coûts pour 20€ de revenu
- L'architecture 3 niveaux (auto/déduit/manuel) garantit qu'aucune promesse irréaliste n'est faite

**Délai** : 16 semaines pour une V1 fonctionnelle.
