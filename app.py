"""Job Application Tracker - main Flask application.

Pages: Dashboard, Companies, Jobs, Applications, Contacts, Job Match.
Each of the four tables has full CRUD (list, detail, add, edit, delete).
"""

import json
import os
import re
from datetime import date, datetime

from flask import Flask, abort, flash, redirect, render_template, request, url_for
from mysql.connector import Error as MySQLError
from mysql.connector import IntegrityError

from database import execute, query_all, query_one
from matching import parse_skills, rank_jobs

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")

JOB_TYPES = ["Full-time", "Part-time", "Contract", "Internship"]
STATUSES = ["Applied", "Screening", "Interview", "Offer", "Rejected", "Withdrawn"]
INTERVIEW_TYPES = ["Phone Screen", "Recruiter Call", "Technical", "Behavioral",
                   "Onsite", "Panel", "Final", "Other"]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[0-9+()\-.\s]{7,20}$")


# ---------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------
def clean(name):
    """Return a trimmed form value, or None if it is blank."""
    value = request.form.get(name, "").strip()
    return value or None


def load_json(value, default):
    """Parse a JSON column (MySQL returns it as str/bytes) safely."""
    if value is None:
        return default
    if isinstance(value, (bytes, bytearray)):
        value = value.decode()
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return default
    return value


def valid_url(value):
    return value.startswith(("http://", "https://"))


def parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def parse_int(value):
    try:
        return int(value.replace(",", "").replace("$", ""))
    except (AttributeError, ValueError):
        return None


def company_choices():
    return query_all("SELECT company_id, company_name FROM companies ORDER BY company_name")


def get_or_404(sql, record_id):
    row = query_one(sql, (record_id,))
    if row is None:
        abort(404)
    return row


@app.context_processor
def inject_globals():
    """Expose today's date and the current nav section to every template."""
    endpoint = request.endpoint or ""
    section = endpoint
    for prefix, name in (("company_", "companies"), ("job_match", "job_match"),
                         ("job_", "jobs"), ("application_", "applications"),
                         ("contact_", "contacts")):
        if endpoint.startswith(prefix):
            section = name
            break
    return {"today": date.today(), "section": section}


@app.template_filter("money")
def money(value):
    return f"${value:,.0f}" if value is not None else "—"


@app.template_filter("status_color")
def status_color(status):
    return {
        "Applied": "primary", "Screening": "info", "Interview": "warning",
        "Offer": "success", "Rejected": "danger", "Withdrawn": "secondary",
    }.get(status, "light")


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", message="That record was not found."), 404


@app.errorhandler(MySQLError)
def database_error(error):
    app.logger.error("Database error: %s", error)
    return render_template(
        "error.html",
        message="Could not reach the database. Check your MySQL server and the "
                "DB_* settings in your .env file.",
        detail=str(error),
    ), 500


# ---------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------
@app.route("/")
def dashboard():
    counts = query_one("""
        SELECT (SELECT COUNT(*) FROM companies)    AS companies,
               (SELECT COUNT(*) FROM jobs)         AS jobs,
               (SELECT COUNT(*) FROM applications) AS applications,
               (SELECT COUNT(*) FROM contacts)     AS contacts
    """)

    status_rows = query_all(
        "SELECT status, COUNT(*) AS total FROM applications GROUP BY status"
    )
    by_status = {s: 0 for s in STATUSES}
    for row in status_rows:
        by_status[row["status"]] = row["total"]

    total_apps = counts["applications"] or 0
    progressed = sum(by_status[s] for s in ("Screening", "Interview", "Offer"))
    response_rate = round(progressed / total_apps * 100) if total_apps else 0

    salary = query_one("""
        SELECT ROUND(AVG((salary_min + salary_max) / 2)) AS avg_mid
        FROM jobs WHERE salary_min IS NOT NULL AND salary_max IS NOT NULL
    """)

    recent = query_all("""
        SELECT a.application_id, a.application_date, a.status,
               j.job_title, c.company_name
        FROM applications a
        JOIN jobs j      ON a.job_id = j.job_id
        JOIN companies c ON j.company_id = c.company_id
        ORDER BY a.application_date DESC, a.application_id DESC
        LIMIT 5
    """)

    # Upcoming interviews come from the interview_data JSON column.
    rows = query_all("""
        SELECT a.application_id, a.interview_data, j.job_title, c.company_name
        FROM applications a
        JOIN jobs j      ON a.job_id = j.job_id
        JOIN companies c ON j.company_id = c.company_id
        WHERE a.interview_data IS NOT NULL
    """)
    upcoming = []
    for row in rows:
        for rnd in load_json(row["interview_data"], []):
            when = parse_date(rnd.get("date"))
            if when and when >= date.today():
                upcoming.append({**rnd, "date": when,
                                 "application_id": row["application_id"],
                                 "job_title": row["job_title"],
                                 "company_name": row["company_name"]})
    upcoming.sort(key=lambda r: r["date"])

    return render_template(
        "dashboard.html", counts=counts, by_status=by_status,
        response_rate=response_rate, avg_salary=salary["avg_mid"],
        recent=recent, upcoming=upcoming[:5],
    )


