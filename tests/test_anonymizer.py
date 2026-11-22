"""Unit and integration tests for the anonymizer module and evaluation invariance."""

import copy
import pytest

from src.anonymizer import (
    EMAIL_TOKEN,
    NAME_TOKEN,
    PHONE_TOKEN,
    PRONOUN_TOKEN,
    anonymize_resume,
    anonymize_text,
)
from src.ranker import ResumeRanker


# ---------------------------------------------------------------------------
# Email Redaction Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "email_address",
    [
        "alice@example.com",
        "john.doe@eng.mail.example.co.uk",
        "jane.doe+screening@gmail.com",
        "first-last@sub.domain.org",
        "user_name_123@tech-corp.net",
        "candidate@domain.io",
    ],
)
def test_anonymize_text_email_formats(email_address: str) -> None:
    """Verifies email redaction across various standard and complex email formats."""
    text = f"Contact me at {email_address} regarding the opening."
    result = anonymize_text(text)
    assert EMAIL_TOKEN in result
    assert email_address not in result
    assert result == f"Contact me at {EMAIL_TOKEN} regarding the opening."


def test_anonymize_text_multiple_emails() -> None:
    """Verifies that multiple emails in a single text are all redacted."""
    text = "Work: alice.smith@corp.com | Personal: alice_personal+test@gmail.com"
    result = anonymize_text(text)
    assert result == f"Work: {EMAIL_TOKEN} | Personal: {EMAIL_TOKEN}"


# ---------------------------------------------------------------------------
# Phone Number Redaction Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "phone_number",
    [
        "555-123-4567",
        "555.123.4567",
        "555 123 4567",
        "(555) 123-4567",
        "(555)123-4567",
        "+1-555-123-4567",
        "+1 (555) 123-4567",
        "1-800-555-0199",
        "(555) 123-4567 ext. 1234",
        "(555) 123-4567 x456",
        "+44 20 7123 4567",
        "+44-20-7123-4567",
        "+91 98765 43210",
        "+91-9876543210",
    ],
)
def test_anonymize_text_phone_formats(phone_number: str) -> None:
    """Verifies phone number redaction across US and international formats."""
    text = f"Please reach out at {phone_number} for interview scheduling."
    result = anonymize_text(text)
    assert PHONE_TOKEN in result
    assert phone_number not in result
    assert result == f"Please reach out at {PHONE_TOKEN} for interview scheduling."


@pytest.mark.parametrize(
    "non_phone_text",
    [
        "Experience from 2020-2024 at Acme Corp.",
        "Worked 2018 - 2022 as lead engineer.",
        "Graduated on 2021-05-12 with honors.",
        "Over 10-15 years of industry experience.",
        "Python 3.10 and v2.4.1 migration.",
        "Salary expectations: $120,000 annually.",
        "Eligible for 401(k) and health benefits.",
        "Managed 15 engineers across 3 squads.",
        "GPA: 3.8/4.0 in Computer Science.",
    ],
)
def test_phone_non_matching_protection(non_phone_text: str) -> None:
    """Verifies that dates, version numbers, ranges, and salaries are not redacted as phones."""
    result = anonymize_text(non_phone_text)
    assert result == non_phone_text
    assert PHONE_TOKEN not in result


# ---------------------------------------------------------------------------
# Gendered Pronoun Redaction Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "pronoun",
    [
        "He", "he", "HE",
        "She", "she", "SHE",
        "Him", "him", "HIM",
        "Her", "her", "HER",
        "His", "his", "HIS",
        "Hers", "hers", "HERS",
        "Himself", "himself", "HIMSELF",
        "Herself", "herself", "HERSELF",
    ],
)
def test_anonymize_text_pronouns(pronoun: str) -> None:
    """Verifies gendered pronoun redaction for all case variations."""
    text = f"{pronoun} developed the cloud architecture."
    result = anonymize_text(text)
    assert result == f"{PRONOUN_TOKEN} developed the cloud architecture."


