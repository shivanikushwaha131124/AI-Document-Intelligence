from pathlib import Path


ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_PAGES = 3


def validate_document_file(filename: str, file_size: int) -> dict:
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        return {
            "is_supported": False,
            "is_readable": False,
            "status": "FAILED",
            "error": "Unsupported file type"
        }

    if file_size == 0:
        return {
            "is_supported": True,
            "is_readable": False,
            "status": "FAILED",
            "error": "Empty file"
        }

    return {
        "is_supported": True,
        "is_readable": True,
        "status": "PASS",
        "error": None
    }