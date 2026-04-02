"""
OpenLoopholes.com — Loophole Registry

Single source of truth for all tax loopholes. Each loophole is a JSON file
in the loopholes/ directory. This module loads, filters, and builds prompt
sections from them.

Adding a new loophole = adding one JSON file. No code changes needed
(unless it needs a new calculator handler).
"""

from __future__ import annotations

import json
from pathlib import Path

LOOPHOLES_DIR = Path(__file__).resolve().parent / "loopholes"

_cache: list[dict] | None = None
_by_id: dict[str, dict] | None = None


def load_all_loopholes() -> list[dict]:
    """Load all loophole JSON files from the loopholes/ directory."""
    global _cache, _by_id
    if _cache is not None:
        return _cache
    loopholes = []
    seen_ids = {}
    for filepath in sorted(LOOPHOLES_DIR.glob("*.json")):
        with open(filepath) as f:
            s = json.load(f)
        sid = s.get("id", filepath.stem)
        if sid in seen_ids:
            raise ValueError(
                f"Duplicate loophole ID '{sid}' found in {filepath.name} "
                f"(already defined in {seen_ids[sid]})"
            )
        seen_ids[sid] = filepath.name
        loopholes.append(s)
    _cache = loopholes
    _by_id = {s["id"]: s for s in loopholes}
    return loopholes


def get_loophole(sid: str) -> dict | None:
    """Look up a loophole by ID."""
    if _by_id is None:
        load_all_loopholes()
    return _by_id.get(sid)


def filter_loopholes(profile: dict, loopholes: list[dict] | None = None) -> list[dict]:
    """
    Filter loopholes to those relevant to a profile.
    Checks jurisdiction (federal + user's state), basic eligibility,
    and actionability (excludes deadline-passed loopholes in retroactive mode).
    """
    if loopholes is None:
        loopholes = load_all_loopholes()

    state = profile.get("state", "").upper()
    entity_types = {e["type"] for e in profile.get("entities", [])}
    age = profile.get("taxpayer_age", 40)
    opt_mode = profile.get("optimization_mode", "both")

    filtered = []
    for s in loopholes:
        # Jurisdiction filter
        jur = s.get("jurisdiction", "federal")
        if jur == "federal":
            pass  # always include
        elif jur.startswith("state:"):
            strategy_state = jur.split(":")[1].upper()
            if strategy_state != state:
                continue
        else:
            continue

        elig = s.get("eligibility", {})

        # Age filter
        min_age = elig.get("min_age")
        if min_age is not None and age < min_age:
            continue
        max_age = elig.get("max_age")
        if max_age is not None and age > max_age:
            continue

        # Entity type filter — only exclude if strategy requires a specific
        # entity type and the profile has NO entities of that type
        req_type = elig.get("requires_entity_type")
        if req_type and req_type not in entity_types:
            continue

        # Actionability filter — in retroactive mode, exclude deadline-passed loopholes
        # Don't even put them in the prompt so the LLM can't waste iterations on them
        if opt_mode == "retroactive":
            act = s.get("actionability", {})
            if act.get("retroactive_status") == "deadline_passed":
                continue

        filtered.append(s)

    return filtered


