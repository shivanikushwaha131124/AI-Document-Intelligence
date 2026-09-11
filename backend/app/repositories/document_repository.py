from sqlalchemy.orm import Session

from app.models.document import Document


def create_document(db: Session, document_data: dict) -> Document:
    document = Document(**document_data)

    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def get_document_by_name(
    db: Session,
    document_name: str
) -> Document | None:

    return (
        db.query(Document)
        .filter(Document.document_name == document_name)
        .first()
    )


def get_all_documents(db: Session) -> list[Document]:
    return (
        db.query(Document)
        .order_by(Document.created_at.desc())
        .all()
    )