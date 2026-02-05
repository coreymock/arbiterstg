#!/usr/bin/env python3
"""
arbiterstg.py — ArbiterSTG (ASTG) v1.0
Structural Trace Governance — Diagnostic / Non-Governing

Consumes a v1.0 trace JSON produced by tracegen.py and emits an Arbiter report:
- Segment-level classification:
  * Admission: admissible / contested / inert
  * Masking suggestion: masked / unmasked
  * Routing labels: which futures are structurally eligible (labels only)
  * Stability flags: saturation / collapse risk / authority-smuggling risk

- Aggregate:
  * Counts
  * Failure taxonomy triggers (structural, not moral)
  * Proxy doctrine notes (numbers are geometry proxies only)

No new operators. No execution claims.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


VERSION = "1.0"
CANONICAL_NAME = "ArbiterSTG"
ABBREV = "ASTG"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


@dataclass
class SegmentDecision:
    seg_id: str
    admissibility: str  # admissible|contested|inert
    masking: str        # masked|unmasked
    mode: str           # routing|shadow
    routing_labels: List[str]
    stability_flags: List[str]
    confidence_proxy: float
    reasons: List[str]


def load_trace(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, obj: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def get_proxy(seg: Dict[str, Any], key: str, default: float = 0.0) -> float:
    # Expect proxies stored like {"score": 0.23} or direct number.
    val = seg.get(key)
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, dict):
        # common keys
        for k in ("score", "strength", "value"):
            if k in val and isinstance(val[k], (int, float)):
                return float(val[k])
    return default


def compute_rlci_proxy(trace: Dict[str, Any]) -> float:
    # RLCI is a "legibility collapse index" proxy:
    # High when segments are simultaneously high-density, high leak pressure, high external closure dependency,
    # and echo structure becomes noisy (high repetition without stable local anchors).
    segs = trace.get("segments", [])
    if not segs:
        return 0.0

    vals = []
    for seg in segs:
        D = get_proxy(seg, "D_proxy", 0.0)
        L = get_proxy(seg, "L_proxy", 0.0)
        ESC = get_proxy(seg, "ESC_proxy", 0.0)
        R = get_proxy(seg, "R_proxy", 0.0)

        # "collapse pressure": high D+L+ESC, penalize stabilizing residue (R) only slightly
        pressure = 0.40 * D + 0.40 * L + 0.35 * ESC + 0.10 * (1.0 - R)
        vals.append(clamp01(pressure))

    # Aggregate as mean + a volatility term
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    volatility = math.sqrt(var)

    rlci = clamp01(0.80 * mean + 0.35 * volatility)
    return rlci


def shadow_mode_triggered(rlci: float) -> bool:
    # v1.0 threshold: if rlci is high, legibility collapse is plausibly underway.
    return rlci >= 0.78


def admission_score(D: float, L: float, ESC: float, R: float) -> float:
    # Admission is about structural legibility + continuation eligibility:
    # - D helps only if it doesn't blow out L and ESC simultaneously
    # - L hurts (too leaky = unstable addressability)
    # - ESC hurts (too dependent on external closure = fragile)
    # - R helps (echo/persistence increases recruitability surface)
    score = (
        0.35 * (1.0 - L) +
        0.25 * (1.0 - ESC) +
        0.25 * R +
        0.15 * (1.0 - abs(D - 0.55))  # mid-ish density tends to be easiest to carry forward
    )
    return clamp01(score)


def classify_admissibility(score: float) -> str:
    if score >= 0.62:
        return "admissible"
    if score >= 0.38:
        return "contested"
    return "inert"


def masking_suggestion(mode: str, admissibility: str, L: float, ESC: float) -> Tuple[str, List[str]]:
    # Masking is NOT erasure; it's "persist without legibility."
    reasons = []
    if mode == "shadow":
        reasons.append("shadow_mode_active")
        return "masked", reasons

    # In routing mode:
    # If trace is too leaky or too externally-closed, suggest masking even if admissible.
    if admissibility == "inert":
        reasons.append("inert_trace")
        return "masked", reasons

    if L >= 0.78:
        reasons.append("leak_pressure_high")
        return "masked", reasons

    if ESC >= 0.78:
        reasons.append("esc_dependency_high")
        return "masked", reasons

    return "unmasked", reasons


def routing_labels(mode: str, admissibility: str, D: float, L: float, ESC: float, R: float) -> List[str]:
    # Labels only. No “action.” Think: “eligible futures if uptake occurs.”
    if mode == "shadow":
        return ["shadow_persistence"]

    if admissibility == "inert":
        return ["inert_persistence"]

    labels = []

    # Memorialization tends to require enough persistence (R) and not-too-high leak (L)
    if R >= 0.45 and L <= 0.65:
        labels.append("memorialization_eligible")  # PERL-adjacent surface

    # Jurisdictional transfer tends to require some structure + addressability
    if D >= 0.25 and L <= 0.72:
        labels.append("jurisdiction_transfer_eligible")  # JTC-adjacent path

    # Diagnostic propagation: often possible even when contested
    labels.append("diagnostic_propagation_eligible")

    # If strongly external, it may still circulate institutionally (but fragile)
    if ESC >= 0.70 and admissibility != "inert":
        labels.append("institution_dependent_carry")

    # If nothing else, default to drift
    if not labels:
        labels.append("drifting_residue")

    return labels


def stability_flags(trace: Dict[str, Any], rlci: float) -> List[str]:
    flags = []

    # Shadow Mode risk: indicates legibility collapse pressure
    if rlci >= 0.78:
        flags.append("rlci_high_shadow_mode_risk")

    segs = trace.get("segments", [])
    if segs:
        # Saturation proxy: too many segments simultaneously high L and high ESC
        high_load = 0
        for seg in segs:
            L = get_proxy(seg, "L_proxy", 0.0)
            ESC = get_proxy(seg, "ESC_proxy", 0.0)
            if L >= 0.75 and ESC >= 0.60:
                high_load += 1
        frac = high_load / len(segs)
        if frac >= 0.45:
            flags.append("shadow_saturation_risk")

        # Trace collapse proxy: most segments inert by admission score
        inert_count = 0
        for seg in segs:
            D = get_proxy(seg, "D_proxy", 0.0)
            L = get_proxy(seg, "L_proxy", 0.0)
            ESC = get_proxy(seg, "ESC_proxy", 0.0)
            R = get_proxy(seg, "R_proxy", 0.0)
            a = classify_admissibility(admission_score(D, L, ESC, R))
            if a == "inert":
                inert_count += 1
        if (inert_count / len(segs)) >= 0.60:
            flags.append("trace_collapse_risk")

    return flags


def authority_smuggling_risk(seg: Dict[str, Any]) -> Tuple[float, List[str]]:
    # Structural-only heuristic:
    # “Authority smuggling” shows up as high external closure dependency + low internal legibility coherence.
    reasons = []
    ESC = get_proxy(seg, "ESC_proxy", 0.0)
    L = get_proxy(seg, "L_proxy", 0.0)
    D = get_proxy(seg, "D_proxy", 0.0)
    R = get_proxy(seg, "R_proxy", 0.0)

    risk = 0.55 * ESC + 0.25 * L + 0.15 * (1.0 - R) + 0.05 * (1.0 - D)
    risk = clamp01(risk)

    if ESC >= 0.75:
        reasons.append("esc_dependency_high")
    if L >= 0.75:
        reasons.append("leak_pressure_high")
    if R <= 0.20:
        reasons.append("low_persistence_surface")

    return risk, reasons


def analyze_trace(trace: Dict[str, Any]) -> Dict[str, Any]:
    rlci = compute_rlci_proxy(trace)
    shadow = shadow_mode_triggered(rlci)
    mode = "shadow" if shadow else "routing"

    segs = trace.get("segments", [])
    decisions: List[SegmentDecision] = []
    admiss_counts = {"admissible": 0, "contested": 0, "inert": 0}
    masking_counts = {"masked": 0, "unmasked": 0}

    for seg in segs:
        seg_id = seg.get("id", "unknown")
        D = get_proxy(seg, "D_proxy", 0.0)
        L = get_proxy(seg, "L_proxy", 0.0)
        ESC = get_proxy(seg, "ESC_proxy", 0.0)
        R = get_proxy(seg, "R_proxy", 0.0)

        a_score = admission_score(D, L, ESC, R)
        admiss = classify_admissibility(a_score)

        mask, mask_reasons = masking_suggestion(mode, admiss, L, ESC)
        routes = routing_labels(mode, admiss, D, L, ESC, R)

        # Local stability flags
        flags_local: List[str] = []
        if mode == "shadow":
            flags_local.append("shadow_mode_active")
        if L >= 0.85:
            flags_local.append("leak_overload_local")
        if ESC >= 0.85:
            flags_local.append("esc_overload_local")

        auth_risk, auth_reasons = authority_smuggling_risk(seg)
        if auth_risk >= 0.78:
            flags_local.append("authority_smuggling_risk_high")

        reasons = []
        if mode == "shadow":
            reasons.append("rlci_triggered")
        reasons.append(f"admission_score={a_score:.3f}")
        if mask_reasons:
            reasons.extend(mask_reasons)
        if auth_reasons and auth_risk >= 0.60:
            reasons.append(f"authority_smuggling_proxy={auth_risk:.3f}")
            reasons.extend(auth_reasons)

        decisions.append(
            SegmentDecision(
                seg_id=seg_id,
                admissibility=admiss,
                masking=mask,
                mode=mode,
                routing_labels=routes,
                stability_flags=flags_local,
                confidence_proxy=clamp01(0.55 * a_score + 0.45 * (1.0 - auth_risk)),
                reasons=reasons,
            )
        )

        admiss_counts[admiss] += 1
        masking_counts[mask] += 1

    # Failure taxonomy (structural)
    agg_flags = stability_flags(trace, rlci)
    failure_classes: List[Dict[str, Any]] = []

    # ASTG-F1 Shadow Saturation
    if "shadow_saturation_risk" in agg_flags:
        failure_classes.append({
            "code": "ASTG-F1",
            "name": "Shadow Saturation",
            "trigger": "high fraction of segments exceed leak+closure load",
            "notes": "masked residue accumulates faster than routing capacity (structural bottleneck)."
        })

    # ASTG-F2 Authority Smuggling
    # If many segments have high authority risk, declare a system-level risk.
    high_auth = 0
    for seg in segs:
        r, _ = authority_smuggling_risk(seg)
        if r >= 0.78:
            high_auth += 1
    if segs and (high_auth / len(segs)) >= 0.30:
        failure_classes.append({
            "code": "ASTG-F2",
            "name": "Authority Smuggling",
            "trigger": "many segments show high external-closure + low persistence/legibility coherence",
            "notes": "prestige/interpretation tends to bypass diagnostic constraints (proxy-detectable)."
        })

    # ASTG-F3 Trace Collapse
    if "trace_collapse_risk" in agg_flags:
        failure_classes.append({
            "code": "ASTG-F3",
            "name": "Trace Collapse",
            "trigger": "majority of segments classify as inert",
            "notes": "residue persists but becomes structurally unavailable to recruitment/memorialization."
        })

    report = {
        "arbiter": {
            "canonical_name": CANONICAL_NAME,
            "abbreviation": ABBREV,
            "version": VERSION,
            "non_governing": True,
            "created_at": utc_now_iso(),
        },
        "input_trace": {
            "schema": trace.get("schema", {}),
            "ids": trace.get("ids", {}),
            "source": trace.get("source", {}),
            "created_at": trace.get("created_at", None),
        },
        "proxy_doctrine": {
            "note": (
                "All numeric values are proxies (geometry/legibility/load). "
                "They are not measures of truth, value, correctness, or meaning."
            ),
            "scale": "0..1 (dimensionless proxy scale)",
        },
        "global_state": {
            "rlci_proxy": rlci,
            "mode": mode,
            "aggregate_flags": agg_flags,
        },
        "segments": [
            {
                "id": d.seg_id,
                "mode": d.mode,
                "admissibility": d.admissibility,
                "masking": d.masking,
                "routing_labels": d.routing_labels,
                "stability_flags": d.stability_flags,
                "confidence_proxy": round(d.confidence_proxy, 6),
                "reasons": d.reasons,
            }
            for d in decisions
        ],
        "aggregate": {
            "segment_count": len(decisions),
            "admissibility_counts": admiss_counts,
            "masking_counts": masking_counts,
            "failure_taxonomy": failure_classes,
        },
    }
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="ArbiterSTG v1.0 — post-execution trace governance (non-governing).")
    ap.add_argument("infile", help="Input trace JSON (from tracegen.py).")
    ap.add_argument("-o", "--out", default="arbiter_report.json", help="Output report JSON.")
    args = ap.parse_args()

    trace = load_trace(args.infile)
    report = analyze_trace(trace)
    save_json(args.out, report)
    print(f"[arbiterstg] wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())