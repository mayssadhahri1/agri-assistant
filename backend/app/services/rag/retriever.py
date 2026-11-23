
from app.services.rag.vector_store import search_documents


def retrieve_context(question: str, top_k: int = 5):
    """
    Recherche les passages les plus pertinents
    pour une question dans la base vectorielle.
    """

    if not question or not question.strip():
        raise ValueError("La question ne doit pas être vide.")

    if top_k < 1:
        raise ValueError("top_k doit être supérieur ou égal à 1.")

    results = search_documents(
        question=question.strip(),
        top_k=top_k
    )

    documents = results.get("documents") or [[]]
    metadatas = results.get("metadatas") or [[]]
    distances = results.get("distances") or [[]]

    documents = documents[0] if documents else []
    metadatas = metadatas[0] if metadatas else []
    distances = distances[0] if distances else []

    passages = []

    for document, metadata, distance in zip(
        documents, metadatas, distances
    ):
        metadata = metadata or {}

        passages.append({
            "contenu": document,
            "source": metadata.get("source", "Source inconnue"),
            "page": metadata.get("page", "Page inconnue"),
            "score_distance": (
                round(float(distance), 4)
                if distance is not None else None
            )
        })

    return {
        "question": question.strip(),
        "nombre_passages": len(passages),
        "passages": passages
    }
