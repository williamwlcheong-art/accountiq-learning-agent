import asyncio
import io
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

import db as db_module
import ingestion as ingestion_module
import main as main_module
from rule_extractor import rule_based_extract


class IsolatedAppTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="accountiq-test-"))
        self.db_path = self.tmpdir / "accountiq_learning.db"
        self.pdf_dir = self.tmpdir / "pdfs"
        self.export_dir = self.tmpdir / "exports"
        self.pdf_dir.mkdir()
        self.export_dir.mkdir()

        self.originals = {
            "db_path": db_module.DB_PATH,
            "main_db_path": main_module.DB_PATH,
            "pdf_dir": main_module.PDF_DIR,
            "export_dir": main_module.EXPORT_DIR,
            "admin_token": os.environ.get("APP_ADMIN_TOKEN"),
            "service_token": os.environ.get("EXTRACTOR_SERVICE_TOKEN"),
        }

        os.environ["APP_ADMIN_TOKEN"] = "test-admin-token"
        db_module.DB_PATH = self.db_path
        main_module.DB_PATH = self.db_path
        main_module.PDF_DIR = self.pdf_dir
        main_module.EXPORT_DIR = self.export_dir
        db_module.init_db()

        self.client = TestClient(main_module.app)
        self.company_id = self._create_company()

    def tearDown(self):
        self.client.close()
        db_module.DB_PATH = self.originals["db_path"]
        main_module.DB_PATH = self.originals["main_db_path"]
        main_module.PDF_DIR = self.originals["pdf_dir"]
        main_module.EXPORT_DIR = self.originals["export_dir"]
        shutil.rmtree(self.tmpdir)
        if self.originals["admin_token"] is None:
            os.environ.pop("APP_ADMIN_TOKEN", None)
        else:
            os.environ["APP_ADMIN_TOKEN"] = self.originals["admin_token"]
        if self.originals["service_token"] is None:
            os.environ.pop("EXTRACTOR_SERVICE_TOKEN", None)
        else:
            os.environ["EXTRACTOR_SERVICE_TOKEN"] = self.originals["service_token"]

    def _create_company(self):
        response = self.client.post(
            "/companies",
            data={"name": "Test Co", "exchange": "NZX", "country": "NZ"},
            headers={"X-Admin-Token": "test-admin-token"},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["id"]

    def _upload(self, filename, content=b"%PDF-1.4 test"):
        return self.client.post(
            "/documents/upload",
            data={"company_id": str(self.company_id)},
            files={"file": (filename, io.BytesIO(content), "application/pdf")},
            headers={"X-Admin-Token": "test-admin-token"},
        )

    def test_upload_rejects_path_traversal_filename(self):
        response = self._upload("../escape.pdf")

        self.assertEqual(response.status_code, 400)
        self.assertFalse((self.tmpdir / "escape.pdf").exists())

    def test_duplicate_upload_does_not_overwrite_existing_file(self):
        first = self._upload("statement.pdf", b"original")
        self.assertEqual(first.status_code, 200)

        second = self._upload("statement.pdf", b"replacement")

        self.assertEqual(second.status_code, 409)
        saved_file = self.pdf_dir / str(self.company_id) / "statement.pdf"
        self.assertEqual(saved_file.read_bytes(), b"original")

    def test_failed_ingestion_updates_document_status(self):
        response = self._upload("broken.pdf", b"not a real pdf")
        self.assertEqual(response.status_code, 200)
        document_id = response.json()["document_id"]

        status = self.client.get(f"/documents/{document_id}/status")

        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["status"], "failed")
        self.assertTrue(status.json()["error_message"])

    def test_settings_requires_admin_token(self):
        response = self.client.post("/settings", data={"claude_model": "claude-sonnet-4-6"})

        self.assertEqual(response.status_code, 401)

    def test_extract_endpoint_requires_service_token(self):
        response = self.client.post(
            "/extract",
            json={
                "storage_object_path": "session/file.pdf",
                "metadata": {"company_name": "Test Co"},
            },
        )

        self.assertEqual(response.status_code, 401)

    def test_extract_endpoint_accepts_local_file_job(self):
        os.environ["EXTRACTOR_SERVICE_TOKEN"] = "test-service-token"
        local_file = self.pdf_dir / "service.pdf"
        local_file.write_bytes(b"not a real pdf")

        response = self.client.post(
            "/extract",
            headers={"X-Service-Token": "test-service-token"},
            json={
                "storage_object_path": "service/service.pdf",
                "metadata": {
                    "company_name": "Service Co",
                    "entity_type": "sme",
                    "local_file_path": str(local_file),
                    "original_filename": "service.pdf",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "processing")
        self.assertIsInstance(payload["job_id"], int)

    def test_cors_does_not_allow_arbitrary_origins(self):
        response = self.client.options(
            "/companies",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertNotEqual(response.headers.get("access-control-allow-origin"), "*")


class ExtractionValidationTest(unittest.TestCase):
    def test_persist_extraction_rejects_unknown_canonical_key(self):
        tmpdir = Path(tempfile.mkdtemp(prefix="accountiq-validation-"))
        db_path = tmpdir / "accountiq_learning.db"
        original_db_path = db_module.DB_PATH
        db_module.DB_PATH = db_path
        try:
            db_module.init_db()

            async def run_case():
                async with ingestion_module.aiosqlite.connect(db_path) as conn:
                    conn.row_factory = ingestion_module.aiosqlite.Row
                    await conn.execute("PRAGMA foreign_keys=ON")
                    await conn.execute(
                        "INSERT INTO companies (id, name, exchange) VALUES (1, 'Test Co', 'NZX')"
                    )
                    await conn.execute(
                        "INSERT INTO documents (id, company_id, filename, filepath) VALUES (1, 1, 'a.pdf', '/tmp/a.pdf')"
                    )
                    await conn.commit()
                    await ingestion_module.persist_extraction(
                        conn,
                        1,
                        1,
                        {
                            "periods": ["2025"],
                            "rows": [
                                {
                                    "statement": "pnl",
                                    "canonical_key": "totally_fake_metric",
                                    "raw_label": "Fake",
                                    "values": {"2025": 100},
                                    "confidence": 0.8,
                                }
                            ],
                        },
                        "listed",
                        "NZX",
                    )

            with self.assertRaises(ValueError):
                asyncio.run(run_case())
        finally:
            db_module.DB_PATH = original_db_path
            shutil.rmtree(tmpdir)


class RuleExtractorTest(unittest.TestCase):
    def test_rule_based_extract_reads_basic_profit_and_loss_rows(self):
        parsed = rule_based_extract(
            [
                """
                Statement of profit or loss
                Year ended 2025 2024
                Revenue 1,200 1,000
                Cost of sales (400) (350)
                Gross profit 800 650
                Profit before tax 300 250
                """
            ]
        )

        rows = {row["canonical_key"]: row for row in parsed["rows"]}
        self.assertEqual(rows["revenue"]["values"]["2025"], 1200)
        self.assertEqual(rows["cogs"]["values"]["2024"], -350)
        self.assertEqual(parsed["periods"], ["2025", "2024"])


if __name__ == "__main__":
    unittest.main()
