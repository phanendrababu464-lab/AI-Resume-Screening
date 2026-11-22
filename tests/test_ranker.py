"""Unit tests for the ResumeRanker module."""

from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
import pytest

from src.ranker import ResumeRanker


@pytest.fixture
def mock_ranker() -> ResumeRanker:
    """Creates a ResumeRanker with a mocked SentenceTransformer model."""
    with patch("src.ranker.SentenceTransformer") as mock_st_cls:
        mock_model = MagicMock()

        def fake_encode(sentences, convert_to_numpy=True, show_progress_bar=False):
            is_single = isinstance(sentences, str)
            input_list = [sentences] if is_single else list(sentences)
            # Deterministic synthetic embedding: Python/FastAPI get vector aligned with [1, 0, 0]
            vectors = []
            for s in input_list:
                s_lower = s.lower()
                if "python" in s_lower or "fastapi" in s_lower:
                    v = np.array([0.9, 0.1, 0.0], dtype=np.float32)
                elif "react" in s_lower:
                    v = np.array([0.1, 0.9, 0.0], dtype=np.float32)
                else:
                    v = np.array([0.0, 0.1, 0.9], dtype=np.float32)
                # Normalize vector to unit length
                v = v / np.linalg.norm(v)
                vectors.append(v)
            arr = np.array(vectors)
            return arr[0] if is_single else arr

        mock_model.encode.side_effect = fake_encode
        mock_st_cls.return_value = mock_model

        ranker = ResumeRanker()
        return ranker


def test_rank_candidates_ordering(
    mock_ranker: ResumeRanker,
    sample_job_description: str,
    sample_candidates: list[dict[str, str]],
) -> None:
    """Verifies that candidates are ranked by match score descending and relevant candidate is #1."""
    df = mock_ranker.rank_candidates(
        job_description=sample_job_description,
        candidates=sample_candidates,
    )

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3
    assert list(df["rank"]) == [1, 2, 3]

    # Alex (Python Expert) should be rank 1
    top_candidate = df.iloc[0]
    assert top_candidate["candidate"] == "Alex_Python_Expert.pdf"
    assert top_candidate["match_score"] >= df.iloc[1]["match_score"]
    assert "Python" in top_candidate["matched_skills"]


def test_rank_candidates_columns(
    mock_ranker: ResumeRanker,
    sample_job_description: str,
    sample_candidates: list[dict[str, str]],
) -> None:
    """Verifies the schema of the returned ranking DataFrame."""
    expected_cols = [
        "rank",
        "candidate",
        "match_score",
        "semantic_score",
        "skill_overlap_score",
        "matched_skills",
        "missing_skills",
    ]
    df = mock_ranker.rank_candidates(sample_job_description, sample_candidates)
    assert list(df.columns) == expected_cols


def test_rank_candidates_empty_input(mock_ranker: ResumeRanker) -> None:
    """Verifies empty DataFrame is returned when candidate list or JD is empty."""
    df_no_cands = mock_ranker.rank_candidates("Job Description", [])
    assert df_no_cands.empty
    assert "rank" in df_no_cands.columns

    df_empty_jd = mock_ranker.rank_candidates("", [{"name": "A", "text": "Python"}])
    assert df_empty_jd.empty


def test_compute_semantic_similarity_empty_strings(mock_ranker: ResumeRanker) -> None:
    """Verifies similarity is 0.0 if any text string is empty."""
    assert mock_ranker.compute_semantic_similarity("", "Some text") == 0.0
    assert mock_ranker.compute_semantic_similarity("Some text", "") == 0.0
    assert mock_ranker.compute_semantic_similarity("   ", "   ") == 0.0
