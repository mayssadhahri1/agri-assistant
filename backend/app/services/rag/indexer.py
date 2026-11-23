
from pathlib import Path

from app.services.rag.pdf_loader import load_pdf
from app.services.rag.text_chunker import create_chunks
from app.services.rag.vector_store import add_documents


# =====================================================
# 1. CONFIGURATION
# =====================================================

BASE_DIR = Path(__file__).resolve().parents[3]

DOCUMENTS_DIR = BASE_DIR / "documents" / "agriculture"


# =====================================================
# 2. PREPARATION DES CHUNKS
# =====================================================

def prepare_chunks(chunks, pdf_path):
    """
    Vérifie et complète les informations des chunks.
    """

    prepared_chunks = []

    for index, chunk in enumerate(chunks):

        if not isinstance(chunk, dict):
            continue

        text = chunk.get("text", "")

        if not text or not str(text).strip():
            continue

        prepared_chunk = {
            "text": str(text).strip(),
            "source": str(chunk.get("source") or pdf_path.name),
            "page": int(chunk.get("page") or 1),
            "chunk_index": int(
                chunk.get("chunk_index", index)
            )
        }

        prepared_chunks.append(prepared_chunk)

    return prepared_chunks


# =====================================================
# 3. INDEXATION D'UN PDF
# =====================================================

def index_pdf(pdf_path):
    """
    Extrait le contenu d'un PDF,
    découpe le texte et enregistre les chunks
    dans ChromaDB.
    """

    pdf_path = Path(pdf_path)

    # Vérification du fichier
    if not pdf_path.exists():
        raise FileNotFoundError(
            f"Fichier PDF introuvable : {pdf_path}"
        )

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(
            "Le fichier doit être au format PDF."
        )

    print("\n" + "=" * 50)
    print(f"Lecture du document : {pdf_path}")
    print("=" * 50)

    # 1. Extraction du texte PDF
    pages = load_pdf(str(pdf_path))

    if not pages:
        print("Aucun texte extrait du PDF.")
        return 0

    print(f"Nombre de pages : {len(pages)}")

    # 2. Découpage du texte
    chunks = create_chunks(pages)

    if not chunks:
        print("Aucun chunk genere.")
        return 0

    print(f"Nombre de chunks : {len(chunks)}")

    # 3. Préparation des chunks
    chunks = prepare_chunks(chunks, pdf_path)

    if not chunks:
        print("Aucun chunk valide a indexer.")
        return 0

    print(f"Chunks valides : {len(chunks)}")

    # 4. Enregistrement dans ChromaDB
    indexed_count = add_documents(chunks)

    print(f"Chunks indexes : {indexed_count}")

    print(
        f"Indexation terminee pour : {pdf_path.name}"
    )

    return indexed_count


# =====================================================
# 4. INDEXATION DE TOUS LES PDF
# =====================================================

def index_all_pdfs():
    """
    Recherche et indexe tous les PDF
    présents dans documents/agriculture.
    """

    DOCUMENTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    pdf_files = sorted(
        DOCUMENTS_DIR.glob("*.pdf")
    )

    if not pdf_files:
        print(
            "Aucun PDF trouve dans documents/agriculture."
        )
        return 0

    print("\n" + "=" * 50)
    print("DEBUT DE L'INDEXATION DES DOCUMENTS")
    print("=" * 50)

    total = 0
    successful = 0
    failed = 0

    for pdf_path in pdf_files:

        try:
            indexed_count = index_pdf(pdf_path)

            total += indexed_count
            successful += 1

        except Exception as error:

            failed += 1

            print(
                f"\nErreur lors de l'indexation de "
                f"{pdf_path.name} : {error}"
            )

    # 5. Rapport final
    print("\n" + "=" * 50)
    print("RAPPORT FINAL DE L'INDEXATION")
    print("=" * 50)

    print(f"Nombre de PDF : {len(pdf_files)}")
    print(f"PDF traites : {successful}")
    print(f"PDF en erreur : {failed}")
    print(f"Total des chunks indexes : {total}")

    print("=" * 50)

    return total


# =====================================================
# 5. POINT D'ENTREE
# =====================================================

if __name__ == "__main__":

    index_all_pdfs()
