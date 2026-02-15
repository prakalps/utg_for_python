# UTG for Python (Unit Test Generator)

This project generates **deterministic, high-quality** `pytest` unit tests for the code under `src/`, with the goal of reaching **100% coverage** (or as close as practical) while keeping the test suite stable and repeatable.

The generator is primarily **rule-based** (deterministic templates). Optionally, it can use an **OpenAI** model as a fallback/augmenter.

## Key features

- **Rule-based generation first**
  - Generates predictable tests that do not depend on randomness.
  - Prefers branch/exception-path tests when coverage indicates gaps.
- **Coverage-driven iteration**
  - Uses `pytest-cov` JSON output (`coverage.json`) to find uncovered lines/symbols and iteratively fill gaps.
- **Bootstrap mode**
  - If `coverage.json` is missing/unusable (for example: empty `tests/` and 0 tests collected), the generator treats all discovered `src/` symbols as gaps and generates an initial suite.
- **Package-aware generated test filenames**
  - Nested modules map to stable filenames (prevents collisions), e.g.
    - `src/helpdesk/api.py` -> `tests/test_helpdesk__api_generated.py`
- **Monotonic regeneration behavior**
  - Existing blocks that are already “good enough” can be preserved.
  - When templates change or blocks require normalization, the generator can overwrite/upgrade blocks.
- **Optional OpenAI integration**
  - If enabled and configured, the generator can request an additional candidate test from an LLM.

## Repository layout

- `src/`
  - Your application/source modules.
- `tests/`
  - Generated tests are written here as `test_*_generated.py`.
- `agents/`
  - Generator internals:
    - `coverage_analyzer.py`: reads `coverage.json` and identifies gaps (includes bootstrap behavior).
    - `test_discovery.py`: maps tests back to source modules (supports package-aware names).
    - `test_generator.py`: builds deterministic rule-based blocks (and optional LLM blocks).
- `automatic_unit_test_generator.py`
  - Main entrypoint: analyze coverage -> generate/update tests -> rerun until stable or max rounds.
- `run_generated_tests.py`
  - Convenience runner for pytest, with an optional `--regen` to call the generator before testing.

## Requirements

- Python 3.13+
- Install dependencies:

```powershell
pip install -r .\requirements.txt
```

## Usage

### 1) Generate / update tests (recommended entrypoint)

```powershell
python .\automatic_unit_test_generator.py
```

What it does:

1. Scans `src/` modules.
2. Runs pytest coverage collection.
3. Reads `coverage.json` and identifies coverage gaps.
4. Generates or updates `tests/test_*_generated.py`.
5. Repeats for a few rounds until:
   - All tests pass
   - Coverage gaps are eliminated (or max rounds reached)

### 2) Run tests (optionally regenerate first)

```powershell
python .\run_generated_tests.py
```

Regenerate then run all tests with coverage:

```powershell
python .\run_generated_tests.py --regen --all --cov
```

## OpenAI (optional)

If you want to enable LLM-generated candidates:

1. Install the `openai` package (if it’s not already in `requirements.txt`).
2. Set an API key:

```powershell
$env:OPENAI_API_KEY = "YOUR_KEY_HERE"
```

Notes:

- If `OPENAI_API_KEY` is not set, the generator will **skip** LLM generation and rely purely on rule-based templates.
- The generator chooses between rule/LLM candidates and prefers deterministic quality.

## Tips / common workflows

### Regenerate from scratch

1. Delete generated tests from `tests/` (any `test_*_generated.py`).
2. Run:

```powershell
python .\automatic_unit_test_generator.py
```

The bootstrap behavior will kick in if no coverage info exists yet.

### Understanding generated tests

Generated test functions are grouped into “blocks” and annotated with headers like:

`# origin=rule quality=high symbol=<name>`

This makes it possible to:

- Preserve high-quality blocks.
- Replace blocks when templates change.
- Avoid duplicates.

## Status

The generator is intended to converge to:

- **All tests passing**
- **0 coverage gaps**
- **High-quality blocks** (no `low` quality blocks)
