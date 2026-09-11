import re
from typing import Any


# ============================================================
# REGEX
# ============================================================

YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

# Financial values normally contain comma grouping and/or
# decimal values. This intentionally ignores small schedule
# numbers such as 13, 14, 15, 16, 18.
FINANCIAL_NUMBER_RE = re.compile(
    r"""
    (?<![A-Za-z])
    \(?\s*
    [$₹€£]?\s*
    (?:
        \d{1,3}(?:,\d{3})+(?:\.\d+)?
        |
        \d+\.\d+
    )
    \s*\)?
    """,
    re.VERBOSE,
)

DATE_RE = re.compile(
    r"""
    \b
    (?:
        \d{1,2}[-/]\d{1,2}[-/]\d{2,4}
        |
        \d{1,2}[-/][A-Za-z]{3,9}[-/]\d{2,4}
        |
        [A-Za-z]{3,9}\s+\d{1,2}(?:st|nd|rd|th)?[,\s]+\d{4}
        |
        \d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}
    )
    \b
    """,
    re.VERBOSE | re.IGNORECASE,
)


# ============================================================
# BASIC HELPERS
# ============================================================

def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _normalise_label(text: str) -> str:
    """
    Converts OCR label into a comparable lowercase label.
    """

    text = text or ""

    text = text.lower()

    # Remove common OCR punctuation.
    text = text.replace(":", " ")
    text = text.replace(",", " ")
    text = text.replace(".", " ")
    text = text.replace("'", "")
    text = text.replace('"', "")

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def _to_number(value: str | int | float | None) -> float | None:

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()

    if not text:
        return None

    if text in {"-", "—", "–", ".", ".."}:
        return None

    negative = (
        text.startswith("(")
        and text.endswith(")")
    )

    text = (
        text.replace(",", "")
        .replace("$", "")
        .replace("₹", "")
        .replace("€", "")
        .replace("£", "")
        .strip()
    )

    text = text.strip("() ")

    try:
        number = float(text)
    except (ValueError, TypeError):
        return None

    return -number if negative else number


def _extract_financial_numbers(text: str) -> list[float]:

    values = []

    for match in FINANCIAL_NUMBER_RE.finditer(text or ""):

        number = _to_number(match.group(0))

        if number is not None:
            values.append(number)

    return values


def _extract_years(text: str) -> list[str]:

    years = []

    for match in YEAR_RE.finditer(text or ""):

        year = match.group(0)

        if year not in years:
            years.append(year)

    return years


def _make_period_values(
    numbers: list[float],
    periods: list[str],
) -> dict[str, float | None]:

    result = {
        period: None
        for period in periods
    }

    if not periods:
        return result

    # First financial number = latest/current period.
    if len(numbers) >= 1:
        result[periods[0]] = numbers[0]

    # Second financial number = comparative period.
    if len(periods) >= 2 and len(numbers) >= 2:
        result[periods[1]] = numbers[1]

    return result


def _make_field(
    value: Any,
    source_text: str | None,
    page_number: int | None,
) -> dict[str, Any]:

    return {
        "value": value,
        "evidence": {
            "page_number": page_number,
            "source_text": source_text,
        },
    }


# ============================================================
# PERIOD DETECTION
# ============================================================

def _detect_statement_periods(
    pages: list[dict[str, Any]],
    all_text: str,
) -> list[str]:

    header_years: list[str] = []

    # First look at the first part of the document because
    # financial statement headers are normally near the top.
    header_text_parts = []

    for page in pages:

        page_text = page.get("text", "")

        lines = page_text.splitlines()

        header_text_parts.extend(
            lines[:25]
        )

    header_text = "\n".join(
        header_text_parts
    )

    # Prefer lines containing financial statement dates.
    candidate_lines = []

    for line in header_text.splitlines():

        low = line.lower()

        if any(
            keyword in low
            for keyword in [
                "year ended",
                "year ending",
                "as at",
                "as on",
                "march",
                "june",
                "september",
                "december",
                "31st",
                "30th",
            ]
        ):
            candidate_lines.append(line)

    for line in candidate_lines:

        for year in _extract_years(line):

            if year not in header_years:
                header_years.append(year)

    # If two explicit years exist, use them.
    if len(header_years) >= 2:
        return header_years[:2]

    # If one year exists, infer the comparative year ONLY
    # because these statements normally show a previous
    # comparative period.
    if len(header_years) == 1:

        latest = int(header_years[0])

        # Determine whether document actually contains
        # comparative financial numbers.
        financial_line_count = 0

        for line in all_text.splitlines():

            if len(
                _extract_financial_numbers(line)
            ) >= 2:
                financial_line_count += 1

        if financial_line_count >= 2:

            return [
                str(latest),
                str(latest - 1),
            ]

        return [str(latest)]

    # Fallback: look through document.
    all_years = _extract_years(
        all_text
    )

    if len(all_years) >= 2:
        return all_years[:2]

    if len(all_years) == 1:
        return all_years

    return []


