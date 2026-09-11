import io
import shutil

import fitz
import pytesseract
from PIL import Image


MAX_PAGES = 3

TESSERACT_PATH = shutil.which("tesseract")

if TESSERACT_PATH:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
else:
    pytesseract.pytesseract.tesseract_cmd = (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )


def _ocr_image(image: Image.Image) -> dict:
    """
    Run OCR while preserving word-level coordinates.
    Coordinates help reconstruct tables and comparative columns.
    """

    data = pytesseract.image_to_data(
        image,
        output_type=pytesseract.Output.DICT,
        config="--psm 4",
    )

    words = []

    for i, word in enumerate(data["text"]):
        word = word.strip()

        if not word:
            continue

        try:
            confidence = float(data["conf"][i])
        except (ValueError, TypeError):
            confidence = -1

        words.append(
            {
                "text": word,
                "left": int(data["left"][i]),
                "top": int(data["top"][i]),
                "width": int(data["width"][i]),
                "height": int(data["height"][i]),
                "confidence": confidence,
                "block_num": int(data["block_num"][i]),
                "par_num": int(data["par_num"][i]),
                "line_num": int(data["line_num"][i]),
            }
        )

    # Reconstruct readable lines.
    grouped = {}

    for word in words:
        key = (
            word["block_num"],
            word["par_num"],
            word["line_num"],
        )

        grouped.setdefault(key, []).append(word)

    lines = []

    for line_words in grouped.values():

        line_words.sort(key=lambda item: item["left"])

        text = " ".join(
            item["text"]
            for item in line_words
        ).strip()

        if not text:
            continue

        lines.append(
            {
                "text": text,
                "words": line_words,
            }
        )

    lines.sort(
        key=lambda item: (
            min(
                word["top"]
                for word in item["words"]
            ),
            min(
                word["left"]
                for word in item["words"]
            ),
        )
    )

    combined_text = "\n".join(
        line["text"]
        for line in lines
    )

    return {
        "text": combined_text,
        "lines": lines,
        "words": words,
        "is_readable": bool(
            combined_text.strip()
        ),
    }


def _render_pdf_page(page: fitz.Page) -> Image.Image:
    """
    Render PDF page at high resolution for OCR.
    """

    pixmap = page.get_pixmap(
        matrix=fitz.Matrix(2.5, 2.5),
        alpha=False,
    )

    return Image.open(
        io.BytesIO(
            pixmap.tobytes("png")
        )
    )


def extract_text_from_pdf(
    file_bytes: bytes,
) -> dict:

    document = None

    try:
        document = fitz.open(
            stream=file_bytes,
            filetype="pdf",
        )

        page_count = len(document)

        if page_count == 0:
            return {
                "text": "",
                "pages": [],
                "page_count": 0,
                "is_readable": False,
                "error": "PDF contains no pages",
            }

        if page_count > MAX_PAGES:
            return {
                "text": "",
                "pages": [],
                "page_count": page_count,
                "is_readable": False,
                "error": "Document exceeds maximum 3 pages",
            }

        pages = []

        for page_number, page in enumerate(
            document,
            start=1,
        ):

            native_text = page.get_text(
                "text"
            ).strip()

            # Native PDF text is useful when available.
            # OCR is still used when native extraction is empty.
            if native_text:
                ocr_data = {
                    "text": native_text,
                    "lines": [
                        {
                            "text": line.strip(),
                            "words": [],
                        }
                        for line in native_text.splitlines()
                        if line.strip()
                    ],
                    "words": [],
                    "is_readable": True,
                }

                ocr_used = False

            else:
                image = _render_pdf_page(page)

                ocr_data = _ocr_image(
                    image
                )

                ocr_used = True

            pages.append(
                {
                    "page_number": page_number,
                    "text": ocr_data["text"],
                    "lines": ocr_data["lines"],
                    "words": ocr_data["words"],
                    "is_readable": ocr_data[
                        "is_readable"
                    ],
                    "ocr_used": ocr_used,
                }
            )

        combined_text = "\n".join(
            page["text"]
            for page in pages
            if page["text"]
        )

        return {
            "text": combined_text,
            "pages": pages,
            "page_count": page_count,
            "is_readable": bool(
                combined_text.strip()
            ),
            "ocr_used": any(
                page["ocr_used"]
                for page in pages
            ),
        }

    except Exception as exc:

        return {
            "text": "",
            "pages": [],
            "page_count": None,
            "is_readable": False,
            "error": "Unable to read PDF",
            "internal_error": str(exc),
        }

    finally:

        if document is not None:
            document.close()


def extract_text_from_image(
    file_bytes: bytes,
) -> dict:

    try:

        image = Image.open(
            io.BytesIO(file_bytes)
        )

        image.verify()

        image = Image.open(
            io.BytesIO(file_bytes)
        )

    except Exception:

        return {
            "text": "",
            "pages": [],
            "page_count": 1,
            "is_readable": False,
            "error": "Invalid or corrupted image file",
        }

    ocr_data = _ocr_image(
        image
    )

    return {
        "text": ocr_data["text"],
        "pages": [
            {
                "page_number": 1,
                "text": ocr_data["text"],
                "lines": ocr_data["lines"],
                "words": ocr_data["words"],
                "is_readable": ocr_data[
                    "is_readable"
                ],
                "ocr_used": True,
            }
        ],
        "page_count": 1,
        "is_readable": ocr_data[
            "is_readable"
        ],
        "ocr_used": True,
    }