"""Eval runner entry point: `uv run python evals/run.py`.

Placeholder until retrieval exists (M4). Cases live in evals/cases/*.yaml and are
written by a human; see CONTRIBUTING.md.
"""

import sys
from pathlib import Path

CASES_DIR = Path(__file__).parent / "cases"


def main() -> int:
    cases = sorted(CASES_DIR.glob("*.yaml"))
    print(f"Found {len(cases)} eval case file(s) in {CASES_DIR}.")
    print("The eval runner is not implemented yet; nothing was scored.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
