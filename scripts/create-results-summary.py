#!/usr/bin/env python3
"""Create a compact accuracy and flip-rate Markdown report from run_summary.json."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from crimino_flipper.reporting import write_results_summary  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--summary",
        default="pilot/artifacts/adaption/run_summary.json",
        help="Path to run_summary.json",
    )
    parser.add_argument(
        "--output",
        default="pilot/results_summary.md",
        help="Markdown output path",
    )
    args = parser.parse_args()
    summary_path = Path(args.summary)
    if not summary_path.exists():
        raise SystemExit(f"Summary file not found: {summary_path}")
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_results_summary(data, output_path)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