# ============================================================
# STATEMENT ROW PARSING
# ============================================================

def _clean_statement_description(
    line: str,
) -> str:

    text = _clean_text(line)

    if not text:
        return ""

    # Remove financial numbers from the right side.
    matches = list(
        FINANCIAL_NUMBER_RE.finditer(text)
    )

    if matches:

        text = text[
            :matches[0].start()
        ].strip()

    # Remove schedule/reference numbers after the label.
    #
    # Example:
    # Interest earned 13
    # -> Interest earned
    #
    # Provisions and contingencies 18 (10)
    # -> Provisions and contingencies
    text = re.sub(
        r"\s+\d{1,2}\s*$",
        "",
        text,
    )

    text = re.sub(
        r"\s+\d{1,2}\s+\(\d{1,2}\)\s*$",
        "",
        text,
    )

    text = re.sub(
        r"\s+\(\d{1,2}\)\s*$",
        "",
        text,
    )

    text = re.sub(
        r"\s+[-–—]\s*$",
        "",
        text,
    )

    return text.strip(" :-")


def _parse_statement_rows(
    pages: list[dict[str, Any]],
    periods: list[str],
) -> list[dict[str, Any]]:

    rows = []

    current_section = None

    for page in pages:

        page_number = page.get(
            "page_number"
        )

        lines = page.get(
            "lines",
            []
        )

        # OCR service provides structured lines.
        if not lines:

            raw_text = page.get(
                "text",
                ""
            )

            lines = [
                {
                    "text": line,
                    "words": [],
                }
                for line in raw_text.splitlines()
                if line.strip()
            ]

        for line_data in lines:

            raw_line = _clean_text(
                line_data.get(
                    "text",
                    ""
                )
            )

            if not raw_line:
                continue

            low = raw_line.lower()

            # ----------------------------------------------
            # Section detection
            #
            # OCR frequently garbles the Roman-numeral
            # section markers (e.g. "I INCOME" becomes
            # "| INCOME", "II EXPENDITURE" becomes
            # "i! EXPENDITURE"). Relying on the numeral
            # prefix is unreliable. A section header line
            # is better identified by the fact that it
            # carries the keyword but NO financial figures
            # (data rows like "Other income 14 128,776,329"
            # always contain numbers). So numbers are
            # computed early and used as the header signal.
            # ----------------------------------------------

            header_numbers = _extract_financial_numbers(
                raw_line
            )

            if (
                "income" in low
                and not header_numbers
            ):
                current_section = "income"

            elif (
                "expenditure" in low
                and not header_numbers
            ):
                current_section = "expenditure"

            elif (
                "profit" in low
                and (
                    "profit" in low
                    and (
                        low.startswith("iii")
                        or low.startswith("ii")
                        or "profit" in low
                    )
                )
            ):
                current_section = "profit"

            elif "appropriation" in low:
                current_section = "appropriations"

            elif (
                "earnings per equity share" in low
                or "earnings per share" in low
            ):
                current_section = "eps"

            elif (
                "capital and liabilities" in low
                or "capital & liabilities" in low
            ):
                current_section = "liabilities"

            elif (
                low == "assets"
                or low.endswith(" assets")
                or "assets" == low.strip(". ")
            ):
                current_section = "assets"

            # ----------------------------------------------
            # Skip obvious non-data lines
            # ----------------------------------------------

            if any(
                bad in low
                for bad in [
                    "significant accounting policies",
                    "integrated annual report",
                    "as per our report",
                    "for and on behalf",
                    "partner",
                    "chief financial officer",
                    "company secretary",
                ]
            ):
                continue

            # ----------------------------------------------
            # Extract financial values.
            #
            # IMPORTANT:
            # This ignores schedule numbers such as 13,14,15.
            # ----------------------------------------------

            numbers = header_numbers

            description = _clean_statement_description(
                raw_line
            )

            # Don't create useless rows.
            if not description:
                continue

             # Header/date/unit rows should not be financial rows.
            #
            # NOTE: "as at" must only be checked as a LINE
            # PREFIX here. Cash-flow statements have genuine
            # data rows such as "Cash and cash equivalents
            # as at April 1st ... 155,385.73" where "as at"
            # appears mid-line - a plain substring check was
            # wrongly discarding those rows entirely.
            if (
                low.startswith("for the year ended")
                or low.startswith("as at")
                or "in crore" in low
                or "in crores" in low
                or low in {
                    "income",
                    "expenditure",
                    "profit",
                    "appropriations",
                    "assets",
                }
            ):
                continue

            # Footer page number.
            if (
                len(numbers) == 1
                and re.fullmatch(
                    r"\d{1,5}",
                    description,
                )
            ):
                continue

            # Rows with no financial numbers are still useful
            # as evidence, but avoid polluting the extracted
            # financial table with signatures/headings.
            if not numbers:
                if current_section in {
                    "income",
                    "expenditure",
                    "profit",
                    "appropriations",
                    "liabilities",
                    "assets",
                    "eps",
                }:
                    rows.append(
                        {
                            "description": description,
                            "values": {
                                period: None
                                for period in periods
                            },
                            "page_number": page_number,
                            "source_text": raw_line,
                            "section": current_section,
                        }
                    )
                continue

            values = _make_period_values(
                numbers,
                periods,
            )

            rows.append(
                {
                    "description": description,
                    "values": values,
                    "page_number": page_number,
                    "source_text": raw_line,
                    "section": current_section,
                }
            )

    return rows


