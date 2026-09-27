"""Post-generation hallucination guard for legal AI responses.

Extracts law citations from AI-generated text, verifies each against the
indian_law_kb knowledge base, and appends warnings for unverified or
contextually mismatched references before the answer reaches the user.
"""
from __future__ import annotations

import re
from typing import Any

from .indian_law_kb import lookup_section

# ---------------------------------------------------------------------------
# 1. Extract citations from AI output
# ---------------------------------------------------------------------------

# Patterns that capture (section_number, act_identifier) pairs
_CITATION_PATTERNS: list[re.Pattern[str]] = [
    # "Section 420 of IPC", "Section 302 IPC", "Sec. 138 NI Act"
    re.compile(
        r"(?:Section|Sec\.?)\s*(\d+[A-Za-z]*)\s+(?:of\s+)?([A-Za-z][\w\s]*?)(?=[,.\s;:\)\]\n])",
        re.IGNORECASE,
    ),
    # "IPC 420", "BNS 318", "CrPC 154"
    re.compile(
        r"\b(IPC|BNS|CrPC|BNSS|BSA|POCSO|PWDVA|NI Act|IT Act|RTI|IDA|ICA|CPA|TPA|COI)"
        r"\s+(?:Section|Sec\.?)?\s*(\d+[A-Za-z]*)",
        re.IGNORECASE,
    ),
    # "Article 21", "Article 14"
    re.compile(
        r"\bArticle\s+(\d+[A-Za-z]*)\b",
        re.IGNORECASE,
    ),
]

# Maps commonly-seen act names in AI output to the short codes used by lookup_section()
_ACT_NORMALIZE: dict[str, str] = {
    "indian penal code": "IPC",
    "bharatiya nyaya sanhita": "BNS",
    "code of criminal procedure": "CrPC",
    "criminal procedure code": "CrPC",
    "bharatiya nagarik suraksha sanhita": "BNSS",
    "bharatiya sakshya adhiniyam": "BSA",
    "evidence act": "BSA",
    "indian evidence act": "BSA",
    "consumer protection act": "CPA",
    "negotiable instruments act": "NI Act",
    "information technology act": "IT Act",
    "constitution of india": "COI",
    "constitution": "COI",
    "transfer of property act": "TPA",
    "right to information act": "RTI",
    "industrial disputes act": "IDA",
    "indian contract act": "ICA",
    "contract act": "ICA",
    "protection of children from sexual offences act": "POCSO",
    "protection of women from domestic violence act": "PWDVA",
    "domestic violence act": "PWDVA",
}


def _normalize_act(raw_act: str) -> str:
    """Normalize a free-text act name to its short code."""
    cleaned = raw_act.strip().rstrip(".,;:")
    upper = cleaned.upper()
    # Already a short code?
    if upper in {
        "IPC", "BNS", "CRPC", "BNSS", "BSA", "POCSO", "PWDVA",
        "NI ACT", "IT ACT", "RTI", "IDA", "ICA", "CPA", "TPA", "COI",
    }:
        return upper if upper not in ("NI ACT", "IT ACT") else cleaned.upper()
    # Try the long-name map
    lower = cleaned.lower()
    for pattern, short in _ACT_NORMALIZE.items():
        if pattern in lower:
            return short
    return cleaned


def extract_citations(answer: str) -> list[dict[str, str]]:
    """Extract law section citations from an AI-generated answer.

    Returns a list of dicts: {"section": "420", "act": "IPC", "raw": "Section 420 IPC"}
    """
    seen: set[tuple[str, str]] = set()
    citations: list[dict[str, str]] = []

    for pattern in _CITATION_PATTERNS:
        for match in pattern.finditer(answer):
            groups = match.groups()
            if len(groups) == 1:
                # Article pattern — only section captured
                section = groups[0]
                act = "COI"
            elif pattern == _CITATION_PATTERNS[1]:
                # Act-first pattern: (act, section)
                act = _normalize_act(groups[0])
                section = groups[1]
            else:
                # Section-first pattern: (section, act)
                section = groups[0]
                act = _normalize_act(groups[1])

            key = (section.upper(), act.upper())
            if key not in seen:
                seen.add(key)
                citations.append({
                    "section": section,
                    "act": act,
                    "raw": match.group(0).strip(),
                })

    return citations


