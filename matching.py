"""Skill-matching logic for the Job Match feature.

Kept separate from app.py so it can be unit-tested without a database.
"""

# Common spellings that should count as the same skill.
SKILL_ALIASES = {
    "js": "javascript",
    "node": "node.js",
    "nodejs": "node.js",
    "postgres": "postgresql",
    "py": "python",
    "rest": "rest apis",
    "rest api": "rest apis",
    "amazon web services": "aws",
    "mysql": "sql",
}


def normalize_skill(skill):
    """Lower-case, trim, and map aliases so 'JS ' and 'JavaScript' match."""
    key = " ".join(skill.strip().lower().split())
    return SKILL_ALIASES.get(key, key)


def parse_skills(text):
    """Turn 'Python, SQL; Flask\\nGit' into a de-duplicated list of skills."""
    if not text:
        return []
    for sep in [";", "\n", "|"]:
        text = text.replace(sep, ",")
    seen, skills = set(), []
    for raw in text.split(","):
        raw = raw.strip()
        if raw and normalize_skill(raw) not in seen:
            seen.add(normalize_skill(raw))
            skills.append(raw)
    return skills


def match_job(user_skills, required_skills):
    """Compare a user's skills to one job's required skills.

    Returns a dict with matched / missing skill lists (using the job's
    original spelling), the counts, and the match percentage.
    """
    user_set = {normalize_skill(s) for s in user_skills}
    matched = [s for s in required_skills if normalize_skill(s) in user_set]
    missing = [s for s in required_skills if normalize_skill(s) not in user_set]
    total = len(required_skills)
    percent = round(len(matched) / total * 100) if total else 0
    return {
        "matched": matched,
        "missing": missing,
        "matched_count": len(matched),
        "total": total,
        "percent": percent,
    }


def rank_jobs(user_skills, jobs, min_percent=0):
    """Score every job and return them sorted best match first.

    `jobs` is a list of dicts that each have a 'skills' list. Jobs with
    no listed skills are skipped because a percentage is meaningless.
    Ties are broken by number of matched skills, then by salary_max.
    """
    results = []
    for job in jobs:
        skills = job.get("skills") or []
        if not skills:
            continue
        score = match_job(user_skills, skills)
        if score["percent"] >= min_percent:
            results.append({**job, **score})
    results.sort(
        key=lambda r: (r["percent"], r["matched_count"], r.get("salary_max") or 0),
        reverse=True,
    )
    return results