# ============================================================
# ROW SEARCH
# ============================================================

def _find_row(
    rows: list[dict[str, Any]],
    aliases: list[str],
    section: str | None = None,
) -> dict[str, Any] | None:

    normalised_aliases = [
        _normalise_label(alias)
        for alias in aliases
    ]

    candidates = rows

    if section:
        section_rows = [
            row
            for row in rows
            if row.get("section") == section
        ]

        if section_rows:
            candidates = section_rows

    # --------------------------------------------------------
    # 1. EXACT MATCH FIRST
    # This prevents:
    # "minority interest"
    # from accidentally matching
    # "profit before minority interest"
    # --------------------------------------------------------

    for row in candidates:

        description = _normalise_label(
            row.get("description", "")
        )

        if description in normalised_aliases:
            return row

    # --------------------------------------------------------
    # 2. Then use controlled partial matching
    # --------------------------------------------------------

    for row in candidates:

        description = _normalise_label(
            row.get("description", "")
        )

        for alias in normalised_aliases:

            if (
                alias in description
                and len(description) <= len(alias) + 60
            ):
                return row

    return None
def _find_row_flexible(
    rows: list[dict[str, Any]],
    patterns: list[str],
    section: str | None = None,
) -> dict[str, Any] | None:
    """
    Cash-flow statement line wording varies a lot year to year
    (e.g. "Net cash flow (used in) / from operating activities"
    vs "Net cash from operating activities" vs "Net cash flows
    from operating activities"). Exact-alias matching is too
    brittle for this, so this matches on regex patterns against
    the row description instead.
    """

    candidates = rows

    if section:
        section_rows = [
            row
            for row in rows
            if row.get("section") == section
        ]

        if section_rows:
            candidates = section_rows

    for row in candidates:

        description = str(
            row.get("description", "")
        ).lower()

        for pattern in patterns:

            if re.search(pattern, description):
                return row

    return None


def _field_from_row_flexible(
    rows: list[dict[str, Any]],
    patterns: list[str],
    periods: list[str],
    section: str | None = None,
) -> dict[str, Any]:

    row = _find_row_flexible(
        rows,
        patterns,
        section,
    )

    if not row:

        return _make_field(
            {
                period: None
                for period in periods
            },
            None,
            None,
        )

    return _make_field(
        row.get(
            "values",
            {}
        ),
        row.get(
            "source_text"
        ),
        row.get(
            "page_number"
        ),
    )
def _field_from_row(
    rows: list[dict[str, Any]],
    aliases: list[str],
    periods: list[str],
    section: str | None = None,
) -> dict[str, Any]:

    row = _find_row(
        rows,
        aliases,
        section,
    )

    if not row:

        return _make_field(
            {
                period: None
                for period in periods
            },
            None,
            None,
        )

    return _make_field(
        row.get(
            "values",
            {}
        ),
        row.get(
            "source_text"
        ),
        row.get(
            "page_number"
        ),
    )


# ============================================================
# INVOICE EXTRACTION
# ============================================================

def _find_invoice_line(
    text: str,
    patterns: list[str],
) -> str | None:

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE,
        )

        if match:
            return match.group(1).strip()

    return None


