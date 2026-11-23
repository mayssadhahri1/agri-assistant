
import chromadb
import hashlib

from pathlib import Path

from app.services.rag.embeddings import (
    generate_embeddings,
    generate_query_embedding
)


# =====================================================
# 1. CONFIGURATION DE LA BASE VECTORIELLE
# =====================================================

BASE_DIR = Path(__file__).resolve().parents[3]

VECTOR_DB_PATH = BASE_DIR / "vector_db"

COLLECTION_NAME = "agriculture_documents"


# =====================================================
# 2. INITIALISATION DE CHROMADB
# =====================================================

VECTOR_DB_PATH.mkdir(parents=True, exist_ok=True)

client = chromadb.PersistentClient(
    path=str(VECTOR_DB_PATH)
)

collection = client.get_or_create_collection(
    name=COLLECTION_NAME,
    metadata={"hnsw:space": "cosine"}
)


# =====================================================
# 3. GENERATION DES IDENTIFIANTS
# =====================================================

def generate_document_id(chunk):
    """
    Génère un identifiant unique pour chaque chunk.
    """

    unique_text = (
        f"{chunk['source']}_"
        f"{chunk['page']}_"
        f"{chunk['chunk_index']}"
    )

    return hashlib.sha256(
        unique_text.encode("utf-8")
    ).hexdigest()


# =====================================================
# 4. AJOUT DES DOCUMENTS
# =====================================================

def add_documents(chunks):
    """
    Enregistre les chunks et leurs embeddings
    dans ChromaDB.
    """

    if not chunks:
        return 0

    valid_chunks = []

    for chunk in chunks:

        if not isinstance(chunk, dict):
            raise ValueError("Chaque chunk doit être un dictionnaire.")

        required_fields = [
            "text",
            "source",
            "page",
            "chunk_index"
        ]

        for field in required_fields:
            if field not in chunk:
                raise ValueError(
                    f"Champ manquant dans le chunk : {field}"
                )

        if not str(chunk["text"]).strip():
            continue

        valid_chunks.append(chunk)

    if not valid_chunks:
        return 0

    # Extraction des textes
    texts = [
        str(chunk["text"])
        for chunk in valid_chunks
    ]

    # Génération des embeddings
    embeddings = generate_embeddings(texts)

    if len(embeddings) != len(texts):
        raise ValueError(
            "Le nombre d'embeddings ne correspond pas au nombre de textes."
        )

    # Préparation des identifiants et métadonnées
    ids = []
    metadatas = []

    for chunk in valid_chunks:

        ids.append(generate_document_id(chunk))

        metadatas.append({
            "source": str(chunk["source"]),
            "page": int(chunk["page"]),
            "chunk_index": int(chunk["chunk_index"])
        })

    # Enregistrement dans ChromaDB
    collection.upsert(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas
    )

    return len(valid_chunks)


# =====================================================
# 5. RECHERCHE DES DOCUMENTS
# =====================================================

def search_documents(question, top_k=5):
    """
    Recherche les passages les plus proches
    de la question dans la base vectorielle.
    """

    if not question or not question.strip():
        raise ValueError(
            "La question ne peut pas être vide."
        )

    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k <= 0:
        raise ValueError(
            "top_k doit être un entier positif."
        )

    total_documents = collection.count()

    if total_documents == 0:
        return {
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]]
        }

    # Génération de l'embedding de la question
    query_embedding = generate_query_embedding(
        question.strip()
    )

    if not query_embedding:
        raise ValueError(
            "Impossible de générer l'embedding de la question."
        )

    # Recherche dans ChromaDB
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, total_documents),
        include=[
            "documents",
            "metadatas",
            "distances"
        ]
    )

    return results


# =====================================================
# 6. SUPPRESSION DES DOCUMENTS D'UNE SOURCE
# =====================================================

def delete_document(source):
    """
    Supprime tous les chunks associés à un PDF.
    """

    if not source or not source.strip():
        raise ValueError("La source ne doit pas être vide.")

    existing = collection.get(
        where={"source": source.strip()},
        include=[]
    )

    ids = existing.get("ids", [])

    if not ids:
        return 0

    collection.delete(ids=ids)

    return len(ids)


# =====================================================
# 7. STATISTIQUES DE LA BASE VECTORIELLE
# =====================================================

def get_collection_stats():
    """
    Retourne les statistiques de la collection.
    """

    return {
        "collection": COLLECTION_NAME,
        "nombre_chunks": collection.count(),
        "chemin_base": str(VECTOR_DB_PATH)
    }


# =====================================================
# 8. RECUPERATION DE TOUS LES DOCUMENTS
# =====================================================

def get_all_documents():
    """
    Retourne les documents enregistrés.
    """

    results = collection.get(
        include=[
            "documents",
            "metadatas"
        ]
    )

    documents = []

    for document, metadata in zip(
        results.get("documents") or [],
        results.get("metadatas") or []
    ):

        documents.append({
            "contenu": document,
            "source": metadata.get("source"),
            "page": metadata.get("page"),
            "chunk_index": metadata.get("chunk_index")
        })

    return documents