@pytest.mark.parametrize(
    "protected_word",
    [
        "hero",
        "theme",
        "history",
        "theirs",
        "shell",
        "shim",
        "sheriff",
        "adherent",
        "heritage",
        "coherence",
        "shepherd",
        "shimmer",
        "hymn",
        "hermetic",
        "hibernate",
        "hierarchy",
        "cohesion",
        "adhesive",
    ],
)
def test_pronoun_word_boundary_protection(protected_word: str) -> None:
    """Verifies words containing pronoun substrings are not altered."""
    text = f"The candidate demonstrated strong knowledge of {protected_word} and design."
    result = anonymize_text(text)
    assert protected_word in result
    assert result == text


def test_pronouns_in_complex_sentence() -> None:
    """Verifies redaction of multiple pronouns within a narrative sentence."""
    text = "She presented her findings to him, and he himself approved her proposal for his team."
    result = anonymize_text(text)
    expected = (
        f"{PRONOUN_TOKEN} presented {PRONOUN_TOKEN} findings to {PRONOUN_TOKEN}, "
        f"and {PRONOUN_TOKEN} {PRONOUN_TOKEN} approved {PRONOUN_TOKEN} proposal for {PRONOUN_TOKEN} team."
    )
    assert result == expected


# ---------------------------------------------------------------------------
# Candidate Name Redaction Tests
# ---------------------------------------------------------------------------

def test_anonymize_text_explicit_candidate_name() -> None:
    """Verifies redaction when candidate_name is explicitly supplied."""
    text = "Jane Marie Smith is a principal engineer. Jane led the team and Smith oversaw delivery."
    result = anonymize_text(text, candidate_name="Jane Marie Smith")
    assert "Jane" not in result
    assert "Smith" not in result
    assert result == (
        f"{NAME_TOKEN} is a principal engineer. "
        f"{NAME_TOKEN} led the team and {NAME_TOKEN} oversaw delivery."
    )


def test_anonymize_text_name_with_honorifics() -> None:
    """Verifies that titles and honorifics are handled cleanly without leaking gender or title."""
    text = "Dr. John Doe, Jr. was hired. Mr. Doe led the project."
    result = anonymize_text(text, candidate_name="Dr. John Doe, Jr.")
    assert "John" not in result
    assert "Doe" not in result
    assert result == f"{NAME_TOKEN} was hired. {NAME_TOKEN} led the project."


def test_anonymize_text_detected_name_from_label() -> None:
    """Verifies name detection and redaction from labeled text without explicit candidate_name."""
    text = "Name: Jane Doe\nEmail: jane.doe@example.com\nSummary: Software Engineer."
    result = anonymize_text(text)
    assert "Jane" not in result
    assert "Doe" not in result
    assert result == f"Name: {NAME_TOKEN}\nEmail: {EMAIL_TOKEN}\nSummary: Software Engineer."


def test_anonymize_text_detected_name_from_header() -> None:
    """Verifies heuristic name detection from top header line."""
    text = "Robert Oppenheimer\nPhysicist with 10 years experience."
    result = anonymize_text(text)
    assert "Oppenheimer" not in result
    assert result == f"{NAME_TOKEN}\nPhysicist with 10 years experience."


# ---------------------------------------------------------------------------
# Resume Dictionary Anonymization Tests
# ---------------------------------------------------------------------------

