from pathlib import Path
import config

from utils import (
    load_document_text,
    clean_text,
    chunk_text,
    list_document_files,
)

from embeddings import get_embeddings
from vectorstore import reset_collection, add_chunks, count_chunks


# Dossier contenant les documents métier
DOCUMENTS_PATH = Path(getattr(config, "DOCUMENTS_PATH", "./documents"))

# Paramètres de chunking
CHUNK_SIZE = int(getattr(config, "CHUNK_SIZE", 500))
CHUNK_OVERLAP = int(getattr(config, "CHUNK_OVERLAP", 50))


# Fichiers à ne pas indexer dans le RAG
# emails_clients_test.csv sert à évaluer le système, pas à nourrir la base documentaire.
EXCLUDED_FILES = {
    "emails_clients_test.csv",
}


def should_ingest_file(file_path: Path) -> bool:
    """
    Détermine si un fichier doit être indexé dans la base RAG.
    """
    if file_path.name in EXCLUDED_FILES:
        return False

    return True


def ingest_document(file_path: Path, collection) -> int:
    """
    Charge, nettoie, découpe et indexe un document dans ChromaDB.

    Retourne le nombre de chunks ajoutés.
    """
    print(f"\nIngestion : {file_path.name}")

    raw_text = load_document_text(file_path)
    cleaned_text = clean_text(raw_text)

    if not cleaned_text:
        print("  Document vide après nettoyage. Ignoré.")
        return 0

    chunks = chunk_text(
        cleaned_text,
        chunk_size=CHUNK_SIZE,
        overlap=CHUNK_OVERLAP,
    )

    if not chunks:
        print("  Aucun chunk généré. Ignoré.")
        return 0

    print(f"  Chunks générés : {len(chunks)}")
    print("  Génération des embeddings...")

    embeddings = get_embeddings(chunks)

    metadatas = []
    ids = []

    for index, _ in enumerate(chunks):
        chunk_id = f"{file_path.stem}_{index}"

        ids.append(chunk_id)

        metadatas.append(
            {
                "source": file_path.name,
                "file_type": file_path.suffix.lower(),
                "chunk_index": index,
                "chunk_id": chunk_id,
            }
        )

    add_chunks(
        collection=collection,
        chunks=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids,
    )

    print(f"  Chunks ajoutés à ChromaDB : {len(chunks)}")

    return len(chunks)


def ingest_all_documents() -> None:
    """
    Ingestion complète de la base documentaire.

    Cette fonction :
    1. liste les documents du dossier documents/
    2. réinitialise la collection ChromaDB
    3. indexe chaque document autorisé
    4. affiche un résumé final
    """
    print("=" * 80)
    print("Démarrage de l’ingestion RAG — NordTrail Gear")
    print("=" * 80)

    print(f"Dossier documents : {DOCUMENTS_PATH}")
    print(f"Chunk size : {CHUNK_SIZE}")
    print(f"Chunk overlap : {CHUNK_OVERLAP}")

    if not DOCUMENTS_PATH.exists():
        raise FileNotFoundError(f"Dossier documents introuvable : {DOCUMENTS_PATH}")

    document_files = list_document_files(DOCUMENTS_PATH)

    document_files = [
        file_path for file_path in document_files
        if should_ingest_file(file_path)
    ]

    if not document_files:
        print("Aucun document à indexer.")
        return

    print("\nDocuments qui seront indexés :")
    for file_path in document_files:
        print(f"  - {file_path.name}")

    print("\nRéinitialisation de la collection ChromaDB...")
    collection = reset_collection()

    total_chunks = 0

    for file_path in document_files:
        try:
            total_chunks += ingest_document(file_path, collection)
        except Exception as error:
            print(f"  Erreur pendant l’ingestion de {file_path.name} : {error}")

    print("\n" + "=" * 80)
    print("Ingestion terminée")
    print("=" * 80)
    print(f"Documents indexés : {len(document_files)}")
    print(f"Chunks ajoutés : {total_chunks}")
    print(f"Chunks présents dans ChromaDB : {count_chunks(collection)}")


if __name__ == "__main__":
    ingest_all_documents()
