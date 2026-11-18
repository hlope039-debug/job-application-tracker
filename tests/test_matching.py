"""Unit tests for the Job Match algorithm (no database needed).

Run with:  python -m pytest tests
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from matching import match_job, normalize_skill, parse_skills, rank_jobs  # noqa: E402


def test_parse_skills_handles_separators_and_duplicates():
    assert parse_skills("Python, SQL; flask\nPython |  Git ") == ["Python", "SQL", "flask", "Git"]
    assert parse_skills("") == []
    assert parse_skills(None) == []


def test_normalize_skill_aliases_and_case():
    assert normalize_skill("  JS ") == "javascript"
    assert normalize_skill("JavaScript") == "javascript"
    assert normalize_skill("Rest   API") == "rest apis"


def test_spec_example():
    """The exact example from the project specification."""
    user = ["Python", "SQL", "Flask"]
    jobs = [
        {"job_title": "Data Analyst", "skills": ["Python", "SQL", "Tableau"]},
        {"job_title": "Software Developer", "skills": ["Python", "SQL", "Flask"]},
    ]
    ranked = rank_jobs(user, jobs)
    assert [r["job_title"] for r in ranked] == ["Software Developer", "Data Analyst"]
    assert ranked[0]["percent"] == 100 and ranked[0]["matched_count"] == 3
    assert ranked[1]["percent"] == 67 and ranked[1]["missing"] == ["Tableau"]


def test_match_is_case_insensitive():
    result = match_job(["python", "sql"], ["Python", "SQL", "AWS", "Docker"])
    assert result["percent"] == 50
    assert result["missing"] == ["AWS", "Docker"]


def test_min_percent_filter_and_empty_skills_skipped():
    jobs = [
        {"job_title": "A", "skills": ["Python"]},
        {"job_title": "B", "skills": ["Java", "Spring"]},
        {"job_title": "C", "skills": []},
    ]
    ranked = rank_jobs(["Python"], jobs, min_percent=50)
    assert [r["job_title"] for r in ranked] == ["A"]


def test_ties_broken_by_matched_count_then_salary():
    jobs = [
        {"job_title": "Low", "skills": ["Python", "SQL"], "salary_max": 50000},
        {"job_title": "High", "skills": ["Python", "SQL"], "salary_max": 90000},
        {"job_title": "Small", "skills": ["Python"], "salary_max": 999999},
    ]
    ranked = rank_jobs(["Python", "SQL"], jobs)
    assert [r["job_title"] for r in ranked] == ["High", "Low", "Small"]
