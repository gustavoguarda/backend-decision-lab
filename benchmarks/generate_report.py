#!/usr/bin/env python3
"""Aggregate k6 --summary-export JSON files into a Markdown comparison report
plus a machine-readable JSON aggregate.

Pure Python 3 standard library only. Runs in a bare python:3.12-slim container.
"""

import json
import os
import sys
import glob
import datetime
import statistics  # noqa: F401  (part of the allowed stdlib toolset)


# Preferred scenario ordering; anything else is appended alphabetically.
SCENARIO_ORDER = ["health", "json", "database", "cpu", "concurrency"]


def usage_and_exit():
    sys.stderr.write(
        "Usage: generate_report.py <input_dir> <output_dir>\n"
        "  <input_dir>  directory of k6 summary-export files named "
        "<scenario>__<stack>.json\n"
        "  <output_dir> directory for report.md and report.json "
        "(created if missing)\n"
    )
    sys.exit(1)


def warn(msg):
    sys.stderr.write("WARNING: " + msg + "\n")


def num(value, default=0.0):
    """Coerce a value to float, falling back to default on failure."""
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_file(path):
    """Parse one k6 summary-export file into a flat record.

    Returns a dict of extracted metrics, or None if the file is unusable.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        warn("could not read/parse %s: %s" % (path, exc))
        return None

    if not isinstance(data, dict):
        warn("unexpected top-level structure (not an object) in %s" % path)
        return None

    metrics = data.get("metrics")
    if not isinstance(metrics, dict):
        warn("no 'metrics' object in %s; skipping" % path)
        return None

    http_reqs = metrics.get("http_reqs") or {}
    iterations = metrics.get("iterations") or {}
    duration = metrics.get("http_req_duration") or {}
    failed = metrics.get("http_req_failed") or {}
    checks = metrics.get("checks") or {}

    record = {
        "rps": num(http_reqs.get("rate")),
        "iterations": num(iterations.get("count")),
        "avg_ms": num(duration.get("avg")),
        "p95_ms": num(duration.get("p(95)")),
        "p99_ms": num(duration.get("p(99)")),
        "error_rate": num(failed.get("value")),
        "checks_passes": int(num(checks.get("passes"))),
        "checks_fails": int(num(checks.get("fails"))),
    }
    return record


def split_name(filename):
    """Derive (scenario, stack) from a <scenario>__<stack>.json filename."""
    base = os.path.basename(filename)
    if base.endswith(".json"):
        base = base[: -len(".json")]
    if "__" not in base:
        return None
    scenario, stack = base.split("__", 1)
    scenario = scenario.strip()
    stack = stack.strip()
    if not scenario or not stack:
        return None
    return scenario, stack


def ordered_scenarios(scenario_names):
    """Return scenario names: preferred order first, then others sorted."""
    present = set(scenario_names)
    ordered = [s for s in SCENARIO_ORDER if s in present]
    rest = sorted(s for s in present if s not in SCENARIO_ORDER)
    return ordered + rest


def fmt_rps(value):
    return "{:,.0f}".format(value)


def fmt_ms(value):
    return "{:.2f}".format(value)


def fmt_pct(value):
    return "{:.2f}".format(value)


def build_markdown(generated_at, scenarios):
    """scenarios: dict scenario -> dict stack -> record."""
    lines = []
    lines.append("# Benchmark Comparison Report")
    lines.append("")
    lines.append("Generated at: %s" % generated_at)
    lines.append("")

    for scenario in ordered_scenarios(scenarios.keys()):
        stacks = scenarios[scenario]
        lines.append("## Scenario: %s" % scenario)
        lines.append("")

        # Rows sorted by RPS descending.
        rows = sorted(
            stacks.items(), key=lambda kv: kv[1]["rps"], reverse=True
        )

        # Determine best (winning) value per column.
        best_rps = max((r["rps"] for _, r in rows), default=None)
        best_avg = min((r["avg_ms"] for _, r in rows), default=None)
        best_p95 = min((r["p95_ms"] for _, r in rows), default=None)
        best_p99 = min((r["p99_ms"] for _, r in rows), default=None)
        best_err = min((r["error_rate"] for _, r in rows), default=None)

        def cell(text, value, best):
            if best is not None and value == best:
                return "**%s**" % text
            return text

        lines.append(
            "| Stack | RPS | avg (ms) | p95 (ms) | p99 (ms) | errors % |"
        )
        lines.append(
            "| --- | ---: | ---: | ---: | ---: | ---: |"
        )
        for stack, rec in rows:
            rps_txt = cell(fmt_rps(rec["rps"]), rec["rps"], best_rps)
            avg_txt = cell(fmt_ms(rec["avg_ms"]), rec["avg_ms"], best_avg)
            p95_txt = cell(fmt_ms(rec["p95_ms"]), rec["p95_ms"], best_p95)
            p99_txt = cell(fmt_ms(rec["p99_ms"]), rec["p99_ms"], best_p99)
            err_val = rec["error_rate"] * 100.0
            err_txt = cell(fmt_pct(err_val), rec["error_rate"], best_err)
            lines.append(
                "| %s | %s | %s | %s | %s | %s |"
                % (stack, rps_txt, avg_txt, p95_txt, p99_txt, err_txt)
            )
        lines.append("")

    # Performance ranking across scenarios.
    ranking = compute_ranking(scenarios)
    lines.append("## Performance ranking")
    lines.append("")
    lines.append(
        "Reflects measured throughput (RPS) only, not the full weighted "
        "decision matrix."
    )
    lines.append("")
    lines.append("| Stack | avg rank | scenarios |")
    lines.append("| --- | ---: | ---: |")
    for entry in ranking:
        lines.append(
            "| %s | %.2f | %d |"
            % (entry["stack"], entry["avg_rank"], entry["scenarios"])
        )
    lines.append("")

    return "\n".join(lines), ranking


def compute_ranking(scenarios):
    """Rank stacks by RPS within each scenario, average ranks across all."""
    ranks = {}  # stack -> list of ranks
    for scenario, stacks in scenarios.items():
        ordered = sorted(
            stacks.items(), key=lambda kv: kv[1]["rps"], reverse=True
        )
        for position, (stack, _rec) in enumerate(ordered, start=1):
            ranks.setdefault(stack, []).append(position)

    ranking = []
    for stack, rank_list in ranks.items():
        avg_rank = sum(rank_list) / len(rank_list)
        ranking.append(
            {
                "stack": stack,
                "avg_rank": round(avg_rank, 4),
                "scenarios": len(rank_list),
            }
        )
    # Sort by avg rank ascending (1 = best); tie-break by stack name.
    ranking.sort(key=lambda e: (e["avg_rank"], e["stack"]))
    return ranking


def main(argv):
    if len(argv) < 3:
        usage_and_exit()

    input_dir = argv[1]
    output_dir = argv[2]

    pattern = os.path.join(input_dir, "*__*.json")
    files = sorted(glob.glob(pattern))

    if not files:
        print(
            "No matching '*__*.json' files found in %s; nothing to do."
            % input_dir
        )
        return 0

    scenarios = {}  # scenario -> { stack -> record }
    parsed_count = 0

    for path in files:
        parts = split_name(path)
        if parts is None:
            warn("filename does not match <scenario>__<stack>.json: %s" % path)
            continue
        scenario, stack = parts

        record = parse_file(path)
        if record is None:
            continue

        scenarios.setdefault(scenario, {})[stack] = record
        parsed_count += 1

    if not scenarios:
        print(
            "No usable benchmark data parsed from %s; nothing to do."
            % input_dir
        )
        return 0

    generated_at = datetime.datetime.now().isoformat(timespec="seconds")

    markdown, ranking = build_markdown(generated_at, scenarios)

    # Ensure output directory exists.
    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as exc:
        sys.stderr.write("ERROR: cannot create output dir %s: %s\n"
                         % (output_dir, exc))
        return 1

    md_path = os.path.join(output_dir, "report.md")
    json_path = os.path.join(output_dir, "report.json")

    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(markdown)
        if not markdown.endswith("\n"):
            fh.write("\n")

    aggregate = {
        "generated_at": generated_at,
        "scenarios": {
            scenario: {
                stack: {
                    "rps": rec["rps"],
                    "avg_ms": rec["avg_ms"],
                    "p95_ms": rec["p95_ms"],
                    "p99_ms": rec["p99_ms"],
                    "error_rate": rec["error_rate"],
                    "iterations": rec["iterations"],
                    "checks_passes": rec["checks_passes"],
                    "checks_fails": rec["checks_fails"],
                }
                for stack, rec in stacks.items()
            }
            for scenario, stacks in scenarios.items()
        },
        "ranking": ranking,
    }

    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(aggregate, fh, indent=2)
        fh.write("\n")

    print(
        "Parsed %d file(s) across %d scenario(s). Wrote %s and %s."
        % (parsed_count, len(scenarios), md_path, json_path)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
