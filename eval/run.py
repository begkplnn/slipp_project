"""Run an extractor over the eval set and write per-receipt outputs plus a summary.

Usage:
    python -m eval.run --model ollama:gemma3:12b
    python -m eval.run --model claude-opus-5-5 --effort low --limit 5
    python -m eval.run --model claude-haiku-5-5 --tag hard

Each label in eval/data/labels/<id>.json is a Receipt plus an "_meta" object:
    {"_meta": {"image": "<file in eval/data/receipts>", "source": "synthetic|real", "tags": ["faded"]}, ...}
"""

import argparse
import json
import statistics
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from eval.metrics import score
from slipp.extract.prompt import PROMPT_VERSION
from slipp.schema import Receipt
from slipp.validate import validate

ROOT = Path(__file__).parent
DATA = ROOT / "data"


def make_extractor(model: str, effort: str):
    if model.startswith("ollama:"):
        from slipp.extract.ollama import OllamaExtractor
        return OllamaExtractor(model.removeprefix("ollama:"))
    from slipp.extract.claude import ClaudeExtractor
    return ClaudeExtractor(model, effort)


def load_cases(tag: str | None, limit: int | None):
    cases = []
    for label_path in sorted((DATA / "labels").glob("*.json")):
        raw = json.loads(label_path.read_text())
        meta = raw.pop("_meta")
        if tag and tag not in meta.get("tags", []):
            continue
        cases.append((label_path.stem, DATA / "receipts" / meta["image"], meta, Receipt.model_validate(raw)))
    return cases[:limit] if limit else cases


def mean(values):
    return round(statistics.mean(values), 3) if values else None


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--effort", default="low")
    ap.add_argument("--tag")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    extractor = make_extractor(args.model, args.effort)
    cases = load_cases(args.tag, args.limit)
    run_id = f"{datetime.now():%Y%m%d-%H%M%S}_{extractor.name.replace(':', '-').replace('@', '-')}"
    out_dir = ROOT / "results" / run_id
    out_dir.mkdir(parents=True)

    rows = []
    for case_id, image, meta, label in cases:
        try:
            res = extractor.extract(image)
        except Exception as e:  # keep going; a crashed case counts as a failure
            print(f"{case_id}: ERROR {e}")
            rows.append({"id": case_id, "tags": meta.get("tags", []), "error": str(e)})
            continue
        row = {
            "id": case_id,
            "tags": meta.get("tags", []),
            "latency_s": round(res.latency_s, 2),
            "input_tokens": res.input_tokens,
            "output_tokens": res.output_tokens,
            "cost_usd": res.cost_usd,
            "error": res.error,
        }
        if res.receipt:
            row["scores"] = score(res.receipt, label)
            row["flags"] = validate(res.receipt, today=_label_today(label)).flags
            (out_dir / f"{case_id}.json").write_text(res.receipt.model_dump_json(indent=2))
        rows.append(row)
        s = row.get("scores", {})
        print(f"{case_id}: total={'ok' if s.get('field_total_minor') else 'X'} "
              f"item_f1={s.get('item_f1', 0):.2f} {row['latency_s']}s err={res.error}")

    scored = [r for r in rows if "scores" in r]
    metric_names = scored[0]["scores"].keys() if scored else []
    summary = {
        "run_id": run_id,
        "model": extractor.name,
        "prompt_version": PROMPT_VERSION,
        "n_cases": len(rows),
        "n_failed": len(rows) - len(scored),
        "metrics": {m: mean([r["scores"][m] for r in scored]) for m in metric_names},
        "flagged_rate": mean([float(bool(r["flags"])) for r in scored]),
        "latency_p50_s": round(statistics.median([r["latency_s"] for r in scored]), 2) if scored else None,
        "cost_per_receipt_usd": round(statistics.mean([r["cost_usd"] for r in scored]), 5) if scored else None,
    }
    (out_dir / "rows.json").write_text(json.dumps(rows, indent=2))
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


def _label_today(label: Receipt):
    # Validate relative to the receipt's own date so old eval receipts aren't all "too old".
    from datetime import date
    return date.fromisoformat(label.purchase_date) if label.purchase_date else None


if __name__ == "__main__":
    main()
