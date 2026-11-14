"""Streamlit Web Application for AI-Based Resume Screening.

Tier 1 Presentation Layer: Relocated and decoupled Streamlit UI.
Interacts strictly through Tier 2 Service Layer (`src.services.screening_service`)
and Pydantic schemas (`src.schemas`). Contains zero domain or business logic.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

import pandas as pd
import streamlit as st

# Ensure repository root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.schemas import CandidateRanking, JobAnalysis, ParsedResume, WeightConfig
from src.services.screening_service import analyze_job, parse_resumes, rank


def main() -> None:
    """Main Streamlit application entry point."""
    st.set_page_config(
        page_title="AI Resume Screening System",
        page_icon="📄",
        layout="wide",
    )

    st.title("📄 AI-Based Resume Screening System")
    st.markdown(
        "Rank technical/IT candidate resumes against a job description using "
        "**all-MiniLM-L6-v2** semantic embeddings, cue-phrase parsing, and "
        "multi-component weighted scoring."
    )

    # --------------------------------------------------------------------------
    # Sidebar: Weight Configuration (Requirement R4)
    # --------------------------------------------------------------------------
    st.sidebar.header("⚙️ Scoring Weights Configuration")
    st.sidebar.markdown(
        "Configure the 4-component scoring weights. Default weights: "
        "**0.50** required, **0.20** preferred, **0.20** semantic, **0.10** experience."
    )

    req_weight = st.sidebar.slider(
        "Required Skills Weight",
        min_value=0.0,
        max_value=1.0,
        value=0.5,
        step=0.05,
        help="Weight for must-have technical skill coverage.",
    )
    pref_weight = st.sidebar.slider(
        "Preferred Skills Weight",
        min_value=0.0,
        max_value=1.0,
        value=0.2,
        step=0.05,
        help="Weight for nice-to-have technical skill coverage.",
    )
    sem_weight = st.sidebar.slider(
        "Semantic Similarity Weight",
        min_value=0.0,
        max_value=1.0,
        value=0.2,
        step=0.05,
        help="Weight for all-MiniLM-L6-v2 contextual embedding similarity.",
    )
    exp_weight = st.sidebar.slider(
        "Experience Match Weight",
        min_value=0.0,
        max_value=1.0,
        value=0.1,
        step=0.05,
        help="Weight for candidate experience match against job minimum experience.",
    )

    total_weight = round(req_weight + pref_weight + sem_weight + exp_weight, 4)
    if total_weight != 1.0:
        st.sidebar.warning(f"⚠️ Total weight sum is {total_weight:.2f} (expected 1.00).")
    else:
        st.sidebar.success("✅ Total weight sum is 1.00.")

    weights = WeightConfig(
        required_skill_weight=req_weight,
        preferred_skill_weight=pref_weight,
        semantic_weight=sem_weight,
        experience_weight=exp_weight,
    )

    # --------------------------------------------------------------------------
    # Main Layout: 2 Columns for Inputs
    # --------------------------------------------------------------------------
    col1, col2 = st.columns([1, 1], gap="medium")

    with col1:
        st.subheader("1. Job Description")
        sample_jd = (
            "Senior Backend Engineer\n\n"
            "Requirements (Must Have):\n"
            "- Hands-on experience with Python and FastAPI\n"
            "- Minimum 4 years of software engineering experience\n"
            "- PostgreSQL database design and query optimization\n\n"
            "Preferred Qualifications (Nice to Have):\n"
            "- Experience with Docker and AWS\n"
            "- Familiarity with Kubernetes, CI/CD, and Microservices architecture"
        )

        jd_text = st.text_area(
            "Paste Technical Job Description:",
            value=sample_jd,
            height=260,
            help="Detail required and preferred languages, frameworks, tools, and experience requirements.",
        )

        # Live Job Analysis Preview via Service Layer
        if jd_text.strip():
            with st.spinner("Analyzing Job Description..."):
                try:
                    job_preview: JobAnalysis = analyze_job(jd_text)
                    preview_col1, preview_col2 = st.columns(2)
                    with preview_col1:
                        st.markdown(f"**Required Skills ({len(job_preview.required_skills)}):**")
                        if job_preview.required_skills:
                            st.write(", ".join(f"`{s}`" for s in job_preview.required_skills))
                        else:
                            st.write("_None detected_")
                    with preview_col2:
                        st.markdown(f"**Preferred Skills ({len(job_preview.preferred_skills)}):**")
                        if job_preview.preferred_skills:
                            st.write(", ".join(f"`{s}`" for s in job_preview.preferred_skills))
                        else:
                            st.write("_None detected_")
                    if job_preview.min_experience_years is not None:
                        st.caption(f"⏱️ Minimum Experience Required: **{job_preview.min_experience_years:.1f} years**")
                except Exception as err:
                    st.error(f"Error analyzing job description: {err}")

    with col2:
        st.subheader("2. Upload Resumes")
        uploaded_files = st.file_uploader(
            "Upload Candidate Resumes (.pdf, .docx):",
            type=["pdf", "docx"],
            accept_multiple_files=True,
            help="Upload PDF or DOCX candidate resumes. PII will be automatically anonymized.",
        )

        if uploaded_files:
            st.info(f"Loaded {len(uploaded_files)} resume file(s). Ready for screening.")

    # --------------------------------------------------------------------------
    # Trigger Screening Pipeline via Service Layer
    # --------------------------------------------------------------------------
    st.divider()
    screen_button = st.button("🚀 Screen and Rank Resumes", type="primary", use_container_width=True)

    if screen_button:
        if not jd_text.strip():
            st.error("Please enter a valid Job Description before screening.")
            return

        if not uploaded_files:
            st.error("Please upload at least one candidate resume (.pdf or .docx).")
            return

        with st.spinner("Analyzing job requirements..."):
            try:
                job_analysis = analyze_job(jd_text)
            except Exception as err:
                st.error(f"Failed to analyze job description: {err}")
                return

        with st.spinner("Parsing and anonymizing resumes..."):
            try:
                parsed_resumes = parse_resumes(uploaded_files)
            except Exception as err:
                st.error(f"Failed to parse resumes: {err}")
                return

        if not parsed_resumes:
            st.error("None of the uploaded resumes could be parsed successfully.")
            return

        with st.spinner("Computing semantic embeddings and multi-component ranking..."):
            try:
                rankings: list[CandidateRanking] = rank(
                    job=job_analysis,
                    resumes=parsed_resumes,
                    weights=weights,
                )
            except Exception as err:
                st.error(f"Failed to compute rankings: {err}")
                return

        # ----------------------------------------------------------------------
        # Leaderboard Summary Table
        # ----------------------------------------------------------------------
        st.subheader("📊 Candidate Ranking Results")

        rows = []
        for r in rankings:
            rows.append({
                "Rank": r.rank,
                "Candidate / File": r.candidate,
                "Composite Score (%)": round(r.match_score, 1),
                "Required Skills (%)": round(r.component_scores.required_skill_score * 100, 1),
                "Preferred Skills (%)": round(r.component_scores.preferred_skill_score * 100, 1),
                "Semantic Match (%)": round(r.component_scores.semantic_score * 100, 1),
                "Experience Match (%)": round(r.component_scores.experience_score * 100, 1),
                "TF-IDF Baseline (%)": (
                    round(r.component_scores.tfidf_baseline_score * 100, 1)
                    if r.component_scores.tfidf_baseline_score is not None
                    else "N/A"
                ),
            })

        summary_df = pd.DataFrame(rows)
        st.dataframe(summary_df, use_container_width=True, hide_index=True)

        # ----------------------------------------------------------------------
        # Detailed Candidate Breakdown Expanders
        # ----------------------------------------------------------------------
        st.subheader("🔍 Detailed Candidate Breakdown")
        for r in rankings:
            with st.expander(f"Rank {r.rank}: {r.candidate} — Score: {r.match_score:.1f}%"):
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Required Skills", f"{r.component_scores.required_skill_score * 100:.1f}%")
                m2.metric("Preferred Skills", f"{r.component_scores.preferred_skill_score * 100:.1f}%")
                m3.metric("Semantic Match", f"{r.component_scores.semantic_score * 100:.1f}%")
                m4.metric("Experience Match", f"{r.component_scores.experience_score * 100:.1f}%")
                tfidf_val = (
                    f"{r.component_scores.tfidf_baseline_score * 100:.1f}%"
                    if r.component_scores.tfidf_baseline_score is not None
                    else "N/A"
                )
                m5.metric("TF-IDF Baseline", tfidf_val)

                st.markdown("---")
                det_col1, det_col2, det_col3 = st.columns(3)
                with det_col1:
                    st.markdown("**Matched Required Skills:**")
                    if r.matched_required_skills:
                        st.write(", ".join(f"`{s}`" for s in r.matched_required_skills))
                    else:
                        st.write("_None matched_")

                with det_col2:
                    st.markdown("**Matched Preferred Skills:**")
                    if r.matched_preferred_skills:
                        st.write(", ".join(f"`{s}`" for s in r.matched_preferred_skills))
                    else:
                        st.write("_None matched_")

                with det_col3:
                    st.markdown("**Missing Required Skills:**")
                    if r.missing_required_skills:
                        st.write(", ".join(f"`{s}`" for s in r.missing_required_skills))
                    else:
                        st.write("🎉 _Candidate possesses all required skills!_")


if __name__ == "__main__":
    main()
