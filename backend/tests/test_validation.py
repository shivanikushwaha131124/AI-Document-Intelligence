from app.services.financial_validation_service import validate_financial_data

def test_profit_and_loss_validation_pass():
    fields = {
        "interest_earned": {"value": {"2026": 100.0}},
        "other_income": {"value": {"2026": 50.0}},
        "total_income": {"value": {"2026": 150.0}},
        "interest_expended": {"value": {"2026": 60.0}},
        "operating_expenses": {"value": {"2026": 30.0}},
        "provisions_and_contingencies": {
            "value": {"2026": 10.0}
        },
        "total_expenditure": {
            "value": {"2026": 100.0}
        },
        "consolidated_net_profit_before_minority": {
            "value": {"2026": 50.0}
        },
        "minority_interest": {
            "value": {"2026": 5.0}
        },
        "consolidated_net_profit_attributable": {
            "value": {"2026": 45.0}
        },
    }

    result = validate_financial_data(
        document_type="profit_and_loss",
        fields=fields,
        tables=[],
        periods=["2026"],
    )

    assert len(result) > 0
    assert any(
        check["status"] == "PASS"
        for check in result
    )


def test_cash_flow_validation_pass():
    fields = {
        "operating_cash_flow": {
            "value": {"2026": 100.0}
        },
        "investing_cash_flow": {
            "value": {"2026": -20.0}
        },
        "financing_cash_flow": {
            "value": {"2026": 30.0}
        },
        "fx_translation": {
            "value": {"2026": -10.0}
        },
        "net_increase_in_cash": {
            "value": {"2026": 100.0}
        },
        "opening_cash": {
            "value": {"2026": 200.0}
        },
        "closing_cash": {
            "value": {"2026": 300.0}
        },
    }

    result = validate_financial_data(
        document_type="cash_flow_statement",
        fields=fields,
        tables=[],
        periods=["2026"],
    )

    assert len(result) > 0
    assert any(
        check["status"] == "PASS"
        for check in result
    )