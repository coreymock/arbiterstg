#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from guardrails import evaluate_text, redact_text

def main() -> int:
    ap = argparse.ArgumentParser(description="Guardrailed trace generator wrapper")
    ap.add_argument("--infile", required=True, help="Input text file")
    ap.add_argument("--out", required=True, help="Output trace JSON file")
    ap.add_argument("--include_text", action="store_true", help="Pass through to tracegen.py")
    args = ap.parse_args()

    text_path = Path(args.infile)
    out_path = Path(args.out)

    text = text_path.read_text(encoding="utf-8")
    gr = evaluate_text(text)

    if gr.decision == "REFUSE":
        print("GUARDRAILS: REFUSE")
        for r in gr.reasons:
            print(f"- {r}")
        return 2

    safe_text = text
    if gr.decision == "ALLOW_REDACTED":
        print("GUARDRAILS: ALLOW_REDACTED")
        for r in gr.reasons:
            print(f"- {r}")
        safe_text = redact_text(text)

    # Write a sibling safe input file and call your existing tracegen on it.
    tmp_in = out_path.with_suffix(".safe_input.txt")
    tmp_in.write_text(safe_text, encoding="utf-8")

    cmd = ["python3", "tracegen.py", "--infile", str(tmp_in), "--out", str(out_path)]
    if args.include_text:
        cmd.append("--include_text")

    import subprocess
    proc = subprocess.run(cmd)
    return proc.returncode

if __name__ == "__main__":
    raise SystemExit(main())