def _extract_invoice(
    pages: list[dict[str, Any]],
) -> dict[str, Any]:

    all_lines = []

    for page in pages:

        page_number = page.get(
            "page_number"
        )

        lines = page.get(
            "lines",
            []
        )

        if not lines:

            lines = [
                {
                    "text": line,
                    "words": [],
                }
                for line in page.get(
                    "text",
                    ""
                ).splitlines()
                if line.strip()
            ]

        for line in lines:

            text = _clean_text(
                line.get(
                    "text",
                    ""
                )
            )

            if text:

                all_lines.append(
                    {
                        "text": text,
                        "page_number": page_number,
                        "words": line.get(
                            "words",
                            [],
                        ),
                    }
                )

    full_text = "\n".join(
        item["text"]
        for item in all_lines
    )

    low_text = full_text.lower()

    fields: dict[str, Any] = {}

    # --------------------------------------------------------
    # Currency
    # --------------------------------------------------------

    currency = None

    currency_patterns = [
        (r"\bCAD\b", "CAD"),
        (r"\bUSD\b", "USD"),
        (r"\bINR\b", "INR"),
        (r"\bGBP\b", "GBP"),
        (r"\bEUR\b", "EUR"),
        (r"\bC\$", "CAD"),
        (r"\bUS\$", "USD"),
        (r"₹", "INR"),
        (r"€", "EUR"),
        (r"£", "GBP"),
        (r"\$", "USD"),
    ]

    for pattern, value in currency_patterns:

        if re.search(
            pattern,
            full_text,
            re.IGNORECASE,
        ):
            currency = value
            break

    fields["currency"] = _make_field(
        currency,
        full_text if currency else None,
        1 if currency else None,
    )

    # --------------------------------------------------------
    # Invoice number
    # --------------------------------------------------------

    invoice_number = None
    invoice_evidence = None
    invoice_page = None

    invoice_patterns = [
        r"\binvoice\s*(?:number|no\.?|#)\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9./_-]*)",
        r"\binv\.?\s*(?:number|no\.?|#)\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9./_-]*)",
        r"\binvoice\s*[:\-]\s*([A-Za-z0-9][A-Za-z0-9./_-]*)",
    ]

    for item in all_lines:

        candidate = _find_invoice_line(
            item["text"],
            invoice_patterns,
        )

        if candidate:

            # Avoid emails being mistaken as invoice numbers.
            if "@" not in candidate:

                invoice_number = candidate
                invoice_evidence = item["text"]
                invoice_page = item["page_number"]
                break

    fields["invoice_number"] = _make_field(
        invoice_number,
        invoice_evidence,
        invoice_page,
    )

    # --------------------------------------------------------
    # Dates
    # --------------------------------------------------------

    invoice_date = None
    due_date = None

    invoice_date_evidence = None
    due_date_evidence = None

    invoice_date_page = None
    due_date_page = None

    for item in all_lines:

        line = item["text"]
        low = line.lower()

        dates = DATE_RE.findall(
            line
        )

        # DATE_RE uses a capturing group-free pattern,
        # so findall returns complete strings.
        if dates:

            date_value = dates[0]

            if (
                "due date" in low
                or "payment due" in low
            ):

                if due_date is None:
                    due_date = date_value
                    due_date_evidence = line
                    due_date_page = item[
                        "page_number"
                    ]

            elif (
                "invoice date" in low
                or "invoice issued" in low
            ):

                if invoice_date is None:
                    invoice_date = date_value
                    invoice_date_evidence = line
                    invoice_date_page = item[
                        "page_number"
                    ]

            elif invoice_date is None:

                invoice_date = date_value
                invoice_date_evidence = line
                invoice_date_page = item[
                    "page_number"
                ]

    fields["invoice_date"] = _make_field(
        invoice_date,
        invoice_date_evidence,
        invoice_date_page,
    )

    fields["due_date"] = _make_field(
        due_date,
        due_date_evidence,
        due_date_page,
    )

    # --------------------------------------------------------
    # Seller / Buyer
    # --------------------------------------------------------

    seller = None
    buyer = None

    seller_evidence = None
    buyer_evidence = None

    seller_page = None
    buyer_page = None

    for item in all_lines:

        line = item["text"]
        low = line.lower()

        if seller is None:

            seller_match = re.search(
                r"(?:seller|vendor|supplier|from)\s*[:\-]?\s*(.+)",
                line,
                re.IGNORECASE,
            )

            if seller_match:

                candidate = seller_match.group(1).strip()

                if candidate and len(candidate) < 200:

                    seller = candidate
                    seller_evidence = line
                    seller_page = item[
                        "page_number"
                    ]

        if buyer is None:

            buyer_match = re.search(
                r"(?:buyer|customer|client|bill\s*to|billed\s*to|ship\s*to|sold\s*to)\s*[:\-]?\s*(.+)",
                line,
                re.IGNORECASE,
            )

            if buyer_match:

                candidate = buyer_match.group(1).strip()

                if candidate and len(candidate) < 200:

                    buyer = candidate
                    buyer_evidence = line
                    buyer_page = item[
                        "page_number"
                    ]

    fields["seller"] = _make_field(
        seller,
        seller_evidence,
        seller_page,
    )

    fields["buyer"] = _make_field(
        buyer,
        buyer_evidence,
        buyer_page,
    )

    # --------------------------------------------------------
    # Generic labelled amount extractor
    # --------------------------------------------------------

    def find_amount(
        labels: list[str],
    ) -> tuple[
        float | None,
        str | None,
        int | None,
    ]:

        for item in all_lines:

            line = item["text"]

            low = line.lower()

            if any(
                label in low
                for label in labels
            ):

                numbers = _extract_financial_numbers(
                    line
                )

                if numbers:

                    return (
                        numbers[-1],
                        line,
                        item["page_number"],
                    )

        return None, None, None

    subtotal, subtotal_source, subtotal_page = find_amount(
        [
            "subtotal",
            "sub total",
            "net amount",
        ]
    )

    tax, tax_source, tax_page = find_amount(
        [
            "sales tax",
            "tax amount",
            "gst",
            "vat",
            "tax",
        ]
    )

    shipping, shipping_source, shipping_page = find_amount(
        [
            "shipping",
            "freight",
            "delivery",
            "s&h",
            "handling",
        ]
    )

    # --------------------------------------------------------
    # Total
    # --------------------------------------------------------

    total = None
    total_source = None
    total_page = None

    total_labels = [
        "amount due",
        "balance due",
        "grand total",
        "total due",
        "invoice total",
        "total amount",
        "total",
    ]

    for item in all_lines:

        line = item["text"]
        low = line.lower()

        if any(
            label in low
            for label in total_labels
        ):

            # Do not let subtotal become total.
            if "subtotal" in low:
                continue

            numbers = _extract_financial_numbers(
                line
            )

            if numbers:

                total = numbers[-1]
                total_source = line
                total_page = item[
                    "page_number"
                ]
                break

    # --------------------------------------------------------
    # Cash paid / change
    # --------------------------------------------------------

    cash_paid, cash_source, cash_page = find_amount(
        [
            "cash paid",
            "cash tendered",
            "amount tendered",
            "paid",
        ]
    )

    change, change_source, change_page = find_amount(
        [
            "change",
            "change due",
        ]
    )

    fields["subtotal"] = _make_field(
        subtotal,
        subtotal_source,
        subtotal_page,
    )

    fields["tax"] = _make_field(
        tax,
        tax_source,
        tax_page,
    )

    fields["shipping"] = _make_field(
        shipping,
        shipping_source,
        shipping_page,
    )

    fields["total"] = _make_field(
        total,
        total_source,
        total_page,
    )

    fields["cash_paid"] = _make_field(
        cash_paid,
        cash_source,
        cash_page,
    )

    fields["change"] = _make_field(
        change,
        change_source,
        change_page,
    )

    # --------------------------------------------------------
    # Tax included detection
    # --------------------------------------------------------

    tax_included = bool(
        re.search(
            r"tax\s+included|gst\s+included|vat\s+included|inclusive\s+of\s+tax",
            low_text,
            re.IGNORECASE,
        )
    )

    fields["tax_included"] = _make_field(
        tax_included,
        full_text if tax_included else None,
        1 if tax_included else None,
    )

    # --------------------------------------------------------
    # Period
    # --------------------------------------------------------

    years = _extract_years(
        full_text
    )

    periods = years[:2]

    if not periods:

        periods = ["invoice"]

    # --------------------------------------------------------
    # Invoice tables
    #
    # This intentionally does NOT treat every number in an
    # invoice as a line item. It looks for a table header.
    # --------------------------------------------------------

    table_rows = []

    header_index = None

    for index, item in enumerate(all_lines):

        low = item["text"].lower()

        has_description = (
            "description" in low
            or "item" in low
            or "product" in low
        )

        has_quantity = (
            "quantity" in low
            or re.search(
                r"\bqty\b",
                low,
            )
        )

        has_price = (
            "price" in low
            or "rate" in low
            or "unit" in low
        )

        if (
            has_description
            and has_quantity
            and has_price
        ):

            header_index = index
            break

    if header_index is not None:

        for item in all_lines[
            header_index + 1:
        ]:

            line = item["text"]
            low = line.lower()

            if any(
                stop in low
                for stop in [
                    "subtotal",
                    "sales tax",
                    "tax total",
                    "grand total",
                    "amount due",
                    "balance due",
                    "total due",
                ]
            ):
                break

            numbers = _extract_financial_numbers(
                line
            )

            if not numbers:
                continue

            # Best-effort line parsing:
            # rightmost values are normally price/amount.
            row = {
                "description": line,
                "quantity": None,
                "unit_price": None,
                "line_total": None,
                "page_number": item[
                    "page_number"
                ],
                "source_text": line,
            }

            if len(numbers) >= 3:

                row["quantity"] = numbers[-3]
                row["unit_price"] = numbers[-2]
                row["line_total"] = numbers[-1]

            elif len(numbers) == 2:

                row["unit_price"] = numbers[-2]
                row["line_total"] = numbers[-1]

            table_rows.append(row)

    return {
        "fields": fields,
        "tables": [
            {
                "name": "invoice_line_items",
                "rows": table_rows,
            }
        ],
        "periods": periods,
        "document_type": "invoice",
    }


