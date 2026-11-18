# AI Usage Documentation

> **To do before submitting:** the sections marked ✏️ must be written in your own
> words. They describe *your* experience (what you changed, what you learned), so
> only you can write them honestly. Delete this note when done.

## Tools Used

- **Claude (Anthropic)** – generated the initial version of the whole application
  from the project specification: database schema and sample data, Flask routes,
  Jinja2 templates, CSS, the skill-matching algorithm, tests, and the README.
- ✏️ *Add any other tools you used (ChatGPT, Gemini, GitHub Copilot, etc.) and what for.*

## Key Prompts

1. "Help me complete this project according to the guidelines." – with the
   `Project_Specification.pdf` attached. This produced the first full version.
2. ✏️ *Add the follow-up prompts you use while testing, customizing, and debugging,
   for example:*
   - "Explain how the `rank_jobs` function sorts ties."
   - "Why does `ON DELETE CASCADE` remove the applications when I delete a company?"
   - "I get `Access denied for user 'root'@'localhost'` – how do I fix it?"

## What Worked Well

- **Working from the spec.** Given the PDF, the AI produced every required page,
  all four tables with the exact columns, and the file layout the spec asked for.
- **Boilerplate CRUD.** The 20 routes for four tables follow one consistent
  pattern (list → detail → form → validate → save), which would have been slow and
  repetitive to type by hand.
- **Job Match algorithm.** The matching logic was put in its own module
  (`matching.py`) with unit tests, including a test that reproduces the exact
  example from the spec (100% / 67% with "Missing: Tableau").
- **Validation.** Server-side checks for every form (required fields, URL/email
  formats, salary range, no future dates, duplicate company names) plus a CHECK
  constraint in the database.
- **Testing.** A pytest suite (30 tests) that loads every page and runs a full
  create → update → delete cycle on all four tables.

## Problems Found During AI-Assisted Development

These came up while the AI was testing its own code, before I received it:

- **MySQL vs. MariaDB JSON syntax.** The `requirements->'$.skills'` shortcut only
  works in MySQL, so queries were switched to `JSON_EXTRACT(requirements, '$.skills')`,
  which works in both.
- **Bootstrap from a CDN failed offline.** The pages loaded unstyled when the CDN
  could not be reached, so Bootstrap and its icons were bundled into
  `static/vendor/` so the instructor can run the app without internet access.
- **Navigation highlighting bug.** The first version did not highlight the
  "Companies" tab on company detail pages (the code guessed the prefix by
  removing an "s"). It was replaced with an explicit mapping in `app.py`.

## What I Modified

✏️ *List the changes you make to the AI's code after reviewing it. Be specific.
Examples of the kind of thing to write (only include what you actually did):*

- *Changed the sample data in `schema.sql` to companies/jobs I'm actually interested in.*
- *Added/removed a dashboard statistic.*
- *Changed colors or layout in `style.css`.*
- *Fixed a bug I found while testing (describe it).*
- *Changed a validation rule (describe why).*

## Lessons Learned

✏️ *Write 3–5 points in your own words. Questions to think about:*

- *Did the AI-generated code run the first time on your machine? What did you have to fix?*
- *Which parts did you have to study to understand well enough to explain in your video?*
- *Where would you trust AI output, and where would you check it carefully?*
- *How did giving the AI the full spec compare to asking smaller questions?*
