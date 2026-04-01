#!/usr/bin/env python3
"""
OpenLoopholes.com — Combination Scanner (Loophole Finder)

Systematically tests pairs of tax strategies to find synergies —
combinations where the combined savings exceed the sum of individual
savings. These are the real "loopholes": legal strategy stacks that
produce outsized results through interaction effects.

No LLM calls. Pure deterministic calculator math.

Usage:
    python find_loopholes.py                                  # Run on sample.json
    python find_loopholes.py --profile profiles/sample.json   # Run on any profile
    python find_loopholes.py --top 20                         # Show top 20 results
    python find_loopholes.py --min-synergy 500                # Only show synergies > $500
"""

from __future__ import annotations

import argparse
import json
import time
from itertools import combinations
from pathlib import Path

from tax_calculator import compute_tax
from strategy_registry import load_all_strategies, filter_strategies

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "results"
DEFAULT_PROFILE = Path(__file__).resolve().parent / "profiles" / "sample.json"


def build_test_strategies(filtered: list[dict]) -> list[dict]:
    """
    Build a list of testable strategy instances from the filtered registry.
    Each gets reasonable default parameters based on its type.
    """
    test_set = []
    for s in filtered:
        sid = s["id"]
        params_schema = s.get("parameters", {})

        # Build default parameters
        params = {}
        for key, spec in params_schema.items():
            ptype = spec.get("type", "int")
            # Assign reasonable defaults based on common parameter names
            if "contribution" in key:
                params[key] = 10000
            elif "amount" in key:
                params[key] = 10000
            elif "expenses" in key:
                params[key] = 10000
            elif "cost" in key:
                params[key] = 25000
            elif "salary" in key:
                params[key] = 50000
            elif "gain" in key or "excluded_gain" in key:
                params[key] = 100000
            elif "loss_amount" in key:
                params[key] = 10000
            elif "days" in key:
                params[key] = 14
            elif "daily_rate" in key:
                params[key] = 2000
            elif "num_children" in key or "num_students" in key:
                params[key] = 2
            elif "wage_per_child" in key:
                params[key] = 12000
            elif "business_miles" in key:
                params[key] = 10000
            elif "years" in key:
                params[key] = 5
            elif "payout_rate" in key:
                params[key] = 0.05
            elif "qualified_expenses" in key:
                params[key] = 50000
            elif ptype == "int":
                params[key] = 10000
            elif ptype == "float":
                params[key] = 0.05

        # Determine entity (use first relevant entity type if entity-specific)
        entity = None
        if s.get("entity_specific") and s.get("entity_types"):
            entity = s["entity_types"][0]  # placeholder — will be resolved by calculator

        test_set.append({
            "id": sid,
            "entity": entity,
            "parameters": params,
            "name": s.get("name", sid),
        })

    return test_set


