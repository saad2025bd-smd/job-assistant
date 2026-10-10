# Job Assistant — Semi-Automated Job Finding & Preparation (Web App)

A personal web app that helps you **find relevant jobs**, **score them against your profile**, **generate tailored cover letters**, and **track applications** — while keeping the final “Submit” decision in your hands.

## Features

- **Multi-source discovery** from free public APIs (no keys required):
  - RemoteOK
  - Remotive
  - Arbeitnow
- **Profile-based matching** (roles, skills, location/remote, salary, exclude keywords)
- **Cover letter generation** tailored to each job
- **Application notes** with talking points
- **Local tracker** (discovered → saved → prepared → applied → interview / offer / rejected)
- **Clean web UI** built with Streamlit

## Quick Start

```bash
cd job_assistant
pip install -r requirements.txt

# Edit your profile (or do it inside the app under Profile)
# nano profile.yaml

# Launch the web app
streamlit run app.py
```

Then open the URL shown in the terminal (usually http://localhost:8501).

## Pages

| Page | What you do there |
|------|-------------------|
| **Dashboard** | Overview + top matches |
| **Search Jobs** | Fetch & score new jobs from free sources |
| **My Jobs** | Browse, filter, and update status |
| **Prepare Application** | Generate cover letter + notes, open apply link, mark applied |
| **Profile** | Edit name, skills, target roles, preferences |
| **Settings** | Enable/disable sources, matching sensitivity |

## Recommended Workflow

1. Fill in your **Profile** (skills + target roles matter most).
2. Run **Search Jobs** regularly.
3. Review matches on **Dashboard** / **My Jobs**.
4. Open **Prepare Application** → generate materials → review cover letter → apply on the website.
5. Click **Mark as Applied** so your pipeline stays accurate.

## CLI still available

The original command-line tool still works:

```bash
python cli.py search
python cli.py list
python cli.py prepare <job_id>
python cli.py applied <job_id>
```

## Notes

- Uses free public feeds only (no LinkedIn/Indeed scraping by default).
- All data stays local on your machine.
- Cover letters are template + rule-based; you can later plug in an LLM for higher quality.

Good luck with the search!
