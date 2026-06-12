"""Job-title targeting: only score/apply to jobs whose title plausibly matches
the user's target keywords. Everything else is skipped as ``title_mismatch``
before any page fetch or LLM call."""
from __future__ import annotations

import re

# Words too generic to count as a match signal on their own.
_GENERIC = frozenset({
    "senior", "sr", "junior", "jr", "lead", "principal", "staff", "head",
    "i", "ii", "iii", "iv", "v", "1", "2", "3",
    "and", "or", "of", "the", "a", "an", "for", "with", "in", "at", "to",
    "remote", "hybrid", "onsite", "fresher", "experienced", "immediate",
    "urgent", "hiring", "opening", "required", "wanted", "needed",
})

# Common equivalences so "QA Engineer" matches "Quality Assurance Engineer" etc.
_SYNONYMS: dict[str, set[str]] = {
    "qa": {"quality", "tester", "testing", "test", "sdet"},
    "sdet": {"qa", "test", "testing", "automation"},
    "developer": {"engineer", "programmer", "dev"},
    "engineer": {"developer", "engineering", "dev"},
    "frontend": {"front-end", "front", "ui"},
    "backend": {"back-end", "back"},
    "fullstack": {"full-stack", "full"},
    "devops": {"sre", "infrastructure"},
    "analyst": {"analytics", "analysis"},
}


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9+#.]+", (text or "").lower()) if t]


def _significant(tokens: list[str]) -> list[str]:
    return [t for t in tokens if t not in _GENERIC and len(t) > 1]


def _token_matches(kw_token: str, title_tokens: set[str]) -> bool:
    if kw_token in title_tokens:
        return True
    # prefix match handles plural/verb forms ("test" ~ "testing", "tester")
    if any(t.startswith(kw_token) or kw_token.startswith(t)
           for t in title_tokens if len(t) > 2 and len(kw_token) > 2):
        return True
    syn = _SYNONYMS.get(kw_token, set())
    return bool(syn & title_tokens)


def title_matches(job_title: str, keywords: list[str]) -> bool:
    """True if the job title plausibly matches AT LEAST ONE target keyword.

    Rule: at least half (rounded up) of a keyword's significant tokens must
    appear in the title (with prefix/synonym tolerance). Keywords with no
    significant tokens are ignored; no keywords at all → allow everything
    (no filter configured).
    """
    sig_keywords = [(_significant(_tokens(kw)), kw) for kw in (keywords or [])]
    sig_keywords = [(toks, kw) for toks, kw in sig_keywords if toks]
    if not sig_keywords:
        return True

    title_tokens = set(_tokens(job_title))
    if not title_tokens:
        return False

    for kw_tokens, _ in sig_keywords:
        needed = (len(kw_tokens) + 1) // 2
        hits = sum(1 for t in kw_tokens if _token_matches(t, title_tokens))
        if hits >= needed:
            return True
    return False
