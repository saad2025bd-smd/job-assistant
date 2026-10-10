#!/usr/bin/env python3
"""
Job Assistant — Semi-automated Job Finding & Preparation Web App
"""
import streamlit as st
from pathlib import Path
from typing import Optional, Dict, Any, List
import yaml
from datetime import datetime

import remoteok, remotive, arbeitnow
from base import Job
from matcher import rank_jobs, score_job
from generator import generate_cover_letter, generate_application_notes, save_materials
from db import JobDB

ROOT = Path(__file__).parent

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Job Assistant",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_yaml(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def load_profile() -> dict:
    path = ROOT / "profile.yaml"
    if not path.exists():
        path = ROOT / "profile.example.yaml"
    return load_yaml(path)


def load_config() -> dict:
    return load_yaml(ROOT / "config.yaml")


def get_db() -> JobDB:
    config = load_config()
    db_path = config.get("settings", {}).get("database", "data/jobs.json")
    return JobDB(str(ROOT / db_path))


def score_color(score: float) -> str:
    if score >= 0.7:
        return "🟢"
    if score >= 0.45:
        return "🟡"
    return "🟠"


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
def render_sidebar():
    st.sidebar.title("💼 Job Assistant")
    st.sidebar.caption("Semi-automated job finding & prep")

    page = st.sidebar.radio(
        "Navigation",
        ["Dashboard", "Search Jobs", "My Jobs", "Prepare Application", "Profile", "Settings"],
        label_visibility="collapsed",
    )

    st.sidebar.divider()
    db = get_db()
    stats = db.stats()
    if stats:
        st.sidebar.markdown("**Pipeline**")
        for status, count in sorted(stats.items(), key=lambda x: -x[1]):
            st.sidebar.write(f"{status}: **{count}**")
    else:
        st.sidebar.info("No jobs tracked yet.\nRun a search to get started.")

    return page


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
def page_dashboard():
    st.header("Dashboard")
    db = get_db()
    stats = db.stats()
    jobs = db.list_jobs(limit=200)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total tracked", len(jobs))
    col2.metric("Discovered", stats.get("discovered", 0))
    col3.metric("Prepared", stats.get("prepared", 0))
    col4.metric("Applied", stats.get("applied", 0))

    st.divider()

    if not jobs:
        st.info("No jobs yet. Go to **Search Jobs** to find matches for your profile.")
        return

    st.subheader("Top matches")
    top = sorted(jobs, key=lambda j: j.get("match_score") or 0, reverse=True)[:10]
    for j in top:
        score = j.get("match_score") or 0
        with st.container():
            c1, c2, c3 = st.columns([0.08, 0.62, 0.30])
            c1.write(f"{score_color(score)} **{score:.0%}**")
            c2.markdown(f"**{j['title']}**  \n{j['company']} · {j.get('location') or '—'}")
            c3.markdown(f"`{j['status']}` · {j['source']}  \n[Open ↗]({j['url']})")
            st.divider()


