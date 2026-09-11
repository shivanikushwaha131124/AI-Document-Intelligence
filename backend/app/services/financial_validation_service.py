from typing import Any


# ============================================================
# NUMBER HELPERS
# ============================================================

def _number(value: Any) -> float | None:

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, dict):
        return None

    text = str(value).strip()

    if text in {"", "-", "—", "–", "."}:
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
        result = float(text)
    except ValueError:
        return None

    return -result if negative else result


def _period_value(
    fields: dict[str, Any],
    name: str,
    period: str,
) -> float | None:

    field = fields.get(name)

    if field is None:
        return None

    # Field format:
    # {"value": {"2017": 123, "2016": 456}}
    if isinstance(field, dict) and "value" in field:

        value = field.get("value")

        if isinstance(value, dict):
            return _number(
                value.get(period)
            )

        return _number(value)

    # Field format:
    # {"2017": 123, "2016": 456}
    if isinstance(field, dict):

        return _number(
            field.get(period)
        )

    # Simple numeric value
    return _number(field)


def _tolerance(
    reported: float,
) -> float:

    # 0.1% tolerance, minimum 0.01
    return max(
        0.01,
        abs(reported) * 0.001,
    )


def _status(
    calculated: float,
    reported: float,
) -> str:

    variance = calculated - reported

    if abs(variance) <= _tolerance(reported):
        return "PASS"

    return "FAIL"


def _check(
    name: str,
    formula: str,
    period: str,
    operands: dict[str, Any],
    calculated: float | None,
    reported: float | None,
) -> dict[str, Any]:

    if calculated is None or reported is None:

        return {
            "name": name,
            "reason": "Required fields are missing.",
            "status": "NOT_APPLICABLE",
            "formula": formula,
            "operands": {
                "period": period,
                **operands,
            },
            "calculated_value": None,
            "reported_value": reported,
            "variance": None,
        }

    variance = calculated - reported

    return {
        "name": name,
        "status": _status(
            calculated,
            reported,
        ),
        "formula": formula,
        "operands": {
            "period": period,
            **operands,
        },
        "calculated_value": calculated,
        "reported_value": reported,
        "variance": variance,
    }


# ============================================================
# INVOICE
# ============================================================

