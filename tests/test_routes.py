"""End-to-end smoke tests that exercise every page and CRUD flow.

These need a running MySQL server with schema.sql loaded. They are
skipped automatically if the database cannot be reached.

Run with:  python -m pytest tests
WARNING: they add and delete test rows; reload schema.sql afterwards
if you want the original sample data back exactly.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
from database import get_db, query_one  # noqa: E402

try:
    get_db().close()
    DB_OK = True
except Exception:  # pragma: no cover - depends on environment
    DB_OK = False

pytestmark = pytest.mark.skipif(not DB_OK, reason="MySQL not reachable")


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.mark.parametrize("path", [
    "/", "/companies", "/jobs", "/applications", "/contacts", "/job-match",
    "/companies/1", "/jobs/1", "/applications/1", "/contacts/1",
    "/companies/new", "/jobs/new", "/applications/new", "/contacts/new",
    "/companies/1/edit", "/jobs/1/edit", "/applications/1/edit", "/contacts/1/edit",
    "/companies?q=tech", "/jobs?type=Full-time", "/applications?status=Offer",
])
def test_pages_load(client, path):
    assert client.get(path).status_code == 200


def test_missing_record_is_404(client):
    assert client.get("/companies/999999").status_code == 404


def test_full_crud_cycle(client):
    # Create company
    r = client.post("/companies/new", data={"company_name": "PyTest Co", "industry": "QA",
                                            "website": "https://pytest.example.com"})
    assert r.status_code == 302
    company_id = int(r.headers["Location"].rstrip("/").split("/")[-1])

    # Create job with JSON requirements
    r = client.post("/jobs/new", data={"company_id": company_id, "job_title": "Test Engineer",
                                       "job_type": "Contract", "salary_min": "50000",
                                       "salary_max": "70000", "skills": "Python, Pytest",
                                       "experience_years": "1"})
    assert r.status_code == 302
    job_id = int(r.headers["Location"].split("/")[-1])
    job = query_one("SELECT requirements FROM jobs WHERE job_id=%s", (job_id,))
    assert "Pytest" in job["requirements"]

    # Create application with an interview round
    r = client.post("/applications/new", data={"job_id": job_id, "application_date": "2026-11-01",
                                               "status": "Applied", "cover_letter_sent": "1",
                                               "iv_date": ["2026-11-20"], "iv_type": ["Technical"],
                                               "iv_interviewer": ["Bot"], "iv_notes": ["n/a"]})
    assert r.status_code == 302
    app_id = int(r.headers["Location"].split("/")[-1])

    # Create contact
    r = client.post("/contacts/new", data={"company_id": company_id, "contact_name": "Test Person",
                                           "email": "test@example.com"})
    assert r.status_code == 302
    contact_id = int(r.headers["Location"].split("/")[-1])

    # Update each
    assert client.post(f"/companies/{company_id}/edit",
                       data={"company_name": "PyTest Co 2"}).status_code == 302
    assert client.post(f"/jobs/{job_id}/edit", data={"company_id": company_id, "job_title": "Sr Test",
                                                     "job_type": "Full-time",
                                                     "skills": "Python"}).status_code == 302
    assert client.post(f"/applications/{app_id}/edit",
                       data={"job_id": job_id, "application_date": "2026-11-02",
                             "status": "Interview"}).status_code == 302
    assert client.post(f"/contacts/{contact_id}/edit",
                       data={"company_id": company_id, "contact_name": "Renamed"}).status_code == 302
    assert query_one("SELECT status FROM applications WHERE application_id=%s",
                     (app_id,))["status"] == "Interview"

    # Job match finds the new job
    r = client.post("/job-match", data={"skills": "python"})
    assert b"Sr Test" in r.data

    # Delete contact, application, job, then company
    assert client.post(f"/contacts/{contact_id}/delete").status_code == 302
    assert client.post(f"/applications/{app_id}/delete").status_code == 302
    assert client.post(f"/jobs/{job_id}/delete").status_code == 302
    assert client.post(f"/companies/{company_id}/delete").status_code == 302
    assert query_one("SELECT 1 FROM companies WHERE company_id=%s", (company_id,)) is None


def test_validation_rejects_bad_input(client):
    r = client.post("/companies/new", data={"company_name": ""})
    assert b"Company name is required" in r.data
    r = client.post("/companies/new", data={"company_name": "TechCorp"})
    assert b"already exists" in r.data
    r = client.post("/jobs/new", data={"company_id": 1, "job_title": "X", "job_type": "Full-time",
                                       "salary_min": "90000", "salary_max": "10000",
                                       "skills": "Python"})
    assert b"cannot be greater" in r.data
    r = client.post("/contacts/new", data={"company_id": 1, "contact_name": "A",
                                           "email": "not-an-email"})
    assert b"valid email" in r.data
    r = client.post("/applications/new", data={"job_id": 1, "application_date": "2999-01-01",
                                               "status": "Applied"})
    assert b"cannot be in the future" in r.data
