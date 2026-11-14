"""Unit tests for technical skill extraction edge cases (Requirement R3).

Covers:
- C# and C++ sub-span resolution (preventing spurious C)
- Standalone C preservation and slash combinations (C/C++)
- .NET and Node.js tokenization and casing variations (.NET Core, Node-JS)
- Single-letter 'R' matching and false-positive guards (R&D, Toys R Us, Section R, lowercase r, R/Python)
- Java vs JavaScript disambiguation
- Skill alias normalization (JS, TS, K8s, Postgres, Mongo, Golang, Sklearn)
- Plural and singular handling (Dockers -> Docker, Microservice <-> Microservices,
  REST APIs -> REST API, WebSockets, Large Language Models)
- Non-plural protected word safety (Redis, Pandas, Keras, AWS, CSS)
- Multi-token subsumption resolution (React Native vs React)
- Custom skills list containment and isolation
- Custom alias dictionary support
"""

import pytest
from src.skill_extractor import TechnicalSkillExtractor


def test_c_sharp_and_c_plus_plus_subspan_resolution() -> None:
    """Verifies that C# and C++ do not spuriously trigger standalone 'C'."""
    extractor = TechnicalSkillExtractor()

    # C# only -> should not contain C
    res_csharp = extractor.extract_skills("Experienced backend developer specializing in C# and ASP.NET.")
    assert "C#" in res_csharp
    assert "C" not in res_csharp

    # C++ only -> should not contain C
    res_cpp = extractor.extract_skills("High-performance scientific computing using C++ and CUDA.")
    assert "C++" in res_cpp
    assert "C" not in res_cpp

    # Standalone C only -> should contain C
    res_c = extractor.extract_skills("Embedded systems firmware engineer proficient in C and assembly.")
    assert "C" in res_c
    assert "C#" not in res_c
    assert "C++" not in res_c

    # All three present -> all three must be extracted
    res_all = extractor.extract_skills("Extensive experience in systems programming with C, C++, and C#.")
    assert "C" in res_all
    assert "C++" in res_all
    assert "C#" in res_all

    # Slash-separated C/C++ -> both C and C++ extracted
    res_slash = extractor.extract_skills("Firmware developer proficient in C/C++.")
    assert "C" in res_slash
    assert "C++" in res_slash


def test_dotnet_and_nodejs_variations() -> None:
    """Verifies extraction and normalization of .NET and Node.js casing and tokenization variations."""
    extractor = TechnicalSkillExtractor()

    # Node.js variations
    texts_node = [
        "Backend services built with Node.js and Express.",
        "Experienced in NodeJS backend architecture.",
        "Full stack engineer using node.js and React.",
        "Hands-on expertise with Node.JS microservices.",
        "Developed APIs using nodejs and MongoDB.",
        "Node-JS backend microservices.",
    ]
    for text in texts_node:
        extracted = extractor.extract_skills(text)
        assert "Node.js" in extracted, f"Failed to extract Node.js from: {text}"

    # Node-JS hyphen guard: verify JS inside Node-JS does NOT trigger JavaScript
    res_node_hyphen = extractor.extract_skills("Node-JS backend developer.")
    assert "Node.js" in res_node_hyphen
    assert "JavaScript" not in res_node_hyphen

    # .NET variations
    texts_dotnet = [
        "Enterprise applications built on .NET framework.",
        "Skilled in dotnet microservices.",
        "Developed enterprise backend with .net and SQL Server.",
        "Experience in C# and DotNet development.",
    ]
    for text in texts_dotnet:
        extracted = extractor.extract_skills(text)
        assert ".NET" in extracted, f"Failed to extract .NET from: {text}"

    # .NET Core variation: sub-span resolution keeps .NET Core and suppresses .NET
    res_dotnet_core = extractor.extract_skills("Skilled in dotnet Core microservices.")
    assert ".NET Core" in res_dotnet_core
    assert ".NET" not in res_dotnet_core


def test_single_letter_r_guard() -> None:
    """Verifies that programming language 'R' is extracted while guarding against false positives."""
    extractor = TechnicalSkillExtractor()

    # Valid positive cases
    positives = [
        "Data analyst with deep expertise in R, Python, and SQL.",
        "Built statistical machine learning models using R programming.",
        "Proficient in R scripts and data visualization with ggplot2.",
        "Skills: Python, R, and Julia.",
        "Proficient in R/Python and R/SQL.",
        "Data analyst with deep expertise in R, Python, and R&D.",
    ]
    for text in positives:
        extracted = extractor.extract_skills(text)
        assert "R" in extracted, f"Failed positive match for R in: {text}"

    # False positive negative cases
    negatives = [
        "Managed engineering projects in the R&D department.",
        "Collaborated closely with the R & D division on new patents.",
        "Engineering work in R/D team.",
        "Previous customer service cashier role at Toys R Us.",
        "Former associate at Toys 'R' Us retail store.",
        'Toy department manager at Toys "R" Us.',
        "Please refer to Section R of the employee handbook.",
        "See Appendix R and Figure R for details.",
        "Refer to Table R in Chapter 4.",
        "Tested Model R in Phase R trials.",
        "Vitamin R dietary supplement.",
        "See clause (r) in Appendix A.",
        "See clause (R) in Appendix B.",
        "Registered trademark Windows(R) environment.",
        "Hey, how r u doing today?",
        "Worked on research and development initiatives.",
        "Correlation coefficient r = 0.85 in analysis.",
        "Regression model R-squared was 0.95.",
        "Adjusted R^2 exceeded 0.90.",
    ]
    for text in negatives:
        extracted = extractor.extract_skills(text)
        assert "R" not in extracted, f"False positive match for R in: {text}"