def _validate_invoice(
    fields: dict[str, Any],
    tables: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    checks = []

    # --------------------------------------------------------
    # Line items
    # --------------------------------------------------------

    invoice_items = []

    for table in tables:

        if table.get("name") == "invoice_line_items":

            invoice_items.extend(
                table.get("rows", [])
            )

    for index, item in enumerate(
        invoice_items,
        start=1,
    ):

        quantity = _number(
            item.get("quantity")
        )

        unit_price = _number(
            item.get("unit_price")
        )

        line_total = _number(
            item.get("line_total")
        )

        calculated = None

        if (
            quantity is not None
            and unit_price is not None
        ):
            calculated = quantity * unit_price

        checks.append(
            _check(
                name=f"Invoice line item {index} reconciliation",
                formula="Quantity × Unit Price ≈ Line Total",
                period="invoice",
                operands={
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "line_total": line_total,
                },
                calculated=calculated,
                reported=line_total,
            )
        )

    # --------------------------------------------------------
    # Subtotal + tax + shipping = total
    # --------------------------------------------------------

    subtotal = _period_value(
        fields,
        "subtotal",
        "invoice",
    )

    tax = _period_value(
        fields,
        "tax",
        "invoice",
    )

    shipping = _period_value(
        fields,
        "shipping",
        "invoice",
    )

    total = _period_value(
        fields,
        "total",
        "invoice",
    )

    calculated = None

    if subtotal is not None:

        calculated = subtotal

        if tax is not None:
            calculated += tax

        if shipping is not None:
            calculated += shipping

    checks.append(
        _check(
            name="Invoice total reconciliation",
            formula="Subtotal + Tax + Shipping ≈ Total",
            period="invoice",
            operands={
                "subtotal": subtotal,
                "tax": tax,
                "shipping": shipping,
            },
            calculated=calculated,
            reported=total,
        )
    )

    # --------------------------------------------------------
    # Sum line totals vs subtotal
    # --------------------------------------------------------

    line_totals = [
        _number(
            item.get("line_total")
        )
        for item in invoice_items
    ]

    line_totals = [
        value
        for value in line_totals
        if value is not None
    ]

    calculated_lines = (
        sum(line_totals)
        if line_totals
        else None
    )

    checks.append(
        _check(
            name="Invoice line totals reconciliation",
            formula="Sum of Line Totals ≈ Subtotal",
            period="invoice",
            operands={
                "line_item_count": len(line_totals),
            },
            calculated=calculated_lines,
            reported=subtotal,
        )
    )

    # --------------------------------------------------------
    # Cash paid - total = change
    # --------------------------------------------------------

    cash_paid = _period_value(
        fields,
        "cash_paid",
        "invoice",
    )

    change = _period_value(
        fields,
        "change",
        "invoice",
    )

    calculated_change = None

    if (
        cash_paid is not None
        and total is not None
    ):
        calculated_change = cash_paid - total

    checks.append(
        _check(
            name="Invoice cash/change reconciliation",
            formula="Cash Paid - Total ≈ Change",
            period="invoice",
            operands={
                "cash_paid": cash_paid,
                "total": total,
            },
            calculated=calculated_change,
            reported=change,
        )
    )

    return checks


# ============================================================
# PROFIT & LOSS
# ============================================================
def _validate_profit_and_loss(
    fields: dict[str, Any],
    periods: list[str],
    tables: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:

    checks = []

    tables = tables or []

    # ========================================================
    # TABLE FALLBACK
    # If a value is missing from fields, recover it from
    # statement_rows. Never invent a value.
    # ========================================================

    statement_rows = []

    for table in tables:
        if table.get("name") == "statement_rows":
            statement_rows.extend(
                table.get("rows", [])
            )

    def row_value(
        description_keywords: list[str],
        period: str,
        section: str | None = None,
    ) -> float | None:

        for row in statement_rows:

            description = str(
                row.get("description", "")
            ).lower()

            if section is not None:
                row_section = row.get("section")
                if row_section != section:
                    continue

            matched = all(
                keyword.lower() in description
                for keyword in description_keywords
            )

            if not matched:
                continue

            values = row.get("values", {})

            if isinstance(values, dict):
                value = values.get(period)

                number = _number(value)

                if number is not None:
                    return number

        return None

    def field_or_table(
        field_name: str,
        period: str,
        keywords: list[str],
        section: str | None = None,
    ) -> float | None:

        # First use the structured field.
        value = _period_value(
            fields,
            field_name,
            period,
        )

        if value is not None:
            return value

        # If field is missing, use the actual statement row.
        return row_value(
            keywords,
            period,
            section,
        )

    # ========================================================
    # SPECIAL FALLBACK FOR "TOTAL"
    #
    # P&L documents can contain several rows called "Total".
    # We identify the correct one using its position between
    # INCOME / EXPENDITURE / PROFIT sections.
    # ========================================================

    def find_total_for_section(
        period: str,
        target: str,
    ) -> float | None:

        current_section = None

        for row in statement_rows:

            description = str(
                row.get("description", "")
            ).lower()

            section = row.get("section")

            if section:
                current_section = section

            source_text = str(
                row.get("source_text", "")
            ).lower()

            # Detect income section.
            if (
                "income" in description
                or "income" in source_text
            ) and "other income" not in description:

                if "expenditure" not in description:
                    current_section = "income"

            # Detect expenditure section.
            if "expenditure" in description:
                current_section = "expenditure"

            # Detect profit section.
            if (
                "profit" in description
                or "profit" in source_text
            ):
                if "appropriation" not in description:
                    current_section = "profit"

            if description.strip() != "total":
                continue

            values = row.get("values", {})

            if not isinstance(values, dict):
                continue

            value = _number(
                values.get(period)
            )

            if value is None:
                continue

            if target == "income" and current_section == "income":
                return value

            if (
                target == "expenditure"
                and current_section == "expenditure"
            ):
                return value

            if target == "appropriations":
                # Appropriation total can have section
                # "appropriations" or appear after that heading.
                if (
                    section == "appropriations"
                    or current_section == "appropriations"
                ):
                    return value

        return None

    # ========================================================
    # PROCESS EVERY COMPARATIVE PERIOD
    # ========================================================

    for period in periods:

        # ----------------------------------------------------
        # 1. TOTAL INCOME
        # ----------------------------------------------------

        interest_earned = field_or_table(
            "interest_earned",
            period,
            ["interest earned"],
        )

        other_income = field_or_table(
            "other_income",
            period,
            ["other income"],
        )

        total_income = _period_value(
            fields,
            "total_income",
            period,
        )

        if total_income is None:
            total_income = find_total_for_section(
                period,
                "income",
            )

        calculated_income = None

        if (
            interest_earned is not None
            and other_income is not None
        ):
            calculated_income = (
                interest_earned
                + other_income
            )

        checks.append(
            _check(
                name=(
                    f"P&L total income "
                    f"reconciliation - {period}"
                ),
                formula=(
                    "Interest Earned + Other Income "
                    "≈ Total Income"
                ),
                period=period,
                operands={
                    "interest_earned": interest_earned,
                    "other_income": other_income,
                },
                calculated=calculated_income,
                reported=total_income,
            )
        )

        # ----------------------------------------------------
        # 2. TOTAL EXPENDITURE
        # ----------------------------------------------------

        interest_expended = field_or_table(
            "interest_expended",
            period,
            ["interest expended"],
        )

        operating_expenses = field_or_table(
            "operating_expenses",
            period,
            ["operating expenses"],
        )

        provisions = field_or_table(
            "provisions_and_contingencies",
            period,
            ["provisions", "contingencies"],
        )

        total_expenditure = _period_value(
            fields,
            "total_expenditure",
            period,
        )

        if total_expenditure is None:
            total_expenditure = find_total_for_section(
                period,
                "expenditure",
            )

        calculated_expenditure = None

        if all(
            value is not None
            for value in [
                interest_expended,
                operating_expenses,
                provisions,
            ]
        ):

            calculated_expenditure = (
                interest_expended
                + operating_expenses
                + provisions
            )

        checks.append(
            _check(
                name=(
                    f"P&L total expenditure "
                    f"reconciliation - {period}"
                ),
                formula=(
                    "Interest Expended + Operating Expenses "
                    "+ Provisions & Contingencies "
                    "≈ Total Expenditure"
                ),
                period=period,
                operands={
                    "interest_expended": interest_expended,
                    "operating_expenses": operating_expenses,
                    "provisions_and_contingencies": provisions,
                },
                calculated=calculated_expenditure,
                reported=total_expenditure,
            )
        )

        # ----------------------------------------------------
        # 3. PROFIT BEFORE MINORITY
        # ----------------------------------------------------

        profit_before_minority = _period_value(
            fields,
            "consolidated_net_profit_before_minority",
            period,
        )

        # Older statements use:
        # "Net profit for the year"
        if profit_before_minority is None:

            profit_before_minority = row_value(
                ["net profit for the year"],
                period,
                "profit",
            )

        # Newer statements use:
        # "Consolidated Net Profit ... before minorities"
        if profit_before_minority is None:

            profit_before_minority = row_value(
                ["consolidated net profit", "before"],
                period,
            )

        calculated_profit = None

        if (
            total_income is not None
            and total_expenditure is not None
        ):

            calculated_profit = (
                total_income
                - total_expenditure
            )

        checks.append(
            _check(
                name=(
                    f"P&L net profit before "
                    f"minority reconciliation - {period}"
                ),
                formula=(
                    "Total Income - Total Expenditure "
                    "≈ Consolidated Net Profit "
                    "before Minority Interest"
                ),
                period=period,
                operands={
                    "total_income": total_income,
                    "total_expenditure": total_expenditure,
                },
                calculated=calculated_profit,
                reported=profit_before_minority,
            )
        )

        # ----------------------------------------------------
        # 4. ATTRIBUTABLE PROFIT
        # ----------------------------------------------------

        minority_interest = field_or_table(
            "minority_interest",
            period,
            ["minority interest"],
        )

        attributable_profit = _period_value(
            fields,
            "consolidated_net_profit_attributable",
            period,
        )

        if attributable_profit is None:

            attributable_profit = row_value(
                [
                    "consolidated profit",
                    "attributable",
                ],
                period,
            )

        # Older statements may contain:
        # "Consolidated profit for the year
        # attributable to the Group"

        calculated_attributable = None

        if (
            profit_before_minority is not None
            and minority_interest is not None
        ):

            calculated_attributable = (
                profit_before_minority
                - minority_interest
            )

            # Some older statements explicitly show
            # share in profits of associates.
            share_associates = row_value(
                [
                    "share in profits",
                    "associates",
                ],
                period,
            )

            if share_associates is not None:

                calculated_attributable += (
                    share_associates
                )

        checks.append(
            _check(
                name=(
                    f"P&L attributable profit "
                    f"reconciliation - {period}"
                ),
                formula=(
                    "Profit before Minority Interest "
                    "- Minority Interest "
                    "+ Share in Profits of Associates "
                    "where present "
                    "≈ Consolidated Net Profit "
                    "attributable to the Group"
                ),
                period=period,
                operands={
                    "profit_before_minority":
                        profit_before_minority,
                    "minority_interest":
                        minority_interest,
                },
                calculated=calculated_attributable,
                reported=attributable_profit,
            )
        )

        # ----------------------------------------------------
        # 5. APPROPRIATIONS
        # ----------------------------------------------------

        appropriation_field = fields.get(
            "appropriations"
        )

        appropriation_data = {}

        if isinstance(
            appropriation_field,
            dict,
        ):

            appropriation_data = (
                appropriation_field.get(
                    "value",
                    {},
                )
            )

        if not isinstance(
            appropriation_data,
            dict,
        ):
            appropriation_data = {}

        def appr(
            key: str,
        ) -> float | None:

            value = appropriation_data.get(key)

            if isinstance(value, dict):

                number = _number(
                    value.get(period)
                )

                if number is not None:
                    return number

            else:

                number = _number(value)

                if number is not None:
                    return number

            return None

        brought_forward = appr(
            "brought_forward"
        )

        if brought_forward is None:

            brought_forward = row_value(
                [
                    "brought",
                    "forward",
                ],
                period,
            )

        # Older wording:
        # Balance in Profit and Loss account brought forward
        if brought_forward is None:

            brought_forward = row_value(
                [
                    "profit and loss",
                    "account brought forward",
                ],
                period,
            )

        appropriations_total = appr(
            "appropriations_total"
        )

        if appropriations_total is None:

            appropriations_total = find_total_for_section(
                period,
                "appropriations",
            )

        # If the section was not detected because OCR
        # removed the heading, search rows explicitly.
        if appropriations_total is None:

            for row in statement_rows:

                description = str(
                    row.get("description", "")
                ).lower()

                if description != "total":
                    continue

                values = row.get("values", {})

                if not isinstance(values, dict):
                    continue

                value = _number(
                    values.get(period)
                )

                if value is not None:
                    # Do not blindly use it unless it appears
                    # after an appropriations row.
                    index = statement_rows.index(row)

                    previous_text = " ".join(
                        str(
                            r.get("description", "")
                        ).lower()
                        for r in statement_rows[
                            max(0, index - 10):index
                        ]
                    )

                    if "appropriation" in previous_text:
                        appropriations_total = value
                        break

        # ----------------------------------------------------
        # Appropriations opening reconciliation
        # ----------------------------------------------------

        calculated_appropriation_total = None

        if (
            brought_forward is not None
            and attributable_profit is not None
        ):

            calculated_appropriation_total = (
                brought_forward
                + attributable_profit
            )

        checks.append(
            _check(
                name=(
                    f"P&L appropriations opening "
                    f"reconciliation - {period}"
                ),
                formula=(
                    "Brought Forward Profit "
                    "+ Current Profit "
                    "≈ Total Available for Appropriation"
                ),
                period=period,
                operands={
                    "brought_forward":
                        brought_forward,
                    "attributable_profit":
                        attributable_profit,
                },
                calculated=calculated_appropriation_total,
                reported=appropriations_total,
            )
        )

        # ----------------------------------------------------
        # Appropriations closing reconciliation
        # ----------------------------------------------------

        distribution_keys = [
            "transfer_to_statutory_reserve",
            "tax_on_dividend",
            "interim_dividend",
            "transfer_to_general_reserve",
            "transfer_to_special_reserve",
            "transfer_to_capital_reserve",
            "dividend_previous_year",
            "transfer_to_investment_reserve",
            "transfer_to_investment_fluctuation_reserve",
            "transfer_to_minority_interest",
            "transfer_to_other_reserves",
        ]

        distributions = []

        for key in distribution_keys:

            value = appr(key)

            if value is not None:
                distributions.append(value)

        balance_carried_over = appr(
            "balance_carried_over"
        )

        if balance_carried_over is None:

            balance_carried_over = row_value(
                [
                    "balance carried over",
                ],
                period,
            )

        calculated_closing = None

        if (
            appropriations_total is not None
            and distributions
        ):

            calculated_closing = (
                appropriations_total
                - sum(distributions)
            )

        checks.append(
            _check(
                name=(
                    f"P&L appropriations closing "
                    f"reconciliation - {period}"
                ),
                formula=(
                    "Appropriations Total "
                    "- Appropriation Transfers/Dividends "
                    "≈ Balance Carried Over"
                ),
                period=period,
                operands={
                    "appropriations_total":
                        appropriations_total,
                    "total_distributions":
                        sum(distributions)
                        if distributions
                        else None,
                },
                calculated=calculated_closing,
                reported=balance_carried_over,
            )
        )

    return checks


# ============================================================
# BALANCE SHEET
# ============================================================

def _validate_balance_sheet(
    fields: dict[str, Any],
    periods: list[str],
) -> list[dict[str, Any]]:

    checks = []

    for period in periods:

        total_assets = _period_value(
            fields,
            "total_assets",
            period,
        )

        total_capital_liabilities = _period_value(
            fields,
            "total_capital_and_liabilities",
            period,
        )

        # ----------------------------------------------------
        # Main balance check
        # ----------------------------------------------------

        checks.append(
            _check(
                name=f"Balance Sheet main reconciliation - {period}",
                formula=(
                    "Total Capital & Liabilities "
                    "≈ Total Assets"
                ),
                period=period,
                operands={
                    "total_capital_and_liabilities":
                        total_capital_liabilities,
                },
                calculated=total_capital_liabilities,
                reported=total_assets,
            )
        )

        # ----------------------------------------------------
        # Asset components
        # ----------------------------------------------------

        asset_keys = [
            "cash_and_balances_with_banks",
            "balances_with_banks",
            "investments",
            "advances",
            "fixed_assets",
            "other_assets",
            "goodwill",
        ]

        asset_values = [
            _period_value(
                fields,
                key,
                period,
            )
            for key in asset_keys
        ]

        # Only validate component sum when ALL
        # required components are present.
        if all(
            value is not None
            for value in asset_values
        ):

            calculated_assets = sum(
                asset_values
            )

            checks.append(
                _check(
                    name=(
                        f"Balance Sheet asset "
                        f"component reconciliation - {period}"
                    ),
                    formula=(
                        "Sum of Available Asset Components "
                        "≈ Total Assets"
                    ),
                    period=period,
                    operands={
                        key: _period_value(
                            fields,
                            key,
                            period,
                        )
                        for key in asset_keys
                    },
                    calculated=calculated_assets,
                    reported=total_assets,
                )
            )

        else:

            checks.append(
                {
                    "name": (
                        f"Balance Sheet asset "
                        f"component reconciliation - {period}"
                    ),
                    "reason": (
                        "Not all asset components are "
                        "available in the extracted statement."
                    ),
                    "status": "NOT_APPLICABLE",
                    "formula": (
                        "Sum of Available Asset Components "
                        "≈ Total Assets"
                    ),
                    "operands": {
                        key: _period_value(
                            fields,
                            key,
                            period,
                        )
                        for key in asset_keys
                    },
                    "calculated_value": None,
                    "reported_value": total_assets,
                    "variance": None,
                }
            )

    return checks


# ============================================================
# CASH FLOW
# ============================================================

def _validate_cash_flow(
    fields: dict[str, Any],
    periods: list[str],
) -> list[dict[str, Any]]:

    checks = []

    for period in periods:

        operating = _period_value(
            fields,
            "operating_cash_flow",
            period,
        )

        investing = _period_value(
            fields,
            "investing_cash_flow",
            period,
        )

        financing = _period_value(
            fields,
            "financing_cash_flow",
            period,
        )

        fx = _period_value(
            fields,
            "fx_translation",
            period,
        )

        net_increase = _period_value(
            fields,
            "net_increase_in_cash",
            period,
        )

        # ----------------------------------------------------
        # Operating + Investing + Financing + FX
        # ----------------------------------------------------

        calculated_net = None

        if all(
            value is not None
            for value in [
                operating,
                investing,
                financing,
                fx,
            ]
        ):

            calculated_net = (
                operating
                + investing
                + financing
                + fx
            )

        checks.append(
            _check(
                name=f"Cash Flow net increase reconciliation - {period}",
                formula=(
                    "Operating + Investing + Financing "
                    "+ FX/Translation ≈ Net Increase in Cash"
                ),
                period=period,
                operands={
                    "operating_cash_flow": operating,
                    "investing_cash_flow": investing,
                    "financing_cash_flow": financing,
                    "fx_translation": fx,
                },
                calculated=calculated_net,
                reported=net_increase,
            )
        )

        # ----------------------------------------------------
        # Opening + Net Increase = Closing
        # ----------------------------------------------------

        opening = _period_value(
            fields,
            "opening_cash",
            period,
        )

        closing = _period_value(
            fields,
            "closing_cash",
            period,
        )

        calculated_closing = None

        if (
            opening is not None
            and net_increase is not None
        ):

            calculated_closing = (
                opening
                + net_increase
            )

        checks.append(
            _check(
                name=f"Cash Flow opening/closing reconciliation - {period}",
                formula=(
                    "Opening Cash + Net Increase "
                    "≈ Closing Cash"
                ),
                period=period,
                operands={
                    "opening_cash": opening,
                    "net_increase_in_cash": net_increase,
                },
                calculated=calculated_closing,
                reported=closing,
            )
        )

    return checks


# ============================================================
# PUBLIC FUNCTION
# ============================================================

def validate_financial_data(
    document_type: str,
    fields: dict[str, Any],
    tables: list[dict[str, Any]] | None = None,
    periods: list[str] | None = None,
) -> list[dict[str, Any]]:

    tables = tables or []

    periods = periods or []

    if document_type == "invoice":

        return _validate_invoice(
            fields,
            tables,
        )

    if document_type == "profit_and_loss":

        return _validate_profit_and_loss(
            fields,
            periods,
            tables,
        )

    if document_type == "balance_sheet":

        return _validate_balance_sheet(
            fields,
            periods,
        )

    if document_type == "cash_flow_statement":

        return _validate_cash_flow(
            fields,
            periods,
        )

    return []