# ---------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------
def company_form_data():
    data = {f: clean(f) for f in
            ("company_name", "industry", "website", "city", "state", "notes")}
    errors = []
    if not data["company_name"]:
        errors.append("Company name is required.")
    elif len(data["company_name"]) > 100:
        errors.append("Company name must be 100 characters or fewer.")
    if data["website"] and not valid_url(data["website"]):
        errors.append("Website must start with http:// or https://")
    for field, limit in (("industry", 50), ("city", 50), ("state", 50), ("website", 200)):
        if data[field] and len(data[field]) > limit:
            errors.append(f"{field.title()} must be {limit} characters or fewer.")
    return data, errors


@app.route("/companies")
def companies():
    search = request.args.get("q", "").strip()
    sql = """
        SELECT c.*,
               (SELECT COUNT(*) FROM jobs j WHERE j.company_id = c.company_id)     AS job_count,
               (SELECT COUNT(*) FROM contacts k WHERE k.company_id = c.company_id) AS contact_count
        FROM companies c
    """
    params = ()
    if search:
        sql += " WHERE c.company_name LIKE %s OR c.industry LIKE %s OR c.city LIKE %s"
        like = f"%{search}%"
        params = (like, like, like)
    sql += " ORDER BY c.company_name"
    return render_template("companies.html", companies=query_all(sql, params), q=search)


@app.route("/companies/<int:company_id>")
def company_detail(company_id):
    company = get_or_404("SELECT * FROM companies WHERE company_id = %s", company_id)
    jobs = query_all(
        "SELECT * FROM jobs WHERE company_id = %s ORDER BY date_posted DESC", (company_id,))
    contacts = query_all(
        "SELECT * FROM contacts WHERE company_id = %s ORDER BY contact_name", (company_id,))
    return render_template("company_detail.html", company=company, jobs=jobs, contacts=contacts)