def test_java_vs_javascript_disambiguation() -> None:
    """Verifies that JavaScript and Java Script do not trigger Java, and vice-versa."""
    extractor = TechnicalSkillExtractor()

    # JavaScript only
    res_js = extractor.extract_skills("Frontend development using JavaScript and HTML5.")
    assert "JavaScript" in res_js
    assert "Java" not in res_js

    # Java Script (spaced)
    res_js_space = extractor.extract_skills("Built responsive user interfaces with Java Script and React.")
    assert "JavaScript" in res_js_space
    assert "Java" not in res_js_space

    # Java only
    res_java = extractor.extract_skills("Backend engineer building enterprise microservices in Java and Spring Boot.")
    assert "Java" in res_java
    assert "JavaScript" not in res_java

    # Both Java and JavaScript present
    res_both = extractor.extract_skills("Full-stack engineer proficient in Java backend and JavaScript frontend.")
    assert "Java" in res_both
    assert "JavaScript" in res_both


def test_skill_alias_normalization() -> None:
    """Verifies that common technical skill aliases normalize to canonical taxonomy names."""
    extractor = TechnicalSkillExtractor()

    # Uppercase and lowercase alias variations
    res = extractor.extract_skills("Proficient in JS, ts, K8S, POSTGRES, and mongo.")
    assert "JavaScript" in res
    assert "TypeScript" in res
    assert "Kubernetes" in res
    assert "PostgreSQL" in res
    assert "MongoDB" in res

    # Check additional aliases
    res2 = extractor.extract_skills("Deployed applications with Golang and Sklearn.")
    assert ("Go" in res2 or "Golang" in res2)
    assert "Scikit-Learn" in res2


def test_plural_and_singular_handling() -> None:
    """Verifies matching and canonicalization of plurals and singulars."""
    extractor = TechnicalSkillExtractor()

    # Dockers -> Docker
    res_docker = extractor.extract_skills("Containerized deployments using Dockers.")
    assert "Docker" in res_docker

    # Microservice (singular) -> Microservices (canonical)
    res_micro = extractor.extract_skills("Architected an event-driven microservice in Go.")
    assert "Microservices" in res_micro

    # Microservices (plural) -> Microservices (canonical)
    res_micros = extractor.extract_skills("Hands-on experience with scalable microservices.")
    assert "Microservices" in res_micros

    # REST APIs -> REST API
    res_rest = extractor.extract_skills("Designed REST APIs and consumed external RESTful APIs.")
    assert "REST API" in res_rest

    # WebSocket -> WebSockets
    res_ws = extractor.extract_skills("Implemented low-latency WebSocket communication.")
    assert "WebSockets" in res_ws

    # Large Language Model -> Large Language Models
    res_llm = extractor.extract_skills("Fine-tuned a Large Language Model for domain summarization.")
    assert "Large Language Models" in res_llm

    # LLMs -> Large Language Models
    res_llms = extractor.extract_skills("Evaluated cutting-edge LLMs and Generative AI techniques.")
    assert "Large Language Models" in res_llms


def test_protected_non_plurals_safety() -> None:
    """Verifies that skills inherently ending with 's' or other characters are never corrupted."""
    extractor = TechnicalSkillExtractor()

    res = extractor.extract_skills("Proficient in Redis, Pandas, Keras, Kubernetes, AWS, and CSS.")
    assert "Redis" in res
    assert "Pandas" in res
    assert "Keras" in res
    assert "Kubernetes" in res
    assert "AWS" in res
    assert "CSS" in res


def test_multi_token_subspan_resolution() -> None:
    """Verifies that multi-token skills suppress their sub-token components."""
    extractor = TechnicalSkillExtractor()

    # React Native vs React: React Native should suppress React
    res_rn = extractor.extract_skills("Mobile developer with React Native experience.")
    assert "React Native" in res_rn
    assert "React" not in res_rn

    # Both React and React Native present independently
    res_both = extractor.extract_skills("Expert in React frontend and React Native mobile development.")
    assert "React" in res_both
    assert "React Native" in res_both


def test_custom_skills_list_with_aliases_and_plurals(sample_skills_data: list[str]) -> None:
    """Verifies that custom skills_list correctly maps aliases/plurals only for active skills."""
    # sample_skills_data contains: Python, FastAPI, Docker, Kubernetes, PostgreSQL, AWS, React, TypeScript, C++, .NET, Machine Learning
    extractor = TechnicalSkillExtractor(skills_list=sample_skills_data)

    text = "Experience with Dockers, TS, K8s, and JS."
    extracted = extractor.extract_skills(text)

    # Active in sample_skills_data:
    assert "Docker" in extracted
    assert "TypeScript" in extracted
    assert "Kubernetes" in extracted

    # NOT in sample_skills_data (JavaScript is not in sample_skills_data fixture):
    assert "JavaScript" not in extracted


def test_custom_aliases_override() -> None:
    """Verifies that custom_aliases passed to constructor work as intended."""
    custom = {"py": "Python", "kube-cluster": "Kubernetes"}
    extractor = TechnicalSkillExtractor(custom_aliases=custom)

    res = extractor.extract_skills("Developed in py and deployed to kube-cluster.")
    assert "Python" in res
    assert "Kubernetes" in res
