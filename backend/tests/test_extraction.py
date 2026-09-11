from app.services.extraction_service import extract_basic_fields


def test_extraction_returns_required_structure():
    pages = [
        {
            "page_number": 1,
            "text": "Invoice Number: INV-001\nTotal: 100.00",
            "lines": [
                {
                    "text": "Invoice Number: INV-001",
                    "words": [],
                },
                {
                    "text": "Total: 100.00",
                    "words": [],
                },
            ],
            "is_readable": True,
            "ocr_used": False,
        }
    ]

    result = extract_basic_fields(
        text="Invoice Number: INV-001\nTotal: 100.00",
        document_type="invoice",
        pages=pages,
    )

    assert isinstance(result, dict)
    assert "fields" in result
    assert "tables" in result
    assert "document_type" in result
    assert result["document_type"] == "invoice"