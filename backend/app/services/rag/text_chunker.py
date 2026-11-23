
def split_text(text: str, chunk_size=500, overlap=100):
    """
    Découpe un texte en morceaux avec chevauchement.
    """

    if chunk_size <= 0:
        raise ValueError("chunk_size doit être positif.")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap doit être inférieur à chunk_size.")

    chunks = []

    start = 0

    while start < len(text):

        end = start + chunk_size

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


def create_chunks(pages):
    """
    Découpe les pages extraites des PDF.
    Conserve la source et le numéro de page.
    """

    all_chunks = []

    for page in pages:

        chunks = split_text(page["text"])

        for index, chunk in enumerate(chunks):

            all_chunks.append({
                "text": chunk,
                "source": page["source"],
                "page": page["page"],
                "chunk_index": index
            })

    return all_chunks
