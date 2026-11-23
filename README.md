# 🌱 Assistant agricole intelligent (VLM + RAG)

Un « ChatGPT de l'agriculteur » : l'agriculteur envoie une photo et pose une question en français ou en arabe. L'application analyse les images et fournit des conseils agricoles fiables, basés sur des documents et des sources.

## 🏗️ Structure du projet

```text
agri-assistant/
│
├── database/
│   └── schema.sql
│
└── backend/
    ├── app/
    │   ├── main.py
    │   ├── services/
    │   │   └── rag/
    │   │       ├── embeddings.py
    │   │       ├── indexer.py
    │   │       ├── pdf_loader.py
    │   │       ├── rag_routes.py
    │   │       ├── retriever.py
    │   │       ├── text_chunker.py
    │   │       ├── vector_store.py
    │   │       └── __init__.py
    │   └── ...
    │
    ├── documents/
    │   └── agriculture/
    │       └── guide_pratique_olivier.pdf
    │
    ├── vector_db/
    ├── uploads/
    │   └── photos/
    │
    ├── requirements.txt
    └── .env
```

# Étape 1 — Base de données et backend (authentification)

### 1. Base de données MySQL

Base de données MySQL avec XAMPP (port 3307).

```powershell
Get-Content database\schema.sql -Raw | C:\xampp\mysql\bin\mysql.exe -u root -P 3307 --protocol=TCP
```

