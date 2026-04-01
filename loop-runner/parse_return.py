#!/usr/bin/env python3
"""
OpenLoopholes.com — Tax Return PDF Parser

Converts a tax return PDF to markdown (via pymupdf4llm), then sends
the markdown to the configured AI provider to extract a structured
multi-entity profile JSON.

Usage:
    python3 parse_return.py ../tax-documents/return.pdf
    python3 parse_return.py ../tax-documents/return.pdf --output profiles/my-profile.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ai_provider import call_llm, get_validation_model

EXTRACTION_PROMPT = """You are a tax return data extractor. Given the text of a US federal tax return (Form 1040 and attached schedules/K-1s), extract a structured financial profile as JSON.

CRITICAL RULES:
- Extract ONLY what is explicitly stated on the forms. Do not infer or calculate values.
- If a field is not present, set it to null or 0.
- Extract EVERY business entity separately (each Schedule C, each K-1, each rental property).
- Dollar amounts as integers (no decimals, no cents).
- Be thorough — there may be many schedules and K-1s.

Output JSON matching this EXACT schema:

{
  "taxpayer_age": <int or null>,
  "spouse_age": <int or null>,
  "filing_status": "single" | "married_joint" | "married_separate" | "head_of_household",
  "state": "<2-letter state code from address on return>",
  "optimization_mode": "retroactive",
  "current_date": "<today's date YYYY-MM-DD>",
  "tax_year": <int, from the return>,
  "dependents": [{"name": "<string>", "age": <int>, "relationship": "child"}],

  "w2_income": [
    {
      "employer": "<string>",
      "wages": <int>,
      "traditional_401k": <int, box 12 code D amount or 0>,
      "roth_401k": <int, box 12 code AA amount or 0>
    }
  ],

  "entities": [
    // For EACH Schedule C:
    {
      "name": "<business name from Schedule C>",
      "type": "schedule_c",
      "net_income": <int, line 31>,
      "is_sstb": <bool, true if law/medicine/accounting/consulting/financial services>
    },

    // For EACH S-Corp K-1 (Form 1120-S):
    {
      "name": "<entity name from K-1>",
      "type": "s_corp",
      "officer_compensation": <int, from W-2 or K-1>,
      "ordinary_income": <int, box 1>,
      "distributions": <int, box 16 code D>,
      "is_sstb": <bool>
    },

    // For EACH Partnership K-1 (Form 1065):
    {
      "name": "<entity name from K-1>",
      "type": "partnership",
      "ordinary_income": <int, box 1>,
      "guaranteed_payments": <int, box 4>,
      "is_sstb": <bool>
    },

    // For EACH rental property (Schedule E Part I):
    {
      "name": "<property address>",
      "type": "rental",
      "net_income": <int>
    }
  ],

  "business_sales": [
    // For large capital gain events (Form 8949, Schedule D):
    {
      "name": "<asset sold>",
      "capital_gain": <int>,
      "gain_type": "long_term" | "short_term",
      "date_sold": "<YYYY-MM-DD if available>"
    }
  ],

  "investment_income": {
    "capital_gains_short": <int, Schedule D Part I total or 0>,
    "capital_gains_long": <int, Schedule D Part II total or 0>,
    "interest_income": <int, 1040 line 2b or 0>,
    "dividend_income_qualified": <int, 1040 line 3a or 0>,
    "dividend_income_ordinary": <int, 1040 line 3b minus 3a or 0>
  },

  "other_income": {
    "social_security": <int, 1040 line 6a or 0>,
    "pension": <int, 1040 line 5a or 0>,
    "other": <int, 1040 line 8 or 0>
  },

  "deductions": {
    "salt_paid": <int, Schedule A line 5d or state taxes paid>,
    "mortgage_interest": <int, Schedule A line 8a or 0>,
    "charitable_cash": <int, Schedule A line 12 or 0>,
    "charitable_noncash": <int, Schedule A line 12 or 0>,
    "medical_expenses": <int, Schedule A line 4 or 0>,
    "student_loan_interest": <int, Schedule 1 line 21 or 0>,
    "educator_expenses": <int, Schedule 1 line 11 or 0>
  },

  "retirement": {
    "traditional_ira_contributions": <int or 0>,
    "hsa_contributions": <int, Form 8889 line 2 or 0>,
    "has_hdhp": <bool>,
    "hdhp_coverage": "self" | "family"
  },

  "self_employed_health_insurance": <int, Schedule 1 line 17 or 0>,

  "extraction_confidence": {
    "overall": "high" | "medium" | "low",
    "low_confidence_fields": ["list of field paths where extraction was uncertain"],
    "notes": "any important observations about the return"
  }
}
"""


def pdf_to_markdown(pdf_path: Path) -> str:
    """Convert PDF to LLM-optimized markdown using pymupdf4llm."""
    try:
        import pymupdf4llm
    except ImportError:
        print("ERROR: pymupdf4llm not installed. Run: pip3 install pymupdf4llm")
        sys.exit(1)

    print(f"Converting PDF to markdown...")
    md = pymupdf4llm.to_markdown(str(pdf_path))
    print(f"  Converted: {len(md):,} characters, ~{len(md.split()):,} words")
    return md


def parse_return(pdf_path: str, output_path: str) -> dict:
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        print(f"ERROR: File not found: {pdf_path}")
        sys.exit(1)

    print(f"Reading PDF: {pdf_path} ({pdf_path.stat().st_size / 1024 / 1024:.1f} MB)")

    # Step 1: Convert PDF to markdown
    markdown = pdf_to_markdown(pdf_path)

    # Step 2: Send markdown to AI for extraction
    model = get_validation_model()
    print(f"Sending to {model} for extraction...")

    user_prompt = f"""Extract the financial profile from this tax return. Output as JSON matching the schema in your instructions.

