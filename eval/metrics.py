"""Scoring an extracted receipt against a hand-checked label.

Header fields: exact match after light normalisation (merchant name is case/punctuation-insensitive).
Line items: each predicted item is matched to at most one label item (best description similarity
above a threshold, greedy). Then:
  - item precision/recall/F1 = did we find the right lines (no invented, none missed)
  - price accuracy = of the matched lines, how many have the exact total_minor
"""

import re
from difflib import SequenceMatcher

from slipp.schema import Receipt

HEADER_FIELDS = ["merchant_name", "purchase_date", "currency", "total_minor"]
MATCH_THRESHOLD = 0.6


def _norm(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def header_scores(pred: Receipt, label: Receipt) -> dict[str, bool]:
    scores = {}
    for f in HEADER_FIELDS:
        p, t = getattr(pred, f), getattr(label, f)
        scores[f] = _norm(p) == _norm(t) if isinstance(t, str) else p == t
    return scores


def match_items(pred: Receipt, label: Receipt) -> list[tuple[int, int]]:
    """Greedy best-first matching on description similarity. Returns (pred_idx, label_idx) pairs."""
    candidates = []
    for i, p in enumerate(pred.line_items):
        for j, t in enumerate(label.line_items):
            sim = SequenceMatcher(None, _norm(p.description), _norm(t.description)).ratio()
            # Same price is strong evidence when OCR mangles a description.
            if p.total_minor == t.total_minor:
                sim += 0.15
            if sim >= MATCH_THRESHOLD:
                candidates.append((sim, i, j))
    used_p, used_t, pairs = set(), set(), []
    for _, i, j in sorted(candidates, reverse=True):
        if i not in used_p and j not in used_t:
            used_p.add(i)
            used_t.add(j)
            pairs.append((i, j))
    return pairs


def item_scores(pred: Receipt, label: Receipt) -> dict[str, float]:
    pairs = match_items(pred, label)
    n_pred, n_label, n_match = len(pred.line_items), len(label.line_items), len(pairs)
    precision = n_match / n_pred if n_pred else float(n_label == 0)
    recall = n_match / n_label if n_label else float(n_pred == 0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    price_ok = sum(pred.line_items[i].total_minor == label.line_items[j].total_minor for i, j in pairs)
    return {
        "item_precision": precision,
        "item_recall": recall,
        "item_f1": f1,
        "item_price_accuracy": price_ok / n_match if n_match else 0.0,
        # The strict business metric: every line found with the right price, nothing invented.
        "items_all_correct": float(n_match == n_pred == n_label and price_ok == n_match),
    }


def score(pred: Receipt, label: Receipt) -> dict[str, float]:
    out: dict[str, float] = {f"field_{k}": float(v) for k, v in header_scores(pred, label).items()}
    out.update(item_scores(pred, label))
    return out
