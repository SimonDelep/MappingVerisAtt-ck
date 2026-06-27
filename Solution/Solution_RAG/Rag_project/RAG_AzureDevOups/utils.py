from pathlib import Path
from pypdf import PdfReader
import re
import csv
import json
from typing import List


SUPPORTED_EXTENSIONS = {".pdf", ".md", ".txt", ".csv", ".json"}


def load_pdf_text(pdf_path: str | Path) -> str:
    """
    Charge le texte d'un fichier PDF.
    """
    reader = PdfReader(str(pdf_path))
    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"[Page {page_number}]\n{text}")

    return "\n\n".join(pages)


def load_text_file(file_path: str | Path) -> str:
    """
    Charge un fichier texte simple : .md ou .txt.
    """
    return Path(file_path).read_text(encoding="utf-8")


def load_csv_as_text(csv_path: str | Path) -> str:
    """
    Transforme un CSV en texte lisible par le RAG.
    Chaque ligne devient une description textuelle.
    """
    rows = []

    with Path(csv_path).open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for index, row in enumerate(reader, start=1):
            row_text = " | ".join(
                f"{key}: {value}" for key, value in row.items()
            )
            rows.append(f"Ligne {index} — {row_text}")

    return "\n".join(rows)


def load_json_as_text(json_path: str | Path) -> str:
    """
    Transforme un fichier JSON en texte structuré.
    """
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))

    if isinstance(data, list):
        entries = []

        for index, item in enumerate(data, start=1):
            entries.append(
                f"Entrée {index}:\n"
                + json.dumps(item, ensure_ascii=False, indent=2)
            )

        return "\n\n".join(entries)

    return json.dumps(data, ensure_ascii=False, indent=2)


def load_document_text(file_path: str | Path) -> str:
    """
    Charge automatiquement un document selon son extension.
    Formats supportés : PDF, Markdown, TXT, CSV, JSON.
    """
    path = Path(file_path)
    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Format non supporté : {path}")

    if extension == ".pdf":
        return load_pdf_text(path)

    if extension in {".md", ".txt"}:
        return load_text_file(path)

    if extension == ".csv":
        return load_csv_as_text(path)

    if extension == ".json":
        return load_json_as_text(path)

    raise ValueError(f"Format non supporté : {path}")


def clean_text(text: str) -> str:
    """
    Nettoyage léger du texte.

    On garde les retours à la ligne utiles pour préserver un peu la structure,
    mais on supprime les caractères parasites et les espaces excessifs.
    """
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """
    Découpage simple par mots.

    chunk_size = nombre approximatif de mots par chunk.
    overlap = nombre de mots repris entre deux chunks.

    Pour un prototype RAG, c'est plus propre qu'un découpage par caractères,
    car on évite de couper les phrases n'importe où.
    """
    if overlap >= chunk_size:
        raise ValueError("overlap doit être inférieur à chunk_size")

    words = text.split()
    chunks = []

    step = chunk_size - overlap

    for start in range(0, len(words), step):
        end = start + chunk_size
        chunk = " ".join(words[start:end]).strip()

        if chunk:
            chunks.append(chunk)

    return chunks


def list_document_files(documents_path: str | Path) -> List[Path]:
    """
    Liste tous les documents exploitables dans le dossier documents/.
    """
    documents_path = Path(documents_path)

    if not documents_path.exists():
        raise FileNotFoundError(f"Dossier introuvable : {documents_path}")

    files = []

    for path in documents_path.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(path)

    return sorted(files)
