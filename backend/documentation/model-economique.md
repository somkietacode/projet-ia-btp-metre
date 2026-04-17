# 💰 Modèle Économique — Plateforme IA BTP Métré

> Document à destination du client — Comment nous résolvons votre problème et pourquoi ça fonctionne.

---

## 1. Votre Problème Aujourd'hui

Le **métré** — l'étape de quantification des matériaux à partir des plans — est aujourd'hui :

| Constat | Impact |
|---------|--------|
| **Manuel** | Un métreur expérimenté passe des heures à compter, mesurer et calculer à la main |
| **Coûteux** | L'intervention d'un spécialiste représente un coût significatif par projet |
| **Source d'erreurs** | Les oublis et erreurs de calcul entraînent des surcoûts chantier de 5 à 15% |
| **Réservé aux experts** | Seuls les professionnels formés maîtrisent les conventions de plans et les règles de calcul |
| **Non scalable** | Impossible de traiter plus de 2 à 5 projets par jour par personne |

---

## 2. Notre Solution : L'IA au Service du Métré

### Ce que fait la plateforme

Vous uploadez un **plan PDF ou image** → l'IA analyse, extrait, calcule → vous obtenez les **quantités par lot** prêtes à exploiter.

```
📄 Plan PDF/Image
    ↓
🔍 Analyse par Intelligence Artificielle (Vision)
    ↓  L'IA lit les cotes, identifie les éléments (murs, ouvertures, toiture...)
📐 Calcul automatique des quantités
    ↓  Surfaces, volumes, comptages, linéaires
✅ Validation par vous
    ↓  Vous vérifiez, corrigez si besoin, complétez les données manquantes
📊 Export PDF / Excel / CSV
    → Prêt pour votre chiffrage
```

### Les 3 niveaux d'automatisation

Notre système est **honnête** — il ne devine pas ce qu'il ne peut pas lire :

| Niveau | Quand ? | Exemple |
|--------|---------|---------|
| **🟢 Automatique** | La cote est lisible ET l'élément est identifié sur le plan | Surface mur = 4.50m × 2.80m = 12.6 m² |
| **🟡 Semi-automatique** | Une donnée manque mais peut être déduite ou demandée | Hauteur sous plafond non cotée → le système vous la demande |
| **🔴 Manuel** | Le plan est insuffisant pour cette donnée | Vous saisissez la valeur directement |

> **Garantie** : chaque résultat est accompagné de sa **justification** (source de la donnée, formule utilisée). Vous savez toujours d'où vient un chiffre.

---

## 3. Ce que Couvre la Plateforme

### Lots et ouvrages pris en charge (V1)

| Lot | Ouvrages calculés |
|-----|-------------------|
| **Terrassement** | Volume de fouilles, emprise au sol, décapage |
| **Fondations** | Linéaire de fondations, volume béton, ferraillage |
| **Maçonnerie** | Surface de murs, nombre de parpaings/briques, déduction des ouvertures |
| **Plâtrerie / Placo** | Surface de cloisons, nombre de plaques BA13, rails et montants |
| **Carrelage** | Surface au sol par pièce, nombre de carreaux avec perte |
| **Toiture** | Surface de couverture, nombre de tuiles/ardoises, linéaire de faîtage et arêtiers |
| **Enduit / Crépi** | Surface de façades extérieures, déduction des ouvertures |
| **Chape / Dalle** | Surface et volume de chape, épaisseur paramétrable |

### Paramétrage métier personnalisable

Vous configurez **vos propres paramètres** :
- Dimensions des matériaux (parpaing 20×20×50, brique, plaque BA13...)
- Coefficients de perte (5%, 10%, 15%...)
- Hauteur sous plafond par défaut
- Épaisseurs standard (chape, enduit, fondation...)

Ces paramètres sont **sauvegardés** et réutilisés automatiquement sur vos prochains projets.

---

## 4. Tarification

### Abonnement unique : **20€ / mois**

| Inclus | Détail |
|--------|--------|
| **~50 projets/mois** | Largement suffisant pour une PME du BTP (2-3 projets/jour ouvré) |
| **Tous les lots** | Terrassement, fondation, maçonnerie, placo, carrelage, toiture, enduit, chape |
| **Export illimité** | PDF, Excel, CSV — autant d'exports que nécessaire |
| **Paramétrage sauvegardé** | Vos matériaux et coefficients sont mémorisés |
| **Historique complet** | Retrouvez tous vos projets et résultats passés |

### Pourquoi ce prix est viable

Notre IA fonctionne avec des **modèles de vision de dernière génération** (Claude, GPT-4o). Voici la transparence sur les coûts :

