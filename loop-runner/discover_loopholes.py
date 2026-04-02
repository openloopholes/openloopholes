#!/usr/bin/env python3
"""
OpenLoopholes.com — Loophole Discovery Engine

Scans IRC sections and asks an LLM to identify deductions, credits,
exclusions, and exemptions that could reduce a taxpayer's liability.
Compares discoveries against the existing loophole registry to find
new loopholes not yet in the system.

Usage:
    python discover_loopholes.py                          # Scan priority subtitles (A, B, C)
    python discover_loopholes.py --subtitle A             # Scan specific subtitle
    python discover_loopholes.py --sections 121,199A,401  # Scan specific sections
    python discover_loopholes.py --all                    # Scan everything (slow, expensive)
    python discover_loopholes.py --dry-run                # Show what would be scanned

Output:
    results/discoveries.json — list of candidate loopholes found
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from loophole_registry import load_all_loopholes
from ai_provider import call_llm, get_discovery_model, get_client

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
TAX_CODE_DIR = Path(__file__).resolve().parent / "tax_code"
SECTIONS_DIR = TAX_CODE_DIR / "sections"
INDEX_PATH = TAX_CODE_DIR / "index.json"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
# Model configured via AI_PROVIDER + DISCOVERY_MODEL env vars (see ai_provider.py)

# IRC subtitle section ranges
SUBTITLES = {
    "A": {"name": "Income Taxes", "range": (1, 1500), "priority": 1,
          "description": "Individual/corporate income tax, deductions, credits, capital gains, partnerships, S-corps, trusts, real estate, international"},
    "B": {"name": "Estate & Gift Taxes", "range": (2001, 2900), "priority": 2,
          "description": "Estate tax, gift tax, generation-skipping transfer tax"},
    "C": {"name": "Employment Taxes", "range": (3101, 3600), "priority": 2,
          "description": "FICA, FUTA, income tax withholding, SE tax"},
    "D": {"name": "Excise Taxes", "range": (4001, 5100), "priority": 3,
          "description": "Excise taxes on fuels, vehicles, insurance, wagering, etc."},
    "E": {"name": "Alcohol, Tobacco & Firearms", "range": (5001, 5900), "priority": 4,
          "description": "Industry-specific taxes — rarely relevant to individual taxpayers"},
    "F": {"name": "Procedure & Administration", "range": (6001, 7900), "priority": 3,
          "description": "Filing requirements, penalties, interest, collections, refunds, judicial proceedings"},
    "G": {"name": "Joint Committee on Taxation", "range": (8001, 8100), "priority": 5,
          "description": "Administrative — no tax savings loopholes"},
    "H": {"name": "Presidential Campaign Financing", "range": (9001, 9100), "priority": 5,
          "description": "Campaign fund checkoff — no tax savings loopholes"},
    "I": {"name": "Trust Fund Code", "range": (9500, 9650), "priority": 4,
          "description": "Highway, airport, hazardous substance trust funds"},
    "J": {"name": "Coal Industry Health Benefits", "range": (9701, 9750), "priority": 5,
          "description": "Industry-specific — rarely relevant"},
    "K": {"name": "Group Health Plan Requirements", "range": (9801, 9900), "priority": 3,
          "description": "HIPAA, COBRA, ACA requirements for group health plans"},
}

# Default: scan priority 1-2 (Income Taxes, Estate/Gift, Employment)
DEFAULT_PRIORITY = 2

MAX_SECTION_CHARS = 15000  # Truncate very long sections to fit context
BATCH_SIZE = 5             # Sections per LLM call
MAX_RETRIES = 3

DISCOVERY_PROMPT = """You are a tax loophole researcher for OpenLoopholes.com. You are reading actual IRC (Internal Revenue Code) section text to identify tax savings opportunities.

For each IRC section provided, identify any:
- **Deductions** (above-the-line or itemized)
- **Credits** (refundable or nonrefundable)
- **Exclusions** (income excluded from gross income)
- **Exemptions** (amounts exempt from tax)
- **Deferrals** (ways to defer tax recognition)
- **Preferential rates** (reduced tax rates for certain income)
- **Elections** (taxpayer choices that reduce liability)

