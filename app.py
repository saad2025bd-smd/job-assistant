#!/usr/bin/env python3
"""
Job Assistant — Friendly AI-powered job finding & application prep
"""
import streamlit as st
from pathlib import Path
from typing import Optional, Dict, Any, List
import yaml
import urllib.parse
from datetime import datetime

import remoteok, remotive, arbeitnow, jobicy, himalayas
from base import Job
from matcher import rank_jobs, score_job
from generator import generate_cover_letter, generate_application_notes, save_materials
from db import JobDB
from cv_parser import extract_text_from_upload, analyze_cv, summarize_cv_for_profile

ROOT = Path(__file__).parent

st.set_page_config(
    page_title="Job Assistant",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.2rem; }
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 12px 16px;
    }
</style>
""", unsafe_allow_html=True)


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


def score_label(score: float) -> str:
    pct = f"{score:.0%}"
    if score >= 0.7:
        return f"🟢 {pct}"
    if score >= 0.45:
        return f"🟡 {pct}"
    return f"🟠 {pct}"




def google_jobs_url(query: str) -> str:
    """Build a Google search URL biased toward job listings."""
    q = query.strip()
    # ibp=htl;jobs opens Google Jobs UI when available
    params = {"q": q, "ibp": "htl;jobs"}
    return "https://www.google.com/search?" + urllib.parse.urlencode(params)


def google_search_url(query: str) -> str:
    return "https://www.google.com/search?" + urllib.parse.urlencode({"q": query})


def related_google_queries(profile: dict, job_title: str = "", company: str = "") -> list:
    """Suggest positive, related Google searches."""
    roles = profile.get("target_roles") or []
    prefs = profile.get("preferences") or {}
    locs = prefs.get("locations") or ["Remote"]
    remote = prefs.get("remote", True)
    queries = []

    def add(label, q):
        queries.append((label, q))

    if job_title and company:
        add(f"Similar to {job_title[:40]}", f"{job_title} jobs remote")
        add(f"More at {company}", f"{company} careers OR jobs hiring")
        add(f"{job_title} hiring now", f"{job_title} hiring now remote")

    for role in roles[:4]:
        loc = "remote" if remote else (locs[0] if locs else "")
        add(f"{role} roles", f"{role} {loc} jobs".strip())
        add(f"{role} near me / open", f"{role} jobs hiring")

    if remote:
        add("Remote tech jobs", "remote software OR developer OR engineer jobs")
    # dedupe by query
    seen = set()
    out = []
    for label, q in queries:
        key = q.lower()
        if key not in seen:
            seen.add(key)
            out.append((label, q))
    return out[:10]

def profile_completeness(profile: dict):
    checks = []
    personal = profile.get("personal", {})
    checks.append(("Name", bool(personal.get("full_name") and personal.get("full_name") != "Your Full Name")))
    checks.append(("Target roles", bool(profile.get("target_roles"))))
    skills = profile.get("skills", {})
    has_skills = any(skills.get(k) for k in ("languages", "frameworks", "tools"))
    checks.append(("Skills", has_skills))
    checks.append(("Experience summary", bool((profile.get("experience_summary") or "").strip())))
    docs = profile.get("documents") or {}
    checks.append(("CV uploaded", bool(docs.get("cv_text"))))
    done = sum(1 for _, ok in checks if ok)
    return done, len(checks), checks


def render_sidebar():
    st.sidebar.markdown("## 💼 Job Assistant")
    st.sidebar.caption("Find roles · Match your profile · Prep applications")
    page = st.sidebar.radio(
        "Go to",
        ["Home", "Search Jobs", "My Jobs", "Prepare Application", "Profile & CV", "Settings"],
        label_visibility="collapsed",
    )
    st.sidebar.divider()
    db = get_db()
    stats = db.stats()
    profile = load_profile()
    done, total, _ = profile_completeness(profile)
    st.sidebar.markdown("**Your pipeline**")
    if stats:
        for status, count in sorted(stats.items(), key=lambda x: -x[1]):
            st.sidebar.write(f"• {status}: **{count}**")
    else:
        st.sidebar.write("_No jobs yet — run a search_")
    st.sidebar.markdown(f"**Profile** {done}/{total} complete")
    st.sidebar.progress(done / total if total else 0)
    st.sidebar.divider()
    st.sidebar.caption(
        "Sources: RemoteOK · Remotive · Arbeitnow · Jobicy · Himalayas  \n"
        "Free public feeds only (no LinkedIn/Indeed scraping)."
    )
    return page


def page_home():
    st.markdown("### Welcome — let's get you hired")
    profile = load_profile()
    gq = related_google_queries(profile)
    if gq:
        st.markdown("##### Quick Google job search")
        cols = st.columns(min(4, len(gq)))
        for i, (label, q) in enumerate(gq[:4]):
            with cols[i]:
                st.link_button(f"🔎 {label[:28]}", google_jobs_url(q), use_container_width=True)
    done, total, checks = profile_completeness(profile)
    db = get_db()
    stats = db.stats()
    jobs = db.list_jobs(limit=200)

    st.markdown("#### Your path")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown("**1. Profile & CV**")
        st.write("Tell the app who you are and upload your resume.")
        st.success("Ready") if done >= total else st.warning(f"{done}/{total} done")
    with c2:
        st.markdown("**2. Search**")
        st.write("Pull jobs from free remote boards and score them.")
        st.info(f"{stats.get('discovered', 0)} discovered")
    with c3:
        st.markdown("**3. Prepare**")
        st.write("Generate a tailored cover letter for each role.")
        st.info(f"{stats.get('prepared', 0)} prepared")
    with c4:
        st.markdown("**4. Apply**")
        st.write("You submit — then track status here.")
        st.info(f"{stats.get('applied', 0)} applied")

    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Tracked jobs", len(jobs))
    m2.metric("Discovered", stats.get("discovered", 0))
    m3.metric("Prepared", stats.get("prepared", 0))
    m4.metric("Applied", stats.get("applied", 0))

    if done < total:
        missing = [name for name, ok in checks if not ok]
        st.info("Start on **Profile & CV** — matching quality depends on it. Missing: " + ", ".join(missing))

    st.subheader("Top matches for you")
    if not jobs:
        st.write("No jobs yet. Complete your profile, then go to **Search Jobs**.")
        return
    top = sorted(jobs, key=lambda j: j.get("match_score") or 0, reverse=True)[:8]
    for j in top:
        score = j.get("match_score") or 0
        a, b, c = st.columns([0.12, 0.58, 0.30])
        a.markdown(f"### {score_label(score)}")
        b.markdown(f"**{j['title']}**  \n{j['company']} · {j.get('location') or '—'}")
        c.markdown(f"`{j['status']}` · {j['source']}  \n[Open posting ↗]({j['url']})")
        st.divider()


def _fetch_remotive(profile, max_jobs):
    terms = (profile.get("target_roles") or ["software"])[:2]
    jobs = []
    for term in terms or [None]:
        jobs.extend(remotive.fetch_jobs(search=term, max_jobs=max_jobs // 2))
    seen, unique = set(), []
    for j in jobs:
        if j.id not in seen:
            seen.add(j.id)
            unique.append(j)
    return unique


def _fetch_jobicy(profile, max_jobs):
    terms = profile.get("target_roles") or []
    if terms:
        jobs = jobicy.fetch_jobs(search=terms[0].split()[0], max_jobs=max_jobs // 2)
        jobs += jobicy.fetch_jobs(search=None, max_jobs=max_jobs // 2)
    else:
        jobs = jobicy.fetch_jobs(max_jobs=max_jobs)
    seen, unique = set(), []
    for j in jobs:
        if j.id not in seen:
            seen.add(j.id)
            unique.append(j)
    return unique[:max_jobs]


def _fetch_himalayas(profile, max_jobs):
    terms = profile.get("target_roles") or []
    if terms:
        jobs = himalayas.fetch_jobs(search=terms[0], max_jobs=max_jobs)
        if len(jobs) < max_jobs // 2:
            jobs += himalayas.fetch_jobs(search=None, max_jobs=max_jobs)
    else:
        jobs = himalayas.fetch_jobs(max_jobs=max_jobs)
    seen, unique = set(), []
    for j in jobs:
        if j.id not in seen:
            seen.add(j.id)
            unique.append(j)
    return unique[:max_jobs]


def page_search():
    st.markdown("### Search jobs")
    st.caption(
        "We search **free public remote job boards**, and also give you one-click **Google Jobs** searches "
        "so you can reach LinkedIn, Indeed, Glassdoor, and company career pages."
    )
    profile = load_profile()
    st.markdown("#### Also search Google")
    st.caption(
        "Opens Google in a new tab (Jobs view when available). From there you can open any listing on LinkedIn, Indeed, etc."
    )
    gq = related_google_queries(profile)
    if gq:
        cols = st.columns(2)
        for i, (label, q) in enumerate(gq[:8]):
            with cols[i % 2]:
                st.link_button(f"🔎 {label}", google_jobs_url(q), use_container_width=True)
    else:
        st.info("Add target roles in **Profile & CV** to personalize Google searches.")
    st.divider()
    config = load_config()
    settings = config.get("settings", {})

    with st.expander("How matching works"):
        st.markdown(
            "1. Fetch from RemoteOK, Remotive, Arbeitnow, **Jobicy**, **Himalayas**.\n"
            "2. Score each job against your roles, skills, CV, location, salary.\n"
            "3. Keep jobs above your minimum score.\n"
            "4. You review, generate a letter, and apply yourself."
        )

    c1, c2, c3 = st.columns(3)
    max_jobs = c1.slider("Jobs per source", 10, 50, 25, 5)
    min_score = c2.slider("Minimum match score", 0.15, 0.70, float(settings.get("min_match_score", 0.35)), 0.05)
    run = c3.button("Search all sources", type="primary", use_container_width=True)

    if not run:
        roles = profile.get("target_roles") or []
        if roles:
            st.write("Target roles: " + ", ".join(f"**{r}**" for r in roles[:6]))
        else:
            st.warning("Add target roles under **Profile & CV** for better results.")
        return

    all_jobs: List[Job] = []
    progress = st.progress(0, text="Starting…")
    log = st.empty()
    lines = []

    def note(msg):
        lines.append(msg)
        log.markdown("  \n".join(lines))

    plan = [
        ("RemoteOK", 0.12, lambda: remoteok.fetch_jobs(max_jobs=max_jobs)),
        ("Remotive", 0.28, lambda: _fetch_remotive(profile, max_jobs)),
        ("Arbeitnow", 0.44, lambda: arbeitnow.fetch_jobs(max_jobs=max_jobs)),
        ("Jobicy", 0.64, lambda: _fetch_jobicy(profile, max_jobs)),
        ("Himalayas", 0.84, lambda: _fetch_himalayas(profile, max_jobs)),
    ]
    for name, p, fn in plan:
        progress.progress(p, text=f"Fetching {name}…")
        try:
            batch = fn()
            all_jobs.extend(batch)
            note(f"✓ **{name}** → {len(batch)} jobs")
        except Exception as e:
            note(f"✗ **{name}** → {e}")

    unique_map = {}
    for j in all_jobs:
        key = (j.title.lower().strip(), j.company.lower().strip())
        if key not in unique_map:
            unique_map[key] = j
    all_jobs = list(unique_map.values())

    progress.progress(0.92, text="Scoring against your profile & CV…")
    ranked = rank_jobs(all_jobs, profile, min_score=min_score)
    db = get_db()
    for job, score, _ in ranked:
        db.upsert_job(job, score=score, status="discovered", save=False)
    db.save()
    progress.progress(1.0, text="Done")
    st.success(f"Found **{len(all_jobs)}** unique jobs · **{len(ranked)}** match you (≥ {min_score:.0%})")

    if ranked:
        st.subheader("Best matches")
        rows = [{
            "Match": f"{score:.0%}",
            "Title": job.title[:60],
            "Company": job.company[:30],
            "Location": (job.location or "—")[:28],
            "Source": job.source,
            "ID": job.id,
        } for job, score, _ in ranked[:40]]
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.caption("Next: **My Jobs** or **Prepare Application**.")


def page_my_jobs():
    st.markdown("### My jobs")
    st.caption("Track every role from discovery to offer.")
    db = get_db()
    status_filter = st.selectbox(
        "Filter",
        ["All", "discovered", "saved", "prepared", "applied", "interview", "rejected", "offer"],
    )
    jobs = db.list_jobs(status=None if status_filter == "All" else status_filter, limit=100)
    if not jobs:
        st.info("No jobs yet. Run **Search Jobs** first.")
        return
    st.write(f"**{len(jobs)}** jobs")
    for j in jobs:
        score = j.get("match_score") or 0
        with st.expander(f"{score_label(score)}  ·  {j['title']} @ {j['company']}  ·  `{j['status']}`"):
            c1, c2 = st.columns([0.68, 0.32])
            with c1:
                st.markdown(f"**Location:** {j.get('location') or '—'}")
                st.markdown(f"**Source:** {j['source']}")
                st.markdown(f"[Open job posting ↗]({j['url']})")
                if j.get("description"):
                    st.write(j["description"][:700] + ("…" if len(j.get("description", "")) > 700 else ""))
            with c2:
                st.caption(f"ID: `{j['id']}`")
                opts = ["discovered", "saved", "prepared", "applied", "interview", "rejected", "offer"]
                cur = j.get("status", "discovered")
                idx = opts.index(cur) if cur in opts else 0
                new_status = st.selectbox("Status", opts, index=idx, key=f"st_{j['id']}")
                if st.button("Update", key=f"up_{j['id']}"):
                    if new_status == "applied":
                        db.mark_applied(j["id"])
                    else:
                        db.update_status(j["id"], new_status)
                    st.success(f"→ {new_status}")
                    st.rerun()
                if st.button("Prepare letter", key=f"pr_{j['id']}"):
                    st.session_state["prepare_job_id"] = j["id"]
                    st.info("Open **Prepare Application** — job will be pre-selected.")


def page_prepare():
    st.markdown("### Prepare application")
    st.caption("Tailored cover letter from your profile + CV + job description. You always submit.")
    db = get_db()
    jobs = db.list_jobs(limit=100)
    if not jobs:
        st.info("No jobs available. Run a search first.")
        return
    options = {f"{(j.get('match_score') or 0):.0%} · {j['title'][:48]} @ {j['company']}": j["id"] for j in jobs}
    default_id = st.session_state.get("prepare_job_id")
    labels = list(options.keys())
    index = 0
    if default_id:
        for i, jid in enumerate(options.values()):
            if jid == default_id:
                index = i
                break
    selected_label = st.selectbox("Choose a job", labels, index=index)
    job_id = options[selected_label]
    job_row = db.get_job(job_id)
    if not job_row:
        st.error("Job not found.")
        return
    st.markdown(f"#### {job_row['title']}")
    st.markdown(f"**{job_row['company']}** · {job_row.get('location') or '—'} · match {(job_row.get('match_score') or 0):.0%}")
    st.markdown(f"[Open original posting ↗]({job_row['url']})")

    profile_for_g = load_profile()
    rel = related_google_queries(profile_for_g, job_title=job_row["title"], company=job_row["company"])
    if rel:
        st.markdown("**Related Google searches**")
        gc1, gc2 = st.columns(2)
        for i, (label, q) in enumerate(rel[:4]):
            with (gc1 if i % 2 == 0 else gc2):
                st.link_button(f"🔎 {label}", google_jobs_url(q), use_container_width=True)

    if st.button("Generate tailored cover letter", type="primary"):
        profile = load_profile()
        job = Job(
            id=job_row["id"], title=job_row["title"], company=job_row["company"],
            url=job_row["url"], source=job_row["source"],
            description=job_row.get("description") or "", location=job_row.get("location") or "",
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
        st.session_state["last_url"] = job.url
        st.success("Cover letter ready — review below.")

    if "last_cover" in st.session_state:
        st.divider()
        st.markdown("#### Cover letter")
        st.text_area("Edit before you apply", value=st.session_state["last_cover"], height=340, key="cover_edit")
        st.markdown("#### Prep notes")
        st.markdown(st.session_state["last_notes"])
        b1, b2 = st.columns(2)
        with b1:
            st.link_button("Open job posting", st.session_state.get("last_url", "#"), use_container_width=True)
        with b2:
            if st.button("Mark as Applied", type="primary", use_container_width=True):
                db.mark_applied(job_id)
                st.success("Logged as applied. Good luck!")
                st.rerun()


def page_profile():
    st.markdown("### Profile & CV")
    st.caption("The more complete this is, the smarter matching and letters become.")
    profile = load_profile()
    personal = profile.get("personal", {})
    skills = profile.get("skills", {})
    prefs = profile.get("preferences", {})
    documents = profile.get("documents", {}) or {}
    done, total, checks = profile_completeness(profile)
    st.progress(done / total if total else 0, text=f"Profile {done}/{total} complete")

    st.markdown("#### Resume / CV")
    up_col, info_col = st.columns([0.55, 0.45])
    with up_col:
        uploaded = st.file_uploader("Upload PDF, Word (.docx), or TXT", type=["pdf", "docx", "txt", "md"])
        if uploaded is not None:
            with st.spinner("Reading your CV…"):
                cv_text, ftype = extract_text_from_upload(uploaded)
            if not cv_text or cv_text.startswith("["):
                st.error(f"Could not read file. {cv_text[:150] if cv_text else ''}")
            else:
                analysis = analyze_cv(cv_text)
                st.success(f"Extracted **{analysis['word_count']} words** ({ftype.upper()})")
                if analysis["skills_found"]:
                    st.write("**Skills found:** " + ", ".join(analysis["skills_found"][:30]))
                st.session_state["pending_cv_text"] = cv_text
                st.session_state["pending_cv_skills"] = analysis["skills_found"]
                st.session_state["pending_cv_name"] = uploaded.name
                with st.expander("Preview text"):
                    st.text(cv_text[:3500] + ("…" if len(cv_text) > 3500 else ""))
    with info_col:
        if documents.get("cv_text"):
            st.success(f"Saved: **{documents.get('cv_filename', 'file')}** · {documents.get('cv_word_count', '?')} words")
            if documents.get("cv_skills"):
                st.caption(", ".join(documents.get("cv_skills")[:18]))
            if st.button("Remove CV"):
                profile["documents"] = {}
                save_yaml(ROOT / "profile.yaml", profile)
                st.rerun()
        elif st.session_state.get("pending_cv_text"):
            st.warning("CV ready — click **Save profile**.")
        else:
            st.info("No CV yet. Upload for stronger matching.")

    st.divider()
    with st.form("profile_form"):
        st.markdown("#### Personal")
        c1, c2 = st.columns(2)
        full_name = c1.text_input("Full name", personal.get("full_name", ""))
        email = c2.text_input("Email", personal.get("email", ""))
        phone = c1.text_input("Phone", personal.get("phone", ""))
        location = c2.text_input("Location", personal.get("location", ""))
        linkedin = c1.text_input("LinkedIn URL", personal.get("linkedin", ""))
        github = c2.text_input("GitHub URL", personal.get("github", ""))
        portfolio = st.text_input("Portfolio", personal.get("portfolio", ""))

        st.markdown("#### What you want")
        roles_text = st.text_area("Target job titles (one per line)", value="\n".join(profile.get("target_roles", [])), height=100)

        st.markdown("#### Skills")
        c1, c2 = st.columns(2)
        languages = c1.text_input("Languages", ", ".join(skills.get("languages", [])))
        frameworks = c2.text_input("Frameworks", ", ".join(skills.get("frameworks", [])))
        tools = c1.text_input("Tools / platforms", ", ".join(skills.get("tools", [])))
        soft = c2.text_input("Soft skills", ", ".join(skills.get("soft_skills", [])))
        experience = st.text_area("Experience summary", profile.get("experience_summary", ""), height=120)

        st.markdown("#### Preferences")
        c1, c2, c3 = st.columns(3)
        remote_opts = [True, False, "hybrid"]
        rv = prefs.get("remote", True)
        ri = remote_opts.index(rv) if rv in remote_opts else 0
        remote = c1.selectbox("Remote?", remote_opts, index=ri)
        salary_min = c2.number_input("Min salary (USD/year)", value=int(prefs.get("salary_min") or 0), step=5000)
        locations = c3.text_input("Preferred locations", ", ".join(prefs.get("locations", [])))
        exclude = st.text_input("Exclude keywords", ", ".join(prefs.get("exclude_keywords", [])))
        merge_cv = st.checkbox("Merge CV skills into Skills & use CV for cover letters", value=True)
        submitted = st.form_submit_button("Save profile", type="primary")

        if submitted:
            lang_list = [s.strip() for s in languages.split(",") if s.strip()]
            fw_list = [s.strip() for s in frameworks.split(",") if s.strip()]
            tool_list = [s.strip() for s in tools.split(",") if s.strip()]
            soft_list = [s.strip() for s in soft.split(",") if s.strip()]
            pending_text = st.session_state.get("pending_cv_text")
            pending_skills = st.session_state.get("pending_cv_skills") or []
            pending_name = st.session_state.get("pending_cv_name", "cv")
            new_documents = dict(documents)
            if pending_text:
                new_documents = {
                    "cv_text": pending_text,
                    "cv_skills": pending_skills,
                    "cv_filename": pending_name,
                    "cv_word_count": len(pending_text.split()),
                }
            if merge_cv and new_documents.get("cv_skills"):
                existing = {s.lower() for s in lang_list + fw_list + tool_list}
                for s in new_documents["cv_skills"]:
                    if s.lower() not in existing:
                        tool_list.append(s)
                        existing.add(s.lower())
            if merge_cv and new_documents.get("cv_text") and not experience.strip():
                experience = summarize_cv_for_profile(new_documents["cv_text"], 800)
            new_profile = {
                "personal": {"full_name": full_name, "email": email, "phone": phone, "location": location,
                             "linkedin": linkedin, "portfolio": portfolio, "github": github},
                "target_roles": [r.strip() for r in roles_text.splitlines() if r.strip()],
                "skills": {"languages": lang_list, "frameworks": fw_list, "tools": tool_list, "soft_skills": soft_list},
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
                "documents": new_documents,
                "cover_letter": profile.get("cover_letter", {"tone": "professional", "length": "medium", "highlight_achievements": True}),
            }
            save_yaml(ROOT / "profile.yaml", new_profile)
            for k in ("pending_cv_text", "pending_cv_skills", "pending_cv_name"):
                st.session_state.pop(k, None)
            st.success("Profile saved" + (" with CV." if new_documents.get("cv_text") else "."))


def page_settings():
    st.markdown("### Settings")
    config = load_config()
    settings = config.get("settings", {})
    st.markdown("#### Job sources (free, no API keys)")
    st.write("RemoteOK · Remotive · Arbeitnow · **Jobicy** · **Himalayas**")
    st.caption("We do not scrape LinkedIn, Indeed, or Glassdoor (blocked / against their terms).")
    min_score = st.slider("Default minimum match score", 0.15, 0.70, float(settings.get("min_match_score", 0.35)), 0.05)
    if st.button("Save settings", type="primary"):
        config.setdefault("settings", {})["min_match_score"] = min_score
        save_yaml(ROOT / "config.yaml", config)
        st.success("Saved.")
    st.divider()
    st.markdown("#### About")
    st.write("Discover remote roles, score them against your CV, generate cover letters, track applications. You stay in control of every submit.")


def main():
    page = render_sidebar()
    if page == "Home":
        page_home()
    elif page == "Search Jobs":
        page_search()
    elif page == "My Jobs":
        page_my_jobs()
    elif page == "Prepare Application":
        page_prepare()
    elif page == "Profile & CV":
        page_profile()
    elif page == "Settings":
        page_settings()


if __name__ == "__main__":
    main()