def test_anonymize_resume_nested_structure() -> None:
    """Verifies anonymize_resume with nested sections, metadata preservation, and immutability."""
    original_resume = {
        "filename": "jane_doe_resume.pdf",
        "name": "Jane Doe",
        "raw_text": "Jane Doe\njane@example.com\n555-123-4567\nShe has 5 years experience.",
        "text": "Jane Doe\njane@example.com\n555-123-4567\nShe has 5 years experience.",
        "cleaned_text": "Jane Doe jane@example.com 555-123-4567 She has 5 years experience.",
        "sections": {
            "summary": "Jane is a developer. Her stack is Python.",
            "experience": "Senior dev at Acme (2020-2024). She led a team.",
        },
        "skills": ["Python", "Docker", "AWS"],
        "experience_years": 5.0,
    }

    original_copy = copy.deepcopy(original_resume)
    anon_resume = anonymize_resume(original_resume)

    # Immutability assertion: original dictionary must not be modified
    assert original_resume == original_copy

    # Metadata assertions
    assert anon_resume["filename"] == "jane_doe_resume.pdf"
    assert anon_resume["skills"] == ["Python", "Docker", "AWS"]
    assert anon_resume["experience_years"] == 5.0

    # Name redaction
    assert anon_resume["name"] == NAME_TOKEN

    # Section redactions
    assert anon_resume["sections"]["summary"] == f"{NAME_TOKEN} is a developer. {PRONOUN_TOKEN} stack is Python."
    assert "2020-2024" in anon_resume["sections"]["experience"]
    assert PRONOUN_TOKEN in anon_resume["sections"]["experience"]

    # Main text and populated anonymized_text
    assert "anonymized_text" in anon_resume
    assert EMAIL_TOKEN in anon_resume["anonymized_text"]
    assert PHONE_TOKEN in anon_resume["anonymized_text"]
    assert PRONOUN_TOKEN in anon_resume["anonymized_text"]
    assert "Jane" not in anon_resume["anonymized_text"]


def test_anonymize_resume_empty_and_fallback() -> None:
    """Verifies anonymize_resume handles empty or minimalist inputs safely."""
    assert anonymize_resume({}) == {"anonymized_text": ""}
    assert anonymize_resume("not_a_dict") == {}

    minimal = {"name": "Alice Smith", "raw_text": "Alice is a Python engineer."}
    anon_minimal = anonymize_resume(minimal)
    assert "anonymized_text" in anon_minimal
    assert "Alice" not in anon_minimal["anonymized_text"]
    assert NAME_TOKEN in anon_minimal["anonymized_text"]


def test_anonymize_text_empty_and_none() -> None:
    """Verifies anonymize_text handles edge case empty/None inputs safely."""
    assert anonymize_text("") == ""
    assert anonymize_text(None) == ""
    assert anonymize_text(12345) == ""


# ---------------------------------------------------------------------------
# Evaluation Invariance Mathematical Proof Tests
# ---------------------------------------------------------------------------

def test_evaluation_invariance_semantic_similarity() -> None:
    """Mathematically proves evaluation invariance for semantic similarity.

    Constructs two resumes differing ONLY in candidate name, email, phone,
    and gendered pronouns. Proves that their downstream semantic similarity
    scores against a job description are mathematically identical:
    assert score_a == score_b
    assert abs(score_a - score_b) == 0.0
    """
    job_description = """
    Senior Python Backend Engineer
    Responsibilities:
    - Build and maintain scalable REST and gRPC microservices using Python and FastAPI.
    - Deploy containerized services with Docker on AWS cloud infrastructure.
    - Optimize relational databases including PostgreSQL.
    Qualifications:
    - 5+ years of software development experience with Python.
    - Strong communication, team collaboration, and problem-solving skills.
    """

    resume_male = """
    John Michael Doe
    john.doe@example.com | +1 (555) 123-4567
    Summary:
    John is a Senior Software Engineer with 6 years of experience in Python, FastAPI, and AWS.
    He designed and deployed microservices at ScaleCorp, where his team maintained 99.99% uptime.
    He optimized PostgreSQL databases and mentored 4 junior engineers himself.
    His leadership and technical vision drove a 40% reduction in API response times.
    """

    resume_female = """
    Jane Marie Smith
    jane.smith@example.com | +1 (555) 987-6543
    Summary:
    Jane is a Senior Software Engineer with 6 years of experience in Python, FastAPI, and AWS.
    She designed and deployed microservices at ScaleCorp, where her team maintained 99.99% uptime.
    She optimized PostgreSQL databases and mentored 4 junior engineers herself.
    Her leadership and technical vision drove a 40% reduction in API response times.
    """

    anon_male = anonymize_text(resume_male, candidate_name="John Michael Doe")
    anon_female = anonymize_text(resume_female, candidate_name="Jane Marie Smith")

    # Assert exact textual equivalence after anonymization
    assert anon_male == anon_female

    # Evaluate real SentenceTransformer model (no mocking)
    ranker = ResumeRanker()
    score_male = ranker.compute_semantic_similarity(anon_male, job_description)
    score_female = ranker.compute_semantic_similarity(anon_female, job_description)

    # Mathematical invariance assertions
    assert score_male == score_female
    assert abs(score_male - score_female) == 0.0
    assert score_male > 0.0