For each loophole found, output:
- A suggested loophole ID (uppercase, underscore-separated, e.g., "DED_MOVING_EXPENSES")
- The IRC section number
- Who it benefits (individual, business, investor, etc.)
- What it does (1-2 sentences)
- Estimated savings potential (high/medium/low/niche)
- Whether it requires specific actions or is automatic

IMPORTANT:
- Only identify loopholes that can REDUCE tax liability for the taxpayer
- Skip procedural rules, definitions, penalties, and administrative provisions
- Skip loopholes that are expired, repealed, or only apply to tax years before 2025
- Be specific — "there might be a deduction here" is not useful

Output valid JSON:
```json
{
  "discoveries": [
    {
      "loophole_id": "string",
      "irc_section": "string",
      "name": "string",
      "description": "string",
      "benefits": "individual|business|investor|estate|employer",
      "savings_potential": "high|medium|low|niche",
      "requires_action": true,
      "eligibility_summary": "string"
    }
  ]
}
```

If a section contains NO actionable tax savings loopholes, return: {"discoveries": []}
"""


def load_index() -> dict:
    with open(INDEX_PATH) as f:
        return json.load(f)


def get_sections_for_subtitle(index: dict, subtitle_key: str) -> list[tuple[str, dict]]:
    """Get all sections belonging to a subtitle's range."""
    info = SUBTITLES[subtitle_key]
    lo, hi = info["range"]
    results = []
    for sec_num, meta in index.items():
        try:
            num = int(sec_num.split("-")[0].split("A")[0].split("B")[0].split("C")[0])
        except ValueError:
            continue
        if lo <= num <= hi:
            results.append((sec_num, meta))
    return sorted(results, key=lambda x: x[0])


def load_section_text(sec_num: str) -> str:
    """Load section text, truncated if too long."""
    filepath = SECTIONS_DIR / f"section_{sec_num}.txt"
    if not filepath.exists():
        return ""
    with open(filepath) as f:
        text = f.read()
    if len(text) > MAX_SECTION_CHARS:
        text = text[:MAX_SECTION_CHARS] + f"\n\n[TRUNCATED — full section is {len(text):,} characters]"
    return text


def call_discovery(sections_text: str) -> list[dict]:
    """Send sections to LLM for loophole discovery."""
    try:
        raw = call_llm(get_discovery_model(), DISCOVERY_PROMPT, sections_text, temperature=0.3)
        data = json.loads(raw)
        if isinstance(data, list):
            data = data[0] if data else {"discoveries": []}
        return data.get("discoveries", [])
    except Exception as e:
        print(f"    FAILED: {e}")
        return []


def deduplicate(discoveries: list[dict], existing_ids: set[str]) -> tuple[list[dict], list[dict]]:
    """Split discoveries into new (not in registry) and existing (already known)."""
    new = []
    existing = []
    seen_ids = set()
    for d in discoveries:
        sid = d.get("strategy_id", "").upper()
        if not sid:
            continue
        if sid in seen_ids:
            continue
        seen_ids.add(sid)
        if sid in existing_ids:
            existing.append(d)
        else:
            new.append(d)
    return new, existing


