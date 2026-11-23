
import fitz
from pathlib import Path


def load_pdf(pdf_path: str):
    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF introuvable : {pdf_path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError("Le fichier doit être un PDF.")

    documents = []

    pdf = fitz.open(str(path))

    try:
        for page_number, page in enumerate(pdf, start=1):
            text = page.get_text("text").strip()

            if text:
                documents.append({
                    "text": text,
                    "source": path.name,
                    "page": page_number
                })
    finally:
        pdf.close()

    return documents
