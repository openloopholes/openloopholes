#!/usr/bin/env python3
"""
OpenLoopholes.com — Autoresearch Loop Runner

Runs the iterative tax optimization loop against a taxpayer profile.
The LLM proposes strategy changes; a deterministic tax calculator scores them.
Following Karpathy's autoresearch pattern: the proposer never grades its own work.

Usage:
    python run.py --iterations 200
    python run.py --iterations 10 --profile profiles/sample.json
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

from tax_calculator import compute_tax
from strategy_registry import load_all_strategies, filter_strategies, build_prompt_sections
from ai_provider import call_llm, get_loop_model, get_validation_model, get_provider_name, log

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT / "prompts"
RESULTS_DIR = ROOT / "results"
LOOP_DIR = Path(__file__).resolve().parent

ITERATION_PROMPT_PATH = PROMPTS_DIR / "iteration-loop-system-prompt.md"
VALIDATION_PROMPT_PATH = PROMPTS_DIR / "final-validation-system-prompt.md"
STATE_PROMPT_PATH = PROMPTS_DIR / "state-utah.md"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CONSECUTIVE_FAILURE_THRESHOLD = 5
CONSECUTIVE_FAILURE_WAIT = 60
EXPERIMENT_HISTORY_WINDOW = 20


def load_file(path: Path) -> str:
    with open(path, "r") as f:
        return f.read()


def load_profile(path: Path) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def build_system_prompt(profile: dict) -> str:
    """Build iteration prompt: static template + dynamic strategy sections from registry."""
    template = load_file(ITERATION_PROMPT_PATH)
    opt_mode = profile.get("optimization_mode", "both")

    # Filter strategies to this profile (jurisdiction + eligibility)
    all_strategies = load_all_strategies()
    relevant = filter_strategies(profile, all_strategies)

    # Build dynamic strategy sections
    strategy_sections = build_prompt_sections(relevant, opt_mode)

    # Insert into template (or append if no placeholder)
    if "{STRATEGY_SECTIONS}" in template:
        return template.replace("{STRATEGY_SECTIONS}", strategy_sections)
    else:
        # Fallback: append after template
        return template + "\n\n---\n\n" + strategy_sections


def build_validation_system_prompt() -> str:
    """Concatenate validation + state prompts."""
    validation = load_file(VALIDATION_PROMPT_PATH)
    state = load_file(STATE_PROMPT_PATH)
    return validation + "\n\n---\n\n" + state


    # get_client() and call_llm() are now in ai_provider.py


def run_iteration(
    system_prompt: str,
    profile: dict,
    best_strategy_set: list[dict],
    best_liability: int,
    baseline_liability: int,
    iteration: int,
    max_iterations: int,
    experiment_history: list[dict],
) -> dict | None:
    """Run a single iteration. LLM proposes, we parse. Returns parsed JSON or None."""
    recent_history = experiment_history[-EXPERIMENT_HISTORY_WINDOW:]
    history_summary = []
    for exp in recent_history:
        history_summary.append({
            "iteration": exp["iteration"],
            "action": exp["action"],
            "strategy": exp["strategy"],
            "result": exp["result"],
            "reason": exp.get("rejection_reason", ""),
        })

    opt_mode = profile.get("optimization_mode", "both")
    current_date = profile.get("current_date", datetime.date.today().isoformat())
    tax_year = profile.get("tax_year", 2025)

    user_prompt = f"""TAXPAYER PROFILE:
{json.dumps(profile, indent=2)}

OPTIMIZATION MODE: {opt_mode}
TAX YEAR: {tax_year}
CURRENT DATE: {current_date}

CURRENT BEST STRATEGY SET:
{json.dumps(best_strategy_set, indent=2)}

CURRENT TAX LIABILITY (computed by calculator): ${best_liability:,}
BASELINE LIABILITY (no strategies): ${baseline_liability:,}
CURRENT SAVINGS: ${baseline_liability - best_liability:,}
ITERATION: {iteration} of {max_iterations}

EXPERIMENT HISTORY (last {len(history_summary)} attempts):
{json.dumps(history_summary, indent=2)}