def run_scanner(profile: dict, top_n: int = 30, min_synergy: int = 100):
    """Run the combination scanner on a profile."""
    start = time.time()

    # Get baseline
    baseline = compute_tax(profile, [])
    baseline_tax = baseline["total_tax"]
    print(f"Baseline liability: ${baseline_tax:,}")

    # Get filtered strategies
    all_strategies = load_all_strategies()
    filtered = filter_strategies(profile, all_strategies)
    print(f"Strategies after filter: {len(filtered)}")

    # Build testable strategy instances
    test_strategies = build_test_strategies(filtered)
    print(f"Testable strategies: {len(test_strategies)}")

    # Phase 1: Test each strategy individually
    print("\nPhase 1: Testing individual strategies...")
    individual_savings = {}
    effective_strategies = []

    for ts in test_strategies:
        strat_input = [{"id": ts["id"], "entity": ts["entity"], "parameters": ts["parameters"]}]
        try:
            result = compute_tax(profile, strat_input)
            savings = baseline_tax - result["total_tax"]
            individual_savings[ts["id"]] = savings
            if savings > 0:
                effective_strategies.append(ts)
        except Exception:
            individual_savings[ts["id"]] = 0

    print(f"  Strategies with individual savings > $0: {len(effective_strategies)}")
    for ts in sorted(effective_strategies, key=lambda x: -individual_savings[x["id"]])[:10]:
        print(f"    {ts['id']}: ${individual_savings[ts['id']]:,}")

    # Also include strategies with $0 individual savings but high potential
    # (they might only work in combination)
    zero_but_potential = [
        ts for ts in test_strategies
        if individual_savings.get(ts["id"], 0) == 0
        and ts["id"] not in [e["id"] for e in effective_strategies]
    ]
    # Limit zero-savings strategies to keep combinatorics manageable
    candidates = effective_strategies + zero_but_potential[:50]
    print(f"  Total candidates for pairing: {len(candidates)}")

    # Phase 2: Test all pairs
    pairs = list(combinations(candidates, 2))
    print(f"\nPhase 2: Testing {len(pairs):,} pairs...")

    loopholes = []
    tested = 0

    for ts_a, ts_b in pairs:
        tested += 1
        if tested % 5000 == 0:
            print(f"  Progress: {tested:,}/{len(pairs):,} pairs tested...")

        strat_input = [
            {"id": ts_a["id"], "entity": ts_a["entity"], "parameters": ts_a["parameters"]},
            {"id": ts_b["id"], "entity": ts_b["entity"], "parameters": ts_b["parameters"]},
        ]

        try:
            result = compute_tax(profile, strat_input)
            combined_savings = baseline_tax - result["total_tax"]
        except Exception:
            continue

        savings_a = individual_savings.get(ts_a["id"], 0)
        savings_b = individual_savings.get(ts_b["id"], 0)
        expected = savings_a + savings_b
        synergy = combined_savings - expected

        if synergy >= min_synergy:
            synergy_pct = (synergy / max(expected, 1)) * 100
            loopholes.append({
                "strategies": [ts_a["id"], ts_b["id"]],
                "strategy_names": [ts_a["name"], ts_b["name"]],
                "savings_a_alone": savings_a,
                "savings_b_alone": savings_b,
                "sum_of_parts": expected,
                "savings_combined": combined_savings,
                "synergy": synergy,
                "synergy_pct": f"{synergy_pct:.0f}%",
            })

    elapsed = time.time() - start

    # Sort by synergy
    loopholes.sort(key=lambda x: -x["synergy"])
    loopholes = loopholes[:top_n]

    print(f"\nDone. {len(loopholes)} loopholes found in {elapsed:.1f}s")

    # Display results
    if loopholes:
        print(f"\n{'='*70}")
        print(f"TOP LOOPHOLES (strategy stacks with synergy > ${min_synergy})")
        print(f"{'='*70}")
        for i, lh in enumerate(loopholes, 1):
            print(f"\n#{i}. {lh['strategies'][0]} + {lh['strategies'][1]}")
            print(f"   {lh['strategy_names'][0]} + {lh['strategy_names'][1]}")
            print(f"   A alone: ${lh['savings_a_alone']:,} | B alone: ${lh['savings_b_alone']:,} | Sum: ${lh['sum_of_parts']:,}")
            print(f"   Combined: ${lh['savings_combined']:,}")
            print(f"   SYNERGY: ${lh['synergy']:,} ({lh['synergy_pct']} more than sum of parts)")

    # Save results
    output = {
        "profile": str(profile.get("_source", "unknown")),
        "baseline_liability": baseline_tax,
        "strategies_tested": len(candidates),
        "pairs_tested": tested,
        "loopholes_found": len(loopholes),
        "elapsed_seconds": round(elapsed, 1),
        "loopholes": loopholes,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / "loopholes.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {output_path}")

    return output


def main():
    parser = argparse.ArgumentParser(description="Find tax strategy loopholes (synergistic pairs)")
    parser.add_argument("--profile", type=str, default=str(DEFAULT_PROFILE),
                        help="Path to profile JSON")
    parser.add_argument("--top", type=int, default=30, help="Show top N results")
    parser.add_argument("--min-synergy", type=int, default=100,
                        help="Minimum synergy amount to report")
    args = parser.parse_args()

    with open(args.profile) as f:
        profile = json.load(f)
    profile["_source"] = Path(args.profile).name

    print("=" * 70)
    print("OpenLoopholes.com — Combination Scanner (Loophole Finder)")
    print("=" * 70)
    print(f"Profile: {Path(args.profile).name}")
    print(f"Mode: {profile.get('optimization_mode', 'both')}")
    print()

    run_scanner(profile, top_n=args.top, min_synergy=args.min_synergy)


if __name__ == "__main__":
    main()