| Poste | Coût par projet |
|-------|----------------|
| Analyse vision des plans (4 pages) | ~0.08 $ |
| Calculs et vérifications IA | ~0.02 $ |
| Infrastructure serveur | ~0.02 $ |
| **Total** | **~0.12 $** |

Pour 50 projets/mois : **6$ de coûts** pour **20€ de revenu** → le service est économiquement pérenne.

### Comparaison avec l'existant

| Solution | Coût | Temps par projet | Précision |
|----------|------|------------------|-----------|
| Métreur humain | 200-500€/projet | 4-8 heures | Haute (mais erreurs humaines) |
| Logiciel métré classique (sans IA) | 50-200€/mois | 1-3 heures (saisie manuelle) | Dépend de l'opérateur |
| **Notre plateforme** | **20€/mois** | **5-15 minutes** | **Haute + traçable** |

---

## 5. Comment ça Marche Techniquement (Résumé)

### Les 4 étapes du traitement

```
1️⃣ IMPORT        Vous uploadez votre plan (PDF ou image)
                  → Le système convertit en images haute résolution

2️⃣ ANALYSE       L'IA de vision lit le plan
                  → Extraction des cotes (dimensions)
                  → Identification des éléments (murs, portes, fenêtres, toiture...)

3️⃣ CALCUL        Le moteur de calcul applique les formules métier
                  → Surface = Longueur × Largeur
                  → Volume = Surface × Épaisseur
                  → Comptage = Surface ÷ Surface_unitaire × (1 + Perte%)
                  → Linéaire = Somme des segments

4️⃣ RÉSULTAT      Vous recevez les quantités par lot
                  → Chaque ligne est justifiée (source + formule)
                  → Vous validez, corrigez si nécessaire, et exportez
```

### Suivi en temps réel

Pendant l'analyse, une **barre de progression** vous montre l'avancement en temps réel via WebSocket. Vous savez exactement où en est le traitement.

### Sécurité et confidentialité

| Mesure | Détail |
|--------|--------|
| **Authentification** | Connexion sécurisée par JWT |
| **Données isolées** | Chaque utilisateur n'accède qu'à ses propres projets |
| **Plans non partagés** | Vos plans ne sont jamais utilisés pour entraîner l'IA |
| **RGPD** | Suppression des données sur demande |

---

## 6. Limites et Transparence

Nous préférons être honnêtes sur ce que la plateforme **peut** et **ne peut pas** faire :

### ✅ Ce que la plateforme fait bien
- Plans architecturaux propres et cotés → résultats fiables
- Plans de masse avec dimensions → emprise et terrassement
- Plans de toiture avec pentes → surface de couverture
- Projets résidentiels standard (maisons, petits immeubles)

### ⚠️ Ce qui nécessite votre intervention
- Plans mal cotés → le système vous demande les dimensions manquantes
- Conventions de plan inhabituelles → validation requise
- Éléments spéciaux non standard → saisie manuelle

### ❌ Ce que la plateforme ne fait pas (V1)
- Calcul de structure (dimensionnement des poutres, armatures...)
- Plans 3D / maquettes BIM (uniquement plans 2D)
- Devis chiffré (elle produit les quantités, pas les prix)

---

## 7. Calendrier de Mise en Service

| Phase | Période | Ce qui est livré |
|-------|---------|-----------------|
| **Phase 1** | Semaines 1-4 | Infrastructure, comptes utilisateurs, base de données |
| **Phase 2** | Semaines 5-8 | Lecture des plans par IA, détection des éléments |
| **Phase 3** | Semaines 9-12 | Moteur de calcul complet, paramétrage métier, résultats |
| **Phase 4** | Semaines 13-16 | Export PDF/Excel, tests sur plans réels, mise en production |

**Durée totale : 16 semaines** pour une V1 fonctionnelle et testée sur des plans réels.

---

## 8. En Résumé

| Question | Réponse |
|----------|---------|
| **Qu'est-ce que c'est ?** | Une plateforme SaaS qui transforme vos plans en quantités chantier grâce à l'IA |
| **Combien ça coûte ?** | 20€/mois, tout inclus |
| **C'est fiable ?** | Chaque résultat est justifié et vérifiable. Vous gardez le contrôle |
| **C'est rapide ?** | 5 à 15 minutes au lieu de plusieurs heures |
| **C'est pour qui ?** | PME du BTP, artisans, maîtres d'œuvre, économistes de la construction |
| **Quand c'est prêt ?** | V1 opérationnelle en 16 semaines |