TAX RETURN CONTENT:

{markdown}"""

    raw = call_llm(model, EXTRACTION_PROMPT, user_prompt, temperature=0.1)
    profile = json.loads(raw)

    # Handle list response
    if isinstance(profile, list):
        profile = profile[0] if profile else {}

    # Print summary
    entities = profile.get("entities", [])
    w2s = profile.get("w2_income", [])
    confidence = profile.get("extraction_confidence", {})

    print(f"\nExtraction complete:")
    print(f"  Filing status: {profile.get('filing_status')}")
    print(f"  State: {profile.get('state')}")
    print(f"  W-2s found: {len(w2s)}")
    print(f"  Entities found: {len(entities)}")
    for e in entities:
        net = e.get("net_income", e.get("ordinary_income", "?"))
        if isinstance(net, int):
            print(f"    - {e.get('name', 'Unknown')} ({e.get('type', '?')}) — net: ${net:,}")
        else:
            print(f"    - {e.get('name', 'Unknown')} ({e.get('type', '?')})")
    print(f"  Confidence: {confidence.get('overall', '?')}")
    if confidence.get("low_confidence_fields"):
        print(f"  Low confidence: {confidence['low_confidence_fields']}")
    if confidence.get("notes"):
        print(f"  Notes: {confidence['notes']}")

    # Save
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(profile, f, indent=2)
    print(f"\nProfile saved to: {output}")

    return profile


def main():
    parser = argparse.ArgumentParser(description="Parse a tax return PDF into structured JSON")
    parser.add_argument("pdf", help="Path to the tax return PDF")
    parser.add_argument("--output", "-o", default=None,
                        help="Output JSON path (default: profiles/<filename>.json)")
    args = parser.parse_args()

    if args.output is None:
        stem = Path(args.pdf).stem
        args.output = str(Path(__file__).parent / "profiles" / f"{stem}.json")

    parse_return(args.pdf, args.output)


if __name__ == "__main__":
    main()