def page_search():
    st.header("Search Jobs")
    profile = load_profile()
    config = load_config()
    settings = config.get("settings", {})

    col1, col2, col3 = st.columns(3)
    max_jobs = col1.slider("Max jobs per source", 10, 50, 20, 5)
    min_score = col2.slider("Min match score", 0.15, 0.70, float(settings.get("min_match_score", 0.35)), 0.05)
    run = col3.button("🔍 Search now", type="primary", use_container_width=True)

    if not run:
        st.info("Adjust filters and click **Search now**. Jobs are fetched from free public APIs (RemoteOK, Remotive, Arbeitnow).")
        return

    all_jobs: List[Job] = []
    progress = st.progress(0, text="Starting...")

    # RemoteOK
    progress.progress(10, text="Fetching RemoteOK...")
    if config.get("sources", {}).get("remoteok", {}).get("enabled", True):
        jobs = remoteok.fetch_jobs(max_jobs=max_jobs)
        all_jobs.extend(jobs)
        st.write(f"RemoteOK → {len(jobs)} jobs")

    # Remotive
    progress.progress(40, text="Fetching Remotive...")
    if config.get("sources", {}).get("remotive", {}).get("enabled", True):
        search_terms = profile.get("target_roles", ["software"])[:2]
        jobs = []
        for term in search_terms or [None]:
            jobs.extend(remotive.fetch_jobs(search=term, max_jobs=max_jobs // 2))
        seen = set()
        unique = []
        for j in jobs:
            if j.id not in seen:
                seen.add(j.id)
                unique.append(j)
        all_jobs.extend(unique)
        st.write(f"Remotive → {len(unique)} jobs")

    # Arbeitnow
    progress.progress(70, text="Fetching Arbeitnow...")
    if config.get("sources", {}).get("arbeitnow", {}).get("enabled", True):
        jobs = arbeitnow.fetch_jobs(max_jobs=max_jobs)
        all_jobs.extend(jobs)
        st.write(f"Arbeitnow → {len(jobs)} jobs")

    # Dedup
    unique_map = {}
    for j in all_jobs:
        key = (j.title.lower().strip(), j.company.lower().strip())
        if key not in unique_map:
            unique_map[key] = j
    all_jobs = list(unique_map.values())

    progress.progress(85, text="Scoring against your profile...")
    ranked = rank_jobs(all_jobs, profile, min_score=min_score)

    db = get_db()
    for job, score, _ in ranked:
        db.upsert_job(job, score=score, status="discovered", save=False)
    db.save()

    progress.progress(100, text="Done")
    st.success(f"Found **{len(all_jobs)}** unique jobs · **{len(ranked)}** match your profile (≥ {min_score:.0%})")

    if ranked:
        st.subheader("Matching jobs")
        rows = []
        for job, score, breakdown in ranked[:40]:
            rows.append({
                "Score": f"{score:.0%}",
                "Title": job.title,
                "Company": job.company,
                "Location": job.location or "—",
                "Source": job.source,
                "ID": job.id,
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.caption("Go to **My Jobs** or **Prepare Application** to work with these results.")


def page_my_jobs():
    st.header("My Jobs")
    db = get_db()

    status_filter = st.selectbox(
        "Filter by status",
        ["All", "discovered", "saved", "prepared", "applied", "interview", "rejected", "offer"],
    )
    jobs = db.list_jobs(
        status=None if status_filter == "All" else status_filter,
        limit=100,
    )

    if not jobs:
        st.info("No jobs in this view. Run a search first.")
        return

    st.write(f"**{len(jobs)}** jobs")

    for j in jobs:
        score = j.get("match_score") or 0
        with st.expander(
            f"{score_color(score)} {score:.0%}  ·  {j['title']} @ {j['company']}  ·  `{j['status']}`",
            expanded=False,
        ):
            c1, c2 = st.columns([0.7, 0.3])
            with c1:
                st.markdown(f"**Location:** {j.get('location') or '—'}")
                st.markdown(f"**Source:** {j['source']}")
                st.markdown(f"[Open job posting ↗]({j['url']})")
                if j.get("description"):
                    st.markdown("**Description (truncated)**")
                    st.write(j["description"][:800] + ("…" if len(j.get("description", "")) > 800 else ""))
            with c2:
                st.markdown(f"**ID:** `{j['id']}`")
                new_status = st.selectbox(
                    "Update status",
                    ["discovered", "saved", "prepared", "applied", "interview", "rejected", "offer"],
                    index=["discovered", "saved", "prepared", "applied", "interview", "rejected", "offer"].index(
                        j.get("status", "discovered")
                    ),
                    key=f"status_{j['id']}",
                )
                if st.button("Save status", key=f"save_{j['id']}"):
                    if new_status == "applied":
                        db.mark_applied(j["id"])
                    else:
                        db.update_status(j["id"], new_status)
                    st.success(f"Updated → {new_status}")
                    st.rerun()

                if st.button("Prepare materials", key=f"prep_{j['id']}"):
                    st.session_state["prepare_job_id"] = j["id"]
                    st.switch_page  # fallback: store and show message
                    st.info(f"Go to **Prepare Application** and select job `{j['id']}`")


def page_prepare():
    st.header("Prepare Application")
    db = get_db()
    jobs = db.list_jobs(limit=100)

    if not jobs:
        st.info("No jobs available. Run a search first.")
        return

    # Build options
    options = {
        f"{(j.get('match_score') or 0):.0%} · {j['title'][:50]} @ {j['company']}": j["id"]
        for j in jobs
    }
    default_id = st.session_state.get("prepare_job_id")
    default_label = None
    if default_id:
        for label, jid in options.items():
            if jid == default_id:
                default_label = label
                break

    labels = list(options.keys())
    index = labels.index(default_label) if default_label in labels else 0
    selected_label = st.selectbox("Select a job", labels, index=index)
    job_id = options[selected_label]
    job_row = db.get_job(job_id)

    if not job_row:
        st.error("Job not found.")
        return

    st.markdown(f"**{job_row['title']}** at **{job_row['company']}**")
    st.markdown(f"[{job_row['url']}]({job_row['url']})")
    st.caption(f"Score: {(job_row.get('match_score') or 0):.0%} · Status: {job_row.get('status')}")

    if st.button("✨ Generate cover letter & notes", type="primary"):
        profile = load_profile()
        job = Job(
            id=job_row["id"],
            title=job_row["title"],
            company=job_row["company"],
            url=job_row["url"],
            source=job_row["source"],
            description=job_row.get("description") or "",
            location=job_row.get("location") or "",
            tags=job_row.get("tags") or [],
        )
        score = job_row.get("match_score") or 0.0
        _, breakdown = score_job(job, profile)

        cover = generate_cover_letter(job, profile)
        notes = generate_application_notes(job, profile, score, breakdown)

        config = load_config()
        out_dir = ROOT / config.get("settings", {}).get("generated_dir", "generated")
        folder = save_materials(job, cover, notes, out_dir)

        db.update_status(job_id, "prepared", notes=notes[:2000], cover_letter_path=str(folder))

        st.session_state["last_cover"] = cover
        st.session_state["last_notes"] = notes
        st.session_state["last_folder"] = str(folder)
        st.session_state["last_url"] = job.url
        st.success(f"Materials saved to `{folder.name}`")

    if "last_cover" in st.session_state:
        st.divider()
        st.subheader("Cover letter")
        st.text_area("Edit if needed", value=st.session_state["last_cover"], height=320, key="cover_edit")

        st.subheader("Application notes")
        st.markdown(st.session_state["last_notes"])

        c1, c2, c3 = st.columns(3)
        with c1:
            st.link_button("Open job posting ↗", st.session_state.get("last_url", "#"), use_container_width=True)
        with c2:
            if st.button("Mark as Applied", type="primary", use_container_width=True):
                db.mark_applied(job_id)
                st.success("Marked as applied. Good luck!")
                st.rerun()
        with c3:
            st.caption(f"Files: {st.session_state.get('last_folder', '')}")


def page_profile():
    st.header("Your Profile")
    st.caption("This drives matching quality and cover letter content. Keep it up to date.")

    profile = load_profile()
    personal = profile.get("personal", {})
    skills = profile.get("skills", {})
    prefs = profile.get("preferences", {})

    with st.form("profile_form"):
        st.subheader("Personal")
        c1, c2 = st.columns(2)
        full_name = c1.text_input("Full name", personal.get("full_name", ""))
        email = c2.text_input("Email", personal.get("email", ""))
        phone = c1.text_input("Phone", personal.get("phone", ""))
        location = c2.text_input("Location", personal.get("location", ""))
        linkedin = c1.text_input("LinkedIn", personal.get("linkedin", ""))
        github = c2.text_input("GitHub", personal.get("github", ""))
        portfolio = st.text_input("Portfolio", personal.get("portfolio", ""))

        st.subheader("Target roles")
        roles_text = st.text_area(
            "One role per line",
            value="\n".join(profile.get("target_roles", [])),
            height=100,
        )

        st.subheader("Skills")
        c1, c2 = st.columns(2)
        languages = c1.text_input("Languages (comma-separated)", ", ".join(skills.get("languages", [])))
        frameworks = c2.text_input("Frameworks", ", ".join(skills.get("frameworks", [])))
        tools = c1.text_input("Tools", ", ".join(skills.get("tools", [])))
        soft = c2.text_input("Soft skills", ", ".join(skills.get("soft_skills", [])))

        st.subheader("Experience summary")
        experience = st.text_area("Short professional summary", profile.get("experience_summary", ""), height=120)

        st.subheader("Preferences")
        c1, c2, c3 = st.columns(3)
        remote = c1.selectbox("Remote preference", [True, False, "hybrid"], index=0 if prefs.get("remote") is True else (1 if prefs.get("remote") is False else 2))
        salary_min = c2.number_input("Min salary (USD)", value=int(prefs.get("salary_min") or 0), step=5000)
        locations = c3.text_input("Preferred locations (comma-separated)", ", ".join(prefs.get("locations", [])))
        exclude = st.text_input("Exclude keywords (comma-separated)", ", ".join(prefs.get("exclude_keywords", [])))

        submitted = st.form_submit_button("💾 Save profile", type="primary")

        if submitted:
            new_profile = {
                "personal": {
                    "full_name": full_name,
                    "email": email,
                    "phone": phone,
                    "location": location,
                    "linkedin": linkedin,
                    "portfolio": portfolio,
                    "github": github,
                },
                "target_roles": [r.strip() for r in roles_text.splitlines() if r.strip()],
                "skills": {
                    "languages": [s.strip() for s in languages.split(",") if s.strip()],
                    "frameworks": [s.strip() for s in frameworks.split(",") if s.strip()],
                    "tools": [s.strip() for s in tools.split(",") if s.strip()],
                    "soft_skills": [s.strip() for s in soft.split(",") if s.strip()],
                },
                "experience_summary": experience,
                "preferences": {
                    "remote": remote,
                    "locations": [s.strip() for s in locations.split(",") if s.strip()],
                    "salary_min": salary_min if salary_min > 0 else None,
                    "salary_currency": "USD",
                    "experience_level": prefs.get("experience_level", "mid"),
                    "job_types": prefs.get("job_types", ["full-time"]),
                    "exclude_keywords": [s.strip() for s in exclude.split(",") if s.strip()],
                },
                "documents": profile.get("documents", {}),
                "cover_letter": profile.get("cover_letter", {"tone": "professional", "length": "medium", "highlight_achievements": True}),
            }
            save_yaml(ROOT / "profile.yaml", new_profile)
            st.success("Profile saved.")


def page_settings():
    st.header("Settings")
    config = load_config()
    sources = config.get("sources", {})
    settings = config.get("settings", {})

    st.subheader("Job sources")
    remoteok_on = st.checkbox("RemoteOK", value=sources.get("remoteok", {}).get("enabled", True))
    remotive_on = st.checkbox("Remotive", value=sources.get("remotive", {}).get("enabled", True))
    arbeitnow_on = st.checkbox("Arbeitnow", value=sources.get("arbeitnow", {}).get("enabled", True))

    st.subheader("Matching")
    min_score = st.slider("Default min match score", 0.15, 0.70, float(settings.get("min_match_score", 0.35)), 0.05)

    if st.button("Save settings", type="primary"):
        config["sources"] = {
            "remoteok": {"enabled": remoteok_on, "url": "https://remoteok.com/api"},
            "remotive": {"enabled": remotive_on, "url": "https://remotive.com/api/remote-jobs"},
            "arbeitnow": {"enabled": arbeitnow_on, "url": "https://www.arbeitnow.com/api/job-board-api"},
        }
        config["settings"]["min_match_score"] = min_score
        save_yaml(ROOT / "config.yaml", config)
        st.success("Settings saved.")

    st.divider()
    st.subheader("About")
    st.markdown(
        """
        **Job Assistant** helps you find relevant roles, score them against your profile,
        generate tailored cover letters, and track applications — while keeping the final
        submit decision in your hands.

        Data stays local on your machine. Sources used are free public feeds.
        """
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    page = render_sidebar()

    if page == "Dashboard":
        page_dashboard()
    elif page == "Search Jobs":
        page_search()
    elif page == "My Jobs":
        page_my_jobs()
    elif page == "Prepare Application":
        page_prepare()
    elif page == "Profile":
        page_profile()
    elif page == "Settings":
        page_settings()


if __name__ == "__main__":
    main()
