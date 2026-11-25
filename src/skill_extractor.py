"""Technical skill extraction engine using spaCy.

Extracts technical/IT skills from resumes and job descriptions using
spaCy's PhraseMatcher and a curated technical taxonomy.
Handles sub-span resolution (C# vs C, C++ vs C), case-sensitive guards ('R'),
tokenization variations (.NET, Node.js), alias normalization, and plurals.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import spacy
from spacy.matcher import PhraseMatcher
from spacy.tokens import Span
from spacy.util import filter_spans

from src.config import DEFAULT_SKILLS_FILE

# Terms that should NEVER have trailing 's' stripped or added
PROTECTED_NON_PLURALS: set[str] = {
    "css",
    "sass",
    "cypress",
    "redis",
    "keras",
    "pandas",
    "kubernetes",
    "jenkins",
    "prometheus",
    "serverless",
    "aws",
    "amazon web services",
    "mlops",
    "devops",
    "postgres",
    "confluence",
    "bitbucket",
    "express.js",
    "node.js",
    "next.js",
    "vue.js",
    "react.js",
    "angularjs",
    "r",
    "c",
    "go",
    "js",
    "ts",
    "pl/sql",
    "graphql",
    "spring",
    "spark",
    "hadoop",
    "ruby on rails",
}

# Curated alias and inflection mapping dictionary
DEFAULT_SKILL_ALIASES: dict[str, str] = {
    # .NET
    "dotnet": ".NET",
    "dot net": ".NET",
    "dot-net": ".NET",
    ".net": ".NET",
    "dotnet core": ".NET Core",
    ".net core": ".NET Core",
    "asp.net": "ASP.NET",
    "aspnet": "ASP.NET",

    # Node.js
    "nodejs": "Node.js",
    "node js": "Node.js",
    "node-js": "Node.js",
    "node.js": "Node.js",

    # JavaScript
    "java script": "JavaScript",
    "java-script": "JavaScript",
    "js": "JavaScript",

    # TypeScript
    "type script": "TypeScript",
    "type-script": "TypeScript",
    "ts": "TypeScript",

    # Kubernetes
    "k8s": "Kubernetes",
    "kube": "Kubernetes",

    # PostgreSQL
    "postgres": "PostgreSQL",
    "pgsql": "PostgreSQL",

    # MongoDB
    "mongo": "MongoDB",

    # Scikit-Learn
    "sklearn": "Scikit-Learn",

    # Go
    "golang": "Go",

    # C# & C++
    "csharp": "C#",
    "c-sharp": "C#",
    "cpp": "C++",
    "cplusplus": "C++",

    # Framework hyphen guards & variants
    "react-js": "React",
    "reactjs": "React",
    "react.js": "React",
    "react js": "React",
    "vue-js": "Vue.js",
    "vuejs": "Vue.js",
    "vue.js": "Vue.js",
    "vue js": "Vue.js",
    "next-js": "Next.js",
    "nextjs": "Next.js",
    "next.js": "Next.js",
    "next js": "Next.js",
    "express-js": "Express.js",
    "expressjs": "Express.js",
    "angularjs": "AngularJS",
    "angular.js": "AngularJS",

    # Plurals & Architecture
    "dockers": "Docker",
    "microservice": "Microservices",
    "microservices": "Microservices",
    "micro services": "Microservices",
    "micro-services": "Microservices",
    "micro-service": "Microservices",
    "rest apis": "REST API",
    "restful apis": "REST API",
    "rest api": "REST API",
    "rest-api": "REST API",
    "rest-apis": "REST API",
    "restful api": "REST API",
    "websocket": "WebSockets",
    "websockets": "WebSockets",
    "web socket": "WebSockets",
    "web sockets": "WebSockets",
    "large language model": "Large Language Models",
    "large language models": "Large Language Models",
    "llm": "Large Language Models",
    "llms": "Large Language Models",
}

# Regex patterns for non-programming usages of single-letter 'R'
FALSE_R_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\btoys\s*[\"'\u201c\u201d\u2018\u2019`]?\s*r\s*[\"'\u201c\u201d\u2018\u2019`]?\s*us\b", re.IGNORECASE),
    re.compile(r"\br\s*&\s*d\b", re.IGNORECASE),
    re.compile(r"\br\s*/\s*d\b", re.IGNORECASE),
    re.compile(
        r"\b(?:section|appendix|chapter|figure|table|part|room|building|terminal|gate|model|level|grade|class|track|phase|group|team|category|type|tier|schedule|vitamin|ward|unit|series)[-\s]+[\"'\u201c\u201d\u2018\u2019`]?\s*r\b",
        re.IGNORECASE,
    ),
    re.compile(r"\br\s*[-^]?\s*(?:squared|2)\b", re.IGNORECASE),
    re.compile(r"\(\s*r\s*\)", re.IGNORECASE),
    re.compile(r"\bhow\s+r\s+u\b|\br\s+u\b", re.IGNORECASE),
]

# Regex patterns for non-programming compound usages of single-letter 'C'
FALSE_C_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bobjective\s*[-]?\s*c\b", re.IGNORECASE),
    re.compile(r"\bc\s*-\s*(?:suite|level|corp|corporation|section|class|band|rank|exec|executive)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:vitamin|type|grade|option|plan|appendix|section|schedule|exhibit|class|tier|track|phase|model|part|unit|usb)\s*[-]?\s*c\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bc\s*/\s*o\b", re.IGNORECASE),
]


class TechnicalSkillExtractor:
    """Extracts technical/IT skills using spaCy PhraseMatcher with edge case resolution."""

    def __init__(
        self,
        skills_path: Path | None = None,
        skills_list: list[str] | None = None,
        custom_aliases: dict[str, str] | None = None,
    ) -> None:
        """Initializes the skill extractor with a spaCy pipeline and skill taxonomy.

        Args:
            skills_path: Path to the JSON file containing the technical skills.
            skills_list: Optional explicit list of skills (takes precedence over file).
            custom_aliases: Optional dictionary of additional alias mappings.
        """
        self.nlp = spacy.load(
            "en_core_web_sm",
            exclude=["tok2vec", "tagger", "parser", "attribute_ruler", "lemmatizer", "ner"],
        )
        self.matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")

        if skills_list is not None:
            raw_skills = skills_list
        else:
            target_path = skills_path or DEFAULT_SKILLS_FILE
            raw_skills = self._load_skills_from_json(target_path)

        # Canonical lookup dictionary: lowercased skill string -> canonical display name
        self.canonical_skills: dict[str, str] = {s.lower().strip(): s.strip() for s in raw_skills}
        self.lookup: dict[str, str] = dict(self.canonical_skills)

        # Check if single-letter 'R' is part of the active taxonomy
        self._has_r: bool = "r" in self.canonical_skills

        # 1. Register explicit aliases whose canonical target is in the active taxonomy
        aliases_to_use = dict(DEFAULT_SKILL_ALIASES)
        if custom_aliases:
            aliases_to_use.update(custom_aliases)

        for alias, target in aliases_to_use.items():
            t_low = target.lower().strip()
            if t_low in self.canonical_skills:
                self.lookup[alias.lower().strip()] = self.canonical_skills[t_low]

        # 2. Register rule-based plural/singular variants for active skills
        for s_low, s_canon in list(self.canonical_skills.items()):
            if s_low in PROTECTED_NON_PLURALS or len(s_low) <= 2 or s_low.endswith((".js", "ss", "us", "is", "less")):
                continue
            words = s_low.split()
            last = words[-1]
            if last.endswith("s") and not last.endswith(("ss", "us", "is", "less")) and last not in PROTECTED_NON_PLURALS:
                sing = " ".join(words[:-1] + [last[:-1]])
                if sing not in self.lookup:
                    self.lookup[sing] = s_canon
            else:
                if not last.endswith(("#", "+", "3", "5")):
                    plur = " ".join(words[:-1] + [last + "s"])
                    if plur not in self.lookup:
                        self.lookup[plur] = s_canon

        # Build phrase matcher patterns (single-letter 'R' is handled exclusively via _has_valid_r)
        patterns = []
        for text in self.lookup.keys():
            if text == "r":
                continue
            patterns.append(self.nlp.make_doc(text))
            # Handle tokenization splits for dotted skills like Node.JS vs node.js vs NODE.JS
            if text.endswith(".js"):
                base = text[:-3]
                patterns.append(self.nlp.make_doc(f"{base.capitalize()}.JS"))
                patterns.append(self.nlp.make_doc(f"{base.upper()}.JS"))
            elif "." in text:
                patterns.append(self.nlp.make_doc(text.upper()))

        if patterns:
            self.matcher.add("TECHNICAL_SKILLS", patterns)

    @staticmethod
    def _load_skills_from_json(file_path: Path) -> list[str]:
        """Loads technical skills list from a JSON file.

        Args:
            file_path: Path to JSON taxonomy file.

        Returns:
            List of skill strings.

        Raises:
            FileNotFoundError: If the skills JSON file does not exist.
            ValueError: If the JSON is invalid or lacks a 'skills' key.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Skills taxonomy file not found at: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or "skills" not in data:
                raise ValueError("JSON file must contain a root 'skills' list.")
            return data["skills"]
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in skills file: {exc}") from exc

    def _has_valid_r(self, text: str) -> bool:
        """Determines if the text contains a valid reference to the programming language 'R'.

        Args:
            text: Input text.

        Returns:
            True if text references 'R' as a programming language, False otherwise.
        """
        if not self._has_r:
            return False

        # Must have standalone uppercase 'R'
        if not re.search(r"\bR\b", text):
            return False

        # Mask out false positive patterns with spaces
        masked = text
        for pat in FALSE_R_PATTERNS:
            for m in pat.finditer(masked):
                s, e = m.span()
                masked = masked[:s] + " " * (e - s) + masked[e:]

        return bool(re.search(r"\bR\b", masked))

    @staticmethod
    def _mask_false_c(text: str) -> str:
        """Masks out non-programming occurrences of 'C' (e.g. C-Suite, Objective-C, USB-C).

        Args:
            text: Input text.

        Returns:
            Text with false-C occurrences masked with whitespace preserving character positions.
        """
        masked = text
        for pat in FALSE_C_PATTERNS:
            for m in pat.finditer(masked):
                s, e = m.span()
                masked = masked[:s] + " " * (e - s) + masked[e:]
        return masked

    def extract_skills(self, text: str) -> list[str]:
        """Extracts unique technical skills found in the provided text.

        Resolves overlapping spans via filter_spans (e.g. C# vs C, JavaScript vs Java),
        enforces case guards for single-letter 'R', suppresses non-programming 'C' compounds,
        and normalizes aliases/plurals.

        Args:
            text: Input text (resume content or job description).

        Returns:
            Sorted list of canonical technical skill names found.
        """
        if not text or not isinstance(text, str):
            return []

        # 1. Normalize slashes around dotted frameworks (.js), sharp/plus (#/+), and .NET
        # to prevent spaCy's tokenizer from agglomerating adjacent tokens into a single URL token.
        normalized_text = re.sub(r"(?<=\.js)/(?=[A-Za-z#\.\+])", " / ", text, flags=re.IGNORECASE)
        normalized_text = re.sub(r"(?<=[#\+])/(?=[A-Za-z0-9\.\+#])", " / ", normalized_text)
        normalized_text = re.sub(r"/(?=\.net\b)", " / ", normalized_text, flags=re.IGNORECASE)

        # 2. Mask non-programming usages of 'C' (e.g. C-Suite, Objective-C, Vitamin-C)
        masked_text = self._mask_false_c(normalized_text)

        doc = self.nlp(masked_text)
        matches = self.matcher(doc)

        spans = [Span(doc, start, end, label=match_id) for match_id, start, end in matches]
        filtered_spans = filter_spans(spans)

        found_skills: set[str] = set()
        for span in filtered_spans:
            matched_key = span.text.lower().strip()
            if matched_key in self.lookup:
                found_skills.add(self.lookup[matched_key])

        # Evaluate specialized single-letter 'R' guard on normalized text
        if self._has_r and self._has_valid_r(normalized_text):
            found_skills.add(self.canonical_skills["r"])

        return sorted(found_skills)

    @staticmethod
    def calculate_skill_overlap(
        resume_skills: list[str],
        job_skills: list[str],
    ) -> dict[str, Any]:
        """Calculates overlap statistics between candidate skills and job description skills.

        Args:
            resume_skills: List of skills extracted from candidate resume.
            job_skills: List of skills extracted from job description.

        Returns:
            Dict containing matched_skills, missing_skills, extra_skills, and overlap_ratio.
        """
        resume_set = {s.lower(): s for s in resume_skills}
        job_set = {s.lower(): s for s in job_skills}

        matched_keys = resume_set.keys() & job_set.keys()
        missing_keys = job_set.keys() - resume_set.keys()
        extra_keys = resume_set.keys() - job_set.keys()

        matched_skills = sorted([job_set[k] for k in matched_keys])
        missing_skills = sorted([job_set[k] for k in missing_keys])
        extra_skills = sorted([resume_set[k] for k in extra_keys])

        overlap_ratio = len(matched_skills) / len(job_skills) if job_skills else 0.0

        return {
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "extra_skills": extra_skills,
            "overlap_ratio": round(overlap_ratio, 4),
        }
