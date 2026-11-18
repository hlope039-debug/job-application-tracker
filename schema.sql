-- =====================================================================
-- Job Application Tracker - Database Creation Script
-- COP4751 Course Project
--
-- Run with:   mysql -u root -p < schema.sql
-- This drops and recreates the job_tracker database with sample data.
-- =====================================================================

DROP DATABASE IF EXISTS job_tracker;
CREATE DATABASE job_tracker
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
USE job_tracker;

-- ---------------------------------------------------------------------
-- companies: organizations the user is interested in
-- ---------------------------------------------------------------------
CREATE TABLE companies (
    company_id    INT PRIMARY KEY AUTO_INCREMENT,
    company_name  VARCHAR(100) NOT NULL,
    industry      VARCHAR(50),
    website       VARCHAR(200),
    city          VARCHAR(50),
    state         VARCHAR(50),
    notes         TEXT,
    CONSTRAINT uq_company_name UNIQUE (company_name)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- jobs: job postings, each belonging to one company
-- requirements JSON shape:
--   {"skills": ["Python", "SQL"], "experience_years": 2, "education": "BS CS"}
-- ---------------------------------------------------------------------
CREATE TABLE jobs (
    job_id        INT PRIMARY KEY AUTO_INCREMENT,
    company_id    INT NOT NULL,
    job_title     VARCHAR(100) NOT NULL,
    job_type      ENUM('Full-time','Part-time','Contract','Internship') DEFAULT 'Full-time',
    salary_min    INT,
    salary_max    INT,
    job_url       VARCHAR(300),
    date_posted   DATE,
    requirements  JSON,
    CONSTRAINT fk_jobs_company
        FOREIGN KEY (company_id) REFERENCES companies(company_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT chk_salary_range
        CHECK (salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max),
    INDEX idx_jobs_company (company_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- applications: the user's application to a specific job
-- interview_data JSON shape (array of rounds):
--   [{"date": "2026-10-02", "type": "Phone", "interviewer": "Jane", "notes": "..."}]
-- ---------------------------------------------------------------------
CREATE TABLE applications (
    application_id     INT PRIMARY KEY AUTO_INCREMENT,
    job_id             INT NOT NULL,
    application_date   DATE NOT NULL,
    status             ENUM('Applied','Screening','Interview','Offer','Rejected','Withdrawn')
                       NOT NULL DEFAULT 'Applied',
    resume_version     VARCHAR(50),
    cover_letter_sent  BOOLEAN NOT NULL DEFAULT FALSE,
    interview_data     JSON,
    CONSTRAINT fk_applications_job
        FOREIGN KEY (job_id) REFERENCES jobs(job_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_applications_job (job_id),
    INDEX idx_applications_status (status)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- contacts: people the user knows at a company
-- ---------------------------------------------------------------------
CREATE TABLE contacts (
    contact_id    INT PRIMARY KEY AUTO_INCREMENT,
    company_id    INT NOT NULL,
    contact_name  VARCHAR(100) NOT NULL,
    title         VARCHAR(100),
    email         VARCHAR(100),
    phone         VARCHAR(20),
    linkedin_url  VARCHAR(200),
    notes         TEXT,
    CONSTRAINT fk_contacts_company
        FOREIGN KEY (company_id) REFERENCES companies(company_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_contacts_company (company_id)
) ENGINE=InnoDB;

-- =====================================================================
-- Sample data
-- =====================================================================
INSERT INTO companies (company_name, industry, website, city, state, notes) VALUES
('TechCorp',        'Software',     'https://techcorp.example.com',   'Miami',         'FL', 'Fast-growing SaaS company. Hybrid schedule.'),
('DataCo',          'Analytics',    'https://dataco.example.com',     'Orlando',       'FL', 'Data consulting firm with many government clients.'),
('CloudNine Systems','Cloud',       'https://cloudnine.example.com',  'Austin',        'TX', 'Remote-first. Strong engineering blog.'),
('BayHealth Digital','Healthcare',  'https://bayhealth.example.com',  'Tampa',         'FL', 'Hospital network building patient portal apps.'),
('FinEdge',         'FinTech',      'https://finedge.example.com',    'New York',      'NY', 'Payments startup, Series B.'),
('GreenGrid Energy','Energy',       'https://greengrid.example.com',  'Fort Lauderdale','FL', 'Smart-grid analytics; met recruiter at career fair.');

INSERT INTO jobs (company_id, job_title, job_type, salary_min, salary_max, job_url, date_posted, requirements) VALUES
(1, 'Software Developer',        'Full-time',  75000,  95000, 'https://techcorp.example.com/careers/101',  '2026-09-15',
    '{"skills": ["Python", "SQL", "Flask"], "experience_years": 1, "education": "BS Computer Science or related"}'),
(2, 'Data Analyst',              'Full-time',  65000,  80000, 'https://dataco.example.com/jobs/da-22',      '2026-09-20',
    '{"skills": ["Python", "SQL", "Tableau"], "experience_years": 0, "education": "BS in a quantitative field"}'),
(3, 'Junior Cloud Engineer',     'Full-time',  80000, 100000, 'https://cloudnine.example.com/jobs/jce',     '2026-10-01',
    '{"skills": ["Python", "AWS", "Docker", "Linux"], "experience_years": 1, "education": "BS or equivalent experience"}'),
(4, 'Web Developer Intern',      'Internship', 20000,  30000, 'https://bayhealth.example.com/intern',       '2026-10-05',
    '{"skills": ["HTML", "CSS", "JavaScript"], "experience_years": 0, "education": "Currently enrolled in a degree program"}'),
(5, 'Backend Engineer',          'Contract',   90000, 120000, 'https://finedge.example.com/jobs/be',        '2026-10-10',
    '{"skills": ["Java", "Spring", "SQL", "REST APIs"], "experience_years": 2, "education": "BS Computer Science"}'),
(1, 'Full Stack Developer',      'Full-time',  85000, 110000, 'https://techcorp.example.com/careers/117',  '2026-10-12',
    '{"skills": ["Python", "Flask", "JavaScript", "SQL", "React"], "experience_years": 2, "education": "BS Computer Science"}'),
(6, 'Data Engineer',             'Part-time',  40000,  55000, 'https://greengrid.example.com/jobs/de',      '2026-10-18',
    '{"skills": ["Python", "SQL", "Spark", "Airflow"], "experience_years": 1, "education": "BS in a technical field"}');

INSERT INTO applications (job_id, application_date, status, resume_version, cover_letter_sent, interview_data) VALUES
(1, '2026-09-18', 'Interview', 'v3-python',  TRUE,
    '[{"date": "2026-10-02", "type": "Phone Screen", "interviewer": "Maria Lopez", "notes": "Went well; asked about Flask projects."},
      {"date": "2026-12-03", "type": "Technical", "interviewer": "Dev Team", "notes": "Live coding, SQL joins."}]'),
(2, '2026-09-22', 'Screening', 'v2-data',    FALSE,
    '[{"date": "2026-10-08", "type": "Recruiter Call", "interviewer": "Sam Chen", "notes": "Asked about Tableau experience."}]'),
(3, '2026-10-03', 'Applied',   'v3-python',  TRUE,  NULL),
(4, '2026-10-07', 'Rejected',  'v1-web',     TRUE,  NULL),
(5, '2026-10-12', 'Withdrawn', 'v2-java',    FALSE, NULL),
(6, '2026-10-14', 'Offer',     'v3-python',  TRUE,
    '[{"date": "2026-10-21", "type": "Phone Screen", "interviewer": "Maria Lopez", "notes": "Culture fit."},
      {"date": "2026-10-28", "type": "Onsite", "interviewer": "Engineering Panel", "notes": "System design + behavioral."}]');

INSERT INTO contacts (company_id, contact_name, title, email, phone, linkedin_url, notes) VALUES
(1, 'Maria Lopez',   'Technical Recruiter',     'maria.lopez@techcorp.example.com', '305-555-0101', 'https://www.linkedin.com/in/example-maria', 'Primary recruiter for both TechCorp roles.'),
(2, 'Sam Chen',      'Talent Acquisition',      'sam.chen@dataco.example.com',      '407-555-0144', 'https://www.linkedin.com/in/example-sam',   'Prefers email over phone.'),
(3, 'Priya Natarajan','Engineering Manager',    'priya@cloudnine.example.com',      NULL,           'https://www.linkedin.com/in/example-priya', 'Met at AWS meetup.'),
(6, 'Jordan Ellis',  'University Recruiter',    'jellis@greengrid.example.com',     '954-555-0199', NULL,                                         'Career fair contact, follow up in November.');