### 2. Installation du backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
```

Lancement du serveur :

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

Swagger : [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 3. Endpoints d'authentification

| Méthode | URL              | Description                          |
| ------- | ---------------- | ------------------------------------ |
| GET     | `/health`        | Vérifier l'API et la connexion MySQL |
| POST    | `/auth/register` | Inscription                          |
| POST    | `/auth/login`    | Connexion et génération du token JWT |
| GET     | `/auth/me`       | Consulter le profil                  |
| PATCH   | `/auth/me`       | Modifier le nom ou la langue         |

# Étape 2 — Gestion des parcelles

Toutes les opérations nécessitent un token JWT.

Chaque agriculteur peut uniquement consulter et gérer ses propres parcelles.

| Méthode | URL                          | Description            |
| ------- | ---------------------------- | ---------------------- |
| POST    | `/parcelles`                 | Créer une parcelle     |
| GET     | `/parcelles?culture=olivier` | Lister les parcelles   |
| GET     | `/parcelles/{id}`            | Consulter une parcelle |
| PATCH   | `/parcelles/{id}`            | Modifier une parcelle  |
| DELETE  | `/parcelles/{id}`            | Supprimer une parcelle |

Cultures acceptées :

- `olivier`
- `tomate`
- `ble`
- `agrumes`
- `palmier_dattier`
- `autre`

# Étape 3 — Conversations, questions et photos

Toutes les opérations nécessitent un token JWT.

Une conversation est associée à une parcelle. L'agriculteur peut poser ses questions en français ou en arabe et joindre jusqu'à 3 photos.

| Méthode | URL                            | Description                           |
| ------- | ------------------------------ | ------------------------------------- |
| POST    | `/conversations`               | Créer une conversation                |
| GET     | `/conversations?parcelle_id=1` | Lister les conversations              |
| GET     | `/conversations/{id}`          | Consulter les messages et photos      |
| DELETE  | `/conversations/{id}`          | Supprimer une conversation            |
| POST    | `/conversations/{id}/messages` | Envoyer une question et des photos    |
| GET     | `/parcelles/{id}/historique`   | Consulter l'historique d'une parcelle |

### Fonctionnalités développées

- Contrôle qualité des photos : détection des images floues, trop sombres ou trop claires.
- Les photos à reprendre sont retournées dans `photos_a_reprendre`.
- Détection automatique de la langue : français (`fr`) ou arabe (`ar`).
- Enregistrement des photos dans `backend/uploads/photos/`.
- Accès aux photos via `/uploads/photos/{nom}.jpg`.

### Dépendance supplémentaire

```powershell
pip install -r requirements.txt
```

La bibliothèque Pillow est utilisée pour le traitement et le contrôle qualité des images.

# Étape 4 — Développement du module RAG (analyse des documents PDF)

**Objectif :** permettre à l'assistant agricole de rechercher des informations dans les documents PDF afin de récupérer des passages pertinents pour répondre aux questions des agriculteurs.

Le module RAG (Retrieval-Augmented Generation) prépare une base de connaissances documentaires qui sera utilisée par le système d'intelligence artificielle.

## 1. Structure du module RAG

Dossier créé :

```text
backend/app/services/rag/
```

Fichiers développés :

| Fichier           | Rôle                                            |
| ----------------- | ----------------------------------------------- |
| `pdf_loader.py`   | Extraction du texte des documents PDF           |
| `text_chunker.py` | Découpage du texte en petits segments           |
| `embeddings.py`   | Transformation du texte en vecteurs numériques  |
| `vector_store.py` | Stockage et recherche vectorielle avec ChromaDB |
| `indexer.py`      | Indexation des documents PDF                    |
| `retriever.py`    | Recherche des passages pertinents               |
| `rag_routes.py`   | Intégration du module RAG dans FastAPI          |
| `__init__.py`     | Initialisation du package Python                |

## 2. Extraction du texte des PDF

Le fichier `pdf_loader.py` a été implémenté avec la bibliothèque PyMuPDF.

Fonctionnalités :

- Ouverture et lecture des fichiers PDF.
- Extraction du texte page par page.
- Conservation du nom du document source.
- Conservation du numéro de chaque page.
- Vérification de l'existence et du format du fichier.
- Fermeture du document après lecture.

Chaque page extraite est représentée par les informations suivantes :

```python
{
    "text": text,
    "source": path.name,
    "page": page_number
}
```

## 3. Découpage du texte

Le fichier `text_chunker.py` permet de diviser les documents en petits segments appelés chunks.

Chaque chunk conserve :

- Le contenu textuel.
- Le nom du fichier PDF.
- Le numéro de page.
- L'indice du chunk.

Cette opération facilite la recherche ciblée dans les documents.

## 4. Génération des embeddings

Le fichier `embeddings.py` transforme les passages textuels en vecteurs numériques.

Ces vecteurs permettent de comparer sémantiquement une question avec les informations présentes dans les documents.

Deux fonctions principales sont utilisées :

- `generate_embeddings()` : génération des vecteurs des documents.
- `generate_query_embedding()` : génération du vecteur d'une question.

## 5. Stockage vectoriel avec ChromaDB

Le fichier `vector_store.py` assure le stockage des chunks et de leurs embeddings dans ChromaDB.

Fonctionnalités :

- Initialisation d'une base vectorielle persistante.
- Création de la collection `agriculture_documents`.
- Enregistrement et mise à jour des chunks.
- Recherche des passages similaires à une question.
- Conservation des métadonnées : source, page et indice du chunk.
- Consultation des statistiques de la collection.
- Suppression des chunks associés à un document.

Le stockage est effectué dans :

```text
backend/vector_db/
```

## 6. Indexation des documents

Le fichier `indexer.py` automatise le traitement des documents PDF.

Pipeline d'indexation :

```text
PDF
 ↓
Extraction du texte (pdf_loader.py)
 ↓
Découpage en chunks (text_chunker.py)
 ↓
Génération des embeddings (embeddings.py)
 ↓