@app.route("/companies/new", methods=["GET", "POST"])
def company_new():
    company = {}
    if request.method == "POST":
        company, errors = company_form_data()
        if not errors:
            try:
                new_id = execute("""
                    INSERT INTO companies (company_name, industry, website, city, state, notes)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, tuple(company.values()))
                flash(f"Company '{company['company_name']}' added.", "success")
                return redirect(url_for("company_detail", company_id=new_id))
            except IntegrityError:
                errors.append("A company with that name already exists.")
        for e in errors:
            flash(e, "danger")
    return render_template("company_form.html", company=company, action="Add")


@app.route("/companies/<int:company_id>/edit", methods=["GET", "POST"])
def company_edit(company_id):
    company = get_or_404("SELECT * FROM companies WHERE company_id = %s", company_id)
    if request.method == "POST":
        data, errors = company_form_data()
        if not errors:
            try:
                execute("""
                    UPDATE companies SET company_name=%s, industry=%s, website=%s,
                           city=%s, state=%s, notes=%s
                    WHERE company_id=%s
                """, (*data.values(), company_id))
                flash("Company updated.", "success")
                return redirect(url_for("company_detail", company_id=company_id))
            except IntegrityError:
                errors.append("A company with that name already exists.")
        for e in errors:
            flash(e, "danger")
        company = {**data, "company_id": company_id}
    return render_template("company_form.html", company=company, action="Edit")


@app.route("/companies/<int:company_id>/delete", methods=["POST"])
def company_delete(company_id):
    company = get_or_404("SELECT company_name FROM companies WHERE company_id = %s", company_id)
    execute("DELETE FROM companies WHERE company_id = %s", (company_id,))
    flash(f"Deleted '{company['company_name']}' and its jobs, applications and contacts.",
          "success")
    return redirect(url_for("companies"))


# ---------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------
def job_form_data():
    data = {
        "company_id": parse_int(request.form.get("company_id", "")),
        "job_title": clean("job_title"),
        "job_type": clean("job_type"),
        "salary_min": parse_int(request.form.get("salary_min", "")),
        "salary_max": parse_int(request.form.get("salary_max", "")),
        "job_url": clean("job_url"),
        "date_posted": clean("date_posted"),
    }
    skills = parse_skills(request.form.get("skills", ""))
    exp_raw = request.form.get("experience_years", "").strip()
    requirements = {"skills": skills}
    if exp_raw:
        requirements["experience_years"] = parse_int(exp_raw)
    if clean("education"):
        requirements["education"] = clean("education")

    errors = []
    if not data["company_id"] or not query_one(
            "SELECT 1 FROM companies WHERE company_id=%s", (data["company_id"],)):
        errors.append("Please choose a valid company.")
    if not data["job_title"]:
        errors.append("Job title is required.")
    if data["job_type"] not in JOB_TYPES:
        errors.append("Please choose a valid job type.")
    for field in ("salary_min", "salary_max"):
        raw = request.form.get(field, "").strip()
        if raw and (data[field] is None or data[field] < 0):
            errors.append(f"{field.replace('_', ' ').title()} must be a positive whole number.")
    if (data["salary_min"] is not None and data["salary_max"] is not None
            and data["salary_min"] > data["salary_max"]):
        errors.append("Minimum salary cannot be greater than maximum salary.")
    if data["job_url"] and not valid_url(data["job_url"]):
        errors.append("Job URL must start with http:// or https://")
    if data["date_posted"] and not parse_date(data["date_posted"]):
        errors.append("Date posted must be a valid date.")
    if exp_raw and (requirements.get("experience_years") is None
                    or requirements["experience_years"] < 0):
        errors.append("Years of experience must be a positive whole number.")
    if not skills:
        errors.append("List at least one required skill (used by Job Match).")

    data["requirements"] = requirements
    return data, errors


def job_row_for_template(job):
    req = load_json(job.get("requirements"), {})
    job["req"] = req
    job["skills"] = req.get("skills", [])
    return job


@app.route("/jobs")
def jobs():
    job_type = request.args.get("type", "")
    company_id = request.args.get("company", "")
    sql = """
        SELECT j.*, c.company_name,
               JSON_LENGTH(JSON_EXTRACT(j.requirements, '$.skills')) AS skill_count,
               (SELECT COUNT(*) FROM applications a WHERE a.job_id = j.job_id) AS app_count
        FROM jobs j JOIN companies c ON j.company_id = c.company_id
        WHERE 1 = 1
    """
    params = []
    if job_type in JOB_TYPES:
        sql += " AND j.job_type = %s"
        params.append(job_type)
    if company_id.isdigit():
        sql += " AND j.company_id = %s"
        params.append(int(company_id))
    sql += " ORDER BY j.date_posted DESC, j.job_id DESC"
    rows = [job_row_for_template(r) for r in query_all(sql, tuple(params))]
    return render_template("jobs.html", jobs=rows, job_types=JOB_TYPES,
                           companies=company_choices(), sel_type=job_type,
                           sel_company=company_id)


@app.route("/jobs/<int:job_id>")
def job_detail(job_id):
    job = get_or_404("""
        SELECT j.*, c.company_name FROM jobs j
        JOIN companies c ON j.company_id = c.company_id WHERE j.job_id = %s
    """, job_id)
    job = job_row_for_template(job)
    apps = query_all(
        "SELECT * FROM applications WHERE job_id = %s ORDER BY application_date DESC", (job_id,))
    return render_template("job_detail.html", job=job, applications=apps)


def render_job_form(job, action):
    return render_template("job_form.html", job=job, action=action,
                           companies=company_choices(), job_types=JOB_TYPES)


@app.route("/jobs/new", methods=["GET", "POST"])
def job_new():
    job = {"company_id": parse_int(request.args.get("company", "")), "skills": [], "req": {}}
    if request.method == "POST":
        data, errors = job_form_data()
        if not errors:
            new_id = execute("""
                INSERT INTO jobs (company_id, job_title, job_type, salary_min, salary_max,
                                  job_url, date_posted, requirements)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (data["company_id"], data["job_title"], data["job_type"], data["salary_min"],
                  data["salary_max"], data["job_url"], data["date_posted"],
                  json.dumps(data["requirements"])))
            flash(f"Job '{data['job_title']}' added.", "success")
            return redirect(url_for("job_detail", job_id=new_id))
        for e in errors:
            flash(e, "danger")
        job = {**data, "req": data["requirements"], "skills": data["requirements"]["skills"]}
    return render_job_form(job, "Add")