def test_evaluation_invariance_rank_candidates() -> None:
    """Mathematically proves evaluation invariance across composite ranking.

    Ensures match_score, semantic_score, skill_overlap_score, matched_skills,
    and missing_skills are identical across demographic variants.
    """
    job_description = """
    Lead Data Engineer
    Requirements:
    - Python, Apache Spark, SQL, Docker, AWS
    - Experience designing high-throughput data pipelines
    """

    candidate_a = {
        "candidate_name": "Carlos Gomez",
        "text": (
            "Carlos Gomez | carlos@example.com | (555) 111-2222\n"
            "Carlos is a Lead Data Engineer proficient in Python, Apache Spark, SQL, Docker, AWS.\n"
            "He built streaming pipelines processing 10TB daily. His team was recognized for excellence."
        ),
    }

    candidate_b = {
        "candidate_name": "Priya Sharma",
        "text": (
            "Priya Sharma | priya@example.com | (555) 333-4444\n"
            "Priya is a Lead Data Engineer proficient in Python, Apache Spark, SQL, Docker, AWS.\n"
            "She built streaming pipelines processing 10TB daily. Her team was recognized for excellence."
        ),
    }

    anon_a = anonymize_resume(candidate_a)
    anon_b = anonymize_resume(candidate_b)

    ranker = ResumeRanker()
    candidates_payload = [
        {"name": "Candidate Alpha", "text": anon_a["anonymized_text"]},
        {"name": "Candidate Beta", "text": anon_b["anonymized_text"]},
    ]

    df = ranker.rank_candidates(job_description, candidates_payload)

    assert len(df) == 2
    score_a = df.loc[0, "match_score"]
    score_b = df.loc[1, "match_score"]

    # Mathematical assertion of zero divergence
    assert score_a == score_b
    assert abs(score_a - score_b) == 0.0

    # Sub-component score assertions
    assert df.loc[0, "semantic_score"] == df.loc[1, "semantic_score"]
    assert df.loc[0, "skill_overlap_score"] == df.loc[1, "skill_overlap_score"]
    assert df.loc[0, "matched_skills"] == df.loc[1, "matched_skills"]
    assert df.loc[0, "missing_skills"] == df.loc[1, "missing_skills"]


def test_evaluation_invariance_multi_demographic_variants() -> None:
    """Verifies evaluation invariance across 4 diverse demographic variants."""
    job_description = (
        "Machine Learning Engineer with experience in Python, PyTorch, Docker, Kubernetes, and SQL."
    )

    variants = [
        {
            "name": "David Miller",
            "email": "david.miller@us-tech.com",
            "phone": "+1-555-432-1098",
            "pronoun_subj": "He",
            "pronoun_pos": "His",
            "pronoun_ref": "himself",
        },
        {
            "name": "Priya Sharma",
            "email": "priya.sharma@corp.co.in",
            "phone": "+91 98765 12345",
            "pronoun_subj": "She",
            "pronoun_pos": "Her",
            "pronoun_ref": "herself",
        },
        {
            "name": "Carlos Garcia",
            "email": "carlos.garcia@madrid-dev.es",
            "phone": "+34 91 123 4567",
            "pronoun_subj": "He",
            "pronoun_pos": "His",
            "pronoun_ref": "himself",
        },
        {
            "name": "Fatima Al-Mansoor",
            "email": "fatima.al-mansoor@gulf.org",
            "phone": "+971 4 123 4567",
            "pronoun_subj": "She",
            "pronoun_pos": "Her",
            "pronoun_ref": "herself",
        },
    ]

    ranker = ResumeRanker()
    anonymized_texts = []
    scores = []

    for v in variants:
        raw = (
            f"{v['name']}\n"
            f"{v['email']} | {v['phone']}\n"
            f"Summary:\n"
            f"{v['name']} is an ML Engineer with 4 years building models in Python and PyTorch.\n"
            f"{v['pronoun_subj']} deployed models using Docker and Kubernetes, querying SQL databases.\n"
            f"{v['pronoun_subj']} managed the pipeline {v['pronoun_ref']}. "
            f"{v['pronoun_pos']} contributions accelerated inference latency by 35%."
        )
        anon = anonymize_text(raw, candidate_name=v["name"])
        anonymized_texts.append(anon)
        score = ranker.compute_semantic_similarity(anon, job_description)
        scores.append(score)

    # Prove all anonymized texts are 100% character-for-character identical
    for anon in anonymized_texts[1:]:
        assert anon == anonymized_texts[0]

    # Prove pairwise scores have strictly 0.0 delta
    for i in range(len(scores)):
        for j in range(i + 1, len(scores)):
            assert scores[i] == scores[j]
            assert abs(scores[i] - scores[j]) == 0.0


