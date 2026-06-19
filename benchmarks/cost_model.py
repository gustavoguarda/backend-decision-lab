#!/usr/bin/env python3
"""Phase 4 cost model for the backend benchmark lab.

Combines MEASURED throughput (report.json) and peak resource usage
(resources.json) with a cloud pricing config (pricing.json) to model
cloud cost efficiency per stack.

Pure Python 3 standard library only (json, os, sys, math). Designed to
run in a bare python:3.12-slim container.

This is an efficiency ESTIMATE derived from measurements, not a cloud bill.
"""

import json
import math
import os
import sys


USAGE = (
    "Usage: python cost_model.py <run_dir> [pricing.json] [out_dir]\n"
    "  <run_dir>      directory containing report.json and resources.json\n"
    "  [pricing.json] pricing config (default: ./pricing.json in CWD)\n"
    "  [out_dir]      output directory (default: <run_dir>)\n"
)


def die(msg, code=1):
    """Print an error to stderr and exit."""
    sys.stderr.write("error: " + msg + "\n")
    sys.exit(code)


def load_json(path, what):
    """Load a JSON file, exiting cleanly on common failures."""
    if not os.path.isfile(path):
        die("%s not found: %s" % (what, path))
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        die("could not read %s (%s): %s" % (what, path, exc))


def num(value, default=0.0):
    """Coerce a value to float, returning default on failure."""
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def pick_representative(stack, scenarios):
    """Choose the representative rps + scenario name for a stack.

    Prefer the 'database' scenario (realistic real-world workload); else
    fall back to the scenario where this stack has the highest rps.
    Returns (scenario_name, rps) or (None, 0.0) if not found.
    """
    db = scenarios.get("database")
    if isinstance(db, dict) and stack in db and isinstance(db[stack], dict):
        return "database", num(db[stack].get("rps"))

    best_name = None
    best_rps = -1.0
    for scen_name, stacks in scenarios.items():
        if not isinstance(stacks, dict):
            continue
        entry = stacks.get(stack)
        if not isinstance(entry, dict):
            continue
        rps = num(entry.get("rps"))
        if rps > best_rps:
            best_rps = rps
            best_name = scen_name
    if best_name is None:
        return None, 0.0
    return best_name, max(best_rps, 0.0)


def fmt_money4(value):
    return "$%.4f" % value


def fmt_money2(value):
    return "$%.2f" % value


