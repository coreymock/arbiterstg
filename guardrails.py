# guardrails.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal
import re

Decision = Literal["ALLOW", "ALLOW_REDACTED", "REFUSE"]

@dataclass
class GuardrailResult:
    decision: Decision
    reasons: List[str]
    confidence: float  # 0..1 (heuristic)

# Keep this small and sane. Expand later.
# Goal: hard-stop CSAM-ish framing; allow legal/clinical/news contexts; redact when needed.

DOC_CONTEXT_CUES = [
    r"\b(case\s+no\.|docket|plaintiff|defendant|court|affidavit|indictment|testimony)\b",
    r"\b(judge|jury|prosecutor|defense\s+counsel|sentencing|probation)\b",
    r"\b(reporting|investigation|journalism|according\s+to|witness)\b",
    r"\b(study|paper|research|methodology|dataset|ethics\s+approval)\b",
    r"\b(therapy|counsel(or|ing)|clinical|diagnos(is|ed)|patient)\b",
]

# High-risk combination example: (minor/child) + (explicit sexual framing) => refuse.
HIGH_RISK_COMBINATIONS = [
    (r"\b(minor|child|underage)\b", r"\b(sexual|pornographic|explicit)\b"),
]

# “Sensitive” terms that can appear in legitimate contexts.
SENSITIVE_TRIGGERS = [
    r"\b(rape|sexual\s+assault|molest(ed|ation)|incest)\b",
    r"\b(abuse|abused|abuser|assault|violence|violent)\b",
]

def _has_any(patterns: List[str], text: str) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)

def _has_pair(a_pat: str, b_pat: str, text: str) -> bool:
    return re.search(a_pat, text, flags=re.IGNORECASE) and re.search(b_pat, text, flags=re.IGNORECASE)

def evaluate_text(text: str) -> GuardrailResult:
    t = text or ""
    reasons: List[str] = []

    # 1) Hard refuse combinations (keep narrow, not a glossary)
    for a_pat, b_pat in HIGH_RISK_COMBINATIONS:
        if _has_pair(a_pat, b_pat, t):
            reasons.append("High-risk combination detected (minor/underage + explicit sexual framing).")
            return GuardrailResult(decision="REFUSE", reasons=reasons, confidence=0.95)

    # 2) Context-aware handling for sensitive but legitimate material
    has_sensitive = _has_any(SENSITIVE_TRIGGERS, t)
    has_doc_context = _has_any(DOC_CONTEXT_CUES, t)

    if has_sensitive and has_doc_context:
        reasons.append("Sensitive terms detected in documentary/legal/clinical context → allow with redaction.")
        return GuardrailResult(decision="ALLOW_REDACTED", reasons=reasons, confidence=0.70)

    if has_sensitive:
        reasons.append("Sensitive terms detected without clear documentary/legal/clinical context → allow with redaction.")
        return GuardrailResult(decision="ALLOW_REDACTED", reasons=reasons, confidence=0.60)

    return GuardrailResult(decision="ALLOW", reasons=["No guardrail triggers."], confidence=0.10)

def redact_text(text: str) -> str:
    """Minimal redaction: replace matched sensitive triggers with [REDACTED]."""
    t = text or ""
    for pat in SENSITIVE_TRIGGERS:
        t = re.sub(pat, "[REDACTED]", t, flags=re.IGNORECASE)
    return t