@app.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
def job_edit(job_id):
    job = job_row_for_template(get_or_404("SELECT * FROM jobs WHERE job_id = %s", job_id))
    if request.method == "POST":
        data, errors = job_form_data()
        if not errors:
            execute("""
                UPDATE jobs SET company_id=%s, job_title=%s, job_type=%s, salary_min=%s,
                       salary_max=%s, job_url=%s, date_posted=%s, requirements=%s
                WHERE job_id=%s
            """, (data["company_id"], data["job_title"], data["job_type"], data["salary_min"],
                  data["salary_max"], data["job_url"], data["date_posted"],
                  json.dumps(data["requirements"]), job_id))
            flash("Job updated.", "success")
            return redirect(url_for("job_detail", job_id=job_id))
        for e in errors:
            flash(e, "danger")
        job = {**data, "job_id": job_id, "req": data["requirements"],
               "skills": data["requirements"]["skills"]}
    return render_job_form(job, "Edit")


@app.route("/jobs/<int:job_id>/delete", methods=["POST"])
def job_delete(job_id):
    job = get_or_404("SELECT job_title FROM jobs WHERE job_id = %s", job_id)
    execute("DELETE FROM jobs WHERE job_id = %s", (job_id,))
    flash(f"Deleted job '{job['job_title']}' and its applications.", "success")
    return redirect(url_for("jobs"))


# ---------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------
def job_choices():
    return query_all("""
        SELECT j.job_id, j.job_title, c.company_name
        FROM jobs j JOIN companies c ON j.company_id = c.company_id
        ORDER BY c.company_name, j.job_title
    """)


def interview_rounds_from_form():
    """Collect the repeating interview-round fields into a list of dicts."""
    rounds = []
    fields = zip(request.form.getlist("iv_date"), request.form.getlist("iv_type"),
                 request.form.getlist("iv_interviewer"), request.form.getlist("iv_notes"))
    for when, kind, who, notes in fields:
        if not (when.strip() or who.strip() or notes.strip()):
            continue  # skip completely empty rows
        rounds.append({"date": when.strip(), "type": kind.strip(),
                       "interviewer": who.strip(), "notes": notes.strip()})
    return rounds


def application_form_data():
    data = {
        "job_id": parse_int(request.form.get("job_id", "")),
        "application_date": clean("application_date"),
        "status": clean("status"),
        "resume_version": clean("resume_version"),
        "cover_letter_sent": 1 if request.form.get("cover_letter_sent") else 0,
    }
    rounds = interview_rounds_from_form()
    errors = []
    if not data["job_id"] or not query_one(
            "SELECT 1 FROM jobs WHERE job_id=%s", (data["job_id"],)):
        errors.append("Please choose a valid job.")
    applied_on = parse_date(data["application_date"])
    if not applied_on:
        errors.append("Application date is required and must be a valid date.")
    elif applied_on > date.today():
        errors.append("Application date cannot be in the future.")
    if data["status"] not in STATUSES:
        errors.append("Please choose a valid status.")
    if data["resume_version"] and len(data["resume_version"]) > 50:
        errors.append("Resume version must be 50 characters or fewer.")
    for i, rnd in enumerate(rounds, start=1):
        if not parse_date(rnd["date"]):
            errors.append(f"Interview round {i} needs a valid date.")
    data["interview_data"] = rounds
    return data, errors


def application_values(data):
    return (data["job_id"], data["application_date"], data["status"], data["resume_version"],
            data["cover_letter_sent"],
            json.dumps(data["interview_data"]) if data["interview_data"] else None)