# ============================================================
# PROFIT & LOSS EXTRACTION
# ============================================================

def _extract_profit_and_loss(
    pages: list[dict[str, Any]],
) -> dict[str, Any]:

    all_text = "\n".join(
        page.get("text", "")
        for page in pages
    )

    periods = _detect_statement_periods(
        pages,
        all_text,
    )

    rows = _parse_statement_rows(
        pages,
        periods,
    )

    fields = {}

    # ========================================================
    # INCOME
    # ========================================================

    fields["interest_earned"] = _field_from_row(
        rows,
        [
            "interest earned",
        ],
        periods,
        "income",
    )

    fields["other_income"] = _field_from_row(
        rows,
        [
            "other income",
        ],
        periods,
        "income",
    )

    fields["total_income"] = _field_from_row(
        rows,
        [
            "total",
        ],
        periods,
        "income",
    )

    # ========================================================
    # EXPENDITURE
    # ========================================================

    fields["interest_expended"] = _field_from_row(
        rows,
        [
            "interest expended",
            "interest expenditure",
        ],
        periods,
        "expenditure",
    )

    fields["operating_expenses"] = _field_from_row(
        rows,
        [
            "operating expenses",
            "operating expense",
        ],
        periods,
        "expenditure",
    )

    fields["provisions_and_contingencies"] = _field_from_row(
        rows,
        [
            "provisions and contingencies",
            "provisions & contingencies",
        ],
        periods,
        "expenditure",
    )

    fields["total_expenditure"] = _field_from_row(
        rows,
        [
            "total",
        ],
        periods,
        "expenditure",
    )

    # ========================================================
    # PROFIT
    # ========================================================

    fields[
        "consolidated_net_profit_before_minority"
    ] = _field_from_row(
        rows,
        [
            "consolidated net profit for the year before minority interest",
            "consolidated net profit before minority interest",
            "net profit before minority interest",
        ],
        periods,
        "profit",
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Minority Interest MUST come from:
    #
    # Less : Minority Interest
    #
    # NOT from:
    # Profit before Minority Interest
    # --------------------------------------------------------

    fields["minority_interest"] = _field_from_row(
        rows,
        [
            "less minority interest",
        ],
        periods,
        "profit",
    )

    fields[
        "consolidated_net_profit_attributable"
    ] = _field_from_row(
        rows,
        [
            "consolidated net profit for the year attributable to the group",
            "consolidated net profit attributable to the group",
            "net profit attributable to the group",
        ],
        periods,
        "profit",
    )

    # ========================================================
    # APPROPRIATIONS
    # ========================================================

    appropriation_aliases = {
        "brought_forward": [
            "brought forward consolidated profit attributable to the group",
            "brought forward profit",
        ],

        "appropriations_total": [
            "total",
        ],

        "balance_carried_over": [
            "balance carried over to consolidated balance sheet",
            "balance carried over",
        ],

        "interim_dividend_paid": [
            "interim dividend paid",
        ],

        "dividend_previous_year": [
            "dividend pertaining to previous year paid during the year",
        ],

        "transfer_to_other_reserves": [
            "transfer to other reserves",
        ],

        "transfer_to_capital_reserve": [
            "transfer to capital reserve",
        ],

        "transfer_to_general_reserve": [
            "transfer to general reserve",
        ],

        "transfer_to_special_reserve": [
            "transfer to special reserve",
        ],

        "transfer_to_minority_interest": [
            "transfer to / from minority interest",
            "transfer to/from minority interest",
            "transfer to minority interest",
        ],

        "transfer_to_statutory_reserve": [
            "transfer to statutory reserve",
        ],
    }

    appropriation_output = {}

    # --------------------------------------------------------
    # IMPORTANT:
    # Appropriation rows are not always marked by OCR as
    # section="appropriations".
    #
    # Therefore search WITHOUT forcing the section.
    # --------------------------------------------------------

    for field_name, aliases in appropriation_aliases.items():

        row = _find_row(
            rows,
            aliases,
            None,
        )

        # For "total", there are multiple Total rows.
        # We specifically want the Total inside appropriations.
        if (
            field_name == "appropriations_total"
        ):
            appropriation_rows = [
                r
                for r in rows
                if r.get("section") == "appropriations"
                and _normalise_label(
                    r.get("description", "")
                ) == "total"
            ]

            if appropriation_rows:
                row = appropriation_rows[-1]

        if row:

            appropriation_output[field_name] = (
                row.get("values", {})
            )

        else:

            appropriation_output[field_name] = {
                period: None
                for period in periods
            }

    fields["appropriations"] = _make_field(
        appropriation_output,
        "Appropriations extracted from statement rows",
        None,
    )

    # ========================================================
    # EPS
    # ========================================================

    fields["eps_basic"] = _field_from_row(
        rows,
        ["basic"],
        periods,
        "eps",
    )

    fields["eps_diluted"] = _field_from_row(
        rows,
        ["diluted"],
        periods,
        "eps",
    )

    return {
        "fields": fields,
        "tables": [
            {
                "name": "statement_rows",
                "rows": rows,
            }
        ],
        "periods": periods,
        "document_type": "profit_and_loss",
    }

# ============================================================
# BALANCE SHEET EXTRACTION
# ============================================================

def _extract_balance_sheet(
    pages: list[dict[str, Any]],
) -> dict[str, Any]:

    all_text = "\n".join(
        page.get("text", "")
        for page in pages
    )

    periods = _detect_statement_periods(
        pages,
        all_text,
    )

    rows = _parse_statement_rows(
        pages,
        periods,
    )

    fields = {}

    fields["share_capital"] = _field_from_row(
        rows,
        [
            "capital",
            "share capital",
        ],
        periods,
        "liabilities",
    )

    fields["employees_stock_options"] = _field_from_row(
        rows,
        [
            "employees stock options",
            "employees stock options / units outstanding",
            "employees stock options units outstanding",
        ],
        periods,
        "liabilities",
    )

    fields["reserves_and_surplus"] = _field_from_row(
        rows,
        [
            "reserves and surplus",
            "reserves & surplus",
        ],
        periods,
        "liabilities",
    )

    fields["minority_interest"] = _field_from_row(
        rows,
        [
            "minority interest",
        ],
        periods,
        "liabilities",
    )

    fields["deposits"] = _field_from_row(
        rows,
        ["deposits"],
        periods,
        "liabilities",
    )

    fields["borrowings"] = _field_from_row(
        rows,
        ["borrowings"],
        periods,
        "liabilities",
    )

    fields["other_liabilities"] = _field_from_row(
        rows,
        [
            "other liabilities and provisions",
            "other liabilities / provisions",
            "other liabilities",
            "other liabilities and provisions",
        ],
        periods,
        "liabilities",
    )

    fields["policyholders_funds"] = _field_from_row(
        rows,
        [
            "policyholders funds",
            "policyholders' funds",
        ],
        periods,
        "liabilities",
    )

    fields["total_capital_and_liabilities"] = _field_from_row(
        rows,
        [
            "total capital and liabilities",
            "total capital & liabilities",
            "total",
        ],
        periods,
        "liabilities",
    )

    # --------------------------------------------------------
    # Assets
    # --------------------------------------------------------
    fields["cash_and_balances_with_banks"] = _field_from_row(
        rows,
        [
            "cash and balances with rbi",
            "cash and balances with bank",
            "cash and balances with banks",
            "cash and balances with reserve bank of india",
        ],
        periods,
        "assets",
    )

    fields["balances_with_banks"] = _field_from_row(
        rows,
        [
            "balances with banks",
            "balances with banks / call / short notice",
            "balances with banks call short notice",
            "balances with banks and money at call and short notice",
        ],
        periods,
        "assets",
    )

    fields["investments"] = _field_from_row(
        rows,
        ["investments"],
        periods,
        "assets",
    )

    fields["advances"] = _field_from_row(
        rows,
        ["advances"],
        periods,
        "assets",
    )

    fields["fixed_assets"] = _field_from_row(
        rows,
        [
            "fixed assets",
        ],
        periods,
        "assets",
    )

    fields["other_assets"] = _field_from_row(
        rows,
        ["other assets"],
        periods,
        "assets",
    )

    fields["goodwill"] = _field_from_row(
        rows,
        ["goodwill"],
        periods,
        "assets",
    )

    fields["total_assets"] = _field_from_row(
        rows,
        [
            "total assets",
            "total",
        ],
        periods,
        "assets",
    )

    fields["contingent_liabilities"] = _field_from_row(
        rows,
        ["contingent liabilities"],
        periods,
        None,
    )

    fields["bills_for_collection"] = _field_from_row(
        rows,
        ["bills for collection"],
        periods,
        None,
    )

    return {
        "fields": fields,
        "tables": [
            {
                "name": "statement_rows",
                "rows": rows,
            }
        ],
        "periods": periods,
        "document_type": "balance_sheet",
    }


# ============================================================
# CASH FLOW EXTRACTION
# ============================================================

def _extract_cash_flow(
    pages: list[dict[str, Any]],
) -> dict[str, Any]:

    all_text = "\n".join(
        page.get("text", "")
        for page in pages
    )

    periods = _detect_statement_periods(
        pages,
        all_text,
    )

    rows = _parse_statement_rows(
        pages,
        periods,
    )

    fields = {}

    fields["operating_cash_flow"] = _field_from_row_flexible(
        rows,
        [
            r"net cash.*operating activit",
        ],
        periods,
        None,
    )

    fields["investing_cash_flow"] = _field_from_row_flexible(
        rows,
        [
            r"net cash.*investing activit",
        ],
        periods,
        None,
    )

    fields["financing_cash_flow"] = _field_from_row_flexible(
        rows,
        [
            r"net cash.*financing activit",
        ],
        periods,
        None,
    )

    fields["fx_translation"] = _field_from_row_flexible(
        rows,
        [
            r"fluctuation.*translation",
            r"translation.*fluctuation",
            r"exchange.*translation",
            r"fx translation",
        ],
        periods,
        None,
    )

    fields["net_increase_in_cash"] = _field_from_row_flexible(
        rows,
        [
            r"increase.*cash and cash equivalents",
            r"decrease.*cash and cash equivalents",
        ],
        periods,
        None,
    )

    fields["opening_cash"] = _field_from_row_flexible(
        rows,
        [
            r"cash and cash equivalents as at april",
            r"cash and cash equivalents at april",
            r"opening cash and cash equivalents",
        ],
        periods,
        None,
    )

    fields["closing_cash"] = _field_from_row_flexible(
        rows,
        [
            r"cash and cash equivalents as at march",
            r"cash and cash equivalents at march",
            r"cash and cash equivalents as at the year end",
            r"closing cash and cash equivalents",
        ],
        periods,
        None,
    )

    fields["amalgamation_adjustment"] = _field_from_row(
        rows,
        [
            "cash and cash equivalents on amalgamation",
            "cash acquired on amalgamation",
            "cash acquired on amalgamation / other applicable adjustments",
        ],
        periods,
        None,
    )

    return {
        "fields": fields,
        "tables": [
            {
                "name": "statement_rows",
                "rows": rows,
            }
        ],
        "periods": periods,
        "document_type": "cash_flow_statement",
    }


# ============================================================
# PUBLIC ENTRY POINT
# ============================================================

def extract_basic_fields(
    text: str,
    document_type: str,
    pages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:

    pages = pages or [
        {
            "page_number": 1,
            "text": text,
            "lines": [
                {
                    "text": line,
                    "words": [],
                }
                for line in (text or "").splitlines()
                if line.strip()
            ],
        }
    ]

    if document_type == "invoice":

        result = _extract_invoice(
            pages
        )

    elif document_type == "balance_sheet":

        result = _extract_balance_sheet(
            pages
        )

    elif document_type == "profit_and_loss":

        result = _extract_profit_and_loss(
            pages
        )

    elif document_type == "cash_flow_statement":

        result = _extract_cash_flow(
            pages
        )

    else:

        result = {
            "fields": {},
            "tables": [],
            "periods": [],
            "document_type": document_type,
        }

    return result