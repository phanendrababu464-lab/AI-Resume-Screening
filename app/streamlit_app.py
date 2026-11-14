"""Streamlit Web Application for AI-Based Resume Screening.

Tier 1 Presentation Layer: Relocated and decoupled Streamlit UI.
Interacts strictly through Tier 2 Service Layer (`src.services.screening_service`)
and Pydantic schemas (`src.schemas`). Contains zero domain or business logic.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

# Ensure repository root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.schemas import (
    CandidateRanking,
    JobAnalysis,
    ParsedResume,
    Recommendation,
    WeightConfig,
)
from src.services.screening_service import (
    analyze_job,
    build_recommendation,
    get_candidate_breakdown_chart_data,
    get_overall_ranking_chart_data,
    get_score_composition_chart_data,
    get_skill_matrix_chart_data,
    parse_resumes,
    rank,
)


def verify_schemas_path(repo_root: Path, schemas_file: Path) -> bool:
    """Verifies that schemas.py is loaded from inside repo_root."""
    try:
        schemas_file.resolve().relative_to(repo_root.resolve())
        return True
    except ValueError:
        return False


def main() -> None:
    """Main Streamlit application entry point."""
    st.set_page_config(
        page_title="AI Resume Screening System",
        page_icon="📄",
        layout="wide",
    )

    # Environment Guard: Ensure schemas module is loaded from this project root
    import src.schemas as _schemas
    schemas_file = Path(_schemas.__file__).resolve()
    if not verify_schemas_path(_REPO_ROOT, schemas_file):
        st.error(
            f"❌ Environment Mismatch Error: 'src.schemas' was loaded from '{schemas_file}', "
            f"which is outside the project root '{_REPO_ROOT.resolve()}'. "
            "Please run the application using the project's own virtual environment (`./run_app.sh`)."
        )
        st.stop()

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
    exp_penalty = st.sidebar.slider(
        "Below-Min-Experience Penalty Multiplier",
        min_value=0.0,
        max_value=1.0,
        value=0.6,
        step=0.05,
        help="Penalty multiplier applied to composite score when candidate experience is below minimum.",
    )

    total_weight = round(req_weight + pref_weight + sem_weight + exp_weight, 4)
    weights_valid = (total_weight == 1.0)
    if not weights_valid:
        st.sidebar.warning(f"⚠️ Total weight sum is {total_weight:.2f} (expected 1.00).")
    else:
        st.sidebar.success("✅ Total weight sum is 1.00.")

    weights = WeightConfig(
        required_skill_weight=req_weight,
        preferred_skill_weight=pref_weight,
        semantic_weight=sem_weight,
        experience_weight=exp_weight,
        experience_penalty=exp_penalty,
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
    if not weights_valid:
        st.error(
            f"🚫 Screening disabled: total scoring weights sum to {total_weight:.2f}. "
            "The 4 component weights must sum to exactly 1.00. Please adjust the sidebar sliders."
        )

    screen_button = st.button(
        "🚀 Screen and Rank Resumes",
        type="primary",
        use_container_width=True,
        disabled=not weights_valid,
    )

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
                "Below Min Exp": "⚠️ True" if r.below_min_experience else "False",
                "Composite Score (%)": round(r.match_score, 1),
                "Required Skills (%)": round(r.component_scores.required_skill_score * 100, 1),
                "Preferred Skills (%)": round(r.component_scores.preferred_skill_score * 100, 1),
                "Semantic Match (%)": round(r.component_scores.semantic_score * 100, 1),
                "Experience Match (%)": round(r.component_scores.experience_score * 100, 1),
                "Related Skills Matched": ", ".join(r.related_skills_matched) if r.related_skills_matched else "None",
                "TF-IDF Baseline (%)": (
                    round(r.component_scores.tfidf_baseline_score * 100, 1)
                    if r.component_scores.tfidf_baseline_score is not None
                    else "N/A"
                ),
            })

        summary_df = pd.DataFrame(rows)
        st.dataframe(summary_df, use_container_width=True, hide_index=True)

        # ----------------------------------------------------------------------
        # Visual Analytics: Charts Section (Requirement 2)
        # ----------------------------------------------------------------------
        st.divider()
        st.subheader("📈 Ranking & Evaluation Analytics")

        tab_overall, tab_comp, tab_matrix = st.tabs([
            "🏆 Overall Ranking",
            "📊 Score Composition",
            "🧩 Skill Match Matrix",
        ])

        # 2.a Overall Ranking Horizontal Bar Chart
        with tab_overall:
            st.markdown("**Candidate Composite Score Ranking (Top Candidate Highlighted):**")
            overall_records = get_overall_ranking_chart_data(rankings)
            df_overall = pd.DataFrame(overall_records)
            chart_h = max(180, len(rankings) * 38)
            base_overall = alt.Chart(df_overall).encode(
                y=alt.Y("candidate:N", sort=alt.EncodingSortField(field="score", order="descending"), title="Candidate"),
                x=alt.X("score:Q", title="Composite Match Score (%)", scale=alt.Scale(domain=[0, 100])),
            )
            bars_overall = base_overall.mark_bar(cornerRadiusEnd=4).encode(
                color=alt.Color(
                    "color_category:N",
                    scale=alt.Scale(
                        domain=["Top Candidate", "Candidate"],
                        range=["#2e7d32", "#455a64"],
                    ),
                    legend=alt.Legend(title="Candidate Tier"),
                ),
                tooltip=["candidate:N", alt.Tooltip("score:Q", format=".1f", title="Composite Score (%)"), "rank:O"],
            )
            text_overall = base_overall.mark_text(
                align="left",
                baseline="middle",
                dx=5,
            ).encode(
                text="label:N"
            )
            st.altair_chart((bars_overall + text_overall).properties(height=chart_h), use_container_width=True)

        # 2.b Score Composition Stacked Bar Chart
        with tab_comp:
            st.markdown("**Weighted Component Breakdown (Percentage Points):**")
            comp_records = get_score_composition_chart_data(rankings, weights)
            df_comp = pd.DataFrame(comp_records)
            comp_h = max(180, len(rankings) * 42)
            stack_base = alt.Chart(df_comp).encode(
                y=alt.Y("candidate:N", sort=alt.EncodingSortField(field="candidate"), title="Candidate"),
                x=alt.X("contribution:Q", title="Score Contribution (Percentage Points)", stack="zero", scale=alt.Scale(domain=[0, 100])),
                color=alt.Color(
                    "component:N",
                    scale=alt.Scale(
                        domain=["1. Required Skills", "2. Preferred Skills", "3. Semantic Match", "4. Experience Match"],
                        range=["#1976d2", "#388e3c", "#f57c00", "#7b1fa2"],
                    ),
                    title="Component",
                ),
                tooltip=[
                    "candidate:N",
                    "component:N",
                    alt.Tooltip("contribution:Q", format=".1f", title="Contribution (pts)"),
                    "percentage_label:N",
                ],
            )
            stack_bars = stack_base.mark_bar()
            stack_text = stack_base.mark_text(
                align="center",
                baseline="middle",
                color="white",
                fontSize=11,
            ).encode(
                detail="component:N",
                text=alt.condition(alt.datum.contribution > 4.0, "percentage_label:N", alt.value("")),
            )
            st.altair_chart((stack_bars + stack_text).properties(height=comp_h), use_container_width=True)

            penalized = [r for r in rankings if r.below_min_experience]
            if penalized:
                penalized_names = ", ".join(f"`{r.candidate}`" for r in penalized)
                st.caption(
                    f"⚠️ **Note on Minimum Experience Penalty**: {penalized_names} fell below the job's minimum experience, "
                    f"so each component contribution reflects the applied penalty multiplier (×{weights.experience_penalty:.2f})."
                )

        # 2.c Skill Match Matrix
        with tab_matrix:
            st.markdown("**Skill Match Matrix (Candidates × Job Skills):**")
            matrix_records = get_skill_matrix_chart_data(rankings, job_analysis)
            if matrix_records:
                df_matrix = pd.DataFrame(matrix_records)
                mat_h = max(180, len(rankings) * 36)
                matrix_chart = alt.Chart(df_matrix).mark_rect(stroke="#ffffff", strokeWidth=1).encode(
                    x=alt.X("skill_display:N", title="Job Requirement (Req = Required, Pre = Preferred)", sort=None),
                    y=alt.Y("candidate:N", sort=alt.EncodingSortField(field="candidate"), title="Candidate"),
                    color=alt.Color(
                        "status:N",
                        scale=alt.Scale(
                            domain=["Exact Match", "Related Match", "Missing"],
                            range=["#2e7d32", "#f57c00", "#d32f2f"],
                        ),
                        title="Match Status",
                    ),
                    tooltip=["candidate:N", "skill:N", "skill_type:N", "status:N"],
                )
                matrix_text = alt.Chart(df_matrix).mark_text(baseline="middle", fontSize=11, color="white").encode(
                    x=alt.X("skill_display:N", sort=None),
                    y=alt.Y("candidate:N"),
                    text="status:N",
                )
                st.altair_chart((matrix_chart + matrix_text).properties(height=mat_h), use_container_width=True)
            else:
                st.info("No specific skills were extracted from the job description to display in the matrix.")

        # ----------------------------------------------------------------------
        # Detailed Candidate Breakdown Expanders (Requirement 2.d)
        # ----------------------------------------------------------------------
        st.divider()
        st.subheader("🔍 Detailed Candidate Breakdown")
        for r in rankings:
            expander_title = f"Rank {r.rank}: {r.candidate} — Score: {r.match_score:.1f}%"
            if r.below_min_experience:
                expander_title += " ⚠️ [Below Min Experience]"
            with st.expander(expander_title):
                if r.below_min_experience:
                    st.warning("⚠️ **Warning: Candidate experience is below the job's minimum required experience.** Score penalized.")

                # Horizontal bar chart of five percentages (Requirement 2.d)
                breakdown_records = get_candidate_breakdown_chart_data(r)
                df_bd = pd.DataFrame(breakdown_records)
                bd_base = alt.Chart(df_bd).encode(
                    y=alt.Y("component:N", sort=None, title=None),
                    x=alt.X("percentage:Q", title="Score (%)", scale=alt.Scale(domain=[0, 100])),
                )
                bd_bar = bd_base.mark_bar(cornerRadiusEnd=3, color="#1e88e5").encode(
                    tooltip=["component:N", alt.Tooltip("percentage:Q", format=".1f", title="Score (%)")]
                )
                bd_label = bd_base.mark_text(align="left", baseline="middle", dx=4).encode(
                    text=alt.Text("percentage:Q", format=".1f")
                )
                st.altair_chart((bd_bar + bd_label).properties(height=160), use_container_width=True)

                st.markdown("---")
                det_col1, det_col2, det_col3, det_col4 = st.columns(4)
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
                    st.markdown("**Related Skills Matched:**")
                    if r.related_skills_matched:
                        st.write(", ".join(f"`{s}`" for s in r.related_skills_matched))
                    else:
                        st.write("_None_")

                with det_col4:
                    st.markdown("**Missing Required Skills:**")
                    if r.missing_required_skills:
                        st.write(", ".join(f"`{s}`" for s in r.missing_required_skills))
                    else:
                        st.write("🎉 _Candidate possesses all required skills!_")

        # ----------------------------------------------------------------------
        # Best Resume at the End (Requirement 3)
        # ----------------------------------------------------------------------
        st.divider()
        recommendation: Recommendation = build_recommendation(rankings, job_analysis)
        st.subheader("🏆 Best Match for This Job")

        with st.container():
            rec_col1, rec_col2 = st.columns([2, 1])
            with rec_col1:
                st.markdown(f"### 🎖️ {recommendation.best_candidate or 'No Candidate'}")
                st.info(f"💡 **Evaluation Summary:** {recommendation.summary_text}")
            with rec_col2:
                top_score_str = f"{recommendation.best_score:.1f}%" if recommendation.best_score is not None else "N/A"
                delta_str = (
                    f"+{recommendation.margin_over_runner_up:.1f}% over runner-up"
                    if recommendation.margin_over_runner_up is not None
                    else "Sole Candidate"
                )
                st.metric(
                    label="Composite Score",
                    value=top_score_str,
                    delta=delta_str,
                )
                if recommendation.runner_up:
                    st.caption(f"Runner-up: **{recommendation.runner_up}**")

            s_col, g_col, w_col = st.columns(3)
            with s_col:
                st.markdown("#### ✅ Strengths")
                if recommendation.strengths:
                    for s in recommendation.strengths:
                        st.markdown(f"- {s}")
                else:
                    st.markdown("_No distinct strengths._")

            with g_col:
                st.markdown("#### 🔍 Gaps & Areas for Review")
                if recommendation.gaps:
                    for g in recommendation.gaps:
                        st.markdown(f"- {g}")
                else:
                    st.markdown("_No major gaps._")

            with w_col:
                st.markdown("#### ⚠️ Advisory Warnings")
                if recommendation.warnings:
                    for w in recommendation.warnings:
                        st.warning(w)
                else:
                    st.success("No warnings — candidate satisfies all minimum criteria.")


if __name__ == "__main__":
    main()
