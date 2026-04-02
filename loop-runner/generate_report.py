#!/usr/bin/env python3
"""
Generate a CPA-ready tax strategy report from optimizer results.
Outputs an HTML file styled with the Architectural Ledger design system.
"""

from __future__ import annotations

import json
from pathlib import Path
from tax_calculator import compute_tax
from strategy_registry import get_strategy

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "results"


def compute_marginal_savings(profile: dict, strategy_set: list[dict]) -> dict[str, int]:
    """
    For each strategy, compute its marginal contribution by running the calculator
    with all strategies EXCEPT that one, then comparing to the full set.
    Deterministic — no LLM estimation.
    """
    full_result = compute_tax(profile, strategy_set)
    full_tax = full_result["total_tax"]

    marginal = {}
    for i, strat in enumerate(strategy_set):
        without = strategy_set[:i] + strategy_set[i+1:]
        without_result = compute_tax(profile, without)
        marginal[f"{strat['id']}:{strat.get('entity') or ''}"] = without_result["total_tax"] - full_tax

    return marginal


def generate_report(results_dir: Path | None = None):
    if results_dir is None:
        results_dir = RESULTS_DIR
    with open(results_dir / "strategies.json") as f:
        data = json.load(f)
    with open(results_dir / "summary.json") as f:
        summary = json.load(f)

    validated_strategies = data.get("final_strategies", [])
    issues = data.get("issues_found", [])
    tax_calendar = data.get("tax_calendar", [])
    next_steps = data.get("next_steps", "")
    disclaimer = data.get("disclaimer", "")
    s = data.get("summary", {})

    # Source of truth: the loop's strategy set (scored by deterministic calculator)
    loop_strategy_set = summary.get("strategy_set", [])

    # Load profile and compute marginal savings deterministically
    profile_name = summary.get("profile", "sample.json")
    profile_path = ROOT / "loop-runner" / "profiles" / profile_name
    with open(profile_path) as f:
        profile = json.load(f)
    marginal_savings = compute_marginal_savings(profile, loop_strategy_set)

    # Build lookups from validation for annotations
    issues_by_id = {}
    for issue in issues:
        issues_by_id[issue.get("strategy_id", "")] = issue

    validated_by_id = {}
    for strat in validated_strategies:
        validated_by_id[strat.get("id", "")] = strat

    # Classify each loop strategy as confirmed or conditional
    confirmed = []
    conditional = []
    for loop_strat in loop_strategy_set:
        sid = loop_strat.get("id", "")
        if sid in issues_by_id and issues_by_id[sid].get("severity") in ("critical", "warning"):
            conditional.append(loop_strat)
        else:
            confirmed.append(loop_strat)

    all_strategy_count = len(loop_strategy_set)

    baseline = summary.get("baseline_liability", 0)
    optimized = summary.get("optimized_liability", 0)
    total_savings = summary.get("total_savings", 0)
    iterations = summary.get("iterations_completed", 0)
    mode = summary.get("optimization_mode", "retroactive")
    filing = summary.get("filing_status", "N/A").replace("_", " ").title()
    tax_year = summary.get("tax_year", 2025)

    # Savings percentage
    savings_pct = round((total_savings / baseline * 100), 1) if baseline > 0 else 0

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenLoopholes.com — Tax Strategy Report</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --surface: #f7fafd;
    --surface-low: #f1f4f7;
    --surface-lowest: #ffffff;
    --surface-high: #e5e8eb;
    --on-surface: #181c1e;
    --on-surface-variant: #424656;
    --primary: #004bca;
    --primary-container: #0061ff;
    --secondary: #006e2f;
    --secondary-container: #6bff8f;
    --outline-variant: rgba(194, 198, 217, 0.15);
    --success: #006e2f;
    --success-light: #e8f5e9;
    --warning: #92400e;
    --warning-light: #fffbeb;
    --warning-border: #fbbf24;
    --error: #991b1b;
    --error-light: #fef2f2;
    --info: #1d4ed8;
    --info-light: #eff6ff;
    --radius-lg: 1rem;
    --radius-xl: 1.5rem;
  }}

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-weight: 500;
    color: var(--on-surface);
    background: var(--surface);
    max-width: 860px;
    margin: 0 auto;
    padding: 3rem 2rem;
    line-height: 1.7;
    -webkit-font-smoothing: antialiased;
  }}

  /* Typography */
  h1 {{
    font-size: 2rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: var(--on-surface);
    margin-bottom: 0.25rem;
  }}
  h2 {{
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--on-surface);
    margin: 3rem 0 1.25rem;
    letter-spacing: -0.01em;
  }}
  h3 {{
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--on-surface);
    margin: 1.25rem 0 0.5rem;
  }}
  .subtitle {{
    color: var(--on-surface-variant);
    font-size: 0.9rem;
    font-weight: 500;
    margin-bottom: 2.5rem;
  }}

  /* Summary Hero */
  .summary-hero {{
    background: linear-gradient(135deg, var(--primary), var(--primary-container));
    border-radius: var(--radius-xl);
    padding: 2.5rem 2rem;
    margin: 2rem 0 3rem;
    color: white;
  }}
  .summary-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 1.5rem;
    text-align: center;
  }}
  .summary-value {{
    font-size: 2rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    font-variant-numeric: tabular-nums;
  }}
  .summary-label {{
    font-size: 0.8rem;
    font-weight: 500;
    opacity: 0.8;
    margin-top: 0.25rem;
  }}
  .summary-meta {{
    text-align: center;
    margin-top: 1.5rem;
    font-size: 0.85rem;
    opacity: 0.7;
  }}
  .savings-highlight {{
    color: var(--secondary-container);
  }}

  /* Strategies — continuous flow, separated by subtle rules */
  .strategy-item {{
    padding: 1.25rem 0;
    border-bottom: 1px solid var(--surface-high);
  }}
  .strategy-item:last-child {{
    border-bottom: none;
  }}
  .strategy-header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 0.5rem;
    gap: 1rem;
  }}
  .strategy-name {{
    font-weight: 700;
    font-size: 1.05rem;
    letter-spacing: -0.01em;
  }}
  .strategy-savings {{
    font-weight: 700;
    color: var(--success);
    font-size: 1.15rem;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }}

  /* Badges */
  .badge {{
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 0.5rem;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    text-transform: uppercase;
  }}
  .badge-confirmed {{ background: var(--success-light); color: var(--success); }}
  .badge-moderate {{ background: #fef9c3; color: var(--warning); }}
  .badge-aggressive {{ background: var(--error-light); color: var(--error); }}
  .badge-conditional {{ background: #fef3c7; color: var(--warning); }}

  /* Condition note */
  .condition-banner {{
    padding: 0.35rem 0;
    margin: 0.5rem 0;
    font-size: 0.88rem;
    color: var(--warning);
    font-weight: 500;
    font-style: italic;
  }}

  /* Action steps */
  .action-steps {{
    margin: 0.75rem 0;
    padding-left: 1.5rem;
  }}
  .action-steps li {{
    margin: 0.5rem 0;
    font-size: 0.92rem;
    color: var(--on-surface);
  }}

  /* Meta info */
  .meta {{
    font-size: 0.82rem;
    color: var(--on-surface-variant);
    margin-top: 0.75rem;
    font-weight: 500;
  }}
  .meta span {{
    margin-right: 1.5rem;
  }}
  .meta strong {{
    color: var(--on-surface);
  }}

  /* Issues — inline, no boxes */
  .issue {{
    padding: 0.4rem 0;
    margin: 0.25rem 0;
    font-size: 0.88rem;
    font-weight: 500;
    color: var(--on-surface);
  }}
  .issue strong {{ font-weight: 700; }}
  .issue em {{ font-weight: 400; font-style: normal; opacity: 0.75; display: block; margin-top: 0.15rem; padding-left: 1rem; }}
  .severity-label {{
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-right: 0.4rem;
  }}
  .issue-critical .severity-label {{ color: #dc2626; }}
  .issue-warning .severity-label {{ color: #d97706; }}
  .issue-info .severity-label {{ color: #2563eb; }}

  /* Tables — alternating row backgrounds, no dividers */
  .data-table {{
    width: 100%;
    border-collapse: collapse;
    margin: 1rem 0;
    border-radius: var(--radius-lg);
    overflow: hidden;
  }}
  .data-table th {{
    text-align: left;
    padding: 0.75rem 1rem;
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--on-surface-variant);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    background: var(--surface-low);
  }}
  .data-table td {{
    padding: 0.65rem 1rem;
    font-size: 0.9rem;
    font-variant-numeric: tabular-nums;
  }}
  .data-table tr:nth-child(even) td {{ background: var(--surface-low); }}
  .data-table tr:nth-child(odd) td {{ background: var(--surface-lowest); }}

  /* Professional help note */
  .pro-tag {{
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--info);
    margin-top: 0.35rem;
  }}

  /* Section description */
  .section-desc {{
    color: var(--on-surface-variant);
    font-size: 0.9rem;
    margin-bottom: 1.25rem;
  }}

  /* Disclaimer */
  .disclaimer {{
    font-size: 0.78rem;
    color: var(--on-surface-variant);
    margin-top: 4rem;
    padding-top: 1.5rem;
    opacity: 0.6;
    line-height: 1.6;
  }}

  /* Print */
  @media print {{
    body {{ padding: 0.5rem; background: white; font-size: 0.9rem; }}
    .summary-hero {{
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
      padding: 1.5rem;
    }}
    .strategy-item {{ break-inside: avoid; }}
    h2 {{ margin-top: 1.5rem; }}
    .badge {{ border: 1px solid currentColor; background: white !important; }}
  }}

  /* Responsive */
  @media (max-width: 640px) {{
    body {{ padding: 1.5rem 1rem; }}
    .summary-grid {{ grid-template-columns: 1fr; gap: 1rem; }}
    .summary-value {{ font-size: 1.5rem; }}
    .strategy-header {{ flex-direction: column; gap: 0.25rem; }}
  }}
</style>
</head>
<body>

<h1>Tax Strategy Report</h1>
<p class="subtitle">{filing} &middot; Tax Year {tax_year} &middot; {mode.title()} Analysis &middot; Generated by OpenLoopholes.com</p>

<div class="summary-hero">
  <div class="summary-grid">
    <div>
      <div class="summary-value">${baseline:,}</div>
      <div class="summary-label">Current Liability</div>
    </div>
    <div>
      <div class="summary-value savings-highlight">${optimized:,}</div>
      <div class="summary-label">Optimized Liability</div>
    </div>
    <div>
      <div class="summary-value savings-highlight">${total_savings:,}</div>
      <div class="summary-label">Estimated Savings ({savings_pct}%)</div>
    </div>
  </div>
  <p class="summary-meta">
    {iterations} experiments &middot; {all_strategy_count} strategies ({len(confirmed)} confirmed, {len(conditional)} conditional)
  </p>
</div>
"""

    # Helper to render a strategy card
    # Strategy metadata loaded from registry (JSON files in strategies/)
    def get_fallback(sid):
        """Get strategy metadata from the registry as fallback for validation data."""
        s = get_strategy(sid)
        if not s:
            return {}
        return {
            "name": s.get("name", ""),
            "description": s.get("description", ""),
            "irc": s.get("irc_reference", ""),
            "deadline": s.get("deadline", ""),
        }

    # Legacy fallbacks kept as backup — registry is primary source now
    _LEGACY_FALLBACKS = {
        "RET_401K_MAX": {"name": "Maximize 401(k) Contributions", "description": "Increase employee 401(k) deferrals to the annual limit, reducing taxable income at your marginal rate.", "irc": "IRC \u00a7401(k)", "deadline": "Dec 31 of tax year (payroll)"},
        "RET_TRAD_IRA": {"name": "Traditional IRA Contribution", "description": "Contribute to a Traditional IRA for an above-the-line deduction. Deductibility depends on MAGI and workplace plan coverage.", "irc": "IRC \u00a7219", "deadline": "April 15 following tax year"},
        "RET_HSA": {"name": "HSA Contribution", "description": "Contribute to a Health Savings Account for an above-the-line deduction. Requires enrollment in a High Deductible Health Plan.", "irc": "IRC \u00a7223; Form 8889", "deadline": "April 15 following tax year"},
        "RET_SOLO_401K": {"name": "Solo 401(k) Contribution", "description": "Contribute to a Solo 401(k) as both employee (deferral) and employer (profit-sharing). Requires self-employment income from the sponsoring entity.", "irc": "IRC \u00a7401(k); Form 5500-EZ", "deadline": "Employee: Dec 31. Employer: filing deadline with extension."},
        "RET_SEP_IRA": {"name": "SEP IRA Contribution", "description": "Employer contribution of up to 25% of net self-employment income. Simple to set up, no employee deferrals.", "irc": "IRC \u00a7408(k)", "deadline": "Filing deadline with extension"},
        "RET_DB_PLAN": {"name": "Defined Benefit Plan", "description": "Establish a defined benefit pension plan for large, tax-deductible contributions. Contribution limits based on actuarial calculations. Requires professional setup.", "irc": "IRC \u00a7412; Form 5500", "deadline": "Plan established by Dec 31, contributions by filing deadline"},
        "SE_HEALTH_INS": {"name": "Self-Employed Health Insurance Deduction", "description": "Deduct health, dental, and vision insurance premiums for yourself, your spouse, and dependents as an above-the-line deduction. Available to self-employed, partners, and >2% S-Corp shareholders.", "irc": "IRC \u00a7162(l)", "deadline": "Premiums paid during tax year"},
        "SE_SCORP_ELECTION": {"name": "S-Corp Election", "description": "Elect S-Corp status for a sole proprietorship to split income into salary (subject to payroll tax) and distributions (not subject to SE tax).", "irc": "IRC \u00a71362; Form 2553", "deadline": "March 15 of election year"},
        "SE_SALARY_OPT": {"name": "S-Corp Salary Optimization", "description": "Optimize the split between officer compensation (W-2 salary) and pass-through distributions to minimize combined income and SE tax.", "irc": "IRC \u00a71366", "deadline": "Year-end payroll adjustment"},
        "UT_PTET": {"name": "Utah Pass-Through Entity Tax (PTET)", "description": "Elect to pay Utah state income tax at the entity level, converting it from a SALT-capped itemized deduction to an uncapped business deduction on the federal return.", "irc": "Notice 2020-75; Utah Code \u00a759-10-1033.1", "deadline": "Election during tax year"},
        "UT_529": {"name": "Utah my529 Education Savings Credit", "description": "Contribute to Utah's my529 plan for a 4.55% state tax credit on contributions, up to $4,580 for MFJ filers.", "irc": "Utah Code \u00a759-10-1017", "deadline": "Dec 31 of tax year"},
        "TIME_TLH": {"name": "Tax Loss Harvesting", "description": "Realize investment losses to offset capital gains. Net losses can offset up to $3,000 of ordinary income per year, with unlimited carryforward.", "irc": "IRC \u00a71091 (wash sale rule)", "deadline": "Losses realized by Dec 31"},
        "TIME_OZ": {"name": "Opportunity Zone Investment", "description": "Invest capital gains into a Qualified Opportunity Zone fund within 180 days of the gain event to defer recognition. After 10+ years, appreciation is tax-free.", "irc": "IRC \u00a71400Z-2", "deadline": "180 days from gain event"},
        "DED_CHARITABLE": {"name": "Charitable Giving Strategy", "description": "Optimize charitable deductions through bunching, donor-advised funds, qualified charitable distributions (age 70\u00bd+), or donations of appreciated stock to avoid capital gains.", "irc": "IRC \u00a7170; Schedule A", "deadline": "Dec 31 of tax year"},
        "BIZ_AUGUSTA": {"name": "Augusta Rule (Home Rental)", "description": "Rent your personal home to your business for up to 14 days per year at fair market value. Rental income is tax-free to you; rental expense is deductible by the business.", "irc": "IRC \u00a7280A(g)", "deadline": "Rental days during tax year"},
        "BIZ_FAMILY_EMPLOY": {"name": "Hire Family Members", "description": "Employ your children (under 18) in legitimate business roles. Wages are deductible to the business and sheltered by the child's standard deduction. No FICA if sole proprietorship.", "irc": "IRC \u00a73121(b)(3)(A)", "deadline": "Work performed during tax year"},
        "CG_DAF": {"name": "Donor Advised Fund", "description": "Contribute appreciated assets to a DAF to receive an immediate charitable deduction at fair market value while avoiding capital gains tax on the appreciation.", "irc": "IRC \u00a7170; \u00a74966", "deadline": "Dec 31 of tax year"},
        "CG_CRT": {"name": "Charitable Remainder Trust", "description": "Transfer appreciated assets to an irrevocable CRT before sale. Avoids immediate capital gains, provides income stream, and generates a charitable deduction for the remainder interest.", "irc": "IRC \u00a7664", "deadline": "Must be established before asset sale"},
        "CG_QSBS_1202": {"name": "Section 1202 QSBS Exclusion", "description": "Exclude up to $10M (or 10x basis) of gain from the sale of Qualified Small Business Stock held 5+ years. Only applies to C-Corporation stock.", "irc": "IRC \u00a71202", "deadline": "Stock must qualify at time of sale"},
        "CG_PRIMARY_RESIDENCE": {"name": "Primary Residence Sale Exclusion", "description": "Exclude up to $250K (single) or $500K (MFJ) of gain from the sale of your primary residence. Must have owned and lived in the home for 2 of the last 5 years.", "irc": "IRC \u00a7121", "deadline": "Sale during tax year"},
        "CG_INSTALLMENT_NOTE": {"name": "Structured Installment Note", "description": "Spread gain recognition over multiple years using a structured installment note or private annuity trust.", "irc": "IRC \u00a7453", "deadline": "Structured at time of sale"},
        "CRD_CHILD": {"name": "Child Tax Credit", "description": "Credit of $2,200 per qualifying child under 17. Partially refundable.", "irc": "IRC \u00a724", "deadline": "Child under 17 at year-end"},
        "CRD_CHILDCARE": {"name": "Child & Dependent Care Credit", "description": "Credit for care expenses enabling you to work. 20-35% of up to $3K (one) or $6K (two+).", "irc": "IRC \u00a721; Form 2441", "deadline": "Expenses during tax year"},
        "CRD_AOTC": {"name": "American Opportunity Tax Credit", "description": "Up to $2,500 per student for first 4 years of college. 40% refundable.", "irc": "IRC \u00a725A(b); Form 8863", "deadline": "Tuition during tax year"},
        "CRD_LLC": {"name": "Lifetime Learning Credit", "description": "20% of up to $10,000 education expenses ($2,000 max). Any post-secondary.", "irc": "IRC \u00a725A(c); Form 8863", "deadline": "Tuition during tax year"},
        "CRD_SAVERS": {"name": "Saver's Credit", "description": "10-50% credit on up to $2,000 of retirement contributions for low-to-moderate income.", "irc": "IRC \u00a725B; Form 8880", "deadline": "Contributions during tax year"},
        "CRD_SOLAR": {"name": "Residential Clean Energy Credit", "description": "30% credit on solar panels, water heaters, battery storage. No maximum.", "irc": "IRC \u00a725D", "deadline": "Installed by Dec 31, 2025"},
        "CRD_EV": {"name": "Clean Vehicle Credit", "description": "Up to $7,500 for qualifying new EVs. Price and income limits apply.", "irc": "IRC \u00a730D", "deadline": "Purchase by Sept 30, 2025"},
        "CRD_ENERGY_HOME": {"name": "Energy Efficient Home Improvement Credit", "description": "30% on insulation, windows, doors, heat pumps. $3,200 annual limit.", "irc": "IRC \u00a725C", "deadline": "Installed by Dec 31, 2025"},
        "CRD_EITC": {"name": "Earned Income Tax Credit", "description": "Refundable credit for low-to-moderate income workers. Varies by income and children.", "irc": "IRC \u00a732", "deadline": "Based on tax year earnings"},
        "DED_QCD": {"name": "Qualified Charitable Distribution", "description": "Distribute up to $105,000 from your IRA directly to qualified charities. The distribution is excluded from income entirely \u2014 better than a deduction because it reduces AGI. Must be age 70\u00bd or older.", "irc": "IRC \u00a7408(d)(8)", "deadline": "Distributions by Dec 31 of tax year"},
        "DED_MEDICAL": {"name": "Medical Expense Deduction", "description": "Deduct unreimbursed medical expenses exceeding 7.5% of AGI.", "irc": "IRC \u00a7213; Schedule A", "deadline": "Expenses during tax year"},
        "DED_STUDENT_LOAN": {"name": "Student Loan Interest Deduction", "description": "Above-the-line deduction up to $2,500. Phases out at higher incomes.", "irc": "IRC \u00a7221", "deadline": "Interest during tax year"},
        "DED_EDUCATOR": {"name": "Educator Expense Deduction", "description": "Above-the-line deduction up to $300 for K-12 educators.", "irc": "IRC \u00a762(a)(2)(D)", "deadline": "Expenses during school year"},
        "DED_HOME_OFFICE": {"name": "Home Office Deduction", "description": "Self-employed: $5/sq ft up to $1,500 (simplified) or actual expenses.", "irc": "IRC \u00a7280A(c); Form 8829", "deadline": "Space used during tax year"},
        "DED_VEHICLE": {"name": "Business Vehicle Deduction", "description": "Standard mileage ($0.70/mile) or actual expenses. Requires mileage log.", "irc": "IRC \u00a7162; Form 4562", "deadline": "Miles during tax year"},
        "DED_SEC179": {"name": "Section 179 Expense Election", "description": "Immediately expense business property. Up to $2,500,000 for 2025.", "irc": "IRC \u00a7179; Form 4562", "deadline": "Property in service during tax year"},
        "DED_BONUS_DEPR": {"name": "Bonus Depreciation", "description": "100% first-year depreciation for qualifying property acquired after 1/19/2025.", "irc": "IRC \u00a7168(k); Form 4562", "deadline": "Property in service during tax year"},
        "OBBB_TIPS": {"name": "OBBB Tip Income Deduction", "description": "Tipped W-2 employees can deduct tip income. Phases out at $75K/$150K.", "irc": "OBBB Act", "deadline": "Tips during tax year"},
        "OBBB_OVERTIME": {"name": "OBBB Overtime Pay Deduction", "description": "FLSA overtime pay for W-2 employees is deductible. Not for self-employed.", "irc": "OBBB Act", "deadline": "Overtime during tax year"},
        "OBBB_AUTO_INT": {"name": "OBBB Auto Loan Interest Deduction", "description": "Interest on US-manufactured vehicle loans is deductible above the line.", "irc": "OBBB Act", "deadline": "Interest during tax year"},
        "RENT_PAL": {"name": "Passive Activity Loss Allowance", "description": "Claim up to $25K of rental losses if actively participating. Phases out $100K-$150K AGI.", "irc": "IRC \u00a7469(i)", "deadline": "Tax year activity"},
        "RENT_REPS": {"name": "Real Estate Professional Status", "description": "750+ hours in RE makes rental losses non-passive, fully deductible.", "irc": "IRC \u00a7469(c)(7)", "deadline": "Tax year activity"},
        "RENT_STR": {"name": "Short-Term Rental Exception", "description": "Avg stay \u22647 days + material participation = non-passive losses.", "irc": "IRC \u00a7469", "deadline": "Tax year activity"},
        "RENT_COST_SEG": {"name": "Cost Segregation Study", "description": "Reclassify building components to shorter lives. Large paper losses with bonus depreciation.", "irc": "IRC \u00a7168", "deadline": "Property in service during tax year"},
        "RENT_1031": {"name": "1031 Like-Kind Exchange", "description": "Defer gains by exchanging investment RE. 45-day ID, 180-day close.", "irc": "IRC \u00a71031", "deadline": "Exchange during tax year"},
        "TIME_DEFER": {"name": "Income Deferral", "description": "Cash-basis self-employed can defer income by delaying invoicing.", "irc": "IRC \u00a7451", "deadline": "Year-end planning"},
        "TIME_ACCEL_EXP": {"name": "Expense Acceleration", "description": "Accelerate deductible expenses into current year.", "irc": "IRC \u00a7162", "deadline": "Dec 31 of tax year"},
        "TIME_INSTALLMENT": {"name": "Installment Sale", "description": "Spread gain over payment period. Report proportionally.", "irc": "IRC \u00a7453; Form 6252", "deadline": "Sale structure"},
        "TIME_NIIT": {"name": "NIIT Planning", "description": "Reduce 3.8% NIIT by lowering investment income or MAGI below threshold.", "irc": "IRC \u00a71411", "deadline": "Year-end planning"},
        "TIME_LTCG": {"name": "LTCG Characterization", "description": "Hold assets 1+ year for preferential 0%/15%/20% rates.", "irc": "IRC \u00a71(h)", "deadline": "Hold period before sale"},
        "TIME_HARVEST_GAINS": {"name": "Capital Gain Harvesting", "description": "Realize gains in low-income years to fill 0% LTCG bracket.", "irc": "IRC \u00a71(h)", "deadline": "Dec 31 of tax year"},
        "BIZ_ACCOUNTABLE": {"name": "Accountable Plan Reimbursements", "description": "S-Corp reimburses business expenses tax-free. Requires written plan.", "irc": "IRC \u00a762(c)", "deadline": "Expenses during tax year"},
        "BIZ_HRA": {"name": "Health Reimbursement Arrangement", "description": "Business pays medical expenses via QSEHRA/ICHRA. Tax-free to employees.", "irc": "IRC \u00a79831(d)", "deadline": "Plan during tax year"},
        "BIZ_R_AND_D": {"name": "R&D Tax Credit", "description": "Credit for research expenses: software dev, experimentation. 14% alt simplified credit.", "irc": "IRC \u00a741; Form 6765", "deadline": "Research during tax year"},
        "BIZ_MEALS": {"name": "Business Meals Deduction", "description": "50% deduction for business meals. Requires documentation.", "irc": "IRC \u00a7274(k)", "deadline": "Meals during tax year"},
        "BIZ_RETIREMENT_MATCH": {"name": "Employer 401(k) Match", "description": "S-Corp employer match: deductible to business, part of $70K total limit.", "irc": "IRC \u00a7401(a); \u00a7404(a)", "deadline": "Contributions by filing deadline"},
        "RET_ROTH_401K": {"name": "Roth 401(k) Contributions", "description": "After-tax 401(k) deferrals. No current deduction, tax-free distributions.", "irc": "IRC \u00a7402A", "deadline": "Dec 31 of tax year"},
        "RET_ROTH_IRA": {"name": "Roth IRA Contribution", "description": "Tax-free growth. No current deduction. MAGI limits apply.", "irc": "IRC \u00a7408A", "deadline": "April 15 following tax year"},
        "RET_BACKDOOR_ROTH": {"name": "Backdoor Roth IRA", "description": "Non-deductible IRA + Roth conversion. Bypasses income limits.", "irc": "IRC \u00a7408A; Form 8606", "deadline": "April 15 following tax year"},
        "RET_MEGA_BACKDOOR": {"name": "Mega Backdoor Roth", "description": "After-tax 401(k) + Roth conversion. Up to $70K total limit.", "irc": "IRC \u00a7402(c)", "deadline": "Dec 31 of tax year"},
        "RET_ROTH_CONVERSION": {"name": "Roth Conversion", "description": "Convert pre-tax to Roth. Taxable now, tax-free later.", "irc": "IRC \u00a7408A(d)(3); Form 8606", "deadline": "Dec 31 of tax year"},
        "RET_SIMPLE_IRA": {"name": "SIMPLE IRA", "description": "Up to $16,500 deferral + employer match. Small businesses \u2264100 employees.", "irc": "IRC \u00a7408(p)", "deadline": "Dec 31 (employee)"},
        "RET_SPOUSAL_IRA": {"name": "Spousal IRA", "description": "IRA for non-working spouse using working spouse's earned income.", "irc": "IRC \u00a7219(c)", "deadline": "April 15 following tax year"},
        "SE_QBI": {"name": "QBI Deduction Optimization", "description": "Optimize 20% QBI deduction considering W-2 wages, SSTB phase-outs.", "irc": "IRC \u00a7199A", "deadline": "Computed on return"},
        "ENT_PTET": {"name": "Pass-Through Entity Tax Election", "description": "Pay state tax at entity level to bypass federal SALT cap.", "irc": "Notice 2020-75", "deadline": "Election during tax year"},
        "ENT_HEALTH_INS": {"name": "S-Corp Health Insurance", "description": "S-Corp pays premiums for >2% shareholders. Deductible above the line.", "irc": "IRC \u00a7162(l); Notice 2008-1", "deadline": "Premiums during tax year"},
        "ENT_C_CORP": {"name": "C-Corp Election/Retention", "description": "21% flat rate on retained earnings. Rate arbitrage at high income.", "irc": "IRC \u00a711", "deadline": "Election timing varies"},
        "SE_SCORP_ELECTION": {"name": "S-Corp Election", "description": "Elect S-Corp status to split income between salary (FICA) and distributions (no SE tax).", "irc": "IRC \u00a71362; Form 2553", "deadline": "March 15 of election year"},
    }

    def render_strategy(loop_strat, counter, is_conditional=False):
        sid = loop_strat.get("id", "")
        entity = loop_strat.get("entity", "")
        params = loop_strat.get("parameters", {})

        v = validated_by_id.get(sid, {})
        issue = issues_by_id.get(sid, {})
        fallback = get_fallback(sid)

        display_name = v.get("name") or fallback.get("name") or sid.replace("_", " ").title()
        if entity and entity not in display_name:
            display_name += f" ({entity})"

        description = v.get("description") or fallback.get("description", "")
        action_steps = v.get("action_steps", [])
        deadline = v.get("deadline") or fallback.get("deadline", "")
        irc_ref = v.get("irc_reference") or fallback.get("irc", "")
        savings = marginal_savings.get(f"{sid}:{entity or ''}", 0)
        confidence = v.get("confidence", "moderate")
        pro_needed = v.get("professional_help_needed", False)
        pro_type = v.get("professional_type", "CPA")
        docs = v.get("documentation_required", [])

        params_str = ", ".join(
            f"{k}: ${v_:,}" if isinstance(v_, int) else f"{k}: {v_}"
            for k, v_ in params.items()
        )

        card_html = '<div class="strategy-item">\n'
        card_html += '  <div class="strategy-header">\n'
        card_html += f'    <span class="strategy-name">#{counter}. {display_name}</span>\n'
        if savings:
            card_html += f'    <span class="strategy-savings">~${savings:,}</span>\n'
        card_html += '  </div>\n'

        if is_conditional:
            condition = issue.get("resolution", issue.get("description", ""))
            card_html += f'  <span class="badge badge-conditional">Conditional</span>\n'
            card_html += f'  <div class="condition-banner">{condition}</div>\n'
        else:
            badge_map = {"well_established": "badge-confirmed", "moderate": "badge-moderate", "aggressive": "badge-aggressive"}
            badge_class = badge_map.get(confidence, "badge-moderate")
            badge_label = confidence.replace("_", " ").title()
            card_html += f'  <span class="badge {badge_class}">{badge_label}</span>\n'

        if description:
            card_html += f'  <p style="margin: 0.75rem 0; font-size: 0.92rem;">{description}</p>\n'

        if action_steps:
            card_html += '  <h3>Action Steps</h3>\n  <ol class="action-steps">\n'
            for step in action_steps:
                card_html += f'    <li>{step}</li>\n'
            card_html += '  </ol>\n'

        if params_str:
            card_html += f'  <div class="meta">Parameters: {params_str}</div>\n'

        meta_parts = []
        if deadline:
            meta_parts.append(f'Deadline: <strong>{deadline}</strong>')
        if irc_ref:
            meta_parts.append(f'IRC: {irc_ref}')
        if meta_parts:
            card_html += '  <div class="meta">' + " &nbsp;&middot;&nbsp; ".join(meta_parts) + '</div>\n'

        if pro_needed:
            card_html += f'  <div class="pro-tag">Requires {pro_type}</div>\n'

        if docs:
            card_html += f'  <div class="meta">Documentation: {", ".join(docs)}</div>\n'

        card_html += '</div>\n'
        return card_html

    # Confirmed Strategies
    if confirmed:
        html += '<h2>Confirmed Strategies</h2>\n'
        counter = 1
        for loop_strat in confirmed:
            html += render_strategy(loop_strat, counter, is_conditional=False)
            counter += 1
    else:
        counter = 1

    # Conditional Strategies
    if conditional:
        html += '<h2>Conditional Strategies</h2>\n'
        html += '<p class="section-desc">These strategies were confirmed by the calculator to reduce your liability, but require eligibility changes or additional action to implement.</p>\n'
        for loop_strat in conditional:
            html += render_strategy(loop_strat, counter, is_conditional=True)
            counter += 1

    # Tax Calendar
    if tax_calendar:
        html += '<h2>Tax Calendar</h2>\n'
        html += '<table class="data-table">\n  <tr><th>Date</th><th>Action</th><th>Strategy</th></tr>\n'
        for item in sorted(tax_calendar, key=lambda x: x.get("date", "")):
            html += f'  <tr><td>{item.get("date", "")}</td><td>{item.get("action", "")}</td><td>{item.get("strategy_id", "")}</td></tr>\n'
        html += '</table>\n'

    # Next Steps
    if next_steps:
        html += f'<h2>Next Steps</h2>\n<p style="font-size: 0.92rem;">{next_steps}</p>\n'

    # Savings by category — removed because this data comes from the LLM's estimates,
    # not the deterministic calculator. The LLM inflates category breakdowns.
    # TODO: compute deterministically by running calculator with each strategy removed.

    # Validation Notes
    if issues:
        html += '<h2>Validation Notes</h2>\n'
        for issue in issues:
            severity = issue.get("severity", "info")
            css_class = f"issue-{severity}"
            resolution = issue.get("resolution", "")
            html += f"""<div class="issue {css_class}">
  <span class="severity-label">{severity}</span><strong>{issue.get('strategy_id', 'N/A')}</strong> &mdash; {issue.get('description', '')}
  {f'<br><em>{resolution}</em>' if resolution else ''}
</div>
"""

    # Disclaimer
    html += f'<div class="disclaimer">{disclaimer}</div>\n'
    html += '</body>\n</html>'

    output_path = results_dir / "tax_strategy_report.html"
    with open(output_path, "w") as f:
        f.write(html)
    print(f"Report saved: {output_path}")
    print("Open in browser and Print > Save as PDF to create a CPA-ready document.")


if __name__ == "__main__":
    generate_report()
