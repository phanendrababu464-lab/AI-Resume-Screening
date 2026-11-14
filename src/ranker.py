"""Candidate ranking and similarity module using Sentence-Transformers and scikit-learn.

Embeds resumes and job descriptions using all-MiniLM-L6-v2 on CPU, calculates
semantic cosine similarity, and combines it with technical skill overlap to produce
a comprehensive candidate ranking.
"""

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

from src.config import (
    DEFAULT_DEVICE,
    DEFAULT_SEMANTIC_WEIGHT,
    DEFAULT_SKILL_WEIGHT,
    EMBEDDING_MODEL_NAME,
)
from src.skill_extractor import TechnicalSkillExtractor


class ResumeRanker:
    """Ranks candidates against a target job description using semantic embeddings and skill matching."""

    def __init__(
        self,
        model_name: str = EMBEDDING_MODEL_NAME,
        device: str = DEFAULT_DEVICE,
        semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT,
        skill_weight: float = DEFAULT_SKILL_WEIGHT,
    ) -> None:
        """Initializes the ranker with a SentenceTransformer model.

        Args:
            model_name: HuggingFace model identifier (e.g. 'all-MiniLM-L6-v2').
            device: Computing device ('cpu').
            semantic_weight: Weight allocated to semantic cosine similarity (0.0 to 1.0).
            skill_weight: Weight allocated to hard skill overlap (0.0 to 1.0).
        """
        self.device = device
        self.semantic_weight = semantic_weight
        self.skill_weight = skill_weight
        self.model = SentenceTransformer(model_name, device=self.device)
        self.skill_extractor = TechnicalSkillExtractor()

    def compute_semantic_similarity(self, text_a: str, text_b: str) -> float:
        """Computes cosine similarity between two text snippets.

        Args:
            text_a: First text string.
            text_b: Second text string.

        Returns:
            Cosine similarity score as a float between 0.0 and 1.0.
        """
        if not text_a.strip() or not text_b.strip():
            return 0.0

        embeddings = self.model.encode(
            [text_a, text_b],
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        score = float(cosine_similarity([embeddings[0]], [embeddings[1]])[0][0])
        # Clip to ensure valid range [0.0, 1.0]
        return float(np.clip(score, 0.0, 1.0))

    def rank_candidates(
        self,
        job_description: str,
        candidates: list[dict[str, Any]],
    ) -> pd.DataFrame:
        """Ranks a list of candidate resumes against a job description.

        Args:
            job_description: Text of the target job description.
            candidates: List of dictionaries with keys:
                - 'name': Candidate or file identifier.
                - 'text': Extracted plain text of resume.
                - 'skills': Optional pre-extracted skills list (extracted if omitted).

        Returns:
            A pandas DataFrame sorted by 'match_score' descending, containing rank,
            candidate name, composite match score, semantic score, skill overlap score,
            matched skills, and missing skills.
        """
        columns = [
            "rank",
            "candidate",
            "match_score",
            "semantic_score",
            "skill_overlap_score",
            "matched_skills",
            "missing_skills",
        ]

        if not candidates or not job_description.strip():
            return pd.DataFrame(columns=columns)

        # Extract skills from the job description
        jd_skills = self.skill_extractor.extract_skills(job_description)

        # Batch encode all texts for CPU efficiency
        jd_embedding = self.model.encode(
            job_description,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        resume_texts = [c.get("text", "") for c in candidates]
        valid_indices = [i for i, t in enumerate(resume_texts) if t.strip()]

        if not valid_indices:
            # All resumes are empty
            records = []
            for i, cand in enumerate(candidates, start=1):
                records.append({
                    "rank": i,
                    "candidate": cand.get("name", f"Candidate {i}"),
                    "match_score": 0.0,
                    "semantic_score": 0.0,
                    "skill_overlap_score": 0.0,
                    "matched_skills": [],
                    "missing_skills": jd_skills,
                })
            return pd.DataFrame(records)

        resume_embeddings = self.model.encode(
            resume_texts,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        jd_embedding_2d = np.atleast_2d(jd_embedding)
        resume_embeddings_2d = np.atleast_2d(resume_embeddings)
        similarities = cosine_similarity(jd_embedding_2d, resume_embeddings_2d)[0]

        records = []
        for idx, cand in enumerate(candidates):
            candidate_name = cand.get("name", f"Candidate {idx + 1}")
            resume_text = cand.get("text", "")

            # If skills not already provided, extract them
            resume_skills = cand.get("skills")
            if resume_skills is None:
                resume_skills = self.skill_extractor.extract_skills(resume_text)

            overlap_stats = self.skill_extractor.calculate_skill_overlap(
                resume_skills=resume_skills,
                job_skills=jd_skills,
            )

            semantic_score = float(np.clip(similarities[idx], 0.0, 1.0))
            skill_score = float(overlap_stats["overlap_ratio"])

            # Weighted composite score
            if jd_skills:
                match_score = (
                    self.semantic_weight * semantic_score + self.skill_weight * skill_score
                )
            else:
                # If JD has no identifiable hard technical skills, rely purely on semantics
                match_score = semantic_score

            records.append({
                "candidate": candidate_name,
                "match_score": round(match_score * 100, 2),
                "semantic_score": round(semantic_score * 100, 2),
                "skill_overlap_score": round(skill_score * 100, 2),
                "matched_skills": overlap_stats["matched_skills"],
                "missing_skills": overlap_stats["missing_skills"],
            })

        # Sort descending by match_score
        df = pd.DataFrame(records).sort_values(by="match_score", ascending=False).reset_index(drop=True)
        df.insert(0, "rank", range(1, len(df) + 1))

        return df[columns]
