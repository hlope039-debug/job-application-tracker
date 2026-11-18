# Job Application Tracker

A full-stack web application for tracking a job search: companies, job postings,
applications (with interview rounds), and networking contacts, plus a **Job Match**
feature that ranks jobs by how well your skills fit.

Built for COP4751 with **MySQL**, **Python 3 / Flask**, and **HTML/CSS (Bootstrap 5)**.

## Features

- **Dashboard** – totals for every table, applications by status, response rate,
  offers, average salary midpoint, recent applications, and upcoming interviews.
- **Full CRUD for all four tables** – list, detail, add, edit, and delete (with a
  confirmation prompt) for Companies, Jobs, Applications, and Contacts.
- **Validation** – required fields, URL/email/phone formats, salary min ≤ max,
  no future application dates, duplicate company names, valid foreign keys.
  Errors are shown as messages and the form keeps what you typed.
- **JSON columns** – `jobs.requirements` stores skills, experience and education;
  `applications.interview_data` stores a list of interview rounds you can add or
  remove in the form.
- **Job Match** – enter your skills and see every job ranked by match percentage,
  with matched and missing skills, optional job-type and minimum-match filters.
- **Search & filters** – search companies and contacts; filter jobs by type/company
  and applications by status.

## Tech Stack

| Layer      | Technology                                   |
|------------|----------------------------------------------|
| Database   | MySQL 8 (4 tables, foreign keys, JSON columns) |
| Backend    | Python 3, Flask, mysql-connector-python      |
| Frontend   | Jinja2 templates, HTML, CSS, Bootstrap 5 (bundled locally in `static/vendor`) |
| Testing    | pytest                                       |

## Project Structure

```
job_tracker/
├── app.py              # Flask routes: dashboard, CRUD, job match
├── database.py         # MySQL connection + query helpers
├── matching.py         # Skill-matching algorithm (unit tested)
├── schema.sql          # Creates the database, tables and sample data
├── templates/          # Jinja2 HTML templates
│   ├── base.html, _macros.html, error.html
│   ├── dashboard.html
│   ├── companies.html, company_detail.html, company_form.html
│   ├── jobs.html, job_detail.html, job_form.html
│   ├── applications.html, application_detail.html, application_form.html
│   ├── contacts.html, contact_detail.html, contact_form.html
│   └── job_match.html
├── static/
│   ├── style.css
│   └── vendor/         # Bootstrap 5.3 + Bootstrap Icons (works offline)
├── tests/              # pytest unit + route tests
├── AI_USAGE.md         # GenAI documentation
├── requirements.txt
└── .env.example        # Copy to .env and add your MySQL password
```

## Setup Instructions

### 1. Prerequisites
- Python 3.10 or newer
- MySQL Server 8.0 or newer (MySQL Workbench is optional)
- Git

### 2. Clone the repository
```bash
git clone https://github.com/<your-username>/job_tracker.git
cd job_tracker
```

### 3. Create a virtual environment and install dependencies
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 4. Create the database
From a terminal:
```bash
mysql -u root -p < schema.sql
```
Or open `schema.sql` in MySQL Workbench and run the whole script (lightning-bolt icon).

This creates the `job_tracker` database with all four tables and sample data.
Running it again resets the database to the original sample data.

### 5. Configure your database password
```bash
# Windows:
copy .env.example .env
# macOS / Linux:
cp .env.example .env
```
Open `.env` and set `DB_PASSWORD` to your MySQL root password (change `DB_USER`
too if you don't use root).

### 6. Run the app
```bash
python app.py
```
Open **http://127.0.0.1:5000** in your browser.

### 7. (Optional) Run the tests
```bash
python -m pytest tests -v
```
The matching tests need no database. The route tests use the live database and
are skipped if MySQL can't be reached; they add and remove their own test rows.

## Database Design

```
companies 1───* jobs 1───* applications
    │
    └──────* contacts
```

| Table          | Key points |
|----------------|-----------|
| `companies`    | `company_name` is required and unique. |
| `jobs`         | FK → `companies`; `job_type` ENUM; CHECK that `salary_min ≤ salary_max`; `requirements` JSON. |
| `applications` | FK → `jobs`; `status` ENUM; `cover_letter_sent` BOOLEAN; `interview_data` JSON. |
| `contacts`     | FK → `companies`. |

All foreign keys use `ON DELETE CASCADE`, so deleting a company also removes its
jobs, their applications, and its contacts. The delete confirmation tells the
user exactly what will be removed.

**JSON formats**

```json
// jobs.requirements
{"skills": ["Python", "SQL", "Flask"], "experience_years": 1, "education": "BS Computer Science"}

// applications.interview_data
[{"date": "2026-10-02", "type": "Phone Screen", "interviewer": "Maria Lopez", "notes": "Went well"}]
```

MySQL JSON functions are used in queries, e.g.
`JSON_LENGTH(JSON_EXTRACT(requirements, '$.skills'))` for the skill count on the
Jobs page and `JSON_LENGTH(interview_data)` for interview counts.

## How Job Match Works

1. The user's skills are split on commas (also `;`, `|`, new lines) and de-duplicated.
2. Each skill is normalized: lower-cased, extra spaces removed, and common aliases
   mapped (e.g. `JS` → `JavaScript`, `Postgres` → `PostgreSQL`).
3. For every job, `match % = matched required skills ÷ total required skills`.
4. Jobs are sorted by match %, then by number of matched skills, then by maximum salary.
5. Each result shows the matched and missing skills and whether you've already applied.

Example from the spec, with skills `Python, SQL, Flask`:
```
1. Software Developer at TechCorp – 100% (3/3 skills)
2. Data Analyst at DataCo – 67% (2/3 skills)   Missing: Tableau
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "Could not reach the database" page | Make sure MySQL is running and the values in `.env` are correct. |
| `Access denied for user 'root'` | Wrong password in `.env`. |
| `Unknown database 'job_tracker'` | Run `schema.sql` first (step 4). |
| `ModuleNotFoundError: flask` | Activate the virtual environment and run `pip install -r requirements.txt`. |
| Port 5000 already in use (common on macOS) | Run with a different port: `PORT=5001 python app.py`. |
