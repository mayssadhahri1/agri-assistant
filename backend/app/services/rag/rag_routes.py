
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.services.rag.retriever import retrieve_context
from app.services.rag.indexer import index_pdf, index_all_pdfs, DOCUMENTS_DIR
from app.services.rag.vector_store import get_collection_stats
from app.security import get_current_user, require_roles

# Indexer des documents = réservé à l'admin et à l'expert ; chercher = utilisateur connecté
gestion_documents = [Depends(require_roles("admin", "expert"))]
connecte = [Depends(get_current_user)]


# =====================================================
# 1. CONFIGURATION DU ROUTER
# =====================================================

router = APIRouter(
    prefix="/rag",
    tags=["RAG - Recherche documentaire"]
)


# =====================================================
# 2. MODELE DE RECHERCHE
# =====================================================

class SearchRequest(BaseModel):

    question: str = Field(
        min_length=3,
        max_length=2000
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=10
    )


# =====================================================
# 3. MODELE D'INDEXATION
# =====================================================

class IndexRequest(BaseModel):

    filename: str = Field(
        min_length=5,
        max_length=255
    )


# =====================================================
# 4. RECHERCHE DOCUMENTAIRE
# =====================================================

@router.post("/search", dependencies=connecte)
def search(request: SearchRequest):
    """
    Recherche les passages pertinents
    pour une question dans les PDF indexes.
    """

    try:

        result = retrieve_context(
            question=request.question,
            top_k=request.top_k
        )

        return {
            "success": True,
            **result
        }

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Erreur pendant la recherche RAG : {str(error)}"
        )


# =====================================================
# 5. INDEXATION D'UN PDF
# =====================================================

@router.post("/index", dependencies=gestion_documents)
def index_single_pdf(request: IndexRequest):
    """
    Indexe un PDF présent dans documents/agriculture.
    """

    filename = request.filename.strip()

    # Vérification du nom du fichier
    if (
        Path(filename).name != filename
        or not filename.lower().endswith(".pdf")
    ):
        raise HTTPException(
            status_code=400,
            detail="Veuillez fournir un nom de fichier PDF valide."
        )

    pdf_path = DOCUMENTS_DIR / filename

    if not pdf_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"PDF introuvable : {filename}"
        )

    try:

        indexed_count = index_pdf(pdf_path)

        return {
            "success": True,
            "message": "Indexation du PDF terminee.",
            "filename": filename,
            "nombre_chunks_indexes": indexed_count
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Erreur pendant l'indexation : {str(error)}"
        )


# =====================================================
# 6. INDEXATION DE TOUS LES PDF
# =====================================================

@router.post("/index-all", dependencies=gestion_documents)
def index_all_documents():
    """
    Indexe tous les PDF du dossier agriculture.
    """

    try:

        total = index_all_pdfs()

        return {
            "success": True,
            "message": "Indexation des documents terminee.",
            "nombre_chunks_indexes": total
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Erreur pendant l'indexation : {str(error)}"
        )


# =====================================================
# 7. STATISTIQUES DE LA BASE VECTORIELLE
# =====================================================

@router.get("/stats", dependencies=gestion_documents)
def get_rag_stats():
    """
    Affiche les statistiques de ChromaDB.
    """

    try:

        stats = get_collection_stats()

        return {
            "success": True,
            "statistiques": stats
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la recuperation des statistiques : {str(error)}"
        )
