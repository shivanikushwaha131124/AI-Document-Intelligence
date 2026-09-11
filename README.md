# **AI Document Intelligence**

> **AI-powered Document Extraction, Validation & API Platform**

A deployable document intelligence platform that extracts structured information from **Invoices, Balance Sheets, Profit & Loss Statements, and Cash Flow Statements** from PDF and image documents.

The system supports **native PDFs and scanned/image-based documents**, performs OCR when required, validates financial data using deterministic rules, stores results in PostgreSQL, and provides both REST APIs and a web dashboard.

---

# **1. Solution Overview**

The platform provides an end-to-end workflow:

```text
Document Upload
      ↓
File Validation
      ↓
PDF / Image Processing
      ↓
Native Text Extraction / OCR
      ↓
Structured Data Extraction
      ↓
Financial Validation
      ↓
PostgreSQL Persistence
      ↓
API + Web Dashboard
Supported Document Types
Invoice
Balance Sheet
Profit & Loss Statement
Cash Flow Statement
Supported Files
PDF
JPG
JPEG
PNG

Maximum supported document length: 3 pages.

Missing information is returned as null or NOT_APPLICABLE; the system does not invent values.

2. Architecture
                    ┌─────────────────────┐
                    │        User         │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Frontend Dashboard │
                    │   HTML/CSS/JavaScript│
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │    FastAPI Backend  │
                    └──────────┬──────────┘
                               │
             ┌─────────────────┼─────────────────┐
             ▼                 ▼                 ▼
      File Validation     PDF / Image       OCR Processing
                               │
                               ▼
                    Structured Extraction
                               │
                               ▼
                    Financial Validation
                               │
                               ▼
                    ┌─────────────────────┐
                    │ PostgreSQL / Supabase│
                    └──────────┬──────────┘
                               │
                               ▼
                    API / Dashboard Result

3. Technology Stack
Technology	Purpose
Python	Backend development
FastAPI	REST API framework
Pydantic	Structured request/response validation
PyMuPDF	PDF text extraction and page rendering
Tesseract OCR	Scanned/image document OCR
Pillow	Image processing
SQLAlchemy	Database ORM
PostgreSQL / Supabase	Persistent database
HTML / CSS / JavaScript	Frontend dashboard
Pytest	Automated testing
Swagger / OpenAPI	API documentation

The implementation uses free/open-source components wherever possible.

4. Project Structure
AI-Document-Intelligence/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes/
│   │   │       └── documents.py
│   │   │
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   └── logging.py
│   │   │
│   │   ├── models/
│   │   │   └── document.py
│   │   │
│   │   ├── repositories/
│   │   │   └── document_repository.py
│   │   │
│   │   ├── schemas/
│   │   │   ├── document.py
│   │   │   └── extraction.py
│   │   │
│   │   ├── services/
│   │   │   ├── document_service.py
│   │   │   ├── document_validation_service.py
│   │   │   ├── extraction_service.py
│   │   │   ├── financial_validation_service.py
│   │   │   └── ocr_service.py
│   │   │
│   │   ├── utils/
│   │   └── main.py
│   │
│   ├── tests/
│   └── requirements.txt
│
├── docs/
│
├── frontend/
│   ├── static/
│   │   ├── css/
│   │   └── js/
│   └── templates/
│       ├── dashboard.html
│       └── document_result.html
│
├── sample_outputs/
│
├── samples/
│   └── New Dataset/
│       ├── Balance Sheet/
│       ├── Cash Flows/
│       ├── Invoices/
│       └── Profit & Loss/
│
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt

5. Local Setup
Clone Repository
git clone https://github.com/shivanikushwaha131124/AI-Document-Intelligence.git
cd AI-Document-Intelligence
Create Virtual Environment
python -m venv .venv
Activate Virtual Environment — Windows PowerShell
.\.venv\Scripts\Activate.ps1
Install Dependencies
pip install -r backend/requirements.txt
6. Environment Configuration

Create a .env file in the project root.

Use .env.example as the template:

DATABASE_URL=your_postgresql_connection_string
Security
Database credentials are stored in environment variables.
.env is excluded from Git.
.env.example contains only placeholders.
No passwords, API keys, or secrets are committed to the repository.
7. Run Locally

From the backend directory:

cd backend
uvicorn app.main:app --reload
Local Backend
http://127.0.0.1:8000
Swagger / OpenAPI
http://127.0.0.1:8000/docs
8. API Endpoints
Health Check
GET /api/v1/health
Process Document
POST /api/v1/documents/process

Request:

multipart/form-data

Parameters:

file
document_type

Example:

curl -X POST "http://127.0.0.1:8000/api/v1/documents/process" \
  -F "file=@invoice.jpg" \
  -F "document_type=invoice"
Get Document
GET /api/v1/documents/{document_name}
List Documents
GET /api/v1/documents
9. Document Processing

The processing pipeline:

Validates the uploaded file.
Checks supported file type.
Checks document readability/corruption.
Checks the maximum 3-page limit.
Extracts native PDF text when available.
Uses OCR for scanned/image-based documents.
Extracts structured fields and tables.
Captures evidence such as source text and page number.
Runs financial validation rules.
Stores the result in PostgreSQL.
Returns the result through the API and dashboard.
10. OCR & Scanned Documents

The system supports both:

Native text PDFs
Scanned/image-based PDFs and images

For PDFs, native text extraction is attempted first.

When usable native text is unavailable, the page is rendered as an image and processed using Tesseract OCR.

For JPG/JPEG/PNG files, OCR is applied directly.

Processing metadata records whether OCR was used.

11. Structured Extraction

Extraction results follow a structured JSON format.

Example:

{
  "document_type": "invoice",
  "fields": {
    "invoice_number": {
      "value": "INV-001",
      "evidence": {
        "source_text": "Invoice #: INV-001",
        "page_number": 1
      }
    },
    "total": {
      "value": 157.48,
      "evidence": {
        "source_text": "Total Due $157.48",
        "page_number": 1
      }
    }
  },
  "tables": []
}

Evidence can include:

source_text
page_number
confidence when available

If a value cannot be reliably extracted, it is not invented.

12. Financial Validation

Financial validation uses deterministic arithmetic reconciliation rules.

Invoice
Quantity × Unit Price ≈ Line Total

Sum of Line Totals ≈ Subtotal

Subtotal + Tax + Shipping ≈ Total

Cash Paid − Total ≈ Change
Balance Sheet
Total Assets ≈ Total Capital & Liabilities

Component reconciliation is also performed where applicable, independently for each period.

Profit & Loss
Interest Earned + Other Income ≈ Total Income

Interest Expended + Operating Expenses
+ Provisions & Contingencies
≈ Total Expenditure

Total Income − Total Expenditure
≈ Net Profit before Minority Interest

Net Profit before Minority Interest
− Minority Interest
≈ Attributable Profit

Appropriation totals are also reconciled where applicable.

Comparative periods are validated independently.

Cash Flow Statement
Operating + Investing + Financing
+ FX / Translation
≈ Net Increase in Cash

Opening Cash + Net Increase
≈ Closing Cash

Parenthesized values are treated as negative values.

13. Validation Status

Every validation check can return:

PASS
FAIL
NOT_APPLICABLE
PASS

The calculated value is within the configured tolerance of the reported value.

FAIL

The calculated value does not reconcile with the reported value.

NOT_APPLICABLE

A required field is missing or genuinely unavailable.

The system does not assume missing values.

Each validation result includes:

Check Name
Formula
Operands
Calculated Value
Reported Value
Variance
Status
14. Database Persistence

Processed documents and results are stored in PostgreSQL using Supabase.

Stored information includes:

Document name
Document type
Processing status
File type
Page count
Supported/readable status
Extracted data
Validation results
Processing metadata
Timestamps

The GET APIs retrieve persisted document results.

15. Frontend Dashboard

The web dashboard provides:

Document type selection
File upload
Processing status
Processed document list
Document name and type
Processing timestamp
Open result action
Extracted fields
Extracted tables / line items
Financial validation results
Processing metadata
Raw JSON result

The dashboard also clearly displays missing or unavailable information.

16. File Validation

The system accepts:

PDF
JPG
JPEG
PNG

The system rejects:

Unsupported file types
Invalid or corrupted documents
Empty/unreadable documents
Documents exceeding 3 pages

Example unsupported-file response:

{
  "detail": {
    "code": "UNSUPPORTED_FILE_TYPE",
    "message": "Only PDF, JPG, JPEG and PNG documents are supported."
  }
}

Unsupported file validation was verified through Swagger with HTTP 400 Bad Request.

17. Testing

Testing covered the required document categories and major processing scenarios.

Document Tests
Invoice
Balance Sheet
Profit & Loss
Cash Flow Statement
Scanned/image-based documents
Validation Tests
Financial reconciliation
Missing required values
PASS
FAIL
NOT_APPLICABLE
Error Handling
Unsupported file type
Invalid/unreadable documents
Page-limit validation
Automated Tests

Automated tests cover:

API health flow
Structured extraction
Financial validation

Successful automated validation tests:

2 passed
18. Known Issues Fixed During Development

During testing, several extraction issues were identified and fixed.

Profit & Loss

OCR garbled Roman-numeral section headers such as I INCOME, causing incorrect field mapping.

The extraction logic was improved to identify section headers using their keywords instead of depending on the Roman-numeral prefix.

Balance Sheet

Some statements used a generic Total row instead of repeating the complete field name.

The extraction logic was updated to interpret the generic total within the correct section.

Cash Flow Statement

Cash-flow wording varied between years, such as:

Net cash from operating activities

and

Net cash flow (used in) / from operating activities

Regex-based matching was added to handle these variations.

A separate header-filtering issue that incorrectly discarded valid rows containing phrases such as as at was also fixed.

Invoice

A naming mismatch between the extracted table name and the validation table name prevented line-item reconciliation checks from running.

The table naming was aligned so that invoice line-item validation can run correctly.

Some individual checks may still return NOT_APPLICABLE when the source document genuinely does not contain the required information or OCR quality is insufficient.

19. Sample Processing Result

Example successful response:

{
  "document_name": "example.pdf",
  "document_type": "invoice",
  "processing_status": "PASS",
  "file_validation": {
    "file_type": "application/pdf",
    "is_supported": true,
    "is_readable": true,
    "page_count": 1,
    "status": "PASS"
  },
  "extracted_data": {},
  "validation": {
    "checks": [],
    "issues": [],
    "overall_status": "PASS"
  }
}
20. Deployment
Frontend
TODO: Add deployed frontend URL
Backend
TODO: Add deployed backend URL
Swagger
TODO: Add deployed Swagger URL
GitHub
https://github.com/shivanikushwaha131124/AI-Document-Intelligence

The deployment URLs will be added after final deployment.

21. Limitations
OCR accuracy depends on scan quality, image resolution, and document layout.
Highly complex invoice layouts may require additional extraction rules.
Poor-quality or distorted documents may produce incomplete extraction.
Unusual financial statement layouts may require additional parsing rules.
Missing information is not guessed and may result in null or NOT_APPLICABLE.
22. Production Improvements

For a production-scale implementation, the following improvements could be added:

Advanced document-layout models
Improved table extraction
Confidence calibration
Human-in-the-loop review
Asynchronous/background processing
Object storage for original files
Authentication and authorization
Rate limiting
Monitoring and alerting
Better OCR preprocessing
Database migrations
Expanded automated test coverage
Stronger security and access controls
23. AI Coding Assistant Usage

AI coding assistants were used during development for:

Project planning
Code generation assistance
Debugging
Error analysis
Test creation assistance
Documentation drafting
Reviewing implementation approaches

Generated code was reviewed, tested, and integrated into the project.

The document processing pipeline itself uses OCR, structured extraction, and deterministic financial validation implemented in the application. No unsupported LLM capability is claimed.

24. Security
Secrets are stored using environment variables.
.env is excluded from version control.
.env.example contains placeholders only.
Database credentials are not committed to GitHub.
No API keys or passwords are included in the repository.
25. Conclusion

AI Document Intelligence provides an end-to-end platform for:

Extract
   ↓
Validate
   ↓
Persist
   ↓
Visualize
   ↓
Access through APIs

It combines OCR, structured document extraction, financial validation, REST APIs, persistent PostgreSQL storage, and a web dashboard into a deployable document intelligence solution.