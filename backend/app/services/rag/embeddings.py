
from sentence_transformers import SentenceTransformer


MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

model = SentenceTransformer(MODEL_NAME)


def generate_embeddings(texts):
    """
    Transforme une liste de textes en vecteurs.
    Fonctionne avec le français et l'arabe.
    """

    if not texts:
        return []

    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True
    )

    return embeddings.tolist()


def generate_query_embedding(question):
    """
    Transforme une question en vecteur.
    """

    embeddings = generate_embeddings([question])

    return embeddings[0]