@app.route("/applications")
def applications():
    status = request.args.get("status", "")
    sql = """
        SELECT a.*, j.job_title, c.company_name, c.company_id,
               COALESCE(JSON_LENGTH(a.interview_data), 0) AS interview_count
        FROM applications a
        JOIN jobs j      ON a.job_id = j.job_id
        JOIN companies c ON j.company_id = c.company_id
    """
    params = ()
    if status in STATUSES:
        sql += " WHERE a.status = %s"
        params = (status,)
    sql += " ORDER BY a.application_date DESC, a.application_id DESC"
    return render_template("applications.html", applications=query_all(sql, params),
                           statuses=STATUSES, sel_status=status)


@app.route("/applications/<int:application_id>")
def application_detail(application_id):
    app_row = get_or_404("""
        SELECT a.*, j.job_title, j.job_id, c.company_name, c.company_id
        FROM applications a
        JOIN jobs j      ON a.job_id = j.job_id
        JOIN companies c ON j.company_id = c.company_id
        WHERE a.application_id = %s
    """, application_id)
    app_row["rounds"] = load_json(app_row["interview_data"], [])
    contacts = query_all("SELECT * FROM contacts WHERE company_id = %s",
                         (app_row["company_id"],))
    return render_template("application_detail.html", a=app_row, contacts=contacts)


def render_application_form(application, action):
    return render_template("application_form.html", a=application, action=action,
                           jobs=job_choices(), statuses=STATUSES,
                           interview_types=INTERVIEW_TYPES)