# ---------------------------------------------------------------------------
# Milestone M3 Iteration 2 Hardening: Title, Skill, and Heuristic Tests
# ---------------------------------------------------------------------------

def test_evaluation_invariance_academic_and_professional_titles() -> None:
    """Verifies that candidates with academic/professional titles (Dr., Prof., Rev., Mr., Ms.)
    achieve identical semantic similarity and match scores compared to untitled candidates.
    """
    job_description = "Senior Python Backend Engineer with FastAPI, Docker, and AWS."
    base_resume = "Python Engineer with 5 years experience in FastAPI, Docker, and AWS microservices."

    ranker = ResumeRanker()
    variants = [
        ("John Doe", f"John Doe\n{base_resume}"),
        ("Dr. John Doe", f"Dr. John Doe\n{base_resume}"),
        ("Prof. John Doe", f"Prof. John Doe\n{base_resume}"),
        ("Rev. John Doe", f"Rev. John Doe\n{base_resume}"),
        ("Mr. John Doe", f"Mr. John Doe\n{base_resume}"),
        ("Ms. Jane Doe", f"Ms. Jane Doe\n{base_resume}"),
    ]

    anonymized_texts = [anonymize_text(text, candidate_name=name) for name, text in variants]

    # Verify all anonymized texts are character-for-character identical
    for anon in anonymized_texts[1:]:
        assert anon == anonymized_texts[0]

    # Verify semantic similarity scores are mathematically identical
    scores = [ranker.compute_semantic_similarity(anon, job_description) for anon in anonymized_texts]
    for s in scores[1:]:
        assert s == scores[0]
        assert abs(s - scores[0]) == 0.0


@pytest.mark.parametrize(
    "candidate_name,skill_name,resume_snippet",
    [
        (
            "Ruby Johnson",
            "Ruby",
            "Ruby Johnson\nSenior Software Engineer with 5 years building web applications in Ruby and Ruby on Rails.",
        ),
        (
            "Rust Anderson",
            "Rust",
            "Rust Anderson\nSystems Engineer with 4 years programming high-performance services in Rust and C++.",
        ),
        (
            "Swift Taylor",
            "Swift",
            "Swift Taylor\niOS Developer with 5 years experience building native mobile apps in Swift.",
        ),
        (
            "Bash Campbell",
            "Bash",
            "Bash Campbell\nDevOps Engineer proficient in Linux administration, Docker, and Bash scripting.",
        ),
        (
            "Go Tanaka",
            "Go",
            "Go Tanaka\nBackend Engineer with 4 years designing microservices in Go and Kubernetes.",
        ),
    ],
)
def test_candidate_name_skill_collision_protection(
    candidate_name: str, skill_name: str, resume_snippet: str
) -> None:
    """Verifies that candidate names coinciding with technical skills do NOT redact
    the technical skills from the resume, preserving skill extraction and downstream scores.
    """
    from src.skill_extractor import TechnicalSkillExtractor

    extractor = TechnicalSkillExtractor()
    anonymized = anonymize_text(resume_snippet, candidate_name=candidate_name)

    # The candidate's full name is redacted
    assert candidate_name not in anonymized
    assert NAME_TOKEN in anonymized

    # The technical skill is preserved in the text
    assert skill_name in anonymized

    # Skill extraction detects the skill
    extracted = extractor.extract_skills(anonymized)
    assert skill_name in extracted

    if skill_name == "Ruby":
        assert "Ruby on Rails" in extracted