def main():
    argv = sys.argv
    if len(argv) < 2:
        sys.stderr.write(USAGE)
        sys.exit(1)

    run_dir = argv[1]
    pricing_path = argv[2] if len(argv) >= 3 and argv[2] else "pricing.json"
    out_dir = argv[3] if len(argv) >= 4 and argv[3] else run_dir

    if not os.path.isdir(run_dir):
        die("run directory not found: %s" % run_dir)

    report = load_json(os.path.join(run_dir, "report.json"), "report.json")
    resources = load_json(os.path.join(run_dir, "resources.json"), "resources.json")
    pricing = load_json(pricing_path, "pricing.json")

    scenarios = report.get("scenarios")
    if not isinstance(scenarios, dict) or not scenarios:
        die("report.json has no 'scenarios' object")
    if not isinstance(resources, dict) or not resources:
        die("resources.json has no stack entries")

    profiles = pricing.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        die("pricing.json has no 'profiles'")
    assumptions = pricing.get("assumptions") or {}
    target_rps = num(assumptions.get("target_rps"), 1000.0)
    hours_per_month = num(assumptions.get("hours_per_month"), 730.0)

    # Determine the representative scenario actually used. If 'database' is
    # present in the report at all, that's the headline; otherwise mixed.
    headline_scenario = "database" if "database" in scenarios else "mixed (per-stack best rps)"

    # Stacks = those that appear in resources.json (we need resource data).
    stacks = sorted(resources.keys())

    # Build per-stack base facts (rps, vcpu, mem) shared across profiles.
    base = {}
    for stack in stacks:
        res = resources.get(stack)
        if not isinstance(res, dict):
            continue
        scen_name, rps = pick_representative(stack, scenarios)
        if scen_name is None:
            # no throughput measurement for this stack; skip it
            continue
        cpu_peak = num(res.get("cpu_peak_pct"))
        mem_peak = num(res.get("mem_peak_mib"))
        vcpu = cpu_peak / 100.0
        mem_gb = mem_peak / 1024.0
        base[stack] = {
            "scenario": scen_name,
            "rps": rps,
            "vcpu": vcpu,
            "mem_gb": mem_gb,
        }

    if not base:
        die("no stacks had both resource data and a throughput measurement")

    # Compute per-profile model.
    json_profiles = {}
    for profile_key, profile in profiles.items():
        if not isinstance(profile, dict):
            continue
        vcpu_hour = num(profile.get("vcpu_hour"))
        gb_hour = num(profile.get("gb_hour"))
        per_stack = {}
        for stack, facts in base.items():
            rps = facts["rps"]
            vcpu = facts["vcpu"]
            mem_gb = facts["mem_gb"]
            hourly_cost = vcpu * vcpu_hour + mem_gb * gb_hour
            if rps > 0:
                cost_per_million = hourly_cost * 1e6 / (rps * 3600.0)
                instances_for_target = int(math.ceil(target_rps / rps)) if target_rps > 0 else 0
            else:
                cost_per_million = float("inf")
                instances_for_target = 0
            monthly_at_target = instances_for_target * hourly_cost * hours_per_month
            per_stack[stack] = {
                "rps": rps,
                "vcpu": vcpu,
                "mem_gb": mem_gb,
                "hourly_cost": hourly_cost,
                "cost_per_million": cost_per_million,
                "instances_for_target": instances_for_target,
                "monthly_at_target": monthly_at_target,
            }
        json_profiles[profile_key] = per_stack

    # ---- Write cost.json ----
    cost_json = {
        "representative_scenario": headline_scenario,
        "target_rps": target_rps,
        "hours_per_month": hours_per_month,
        "profiles": json_profiles,
    }

    os.makedirs(out_dir, exist_ok=True)
    cost_json_path = os.path.join(out_dir, "cost.json")
    with open(cost_json_path, "w", encoding="utf-8") as fh:
        json.dump(cost_json, fh, indent=2)
        fh.write("\n")

    # ---- Write cost.md ----
    lines = []
    lines.append("# Phase 4 Cost Model")
    lines.append("")
    lines.append(
        "> Modeled from measured throughput and peak resource usage "
        "— an efficiency estimate, NOT a cloud bill. "
        "Representative scenario: %s." % headline_scenario
    )
    lines.append("")
    lines.append(
        "Provisioning assumes one instance is sized for measured peak CPU/memory. "
        "Target throughput: %s rps over %s hours/month."
        % ("{:,.0f}".format(target_rps), "{:,.0f}".format(hours_per_month))
    )
    lines.append("")

    target_label = "{:,.0f}".format(target_rps)
    header = (
        "| Stack | RPS | vCPU | Mem (GB) | $/hr (1 inst) | $/1M req "
        "| instances @ %s rps | $/mo @ target |" % target_label
    )
    sep = "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"

    for profile_key, profile in profiles.items():
        if profile_key not in json_profiles:
            continue
        label = profile.get("label", profile_key) if isinstance(profile, dict) else profile_key
        per_stack = json_profiles[profile_key]
        lines.append("### %s" % label)
        lines.append("")
        lines.append(header)
        lines.append(sep)

        # Sort by cost_per_million ascending (cheapest first).
        rows = sorted(per_stack.items(), key=lambda kv: kv[1]["cost_per_million"])
        cheapest_cpm = rows[0][1]["cost_per_million"] if rows else None

        for stack, m in rows:
            cpm = m["cost_per_million"]
            if math.isinf(cpm):
                cpm_cell = "n/a"
            else:
                cpm_cell = fmt_money4(cpm)
                if cheapest_cpm is not None and cpm == cheapest_cpm:
                    cpm_cell = "**%s**" % cpm_cell
            rps_cell = "{:,.0f}".format(m["rps"])
            lines.append(
                "| %s | %s | %.2f | %.2f | %s | %s | %d | %s |"
                % (
                    stack,
                    rps_cell,
                    m["vcpu"],
                    m["mem_gb"],
                    fmt_money4(m["hourly_cost"]),
                    cpm_cell,
                    m["instances_for_target"],
                    fmt_money2(m["monthly_at_target"]),
                )
            )
        lines.append("")

    # Takeaway under the default profile (aws-fargate) by $/1M req.
    default_key = "aws-fargate"
    if default_key in json_profiles and json_profiles[default_key]:
        best_stack, best_m = min(
            json_profiles[default_key].items(),
            key=lambda kv: kv[1]["cost_per_million"],
        )
        default_label = profiles.get(default_key, {}).get("label", default_key) if isinstance(profiles.get(default_key), dict) else default_key
        if math.isinf(best_m["cost_per_million"]):
            lines.append(
                "**Takeaway:** no stack produced a valid throughput measurement under %s."
                % default_label
            )
        else:
            lines.append(
                "**Takeaway:** under %s, **%s** is the most cost-efficient stack at %s per 1M requests."
                % (default_label, best_stack, fmt_money4(best_m["cost_per_million"]))
            )
        lines.append("")

    cost_md_path = os.path.join(out_dir, "cost.md")
    with open(cost_md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    # ---- stdout summary ----
    sys.stdout.write(
        "cost_model: %d stacks modeled across %d profiles "
        "(scenario=%s) -> %s, %s\n"
        % (
            len(base),
            len(json_profiles),
            headline_scenario,
            cost_md_path,
            cost_json_path,
        )
    )


if __name__ == "__main__":
    main()