def run_discovery(
    sections_to_scan: list[tuple[str, dict]],
    existing_ids: set[str],
    dry_run: bool = False,
) -> dict:
    """Run the discovery engine on a list of sections."""
    total = len(sections_to_scan)
    print(f"Scanning {total} IRC sections...")

    if dry_run:
        print("DRY RUN — showing sections that would be scanned:")
        for sec_num, meta in sections_to_scan[:20]:
            print(f"  §{sec_num}: {meta['title']} ({meta['words']:,} words)")
        if total > 20:
            print(f"  ... and {total - 20} more")
        return {"discoveries": [], "new": [], "existing": [], "sections_scanned": total}

    # AI provider auto-detected from env vars (see ai_provider.py)
    all_discoveries = []
    batches = [sections_to_scan[i:i + BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]

    for batch_idx, batch in enumerate(batches):
        # Build combined text for this batch
        combined = ""
        sec_nums = []
        for sec_num, meta in batch:
            text = load_section_text(sec_num)
            if not text.strip():
                continue
            combined += f"\n\n{'='*60}\nIRC §{sec_num}: {meta['title']}\n{'='*60}\n\n{text}"
            sec_nums.append(sec_num)

        if not combined.strip():
            continue

        print(f"  Batch {batch_idx + 1}/{len(batches)}: §{', §'.join(sec_nums)}")

        discoveries = call_discovery(combined)
        all_discoveries.extend(discoveries)

        if discoveries:
            for d in discoveries:
                print(f"    FOUND: {d.get('strategy_id', '?')} — {d.get('name', '?')} (§{d.get('irc_section', '?')})")

        # Rate limiting
        time.sleep(0.5)

    # Deduplicate against existing registry
    new, existing = deduplicate(all_discoveries, existing_ids)

    print(f"\nDiscovery complete:")
    print(f"  Total found: {len(all_discoveries)}")
    print(f"  New (not in registry): {len(new)}")
    print(f"  Already known: {len(existing)}")
    print(f"  Sections scanned: {total}")

    return {
        "discoveries": all_discoveries,
        "new": new,
        "existing": existing,
        "sections_scanned": total,
    }


def main():
    parser = argparse.ArgumentParser(description="Discover tax loopholes from IRC sections")
    parser.add_argument("--subtitle", type=str, help="Scan specific subtitle (A, B, C, ...)")
    parser.add_argument("--sections", type=str, help="Scan specific sections (comma-separated)")
    parser.add_argument("--all", action="store_true", help="Scan all subtitles")
    parser.add_argument("--priority", type=int, default=DEFAULT_PRIORITY,
                        help=f"Scan subtitles up to this priority level (default: {DEFAULT_PRIORITY})")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be scanned")
    args = parser.parse_args()

    if not INDEX_PATH.exists():
        print("ERROR: Tax code not parsed yet. Run: python parse_tax_code.py --download")
        sys.exit(1)

    index = load_index()

    # Load existing loophole IDs
    existing_loopholes = load_all_loopholes()
    existing_ids = {s["id"] for s in existing_loopholes}
    print(f"Existing loopholes in registry: {len(existing_ids)}")

    # Determine which sections to scan
    sections_to_scan = []

    if args.sections:
        # Specific sections
        for sec_num in args.sections.split(","):
            sec_num = sec_num.strip()
            if sec_num in index:
                sections_to_scan.append((sec_num, index[sec_num]))
            else:
                print(f"WARNING: Section §{sec_num} not found in index")
    elif args.subtitle:
        # Specific subtitle
        key = args.subtitle.upper()
        if key not in SUBTITLES:
            print(f"ERROR: Unknown subtitle '{key}'. Valid: {', '.join(SUBTITLES.keys())}")
            sys.exit(1)
        sections_to_scan = get_sections_for_subtitle(index, key)
        info = SUBTITLES[key]
        print(f"Subtitle {key}: {info['name']} — {info['description']}")
    elif args.all:
        # All subtitles
        for key in sorted(SUBTITLES.keys()):
            sections_to_scan.extend(get_sections_for_subtitle(index, key))
        print("Scanning ALL subtitles")
    else:
        # Default: priority-based
        for key, info in sorted(SUBTITLES.items(), key=lambda x: x[1]["priority"]):
            if info["priority"] <= args.priority:
                subtitle_sections = get_sections_for_subtitle(index, key)
                sections_to_scan.extend(subtitle_sections)
                print(f"  Subtitle {key} ({info['name']}): {len(subtitle_sections)} sections [priority {info['priority']}]")
            else:
                print(f"  Subtitle {key} ({info['name']}): SKIPPED [priority {info['priority']} > {args.priority}]")

    if not sections_to_scan:
        print("No sections to scan.")
        return

    print(f"\nTotal sections to scan: {len(sections_to_scan)}")
    print()

    results = run_discovery(sections_to_scan, existing_ids, dry_run=args.dry_run)

    # Save results
    if not args.dry_run:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = RESULTS_DIR / "discoveries.json"
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to {output_path}")

        if results["new"]:
            print(f"\n{'='*60}")
            print("NEW LOOPHOLES FOUND (not in registry):")
            print(f"{'='*60}")
            for d in results["new"]:
                print(f"  {d['strategy_id']}: {d['name']}")
                print(f"    §{d['irc_section']} — {d['description']}")
                print(f"    Benefits: {d['benefits']} | Savings: {d['savings_potential']}")
                print()


if __name__ == "__main__":
    main()