Propose ONE modification to the current strategy set."""

    raw = call_llm(get_loop_model(), system_prompt, user_prompt)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def run_validation(
    profile: dict, best_strategy_set: list[dict],
    baseline_liability: int, best_liability: int,
    iterations_completed: int,
) -> dict | None:
    """Run the final validation pass with Gemini Flash."""
    system_prompt = build_validation_system_prompt()

    user_prompt = f"""TAXPAYER PROFILE:
{json.dumps(profile, indent=2)}

PROPOSED STRATEGY SET (from optimization loop):
{json.dumps(best_strategy_set, indent=2)}

BASELINE LIABILITY (calculator): ${baseline_liability:,}
OPTIMIZED LIABILITY (calculator): ${best_liability:,}
ESTIMATED REDUCTION: ${baseline_liability - best_liability:,}
ITERATIONS RUN: {iterations_completed}

Validate this strategy set and produce the final consumer-facing output."""

    raw = call_llm(get_validation_model(), system_prompt, user_prompt)
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            data = data[0] if data else {}
        return data
    except json.JSONDecodeError:
        log.error("Failed to parse validation response")
        return None


def main():
    parser = argparse.ArgumentParser(description="OpenLoopholes.com Autoresearch Loop Runner")
    parser.add_argument("--iterations", type=int, default=200, help="Max iterations (default: 200)")
    parser.add_argument("--profile", type=str, default="profiles/sample.json", help="Path to profile JSON")
    args = parser.parse_args()

    # --- Setup ---
    # AI provider auto-detected from env vars (see ai_provider.py)
    provider = get_provider_name()

    profile_path = LOOP_DIR / args.profile
    profile = load_profile(profile_path)
    system_prompt = build_system_prompt(profile)
    max_iterations = args.iterations

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    log.info("=" * 60)
    log.info("OpenLoopholes.com — Autoresearch Loop Runner")
    log.info("=" * 60)
    log.info(f"Profile: {profile_path.name}")
    log.info(f"Filing status: {profile['filing_status']}")
    log.info(f"Entities: {len(profile.get('entities', []))}")
    for e in profile.get("entities", []):
        log.info(f"  - {e['name']} ({e['type']})")
    log.info(f"W-2s: {len(profile.get('w2_income', []))}")
    log.info(f"Max iterations: {max_iterations}")
    log.info(f"AI provider: {provider}")
    log.info(f"Loop model: {get_loop_model()}")
    log.info(f"Validation model: {get_validation_model()}")
    log.info(f"Scorer: deterministic tax calculator")
    log.info(f"Mode: {profile.get('optimization_mode', 'both')}")
    log.info(f"Current date: {profile.get('current_date', datetime.date.today().isoformat())}")
    log.info("=" * 60)

    # --- Step 1: Baseline (deterministic — no LLM call) ---
    log.info("\n[STEP 1] Computing baseline tax liability (deterministic)...")
    start_time = time.time()
    baseline_result = compute_tax(profile, [])
    baseline_liability = baseline_result["total_tax"]
    log.info(f"  Baseline liability: ${baseline_liability:,}")
    log.info(f"  Federal: ${baseline_result['federal_tax']:,} | State: ${baseline_result['state_tax']:,}")
    log.info(f"  Breakdown: income_tax=${baseline_result['breakdown']['income_tax']:,}, "
             f"se_tax=${baseline_result['breakdown']['se_tax']:,}, "
             f"niit=${baseline_result['breakdown']['niit']:,}, "
             f"credits=${baseline_result['breakdown']['total_credits']:,}")

    best_liability = baseline_liability
    best_strategy_set: list[dict] = []
    experiments = []
    consecutive_api_failures = 0
    keeps = 0

    # --- Step 2: Iteration Loop ---
    log.info(f"\n[STEP 2] Running optimization loop ({max_iterations} iterations)...\n")
    log.info(f"{'Iter':>5} | {'Action':<8} | {'Strategy':<30} | {'Result':<8} | {'Liability':>12} | {'Savings':>12}")
    log.info("-" * 95)

    for i in range(1, max_iterations + 1):
        # LLM proposes a change
        try:
            response = run_iteration(
                system_prompt, profile, best_strategy_set,
                best_liability, baseline_liability,
                i, max_iterations, experiments,
            )
        except Exception as e:
            consecutive_api_failures += 1
            log.info(f"  {i:>5} | {'ERROR':<8} | API failure: {e}")
            experiments.append({
                "iteration": i,
                "action": "error",
                "strategy": "api_error",
                "detail": str(e),
                "estimated_liability": best_liability,
                "result": "rejected",
                "rejection_reason": "api_error",
                "improvement": 0,
            })
            if consecutive_api_failures >= CONSECUTIVE_FAILURE_THRESHOLD:
                log.info(f"  {CONSECUTIVE_FAILURE_THRESHOLD}+ consecutive API failures. Waiting {CONSECUTIVE_FAILURE_WAIT}s...")
                time.sleep(CONSECUTIVE_FAILURE_WAIT)
                consecutive_api_failures = 0
            continue

        consecutive_api_failures = 0

        # Handle parse failure
        if response is None:
            experiments.append({
                "iteration": i,
                "action": "error",
                "strategy": "parse_error",
                "detail": "Failed to parse JSON response",
                "estimated_liability": best_liability,
                "result": "rejected",
                "rejection_reason": "invalid_response",
                "improvement": 0,
            })
            log.info(f"  {i:>5} | {'ERROR':<8} | {'JSON parse failure':<30} | {'reject':<8} | {'':>12} | {'':>12}")
            continue

        # Extract the proposed strategy set
        exp = response.get("experiment", {})
        action = exp.get("action", "unknown")
        strategy_id = exp.get("strategy_id", "unknown")
        entity_name = exp.get("entity", None)
        description = exp.get("description", "")
        confidence = response.get("confidence", "unknown")
        new_strategy_set = response.get("updated_strategy_set", best_strategy_set)

        # DETERMINISTIC SCORING — the calculator grades the proposal
        try:
            calc_result = compute_tax(profile, new_strategy_set)
            new_liability = calc_result["total_tax"]
        except Exception as e:
            experiments.append({
                "iteration": i,
                "action": action,
                "strategy": strategy_id,
                "detail": f"Calculator error: {e}",
                "estimated_liability": best_liability,
                "result": "rejected",
                "rejection_reason": "calculator_error",
                "improvement": 0,
            })
            log.info(f"  {i:>5} | {action:<8} | {strategy_id[:30]:<30} | {'reject':<8} | {'calc err':>12} | {'':>12}")
            continue

        # Compare — based on calculator output, not LLM estimate
        if new_liability < best_liability:
            result = "keep"
            improvement = best_liability - new_liability
            best_liability = new_liability
            best_strategy_set = new_strategy_set
            keeps += 1
        else:
            result = "discard"
            improvement = 0

        # Log
        experiment_record = {
            "iteration": i,
            "action": action,
            "strategy": strategy_id,
            "entity": entity_name,
            "detail": description,
            "estimated_liability": new_liability,
            "result": result,
            "rejection_reason": "" if result == "keep" else "no_improvement",
            "improvement": improvement,
            "confidence": confidence,
            "expected_effect": response.get("expected_effect", ""),
        }
        experiments.append(experiment_record)

        # Print progress
        liability_str = f"${new_liability:,}" if result == "keep" else ""
        savings_str = f"${baseline_liability - best_liability:,}" if result == "keep" else ""
        entity_tag = f" ({entity_name})" if entity_name else ""
        strategy_display = (strategy_id + entity_tag)[:30]
        log.info(f"  {i:>5} | {action:<8} | {strategy_display:<30} | {result:<8} | {liability_str:>12} | {savings_str:>12}")

        # Convergence check — fixed window of 20 consecutive discards
        lookback = 20
        if i >= lookback:
            recent = experiments[-lookback:]
            recent_keeps = sum(1 for e in recent if e["result"] == "keep")
            if recent_keeps == 0:
                log.info(f"\n  Converged: {lookback} iterations with no improvements. Stopping early.")
                break

    loop_time = time.time() - start_time
    iterations_completed = len(experiments)
    total_savings = baseline_liability - best_liability

    log.info("-" * 95)
    log.info(f"\nLoop complete: {iterations_completed} iterations, {keeps} improvements, ${total_savings:,} total savings")
    log.info(f"Time: {loop_time:.1f}s")

    # Print final breakdown
    final_result = compute_tax(profile, best_strategy_set)
    log.info(f"\nFinal breakdown:")
    log.info(f"  Federal: ${final_result['federal_tax']:,} | State: ${final_result['state_tax']:,}")
    bd = final_result["breakdown"]
    log.info(f"  AGI: ${bd['agi']:,} | Taxable: ${bd['taxable_income']:,}")
    log.info(f"  Income tax: ${bd['income_tax']:,} | SE tax: ${bd['se_tax']:,} | NIIT: ${bd['niit']:,}")
    log.info(f"  Credits: ${bd['total_credits']:,} | QBI deduction: ${bd['qbi_deduction']:,}")
    log.info(f"  Strategies: {bd['strategies_applied']}")

    # --- Step 3: Final Validation ---
    log.info("\n[STEP 3] Running final validation...")
    validation_result = run_validation(
        profile, best_strategy_set,
        baseline_liability, best_liability,
        iterations_completed,
    )

    if validation_result:
        summary_data = validation_result.get("summary", {})
        final_strategies = validation_result.get("final_strategies", [])
        log.info(f"  Validation: {validation_result.get('validation_result', 'unknown')}")
        log.info(f"  Final strategies: {len(final_strategies)}")
        log.info(f"  Validated savings: ${summary_data.get('total_estimated_savings', total_savings):,}")

        issues = validation_result.get("issues_found", [])
        if issues:
            log.info(f"  Issues found: {len(issues)}")
            for issue in issues:
                log.info(f"    - [{issue.get('severity', '?')}] {issue.get('strategy_id', '?')}: {issue.get('description', '')}")
    else:
        log.info("  Validation failed — using loop results as-is")
        final_strategies = best_strategy_set

    total_time = time.time() - start_time

    # --- Step 4: Save Results ---
    log.info("\n[STEP 4] Saving results...")

    with open(RESULTS_DIR / "experiments.json", "w") as f:
        json.dump(experiments, f, indent=2)

    with open(RESULTS_DIR / "strategies.json", "w") as f:
        json.dump(validation_result if validation_result else {"strategies": best_strategy_set}, f, indent=2)

    summary = {
        "profile": profile_path.name,
        "filing_status": profile["filing_status"],
        "entity_count": len(profile.get("entities", [])),
        "baseline_liability": baseline_liability,
        "optimized_liability": best_liability,
        "total_savings": total_savings,
        "iterations_completed": iterations_completed,
        "iterations_target": max_iterations,
        "improvements_found": keeps,
        "strategy_count": len(best_strategy_set),
        "strategy_set": best_strategy_set,
        "convergence": iterations_completed < max_iterations,
        "loop_model": get_loop_model(),
        "validation_model": get_validation_model(),
        "scorer": "deterministic_tax_calculator",
        "total_time_seconds": round(total_time, 1),
        "baseline_breakdown": baseline_result["breakdown"],
        "final_breakdown": final_result["breakdown"],
    }
    with open(RESULTS_DIR / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    log.info(f"  Saved to {RESULTS_DIR}/")
    log.info(f"\n{'=' * 60}")
    log.info(f"RESULTS SUMMARY")
    log.info(f"{'=' * 60}")
    log.info(f"  Baseline liability:  ${baseline_liability:,}")
    log.info(f"  Optimized liability: ${best_liability:,}")
    log.info(f"  Total savings:       ${total_savings:,}")
    log.info(f"  Strategies:          {len(best_strategy_set)}")
    log.info(f"  Experiments:         {iterations_completed}")
    log.info(f"  Time:                {total_time:.1f}s")
    log.info(f"  Scorer:              deterministic calculator")
    log.info(f"{'=' * 60}")


if __name__ == "__main__":
    main()
