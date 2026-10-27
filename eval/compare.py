"""Print a markdown table comparing the latest run of each model. Paste it into the README."""

import json
from pathlib import Path

RESULTS = Path(__file__).parent / "results"
COLUMNS = [
    ("field_total_minor", "Total"),
    ("field_purchase_date", "Date"),
    ("field_merchant_name", "Merchant"),
    ("item_f1", "Item F1"),
    ("item_price_accuracy", "Item price"),
    ("items_all_correct", "All items correct"),
]


def main():
    latest = {}
    for path in sorted(RESULTS.glob("*/summary.json")):
        s = json.loads(path.read_text())
        latest[s["model"]] = s  # sorted by run_id timestamp, so last one wins
    header = ["Model", "n"] + [c[1] for c in COLUMNS] + ["p50 latency", "$/receipt"]
    print("| " + " | ".join(header) + " |")
    print("|" + "---|" * len(header))
    for model, s in latest.items():
        m = s["metrics"]
        cells = [model, f"{s['n_cases'] - s['n_failed']}/{s['n_cases']}"]
        cells += [f"{m[k]:.0%}" if m.get(k) is not None else "-" for k, _ in COLUMNS]
        cells += [f"{s['latency_p50_s']}s", f"${s['cost_per_receipt_usd']:.4f}"]
        print("| " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
