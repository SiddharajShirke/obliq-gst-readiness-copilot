import json
from io import BytesIO

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer demo-admin-token"}
APP_ID = "30000000-0000-0000-0000-000000000004"


def make_purchase_xlsx() -> bytes:
    frame = pd.DataFrame([
        {"Invoice No": "P-1", "Invoice Date": "2026-04-10", "Supplier GSTIN": "27ABCDE1234F1Z5", "Taxable Amount": 1000, "CGST": 90, "SGST": 90, "Total": 1180},
        {"Invoice No": "P-2", "Invoice Date": "2026-04-11", "Supplier GSTIN": "27ABCDE1234F1Z5", "Taxable Amount": 2000, "CGST": 180, "SGST": 180, "Total": 2360},
    ])
    output = BytesIO()
    frame.to_excel(output, index=False)
    return output.getvalue()


def test_reconciliation_and_readiness_exports() -> None:
    purchase = client.post(
        f"/api/v1/applications/{APP_ID}/documents",
        headers=AUTH,
        data={"requirement_type": "purchase_register"},
        files={"file": ("Purchase_Register_April.xlsx", make_purchase_xlsx(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert purchase.status_code == 201

    gstr_payload = {
        "records": [
            {"Invoice No": "P-1", "Invoice Date": "2026-04-10", "Supplier GSTIN": "27ABCDE1234F1Z5", "Taxable Amount": 1000, "CGST": 90, "SGST": 90, "Total": 1180},
            {"Invoice No": "P-2", "Invoice Date": "2026-04-11", "Supplier GSTIN": "27ABCDE1234F1Z5", "Taxable Amount": 2100, "CGST": 189, "SGST": 189, "Total": 2478},
            {"Invoice No": "G-ONLY", "Invoice Date": "2026-04-12", "Supplier GSTIN": "27ABCDE1234F1Z5", "Taxable Amount": 500, "CGST": 45, "SGST": 45, "Total": 590},
        ]
    }
    gstr = client.post(
        f"/api/v1/applications/{APP_ID}/documents",
        headers=AUTH,
        data={"requirement_type": "gstr2b"},
        files={"file": ("GSTR2B_April.json", json.dumps(gstr_payload).encode(), "application/json")},
    )
    assert gstr.status_code == 201

    reconciliation = client.post(f"/api/v1/applications/{APP_ID}/reconcile", headers=AUTH)
    assert reconciliation.status_code == 200
    assert reconciliation.json()["summary"]["matched"] == 1
    assert reconciliation.json()["summary"]["amount_mismatch"] == 1
    assert reconciliation.json()["summary"]["gstr2b_only"] == 1

    readiness = client.get(f"/api/v1/applications/{APP_ID}/readiness-summary", headers=AUTH)
    assert readiness.status_code == 200
    assert readiness.json()["reconciliation"]["matched"] == 1
    assert "subject to CA review" in readiness.json()["disclaimer"]

    export = client.post(f"/api/v1/applications/{APP_ID}/export", headers=AUTH)
    assert export.status_code == 200
    assert {"readiness_pdf", "invoice_csv", "reconciliation_csv"}.issubset(export.json())
