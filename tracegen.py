import argparse
import json
import hashlib
from datetime import datetime, timezone

# -------------------------------------------------
# Argument parser
# -------------------------------------------------
parser = argparse.ArgumentParser(description="Generate MDS trace from text")

parser.add_argument("--infile", required=True, help="Input text file")
parser.add_argument("--out", required=True, help="Output trace JSON")
parser.add_argument("--include_text", action="store_true",
                    help="Include full segment text in output (default: off)")

args = parser.parse_args()

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def make_id(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]

def load_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

# --- placeholder scoring functions ---
# keep yours if you already have them
def score_D(text): return 0.4
def score_L(text): return 0.05
def score_ESC(text): return 0.25
def score_R(text): return 0.3

# -------------------------------------------------
# Load + segment
# -------------------------------------------------
full_text = load_text(args.infile)
content_id = make_id(full_text)

# simple single-segment run (replace if multi-segment)
segments_raw = [full_text]

segments = []
cursor = 0

for i, seg_text in enumerate(segments_raw, start=1):
    start = cursor
    end = cursor + len(seg_text)
    cursor = end + 1

    seg_id = f"p{str(i).zfill(3)}.s001"

    segment = {
        "id": seg_id,
        "span": {
            "start_char": start,
            "end_char": end
        },

        # ← THIS is the privacy switch
        **({"text": seg_text} if args.include_text else {}),

        "D_proxy": {
            "score": score_D(seg_text)
        },
        "L_proxy": {
            "score": score_L(seg_text)
        },
        "ESC_proxy": {
            "dependency": "low",
            "score": score_ESC(seg_text)
        },
        "R_proxy": {
            "strength": score_R(seg_text),
            "sign": "unknown",
            "signatures": ["echo_surface"],
            "echo_links": []
        }
    }

    segments.append(segment)

# -------------------------------------------------
# Build trace object
# -------------------------------------------------
utc_now = datetime.now(timezone.utc)
run_stamp = utc_now.isoformat(timespec="microseconds")

trace = {
    "schema": {
        "name": "MDS_Trace",
        "version": "1.0"
    },
    "ids": {
        "content_id": content_id,
        "trace_id": make_id(content_id + run_stamp)
    },
    "created_at": run_stamp,
    "source": {
        "title": "Run",
        "kind": "user_text",
        "canonical_status": "draft"
    },
    "non_governing": True,
    "segments": segments,
    "aggregate": {
        "segment_count": len(segments),
        "echo_graph": {
            "nodes": [s["id"] for s in segments],
            "edges": [],
            "density": 0.0
        }
    }
}

# -------------------------------------------------
# Save
# -------------------------------------------------
with open(args.out, "w", encoding="utf-8") as f:
    json.dump(trace, f, indent=2)

print(f"Trace written → {args.out}")