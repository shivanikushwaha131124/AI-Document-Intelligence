import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.document_service import (
    fetch_all_documents,
    fetch_document,
    save_document,
)
from app.services.document_validation_service import (
    validate_document_file,
)
from app.services.extraction_service import (
    extract_basic_fields,
)
from app.services.financial_validation_service import (
    validate_financial_data,
)
from app.services.ocr_service import (
    extract_text_from_image,
    extract_text_from_pdf,
)


router = APIRouter(
    prefix="/api/v1/documents",
    tags=["Documents"],
)


ALLOWED_DOCUMENT_TYPES = {
    "invoice",
    "balance_sheet",
    "profit_and_loss",
    "cash_flow_statement",
}


@router.post("/process")
async def process_document(
    file: UploadFile = File(...),
    document_type: str = Form(...),
    db: Session = Depends(get_db),
):

    start_time = time.perf_counter()

    # -----------------------------------------------------
    # Document type
    # -----------------------------------------------------

    document_type = document_type.strip().lower()

    if document_type not in ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_DOCUMENT_TYPE",
                "message": (
                    "document_type must be one of: "
                    "invoice, balance_sheet, "
                    "profit_and_loss, "
                    "cash_flow_statement"
                ),
            },
        )

    # -----------------------------------------------------
    # File
    # -----------------------------------------------------

    filename = file.filename or ""

    if not filename:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "MISSING_FILE_NAME",
                "message": (
                    "Uploaded file must have a file name."
                ),
            },
        )

    file_bytes = await file.read()

    file_check = validate_document_file(
        filename,
        len(file_bytes),
    )

    if not file_check["is_supported"]:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "UNSUPPORTED_FILE_TYPE",
                "message": (
                    "Only PDF, JPG, JPEG and PNG "
                    "documents are supported."
                ),
            },
        )

    if not file_check["is_readable"]:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_FILE",
                "message": file_check.get(
                    "error",
                    "File is empty or invalid.",
                ),
            },
        )

    extension = Path(filename).suffix.lower()

    # -----------------------------------------------------
    # OCR / text extraction
    # -----------------------------------------------------

    try:

        if extension == ".pdf":

            ocr_result = extract_text_from_pdf(
                file_bytes
            )

        elif extension in {
            ".jpg",
            ".jpeg",
            ".png",
        }:

            ocr_result = extract_text_from_image(
                file_bytes
            )

        else:

            raise HTTPException(
                status_code=400,
                detail={
                    "code": "UNSUPPORTED_FILE_TYPE",
                    "message": (
                        "Only PDF, JPG, JPEG and PNG "
                        "documents are supported."
                    ),
                },
            )

    except HTTPException:
        raise

    except Exception as exc:

        print(
            f"OCR ERROR: "
            f"{type(exc).__name__}: {exc}"
        )

        raise HTTPException(
            status_code=422,
            detail={
                "code": "OCR_PROCESSING_FAILED",
                "message": (
                    "The document could not be "
                    "read or processed."
                ),
            },
        )

    # -----------------------------------------------------
    # Page validation
    # -----------------------------------------------------

    page_count = ocr_result.get(
        "page_count",
        0,
    )

    if page_count > 3:

        raise HTTPException(
            status_code=400,
            detail={
                "code": "PAGE_LIMIT_EXCEEDED",
                "message": (
                    "Documents with more than "
                    "3 pages are not supported."
                ),
            },
        )

    if not ocr_result.get(
        "is_readable",
        False,
    ):

        raise HTTPException(
            status_code=422,
            detail={
                "code": "DOCUMENT_NOT_READABLE",
                "message": ocr_result.get(
                    "error",
                    "Document text could not be read.",
                ),
            },
        )

    # -----------------------------------------------------
    # Structured extraction
    # -----------------------------------------------------

    try:

        extracted_data = extract_basic_fields(
            text=ocr_result.get(
                "text",
                "",
            ),
            document_type=document_type,
            pages=ocr_result.get(
                "pages",
                [],
            ),
        )

    except Exception as exc:

        print(
            f"EXTRACTION ERROR: "
            f"{type(exc).__name__}: {exc}"
        )

        raise HTTPException(
            status_code=500,
            detail={
                "code": "EXTRACTION_FAILED",
                "message": (
                    "Document extraction failed."
                ),
            },
        )

    # -----------------------------------------------------
    # Financial validation
    # -----------------------------------------------------

    financial_fields = {
        key: (
            value.get("value")
            if isinstance(value, dict)
            else value
        )
        for key, value in extracted_data.get(
            "fields",
            {},
        ).items()
    }

    try:

        validation_checks = validate_financial_data(
            document_type=document_type,
            fields=financial_fields,
            tables=extracted_data.get(
                "tables",
                [],
            ),
            periods=extracted_data.get(
                "periods",
                [],
            ),
        )

    except Exception as exc:

        print(
            f"VALIDATION ERROR: "
            f"{type(exc).__name__}: {exc}"
        )

        raise HTTPException(
            status_code=500,
            detail={
                "code": "VALIDATION_FAILED",
                "message": (
                    "Financial validation failed."
                ),
            },
        )

    validation_checks = jsonable_encoder(
        validation_checks
    )

    # -----------------------------------------------------
    # Overall validation status
    # -----------------------------------------------------

    statuses = [
        check.get("status")
        for check in validation_checks
    ]

    if "FAIL" in statuses:

        overall_status = "FAIL"

    elif "PASS" in statuses:

        overall_status = "PASS"

    elif "NOT_APPLICABLE" in statuses:

        overall_status = "NOT_APPLICABLE"

    else:

        overall_status = "NOT_APPLICABLE"

    # -----------------------------------------------------
    # Validation issues
    # -----------------------------------------------------

    issues = []

    for check in validation_checks:

        if check.get("status") == "FAIL":

            issues.append(
                {
                    "name": check.get("name"),
                    "formula": check.get("formula"),
                    "variance": check.get("variance"),
                    "reason": check.get("reason"),
                }
            )

    # -----------------------------------------------------
    # Metadata
    # -----------------------------------------------------

    processing_time_ms = round(
        (
            time.perf_counter()
            - start_time
        )
        * 1000,
        2,
    )

    processed_at = datetime.now(
        timezone.utc
    )

    processing_metadata = {
        "ocr_used": ocr_result.get(
            "ocr_used",
            False,
        ),
        "processed_at": processed_at.isoformat(),
        "processing_time_ms": processing_time_ms,
    }

    # -----------------------------------------------------
    # File validation result
    # -----------------------------------------------------

    file_validation = {
        "file_type": (
            file.content_type
            or ""
        ),
        "is_supported": True,
        "is_readable": True,
        "page_count": page_count,
        "status": "PASS",
    }

    extracted_data = jsonable_encoder(
        extracted_data
    )

    # -----------------------------------------------------
    # Persistence
    # -----------------------------------------------------

    document_data = {
        "document_name": filename,
        "document_type": document_type,
        "processing_status": "PASS",
        "file_type": (
            file.content_type
            or ""
        ),
        "page_count": page_count,
        "is_supported": True,
        "is_readable": True,
        "extracted_data": extracted_data,
        "validation": {
            "checks": validation_checks,
            "overall_status": overall_status,
            "issues": issues,
        },
        "processing_metadata": processing_metadata,
        "processed_at": processed_at,
    }

    try:

        document = save_document(
            db,
            document_data,
        )

    except Exception as exc:

        print(
            f"DATABASE ERROR: "
            f"{type(exc).__name__}: {exc}"
        )

        raise HTTPException(
            status_code=500,
            detail={
                "code": "DATABASE_ERROR",
                "message": (
                    "Processed document could "
                    "not be stored."
                ),
            },
        )

    # -----------------------------------------------------
    # Response
    # -----------------------------------------------------

    return {
        "document_name": document.document_name,
        "document_type": document.document_type,
        "processing_status": document.processing_status,
        "file_validation": file_validation,
        "extracted_data": document.extracted_data,
        "validation": document.validation,
        "processing_metadata": document.processing_metadata,
    }


# =========================================================
# GET DOCUMENT
# =========================================================

@router.get("/{document_name}")
def get_document(
    document_name: str,
    db: Session = Depends(get_db),
):

    document = fetch_document(
        db,
        document_name,
    )

    if not document:

        raise HTTPException(
            status_code=404,
            detail={
                "code": "DOCUMENT_NOT_FOUND",
                "message": "Document not found.",
            },
        )

    return {
        "document_name": document.document_name,
        "document_type": document.document_type,
        "processing_status": document.processing_status,
        "file_validation": {
            "file_type": document.file_type,
            "is_supported": document.is_supported,
            "is_readable": document.is_readable,
            "page_count": document.page_count,
            "status": (
                "PASS"
                if document.is_readable
                else "FAILED"
            ),
        },
        "extracted_data": document.extracted_data,
        "validation": document.validation,
        "processing_metadata": document.processing_metadata,
    }


# =========================================================
# LIST DOCUMENTS
# =========================================================

@router.get("")
def list_documents(
    db: Session = Depends(get_db),
):

    documents = fetch_all_documents(db)

    return [
        {
            "document_name": document.document_name,
            "document_type": document.document_type,
            "processing_status": document.processing_status,
            "processed_at": document.processed_at,
        }
        for document in documents
    ]