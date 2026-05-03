# Backend IA de Metre


Ce projet consiste à réaliser une IA pour metre les projet de btp et identifier les quantités d'oeuvres nécessaire pour effectuer les travaux.

## Prise en main & installation

Ce projet fonctionne sous forme de container docker avec pour point d'entré le fichier docker-compose.yml . Celui-ci orchestre 3 système pour l'instant :

- le backend : Une API REST en fast API qu'il est possible d'invoquer via un frontend.
- la base de donnée : Une base de donnée postgreSQL qui permet de stocker les données du système (utilisateur, plan etc).
- la base de donnée vectoriel (Qdrant db pour le stockage de vecteur et recherche vectoriel du llm).
- le moniteur ia : azire phoenix

### Comment installer le logiciel ?

Pour installer le logiciel il faut déjà avoir d'abord accès au répertoire github. 

1. Utiliser l'invite de commande pour cloner le repo :

```shell
git clone https://github.com/{username}/{project}
```

2. Copier le fichier de configration .env.exemple dans .env
```shell
cd backend/
cp .env.exemple .env
```

3. Configurer le fichier d'environnement avec vos propre variable et enfin lancer le container avec la commande `docker compose up -d --build` le service est exposé sur le pour 8742.


## Point restant 

Il est important de noter ce qui à été fait et ce qu'il reste à faire.

Pour ce qui est déjà fait :

1. Achitecture de base de la base de donnée (system d'utilisatieur, plan, quota, document, projet)
2. 