# ---------------------------------------------------------------------------
# 2. Verify citations against the knowledge base
# ---------------------------------------------------------------------------

# Category mapping for mismatch detection — mirrors rag_pipeline.LEGAL_ISSUE_CATEGORIES
_LEGAL_ISSUE_CATEGORIES: dict[str, list[str]] = {
    "fraud_cheating": ["fraud", "cheat", "deceive", "misrepresentation", "420", "false promise", "scam"],
    "breach_contract": ["breach", "default", "not paid", "didn't deliver", "violation", "broke the agreement"],
    "employment": ["salary", "fired", "terminated", "employer", "employee", "retrenchment", "labour", "workman", "notice period"],
    "tenancy_property": ["rent", "tenant", "landlord", "eviction", "lease", "property", "possession"],
    "consumer": ["product", "defective", "consumer", "refund", "service deficiency", "online purchase"],
    "criminal": ["murder", "theft", "assault", "rape", "robbery", "arrested", "fir", "bail", "accused"],
    "family_matrimonial": ["divorce", "maintenance", "alimony", "custody", "marriage", "dowry", "cruelty"],
    "cyber_it": ["hacking", "cyber", "online fraud", "password", "data", "social media", "defamatory post"],
    "fundamental_rights": ["fundamental right", "discrimination", "article 21", "liberty", "free speech"],
    "child_protection": ["child", "minor", "pocso", "juvenile"],
}


def _spot_legal_issues(question: str) -> list[str]:
    """Identify which legal issue categories the question falls into."""
    question_lower = question.lower()
    detected = []
    for category, patterns in _LEGAL_ISSUE_CATEGORIES.items():
        if any(p in question_lower for p in patterns):
            detected.append(category)
    return detected


def verify_citations(
    citations: list[dict[str, str]],
    question: str,
) -> list[dict[str, Any]]:
    """Verify each citation against the KB and check contextual relevance.

    Returns enriched citation dicts with 'verified', 'kb_result', and
    'mismatch_warning' fields.
    """
    question_categories = _spot_legal_issues(question)
    results: list[dict[str, Any]] = []

    for cite in citations:
        query_str = f"{cite['act']} {cite['section']}"
        kb_result = lookup_section(query_str)

        entry: dict[str, Any] = {
            **cite,
            "verified": kb_result is not None,
            "kb_result": kb_result,
            "mismatch_warning": None,
        }

        # Check for category mismatch
        if kb_result and question_categories:
            cite_category = kb_result.get("category", "")
            # Simple heuristic: if the cited section's category has no overlap
            # with any detected issue category, flag it
            if cite_category and cite_category not in question_categories:
                # Check via keyword overlap as a softer signal
                cite_keywords = kb_result.get("keywords", [])
                question_lower = question.lower()
                has_overlap = any(kw in question_lower for kw in cite_keywords)
                if not has_overlap:
                    entry["mismatch_warning"] = (
                        f"{cite['raw']} relates to \"{kb_result.get('title', cite_category)}\", "
                        f"which may not directly apply to your query."
                    )

        results.append(entry)

    return results


# ---------------------------------------------------------------------------
# 3. Guard the full response
# ---------------------------------------------------------------------------

def guard_response(answer: str, question: str) -> str:
    """Run hallucination checks on an AI answer and append warnings if needed.

    This is the main entry point. Call after the LLM generates its response
    but before returning it to the user.
    """
    citations = extract_citations(answer)
    if not citations:
        return answer

    verified = verify_citations(citations, question)

    warnings: list[str] = []

    # Collect unverified citations
    unverified = [v for v in verified if not v["verified"]]
    if unverified:
        refs = ", ".join(f'"{v["raw"]}"' for v in unverified)
        warnings.append(
            f"⚠️ **Verification Note:** The reference(s) {refs} could not be "
            f"verified against our legal database. Please confirm with a qualified lawyer."
        )

    # Collect mismatched citations
    mismatched = [v for v in verified if v["mismatch_warning"]]
    for m in mismatched:
        warnings.append(f"⚠️ **Context Note:** {m['mismatch_warning']}")

    if warnings:
        warning_block = "\n\n---\n" + "\n".join(warnings)
        return answer + warning_block

    return answer
