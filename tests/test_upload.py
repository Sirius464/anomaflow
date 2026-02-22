"""
AnomaFlow v2.0 — Tests des endpoints d'upload et de rapports
Couvre : validation CSV, analyse, pagination, accès aux rapports.
"""
import io
import pytest


def make_csv(rows: list[dict]) -> bytes:
    """Génère un CSV valide à partir d'une liste de dicts."""
    if not rows:
        return b"transaction_id,user_id,amount,timestamp\n"
    headers = ",".join(rows[0].keys())
    lines   = [headers] + [",".join(str(v) for v in r.values()) for r in rows]
    return "\n".join(lines).encode("utf-8")


VALID_ROWS = [
    {"transaction_id": f"TX{i:03d}", "user_id": f"U{i%3}", "amount": 50.0 + i,
     "timestamp": f"2025-06-15 {10+i//60:02d}:{i%60:02d}:00"}
    for i in range(15)
]


class TestUploadValidation:
    def test_upload_valid_csv(self, client, auth_headers):
        content = make_csv(VALID_ROWS)
        res = client.post("/upload", headers={**auth_headers},
                          files={"file": ("transactions.csv", io.BytesIO(content), "text/csv")})
        assert res.status_code == 200
        data = res.json()
        assert data["rows_processed"] == 15
        assert data["status"] == "completed"
        assert "risk_summary" in data

    def test_upload_non_csv_rejected(self, client, auth_headers):
        res = client.post("/upload", headers={**auth_headers},
                          files={"file": ("data.xlsx", io.BytesIO(b"fake"), "application/vnd.ms-excel")})
        assert res.status_code == 400

    def test_upload_empty_file(self, client, auth_headers):
        res = client.post("/upload", headers={**auth_headers},
                          files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")})
        assert res.status_code == 400

    def test_upload_missing_columns(self, client, auth_headers):
        """CSV sans colonne 'amount'."""
        bad_csv = b"transaction_id,user_id,timestamp\nTX001,U1,2025-01-01 10:00:00\n"
        res = client.post("/upload", headers={**auth_headers},
                          files={"file": ("bad.csv", io.BytesIO(bad_csv), "text/csv")})
        assert res.status_code == 422

    def test_upload_requires_auth(self, client, minimal_csv_bytes):
        res = client.post("/upload",
                          files={"file": ("tx.csv", io.BytesIO(minimal_csv_bytes), "text/csv")})
        assert res.status_code in (401, 403)

    def test_upload_response_structure(self, client, auth_headers):
        content = make_csv(VALID_ROWS)
        res = client.post("/upload", headers={**auth_headers},
                          files={"file": ("tx.csv", io.BytesIO(content), "text/csv")})
        data = res.json()
        required = {"file_id", "filename", "rows_processed", "anomalies_detected", "status", "risk_summary"}
        assert required.issubset(data.keys())

    def test_upload_risk_summary_structure(self, client, auth_headers):
        content = make_csv(VALID_ROWS)
        res = client.post("/upload", headers={**auth_headers},
                          files={"file": ("tx.csv", io.BytesIO(content), "text/csv")})
        rs = res.json()["risk_summary"]
        assert {"score", "level", "anomaly_rate", "by_type", "by_severity"}.issubset(rs.keys())

    def test_upload_with_anomalies_detected(self, client, auth_headers):
        """Un CSV avec un montant très élevé doit produire des anomalies."""
        rows = VALID_ROWS + [
            {"transaction_id": "TX999", "user_id": "FRAUD",
             "amount": 999999.0, "timestamp": "2025-06-15 11:00:00"}
        ]
        content = make_csv(rows)
        res = client.post("/upload", headers={**auth_headers},
                          files={"file": ("tx.csv", io.BytesIO(content), "text/csv")})
        assert res.status_code == 200
        assert res.json()["anomalies_detected"] >= 1


class TestReports:
    def _upload_file(self, client, auth_headers):
        content = make_csv(VALID_ROWS)
        res = client.post("/upload", headers={**auth_headers},
                          files={"file": ("tx.csv", io.BytesIO(content), "text/csv")})
        return res.json()["file_id"]

    def test_list_reports_empty(self, client, auth_headers):
        res = client.get("/reports", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_reports_after_upload(self, client, auth_headers):
        self._upload_file(client, auth_headers)
        res = client.get("/reports", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["total"] == 1

    def test_list_reports_pagination_structure(self, client, auth_headers):
        res = client.get("/reports?page=1&page_size=10", headers=auth_headers)
        data = res.json()
        assert {"total", "page", "page_size", "items"}.issubset(data.keys())
        assert data["page"] == 1
        assert data["page_size"] == 10

    def test_list_reports_invalid_page(self, client, auth_headers):
        res = client.get("/reports?page=0", headers=auth_headers)
        assert res.status_code == 422

    def test_get_report_by_id(self, client, auth_headers):
        fid = self._upload_file(client, auth_headers)
        res = client.get(f"/reports/{fid}", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["report_id"] == fid
        assert "summary" in data
        assert "anomalies" in data

    def test_get_report_not_found(self, client, auth_headers):
        res = client.get("/reports/99999", headers=auth_headers)
        assert res.status_code == 404

    def test_get_report_isolation(self, client):
        """Un utilisateur ne peut pas voir les rapports d'un autre."""
        # Utilisateur A
        client.post("/auth/register", json={"email": "a@test.io", "password": "password123"})
        res_a = client.post("/auth/login", json={"email": "a@test.io", "password": "password123"})
        headers_a = {"Authorization": f"Bearer {res_a.json()['access_token']}"}

        # Utilisateur B
        client.post("/auth/register", json={"email": "b@test.io", "password": "password123"})
        res_b = client.post("/auth/login", json={"email": "b@test.io", "password": "password123"})
        headers_b = {"Authorization": f"Bearer {res_b.json()['access_token']}"}

        # A upload un fichier
        content = make_csv(VALID_ROWS)
        upload_a = client.post("/upload", headers={**headers_a},
                               files={"file": ("tx.csv", io.BytesIO(content), "text/csv")})
        report_id = upload_a.json()["file_id"]

        # B ne doit pas y accéder
        res = client.get(f"/reports/{report_id}", headers=headers_b)
        assert res.status_code == 404

    def test_get_user_reports_endpoint(self, client, auth_headers):
        """GET /reports/user/{user_id} doit exister et retourner 200."""
        me = client.get("/users/me", headers=auth_headers).json()
        res = client.get(f"/reports/user/{me['id']}", headers=auth_headers)
        assert res.status_code == 200

    def test_get_user_reports_unknown_user(self, client, auth_headers):
        res = client.get("/reports/user/99999", headers=auth_headers)
        assert res.status_code == 404

    def test_reports_requires_auth(self, client):
        res = client.get("/reports")
        assert res.status_code in (401, 403)


class TestDashboard:
    def test_dashboard_empty(self, client, auth_headers):
        res = client.get("/dashboard", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total_files"] == 0
        assert data["total_transactions"] == 0

    def test_dashboard_after_upload(self, client, auth_headers):
        content = make_csv(VALID_ROWS)
        client.post("/upload", headers={**auth_headers},
                    files={"file": ("tx.csv", io.BytesIO(content), "text/csv")})
        res = client.get("/dashboard", headers=auth_headers)
        data = res.json()
        assert data["total_files"] == 1
        assert data["total_transactions"] == len(VALID_ROWS)

    def test_dashboard_requires_auth(self, client):
        res = client.get("/dashboard")
        assert res.status_code in (401, 403)
