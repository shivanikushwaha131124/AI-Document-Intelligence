from sqlalchemy.orm import Session

from app.repositories.document_repository import (
    create_document,
    get_all_documents,
    get_document_by_name,
)


def save_document(db: Session, document_data: dict):
    existing = get_document_by_name(
        db,
        document_data["document_name"]
    )

    if existing:
        for key, value in document_data.items():
            setattr(existing, key, value)

        db.commit()
        db.refresh(existing)

        return existing

    return create_document(db, document_data)


def fetch_document(db: Session, document_name: str):
    return get_document_by_name(db, document_name)


def fetch_all_documents(db: Session):
    return get_all_documents(db)