Enregistrement dans ChromaDB (vector_store.py)
```

Dossier contenant les documents agricoles :

```text
backend/documents/agriculture/
```

Commande d'indexation :

```powershell
python -m app.services.rag.indexer
```

## 7. Recherche des passages pertinents

Le fichier `retriever.py` permet de rechercher les passages les plus pertinents à partir d'une question.

Fonctionnalités :

- Recherche sémantique dans ChromaDB.
- Récupération des meilleurs passages.
- Retour du contenu des passages.
- Identification du document source.
- Conservation des numéros de pages.
- Retour du score de distance.
- Préparation du contexte documentaire pour la future génération de réponses.

## 8. Intégration dans FastAPI

Le fichier `rag_routes.py` expose les fonctionnalités RAG sous forme d'endpoints API.

Le routeur est intégré dans `app/main.py`.

Endpoints développés :

| Méthode | URL              | Description                            |
| ------- | ---------------- | -------------------------------------- |
| POST    | `/rag/index`     | Indexer un document PDF                |
| POST    | `/rag/index-all` | Indexer tous les PDF agricoles         |
| POST    | `/rag/search`    | Rechercher les passages pertinents     |
| GET     | `/rag/stats`     | Consulter les statistiques de ChromaDB |

### Exemple de recherche

Requête :

```json
{
    "question": "Comment cultiver un olivier ?",
    "top_k": 5
}
```

Exemple de structure de réponse :

```json
{
    "success": true,
    "question": "Comment cultiver un olivier ?",
    "nombre_passages": 2,
    "passages": [
        {
            "contenu": "Contenu extrait du document...",
            "source": "guide_pratique_olivier.pdf",
            "page": 1,
            "score_distance": 0.245
        }
    ],
    "message": "Passages récupérés avec succès."
}
```

Les résultats dépendent du contenu réel des documents indexés.

## 9. Tests et vérifications

Vérification de PyMuPDF :

```powershell
python -c "import fitz; print('PyMuPDF fonctionne correctement')"
```

Vérification de ChromaDB :

```powershell
python -c "from app.services.rag.vector_store import get_collection_stats; print(get_collection_stats())"
```

Test de recherche :

```powershell
python -c "from app.services.rag.retriever import retrieve_context; print(retrieve_context('Comment cultiver un olivier ?', 5))"
```

Lancement du serveur :

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

Documentation Swagger :

[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### État d'avancement de l'étape 4

- [x] Création du dossier RAG.
- [x] Création des fichiers du module RAG.
- [x] Extraction du texte PDF avec PyMuPDF.
- [x] Extraction du texte page par page.
- [x] Conservation des références des pages et des documents.
- [x] Découpage du texte en chunks.
- [x] Génération des embeddings.
- [x] Mise en place du stockage vectoriel avec ChromaDB.
- [x] Indexation des documents PDF.
- [x] Recherche des passages pertinents.
- [x] Intégration du module RAG dans FastAPI.
- [x] Validation complète des endpoints sur Swagger.



# Étape 5 — Intégration de l'intelligence artificielle (prochaine étape)

L'objectif est de connecter les différents composants intelligents de l'application afin de produire des conseils agricoles adaptés aux besoins de l'agriculteur.

### 1. RAG — Recherche documentaire

- Récupération des informations pertinentes dans les PDF agricoles.
- Transmission du contexte documentaire au modèle de langage.
- Conservation des sources et des numéros de pages.

### 2. LLM — Génération des réponses

- Génération de réponses à partir des questions des agriculteurs.
- Utilisation du contexte récupéré par le RAG.
- Réponses en français ou en arabe.
- Refus de fournir des informations non présentes dans les sources lorsque celles-ci sont insuffisantes.

### 3. VLM — Analyse des photos

- Analyse des images des cultures.
- Identification des problèmes visibles.
- Détection éventuelle des maladies et des anomalies.
- Combinaison des informations visuelles avec les connaissances documentaires.

### 4. Météo — Informations météorologiques

- Récupération des conditions météorologiques.
- Prise en compte de la météo dans les recommandations agricoles.
- Adaptation des conseils selon les conditions climatiques.

### 5. Vérification des réponses

- Vérification de la cohérence des réponses avec les documents.
- Affichage des sources et des pages utilisées.
- Signalement lorsque les documents ne contiennent pas suffisamment d'informations.
- Réduction des risques d'hallucination.

# Technologies utilisées

| Domaine                   | Technologies               |
| ------------------------- | -------------------------- |
| Backend                   | Python, FastAPI            |
| Base de données           | MySQL                      |
| Authentification          | JWT                        |
| Traitement PDF            | PyMuPDF                    |
| Découpage du texte        | Python                     |
| Embeddings                | Sentence Transformers      |
| Stockage vectoriel        | ChromaDB                   |
| Traitement des images     | Pillow                     |
| Intelligence artificielle | RAG, LLM, VLM              |
| Documentation API         | Swagger / OpenAPI          |
| Environnement             | Python Virtual Environment |

# Lancement du projet

Depuis le dossier `backend` :

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

Documentation Swagger :

[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

**Projet : Assistant agricole intelligent (VLM + RAG)**

Objectif : développer un assistant intelligent permettant aux agriculteurs d'obtenir des conseils fiables à partir de photos, de questions et de documents agricoles.