def build_prompt_sections(loopholes: list[dict], optimization_mode: str = "forward") -> str:
    """
    Build the dynamic loophole sections for the iteration prompt.
    Returns markdown string with: loophole table, parameter reference,
    conflict rules, and actionability rules.
    """
    # Group by category
    categories = {}
    for s in loopholes:
        cat = s.get("category", "other")
        categories.setdefault(cat, []).append(s)

    category_labels = {
        "retirement": "Retirement",
        "se_tax": "Self-Employment Tax",
        "deduction": "Deductions",
        "credit": "Credits",
        "business": "Business Owner Strategies",
        "entity": "Entity Structure",
        "capital_gain": "Capital Gain Strategies",
        "rental": "Rental Property",
        "timing": "Income Timing",
        "obbb": "OBBB Provisions",
    }

    lines = []

    # === LOOPHOLE IDS AND ELIGIBILITY ===
    lines.append("## LOOPHOLE IDS AND ELIGIBILITY QUICK-REFERENCE\n")
    for cat, label in category_labels.items():
        strats = categories.get(cat, [])
        if not strats:
            continue
        lines.append(f"### {label}")
        lines.append("| ID | Strategy | Key Eligibility |")
        lines.append("|----|----------|----------------|")
        for s in strats:
            elig_desc = s.get("eligibility", {}).get("description", "")
            lines.append(f"| {s['id']} | {s['name']} | {elig_desc} |")
        lines.append("")

    # === CONFLICT RULES ===
    lines.append("## CONFLICT RULES (MUST CHECK)\n")
    conflict_num = 1
    seen_conflicts = set()
    for s in loopholes:
        for conflict_id in s.get("conflicts", []):
            pair = tuple(sorted([s["id"], conflict_id]))
            if pair not in seen_conflicts:
                seen_conflicts.add(pair)
                lines.append(f"{conflict_num}. {s['id']} \u2194 {conflict_id}: Check for incompatibility")
                conflict_num += 1
    # Add the standard hardcoded conflicts that aren't per-loophole
    lines.append(f"{conflict_num}. Multiple 401(k) deferrals: $23,500 limit is per person across all plans")
    conflict_num += 1
    lines.append(f"{conflict_num}. DED_SEC179: Cannot create net loss; DED_BONUS_DEPR can")
    conflict_num += 1
    lines.append(f"{conflict_num}. RET_ROTH_CONVERSION: Increases AGI \u2192 cascading phase-out effects")
    conflict_num += 1
    lines.append(f"{conflict_num}. RENT_REPS \u2194 full-time W-2: Incompatible")
    conflict_num += 1
    lines.append(f"{conflict_num}. RENT_PAL $25K \u2194 AGI >$150K: Fully phased out")
    conflict_num += 1
    lines.append(f"{conflict_num}. DED_SALT \u2194 standard deduction: SALT only helps itemizers")
    conflict_num += 1
    lines.append(f"{conflict_num}. RET_HSA \u2194 Medicare or non-HDHP: Cannot contribute")
    conflict_num += 1
    lines.append(f"{conflict_num}. CG_QSBS_1202 \u2194 S-Corp: Section 1202 only applies to C-Corp stock")
    conflict_num += 1
    lines.append(f"{conflict_num}. BIZ_FAMILY_EMPLOY: No FICA only if sole prop or partnership (NOT S-Corp)")
    conflict_num += 1
    lines.append(f"{conflict_num}. CG_CRT: Irrevocable. Must be established BEFORE the sale closes")
    conflict_num += 1
    lines.append(f"{conflict_num}. BIZ_HRA \u2194 SE_HEALTH_INS: For >2% S-Corp shareholders, use SE_HEALTH_INS")
    conflict_num += 1
    lines.append(f"{conflict_num}. CG_DAF: Deduction limited to 30% AGI for appreciated property, 60% for cash")
    conflict_num += 1
    lines.append(f"{conflict_num}. DED_QCD \u2194 DED_CHARITABLE: QCD amount cannot also be claimed as charitable deduction")
    lines.append("")

    # === ACTIONABILITY RULES ===
    if optimization_mode in ("retroactive", "both"):
        lines.append("## ACTIONABILITY RULES\n")
        available = []
        deadline_passed = []
        depends = []
        for s in loopholes:
            act = s.get("actionability", {})
            status = act.get("retroactive_status", "available")
            note = act.get("retroactive_note", "")
            entry = f"- {s['id']} \u2014 {note}"
            if status == "available":
                available.append(entry)
            elif status == "deadline_passed":
                deadline_passed.append(entry)
            elif status == "depends":
                depends.append(entry)
        if available:
            lines.append("### STILL ACTIONABLE (before filing deadline)")
            lines.extend(available)
            lines.append("")
        if deadline_passed:
            lines.append("### DEADLINE PASSED — DO NOT PROPOSE in retroactive mode")
            lines.extend(deadline_passed)
            lines.append("")
        if depends:
            lines.append("### DEPENDS ON CIRCUMSTANCES (retroactive mode)")
            lines.extend(depends)
            lines.append("")

    # === PARAMETER REFERENCE ===
    lines.append("## LOOPHOLE PARAMETER REFERENCE\n")
    lines.append("Entity-specific loopholes MUST include an `\"entity\"` field matching the entity name.\n")

    # Personal-level
    personal = [s for s in loopholes if not s.get("entity_specific", False)]
    entity_strats = [s for s in loopholes if s.get("entity_specific", False)]

    lines.append("### Personal-Level Loopholes (no entity field needed)\n")
    lines.append("| Strategy ID | Required Parameters |")
    lines.append("|-------------|-------------------|")
    for s in personal:
        params = s.get("parameters", {})
        if not params:
            lines.append(f"| {s['id']} | `{{}}` |")
        else:
            param_str = ", ".join(f'"{k}": <{v["type"]}>' for k, v in params.items())
            desc = ", ".join(v.get("description", "") for v in params.values())
            lines.append(f"| {s['id']} | `{{{param_str}}}` \u2014 {desc} |")

    lines.append("")
    lines.append("### Entity-Specific Loopholes (MUST include `\"entity\": \"Entity Name\"`)\n")
    lines.append("| Strategy ID | Entity Types | Required Parameters |")
    lines.append("|-------------|-------------|-------------------|")
    for s in entity_strats:
        types = ", ".join(s.get("entity_types", []))
        params = s.get("parameters", {})
        if not params:
            lines.append(f"| {s['id']} | {types} | `{{}}` |")
        else:
            param_str = ", ".join(f'"{k}": <{v["type"]}>' for k, v in params.items())
            desc = ", ".join(v.get("description", "") for v in params.values())
            lines.append(f"| {s['id']} | {types} | `{{{param_str}}}` \u2014 {desc} |")

    lines.append("")

    return "\n".join(lines)
