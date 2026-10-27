# Slipp

Receipts in, loyalty rewards out. One app instead of one loyalty app per brand.

> Work in progress. Week 1: receipt extraction, validation and evals. The full README (screenshots, architecture, eval table, cost analysis, risks) comes in week 3.

## Layout

```
backend/slipp/
  schema.py            Receipt schema (Pydantic): the contract for the LLM, validation, evals and DB
  validate.py          Deterministic checks: sums, dates, plausibility. Code decides, not the LLM
  extract/
    prompt.py          Versioned extraction prompt
    claude.py          Claude API extractor (structured outputs + cost per call)
    ollama.py          Local vision model extractor (Ollama, JSON-schema constrained)
eval/
  data/receipts/       Images/PDFs (real_* files are git-ignored)
  data/labels/         Hand-checked ground truth, one JSON per receipt
  metrics.py           Field accuracy + line-item matching (precision/recall/F1, price accuracy)
  run.py               Run one model over the eval set -> eval/results/<run_id>/
  compare.py           Markdown table of the latest run per model
scripts/make_synthetic.py   Synthetic receipts with hard-case variants
tests/
```

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
cp .env.example .env   # add ANTHROPIC_API_KEY
```

## Run the eval

```bash
.venv/bin/python scripts/make_synthetic.py --n 20 --seed 1
.venv/bin/python -m eval.run --model ollama:gemma3:12b
.venv/bin/python -m eval.run --model claude-opus-5-5 --effort low
.venv/bin/python -m eval.compare
```

`--tag faded|blur|rotated|noise|injection|clean` runs a subset; `--limit N` runs the first N.

## Adding a real receipt

1. Remove personal data first (card digits, names, loyalty numbers): crop or black them out.
2. Save as `eval/data/receipts/real_<nn>.jpg`.
3. Write `eval/data/labels/real_<nn>.json` by hand (copy a synthetic label as a template), with `"_meta": {"image": "real_<nn>.jpg", "source": "real", "tags": [...]}`.
