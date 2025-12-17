#!/usr/bin/env python3.12
"""Find users who accessed the survey more than once.

Reads a log file containing lines such as:
    2025-11-24T15:46:49Z {"message": "participant_id:STP05087 survey accessed", ...}

Outputs JSON of:
[
  { "participant_id": "STP03938", "access_count": 3 },
  { "participant_id": "STP11466", "access_count": 2 },
  ...
]

Also prints total extra access attempts (sum of count - 1 for each user).
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from collections.abc import Iterable

ACCESS_RE = re.compile(r"participant_id:([A-Za-z0-9_-]+)")
SURVEY_ACCESSED_TOKEN = "survey accessed"  # noqa: S105 # nosec B105


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for log file and output format."""
    parser = argparse.ArgumentParser(
        description="Detect repeated survey access attempts.",
    )
    parser.add_argument(
        "logfile",
        help="Path to log file",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON instead of plain text.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def find_multiple_accesses(path: str) -> tuple[list[dict[str, object]], int]:
    """Scan the log file and find repeat accesses."""
    counts: Counter[str] = Counter()

    with open(path, encoding="utf-8") as file:
        for line in file:
            if SURVEY_ACCESSED_TOKEN not in line:
                continue

            match = ACCESS_RE.search(line)
            if match:
                pid = match.group(1)
                counts[pid] += 1

    # extract only those with >1 access
    repeated = [
        {"participant_id": pid, "access_count": count}
        for pid, count in counts.items()
        if count > 1
    ]

    # total extra access attempts across all users
    extra_attempts = sum(count - 1 for count in counts.values() if count > 1)

    return repeated, extra_attempts


def main() -> None:
    """Main entry point."""
    args = parse_args()
    repeated, extra = find_multiple_accesses(args.logfile)

    if args.json:
        print(
            json.dumps(
                {
                    "duplicate_accesses": repeated,
                    "duplicate_user_count": len(repeated),
                    "extra_access_attempts": extra,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print(f"Users accessing more than once: {len(repeated)}")
        print(f"Extra access attempts: {extra}\n")
        for entry in repeated:
            print(f"{entry['participant_id']}: {entry['access_count']} times")


if __name__ == "__main__":
    main()