@app.route("/applications/new", methods=["GET", "POST"])
def application_new():
    application = {"job_id": parse_int(request.args.get("job", "")),
                   "application_date": date.today().isoformat(),
                   "status": "Applied", "rounds": []}
    if request.method == "POST":
        data, errors = application_form_data()
        if not errors:
            new_id = execute("""
                INSERT INTO applications (job_id, application_date, status, resume_version,
                                          cover_letter_sent, interview_data)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, application_values(data))
            flash("Application added.", "success")
            return redirect(url_for("application_detail", application_id=new_id))
        for e in errors:
            flash(e, "danger")
        application = {**data, "rounds": data["interview_data"]}
    return render_application_form(application, "Add")


@app.route("/applications/<int:application_id>/edit", methods=["GET", "POST"])
def application_edit(application_id):
    application = get_or_404(
        "SELECT * FROM applications WHERE application_id = %s", application_id)
    application["rounds"] = load_json(application["interview_data"], [])
    if request.method == "POST":
        data, errors = application_form_data()
        if not errors:
            execute("""
                UPDATE applications SET job_id=%s, application_date=%s, status=%s,
                       resume_version=%s, cover_letter_sent=%s, interview_data=%s
                WHERE application_id=%s
            """, (*application_values(data), application_id))
            flash("Application updated.", "success")
            return redirect(url_for("application_detail", application_id=application_id))
        for e in errors:
            flash(e, "danger")
        application = {**data, "application_id": application_id,
                       "rounds": data["interview_data"]}
    return render_application_form(application, "Edit")


@app.route("/applications/<int:application_id>/delete", methods=["POST"])
def application_delete(application_id):
    get_or_404("SELECT 1 FROM applications WHERE application_id = %s", application_id)
    execute("DELETE FROM applications WHERE application_id = %s", (application_id,))
    flash("Application deleted.", "success")
    return redirect(url_for("applications"))


# ---------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------
def contact_form_data():
    data = {
        "company_id": parse_int(request.form.get("company_id", "")),
        "contact_name": clean("contact_name"),
        "title": clean("title"),
        "email": clean("email"),
        "phone": clean("phone"),
        "linkedin_url": clean("linkedin_url"),
        "notes": clean("notes"),
    }
    errors = []
    if not data["company_id"] or not query_one(
            "SELECT 1 FROM companies WHERE company_id=%s", (data["company_id"],)):
        errors.append("Please choose a valid company.")
    if not data["contact_name"]:
        errors.append("Contact name is required.")
    if data["email"] and not EMAIL_RE.match(data["email"]):
        errors.append("Please enter a valid email address.")
    if data["phone"] and not PHONE_RE.match(data["phone"]):
        errors.append("Phone may contain only digits, spaces, + ( ) - . (7-20 characters).")
    if data["linkedin_url"] and not valid_url(data["linkedin_url"]):
        errors.append("LinkedIn URL must start with http:// or https://")
    return data, errors


@app.route("/contacts")
def contacts():
    search = request.args.get("q", "").strip()
    sql = """
        SELECT k.*, c.company_name FROM contacts k
        JOIN companies c ON k.company_id = c.company_id
    """
    params = ()
    if search:
        sql += " WHERE k.contact_name LIKE %s OR c.company_name LIKE %s OR k.title LIKE %s"
        like = f"%{search}%"
        params = (like, like, like)
    sql += " ORDER BY k.contact_name"
    return render_template("contacts.html", contacts=query_all(sql, params), q=search)


@app.route("/contacts/<int:contact_id>")
def contact_detail(contact_id):
    contact = get_or_404("""
        SELECT k.*, c.company_name FROM contacts k
        JOIN companies c ON k.company_id = c.company_id WHERE k.contact_id = %s
    """, contact_id)
    return render_template("contact_detail.html", contact=contact)


def render_contact_form(contact, action):
    return render_template("contact_form.html", contact=contact, action=action,
                           companies=company_choices())


@app.route("/contacts/new", methods=["GET", "POST"])
def contact_new():
    contact = {"company_id": parse_int(request.args.get("company", ""))}
    if request.method == "POST":
        contact, errors = contact_form_data()
        if not errors:
            new_id = execute("""
                INSERT INTO contacts (company_id, contact_name, title, email, phone,
                                      linkedin_url, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, tuple(contact.values()))
            flash(f"Contact '{contact['contact_name']}' added.", "success")
            return redirect(url_for("contact_detail", contact_id=new_id))
        for e in errors:
            flash(e, "danger")
    return render_contact_form(contact, "Add")


@app.route("/contacts/<int:contact_id>/edit", methods=["GET", "POST"])
def contact_edit(contact_id):
    contact = get_or_404("SELECT * FROM contacts WHERE contact_id = %s", contact_id)
    if request.method == "POST":
        data, errors = contact_form_data()
        if not errors:
            execute("""
                UPDATE contacts SET company_id=%s, contact_name=%s, title=%s, email=%s,
                       phone=%s, linkedin_url=%s, notes=%s
                WHERE contact_id=%s
            """, (*data.values(), contact_id))
            flash("Contact updated.", "success")
            return redirect(url_for("contact_detail", contact_id=contact_id))
        for e in errors:
            flash(e, "danger")
        contact = {**data, "contact_id": contact_id}
    return render_contact_form(contact, "Edit")


@app.route("/contacts/<int:contact_id>/delete", methods=["POST"])
def contact_delete(contact_id):
    contact = get_or_404("SELECT contact_name FROM contacts WHERE contact_id = %s", contact_id)
    execute("DELETE FROM contacts WHERE contact_id = %s", (contact_id,))
    flash(f"Deleted contact '{contact['contact_name']}'.", "success")
    return redirect(url_for("contacts"))


# ---------------------------------------------------------------------
# Job Match
# ---------------------------------------------------------------------
@app.route("/job-match", methods=["GET", "POST"])
def job_match():
    skills_text = request.values.get("skills", "")
    job_type = request.values.get("job_type", "")
    min_percent = parse_int(request.values.get("min_percent", "0")) or 0
    user_skills = parse_skills(skills_text)
    results = None

    if user_skills:
        sql = """
            SELECT j.job_id, j.job_title, j.job_type, j.salary_min, j.salary_max,
                   j.requirements, c.company_name,
                   EXISTS(SELECT 1 FROM applications a WHERE a.job_id = j.job_id) AS applied
            FROM jobs j JOIN companies c ON j.company_id = c.company_id
        """
        params = ()
        if job_type in JOB_TYPES:
            sql += " WHERE j.job_type = %s"
            params = (job_type,)
        jobs_list = [job_row_for_template(r) for r in query_all(sql, params)]
        results = rank_jobs(user_skills, jobs_list, min_percent)
    elif request.method == "POST":
        flash("Enter at least one skill, separated by commas.", "warning")

    return render_template("job_match.html", skills_text=skills_text, user_skills=user_skills,
                           results=results, job_types=JOB_TYPES, sel_type=job_type,
                           min_percent=min_percent)


if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("FLASK_DEBUG", "1") == "1")