def test_candidate_name_julia_protection() -> None:
    """Verifies that candidate name 'Julia Roberts' does not redact standalone 'Julia'."""
    snippet = "Julia Roberts\nData Scientist with 3 years applying Julia and Python to numerical modeling."
    anonymized = anonymize_text(snippet, candidate_name="Julia Roberts")
    assert "Julia Roberts" not in anonymized
    assert NAME_TOKEN in anonymized
    assert "Julia and Python" in anonymized


def test_candidate_name_skill_collision_score_invariance() -> None:
    """Verifies that Candidate 'Ruby Johnson' and Candidate 'Alice Johnson' achieve
    identical match scores and skill extraction against a Ruby on Rails job description.
    """
    from src.skill_extractor import TechnicalSkillExtractor

    job_description = "Ruby on Rails Backend Engineer with experience in Ruby, PostgreSQL, and AWS."
    resume_ruby = (
        "Ruby Johnson\nruby@example.com | 555-123-4567\n"
        "Summary: Software Engineer with 5 years experience in Ruby, Ruby on Rails, PostgreSQL, and AWS.\n"
        "She architected REST APIs and optimized PostgreSQL queries."
    )
    resume_alice = (
        "Alice Johnson\nalice@example.com | 555-123-4567\n"
        "Summary: Software Engineer with 5 years experience in Ruby, Ruby on Rails, PostgreSQL, and AWS.\n"
        "She architected REST APIs and optimized PostgreSQL queries."
    )

    anon_ruby = anonymize_text(resume_ruby, candidate_name="Ruby Johnson")
    anon_alice = anonymize_text(resume_alice, candidate_name="Alice Johnson")

    assert anon_ruby == anon_alice

    extractor = TechnicalSkillExtractor()
    skills_ruby = extractor.extract_skills(anon_ruby)
    skills_alice = extractor.extract_skills(anon_alice)
    assert skills_ruby == skills_alice
    assert "Ruby" in skills_ruby
    assert "Ruby on Rails" in skills_ruby

    ranker = ResumeRanker()
    score_ruby = ranker.compute_semantic_similarity(anon_ruby, job_description)
    score_alice = ranker.compute_semantic_similarity(anon_alice, job_description)
    assert score_ruby == score_alice
    assert abs(score_ruby - score_alice) == 0.0


def test_candidate_name_modal_verb_and_stopword_protection() -> None:
    """Verifies that candidates with names containing modal verbs (Will, May, Can, Art)
    do not have common verbs, polysemes, or months redacted in narrative text.
    """
    text = (
        "Will Smith\n"
        "will.smith@example.com | 555-019-2834\n"
        "Summary:\n"
        "Will is a Lead Architect. The candidate will lead engineering teams, "
        "will design microservices, and can mentor junior staff. "
        "Work history from May 2020 to Aug 2023 creating state of the art systems."
    )
    anonymized = anonymize_text(text, candidate_name="Will Smith")

    # Name is redacted
    assert "Will Smith" not in anonymized

    # Modal verbs, months, and common phrases are preserved
    assert "will lead" in anonymized
    assert "will design" in anonymized
    assert "can mentor" in anonymized
    assert "May 2020" in anonymized
    assert "Aug 2023" in anonymized
    assert "state of the art" in anonymized


def test_job_title_header_suppression() -> None:
    """Verifies that top-line professional designations (e.g. 'Senior Software Engineer')
    are not falsely detected and redacted as candidate names when candidate_name is omitted.
    """
    text = (
        "Senior Software Engineer\n"
        "Python and Cloud specialist with 8 years experience building backend systems."
    )
    anonymized = anonymize_text(text)

    # Job title should NOT be redacted to [NAME]
    assert "Senior Software Engineer" in anonymized
    assert NAME_TOKEN not in anonymized

