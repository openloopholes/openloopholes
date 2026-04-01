"""
OpenLoopholes.com — Deterministic Tax Calculator (2025)
Multi-Entity Version

The immutable eval harness. Given a taxpayer profile (with multiple business
entities) and a strategy set with specific parameters, computes total federal
+ state tax liability.

The LLM proposes strategies; this calculator scores them.
The LLM never estimates liability.

Tax Year 2025 — reflects One Big Beautiful Bill Act (signed July 4, 2025)
"""

from __future__ import annotations


# =============================================================================
# 2025 TAX CONSTANTS
# =============================================================================

BRACKETS = {
    "married_joint": [
        (23_850, 0.10), (96_950, 0.12), (206_700, 0.22), (394_600, 0.24),
        (501_050, 0.32), (751_600, 0.35), (float("inf"), 0.37),
    ],
    "single": [
        (11_925, 0.10), (48_475, 0.12), (103_350, 0.22), (197_300, 0.24),
        (250_525, 0.32), (626_350, 0.35), (float("inf"), 0.37),
    ],
    "head_of_household": [
        (17_000, 0.10), (64_850, 0.12), (103_350, 0.22), (197_300, 0.24),
        (250_500, 0.32), (626_350, 0.35), (float("inf"), 0.37),
    ],
    "married_separate": [
        (11_925, 0.10), (48_475, 0.12), (103_350, 0.22), (197_300, 0.24),
        (250_525, 0.32), (375_800, 0.35), (float("inf"), 0.37),
    ],
}

STANDARD_DEDUCTION = {
    "single": 15_750, "married_joint": 31_500, "married_separate": 15_750,
    "head_of_household": 23_625, "qualifying_surviving_spouse": 31_500,
}

LTCG_BRACKETS = {
    "married_joint": [(96_700, 0.0), (600_050, 0.15), (float("inf"), 0.20)],
    "single": [(48_350, 0.0), (533_400, 0.15), (float("inf"), 0.20)],
    "head_of_household": [(64_750, 0.0), (566_700, 0.15), (float("inf"), 0.20)],
    "married_separate": [(48_350, 0.0), (300_000, 0.15), (float("inf"), 0.20)],
}

SS_WAGE_BASE = 176_100
SS_RATE = 0.124
MEDICARE_RATE = 0.029
ADDITIONAL_MEDICARE_RATE = 0.009
ADDITIONAL_MEDICARE_THRESHOLD = {
    "married_joint": 250_000, "single": 200_000,
    "head_of_household": 200_000, "married_separate": 125_000,
}

SE_INCOME_FACTOR = 0.9235
SE_TAX_DEDUCTION_FACTOR = 0.5

NIIT_RATE = 0.038
NIIT_THRESHOLD = {
    "married_joint": 250_000, "single": 200_000,
    "head_of_household": 200_000, "married_separate": 125_000,
}

SALT_CAP_BASE = {"married_joint": 40_000, "single": 40_000,
                  "head_of_household": 40_000, "married_separate": 20_000}
SALT_PHASEDOWN_START = {"married_joint": 500_000, "single": 250_000,
                         "head_of_household": 375_000, "married_separate": 250_000}
SALT_PHASEDOWN_RATE = 0.30
SALT_FLOOR = 10_000

QBI_RATE = 0.20
QBI_SSTB_PHASEOUT = {
    "married_joint": (394_600, 444_600), "single": (197_300, 247_300),
    "head_of_household": (197_300, 247_300), "married_separate": (197_300, 247_300),
}

CTC_PER_CHILD = 2_200
CTC_PHASEOUT_START = {"married_joint": 400_000, "single": 200_000,
                       "head_of_household": 200_000, "married_separate": 200_000}
CTC_PHASEOUT_RATE = 50

LIMIT_401K = 23_500
LIMIT_401K_CATCHUP_50 = 7_500
LIMIT_401K_CATCHUP_60_63 = 11_250
LIMIT_IRA = 7_000
LIMIT_IRA_CATCHUP_50 = 1_000
LIMIT_SEP_IRA_RATE = 0.25
LIMIT_SEP_IRA_MAX = 70_000
LIMIT_SOLO_401K_TOTAL = 70_000
LIMIT_HSA_SELF = 4_300
LIMIT_HSA_FAMILY = 8_550
LIMIT_HSA_CATCHUP_55 = 1_000

HOME_OFFICE_SIMPLIFIED_RATE = 5
HOME_OFFICE_SIMPLIFIED_MAX_SQFT = 300
STANDARD_MILEAGE_RATE = 0.70

UTAH_RATE = 0.0455

# Child & Dependent Care Credit (§21)
CHILDCARE_MAX_EXPENSES = {"one": 3_000, "two_or_more": 6_000}
CHILDCARE_CREDIT_RATE_MAX = 0.35
CHILDCARE_CREDIT_RATE_MIN = 0.20
CHILDCARE_AGI_FLOOR = 15_000
CHILDCARE_AGI_STEP = 2_000

# American Opportunity Credit (§25A)
AOTC_MAX = 2_500
AOTC_PHASEOUT = {"single": (80_000, 90_000), "married_joint": (160_000, 180_000),
                  "head_of_household": (80_000, 90_000), "married_separate": (80_000, 90_000)}

# Lifetime Learning Credit (§25A)
LLC_MAX = 2_000
LLC_PHASEOUT = {"single": (80_000, 90_000), "married_joint": (160_000, 180_000),
                "head_of_household": (80_000, 90_000), "married_separate": (80_000, 90_000)}

# Saver's Credit (§25B)
SAVERS_CREDIT_LIMITS = {
    "married_joint": [(47_500, 0.50), (51_000, 0.20), (79_000, 0.10)],
    "head_of_household": [(35_625, 0.50), (38_250, 0.20), (59_250, 0.10)],
    "single": [(23_750, 0.50), (25_500, 0.20), (39_500, 0.10)],
    "married_separate": [(23_750, 0.50), (25_500, 0.20), (39_500, 0.10)],
}
SAVERS_MAX_CONTRIBUTION = 2_000

# Clean Energy Credits
SOLAR_CREDIT_RATE = 0.30  # 30% of cost (§25D)
EV_CREDIT_MAX = 7_500     # §30D, expires 9/30/2025
ENERGY_HOME_MAX = 3_200    # §25C annual limit

# EITC (§32) — 2025 estimates
EITC_MAX = {"0": 649, "1": 4_328, "2": 7_152, "3": 8_046}
EITC_INVESTMENT_INCOME_LIMIT = 11_950
EITC_PHASEOUT = {
    "married_joint": {"0": (8_490, 17_250, 649), "1": (12_730, 28_120, 4_328),
                      "2": (17_880, 28_120, 7_152), "3": (17_880, 28_120, 8_046)},
    "single": {"0": (8_490, 10_620, 649), "1": (12_730, 21_490, 4_328),
               "2": (17_880, 21_490, 7_152), "3": (17_880, 21_490, 8_046)},
}

# OBBB Provisions
OBBB_TIPS_PHASEOUT = {"single": 75_000, "married_joint": 150_000,
                       "head_of_household": 112_500, "married_separate": 75_000}
OBBB_OVERTIME_PHASEOUT = {"single": 75_000, "married_joint": 150_000,
                           "head_of_household": 112_500, "married_separate": 75_000}

# Passive Activity Loss
PAL_ALLOWANCE = 25_000
PAL_PHASEOUT_START = 100_000
PAL_PHASEOUT_END = 150_000

# SIMPLE IRA
LIMIT_SIMPLE_IRA = 16_500
LIMIT_SIMPLE_IRA_CATCHUP_50 = 3_500
LIMIT_SIMPLE_IRA_CATCHUP_60_63 = 5_250

# Student Loan Interest
STUDENT_LOAN_MAX = 2_500
STUDENT_LOAN_PHASEOUT = {"single": (80_000, 95_000), "married_joint": (165_000, 195_000),
                          "head_of_household": (80_000, 95_000), "married_separate": (0, 0)}

# Educator Expenses
EDUCATOR_MAX = 300

# R&D Credit (§41) — simplified calculation
RD_CREDIT_RATE = 0.20  # Regular credit rate on QREs above base
RD_CREDIT_RATE_ALT = 0.14  # Alternative simplified credit

# Primary Residence Exclusion (§121)
HOME_SALE_EXCLUSION = {"single": 250_000, "married_joint": 500_000,
                        "head_of_household": 250_000, "married_separate": 250_000}

# Business Meals
MEALS_DEDUCTION_RATE = 0.50

# Qualified Charitable Distribution (§408(d)(8))
QCD_MAX = 105_000  # Per person, age 70½+
QCD_MIN_AGE = 70


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def compute_bracket_tax(taxable_income: float, filing_status: str) -> float:
    brackets = BRACKETS.get(filing_status, BRACKETS["single"])
    tax = 0.0
    prev = 0
    for threshold, rate in brackets:
        if taxable_income <= 0:
            break
        amount = min(taxable_income, threshold) - prev
        if amount > 0:
            tax += amount * rate
        prev = threshold
        if taxable_income <= threshold:
            break
    return tax


def compute_ltcg_tax(ltcg: float, taxable_income: float, filing_status: str) -> float:
    if ltcg <= 0:
        return 0.0
    brackets = LTCG_BRACKETS.get(filing_status, LTCG_BRACKETS["single"])
    ordinary = taxable_income - ltcg
    tax = 0.0
    prev = 0
    remaining = ltcg
    for threshold, rate in brackets:
        filled = max(0, min(ordinary, threshold) - prev)
        available = (threshold - prev) - filled
        taxable_here = min(remaining, available)
        if taxable_here > 0:
            tax += taxable_here * rate
            remaining -= taxable_here
        prev = threshold
        if remaining <= 0:
            break
    return tax


def compute_se_tax(net_se_income: float, w2_wages: float = 0) -> dict:
    se_earnings = net_se_income * SE_INCOME_FACTOR
    if se_earnings <= 0:
        return {"se_tax": 0, "se_tax_deduction": 0, "ss_portion": 0,
                "medicare_portion": 0, "se_earnings": 0}
    ss_remaining = max(0, SS_WAGE_BASE - w2_wages)
    ss_tax = min(se_earnings, ss_remaining) * SS_RATE
    medicare_tax = se_earnings * MEDICARE_RATE
    se_tax = ss_tax + medicare_tax
    return {"se_tax": se_tax, "se_tax_deduction": se_tax * SE_TAX_DEDUCTION_FACTOR,
            "ss_portion": ss_tax, "medicare_portion": medicare_tax,
            "se_earnings": se_earnings}


def compute_additional_medicare(total_earned: float, filing_status: str) -> float:
    threshold = ADDITIONAL_MEDICARE_THRESHOLD.get(filing_status, 200_000)
    return max(0, total_earned - threshold) * ADDITIONAL_MEDICARE_RATE


def compute_niit(investment_income: float, magi: float, filing_status: str) -> float:
    threshold = NIIT_THRESHOLD.get(filing_status, 200_000)
    return min(investment_income, max(0, magi - threshold)) * NIIT_RATE


def compute_salt_cap(magi: float, filing_status: str) -> float:
    base = SALT_CAP_BASE.get(filing_status, 40_000)
    start = SALT_PHASEDOWN_START.get(filing_status, 500_000)
    if magi <= start:
        return base
    return max(SALT_FLOOR, base - (magi - start) * SALT_PHASEDOWN_RATE)


def compute_qbi_deduction(qbi: float, taxable_before_qbi: float,
                           filing_status: str, is_sstb: bool = False) -> float:
    if qbi <= 0:
        return 0.0
    base = qbi * QBI_RATE
    start, end = QBI_SSTB_PHASEOUT.get(filing_status, (197_300, 247_300))
    if is_sstb:
        if taxable_before_qbi <= start:
            return base
        elif taxable_before_qbi >= end:
            return 0.0
        else:
            return base * (end - taxable_before_qbi) / (end - start)
    return base


def compute_child_tax_credit(num_qualifying: int, agi: float, filing_status: str) -> float:
    if num_qualifying <= 0:
        return 0.0
    base = num_qualifying * CTC_PER_CHILD
    threshold = CTC_PHASEOUT_START.get(filing_status, 200_000)
    if agi <= threshold:
        return base
    return max(0, base - ((agi - threshold) // 1_000) * CTC_PHASEOUT_RATE)


def compute_childcare_credit(expenses: float, num_qualifying: int, agi: float) -> float:
    if num_qualifying <= 0 or expenses <= 0:
        return 0.0
    max_exp = CHILDCARE_MAX_EXPENSES["two_or_more"] if num_qualifying >= 2 else CHILDCARE_MAX_EXPENSES["one"]
    eligible = min(expenses, max_exp)
    # Rate starts at 35% and decreases by 1% per $2K of AGI above $15K, floor 20%
    rate = max(CHILDCARE_CREDIT_RATE_MIN,
               CHILDCARE_CREDIT_RATE_MAX - max(0, (agi - CHILDCARE_AGI_FLOOR)) // CHILDCARE_AGI_STEP * 0.01)
    return eligible * rate


def compute_education_credit_phaseout(credit: float, agi: float, filing_status: str,
                                       phaseout_table: dict) -> float:
    start, end = phaseout_table.get(filing_status, (80_000, 90_000))
    if agi <= start:
        return credit
    if agi >= end:
        return 0.0
    return credit * (end - agi) / (end - start)


def compute_eitc(earned_income: float, investment_income: float, agi: float,
                  filing_status: str, num_qualifying_children: int) -> float:
    if investment_income > EITC_INVESTMENT_INCOME_LIMIT:
        return 0.0
    children_key = str(min(num_qualifying_children, 3))
    fs = filing_status if filing_status in EITC_PHASEOUT else "single"
    if children_key not in EITC_PHASEOUT.get(fs, {}):
        return 0.0
    phase_in_end, phase_out_start, max_credit = EITC_PHASEOUT[fs][children_key]
    # Simplified: if earned income > phaseout start, reduce
    if earned_income > phase_out_start + max_credit / 0.0765:  # rough phaseout
        return 0.0
    if earned_income <= phase_in_end:
        return min(earned_income * (max_credit / phase_in_end), max_credit) if phase_in_end > 0 else 0.0
    if agi <= phase_out_start:
        return max_credit
    # Phase-out
    reduction = (agi - phase_out_start) * 0.0765 if num_qualifying_children == 0 else (agi - phase_out_start) * 0.1598 if num_qualifying_children == 1 else (agi - phase_out_start) * 0.2106
    return max(0, max_credit - reduction)


def compute_savers_credit(contribution: float, agi: float, filing_status: str) -> float:
    tiers = SAVERS_CREDIT_LIMITS.get(filing_status, SAVERS_CREDIT_LIMITS["single"])
    eligible = min(contribution, SAVERS_MAX_CONTRIBUTION)
    for threshold, rate in tiers:
        if agi <= threshold:
            return eligible * rate
    return 0.0


def compute_student_loan_deduction(interest: float, agi: float, filing_status: str) -> float:
    start, end = STUDENT_LOAN_PHASEOUT.get(filing_status, (80_000, 95_000))
    if start == 0 and end == 0:
        return 0.0  # MFS gets nothing
    base = min(interest, STUDENT_LOAN_MAX)
    if agi <= start:
        return base
    if agi >= end:
        return 0.0
    return base * (end - agi) / (end - start)


def get_401k_limit(age: int) -> int:
    if 60 <= age <= 63:
        return LIMIT_401K + LIMIT_401K_CATCHUP_60_63
    elif age >= 50:
        return LIMIT_401K + LIMIT_401K_CATCHUP_50
    return LIMIT_401K


def get_ira_limit(age: int) -> int:
    return LIMIT_IRA + LIMIT_IRA_CATCHUP_50 if age >= 50 else LIMIT_IRA


def get_hsa_limit(age: int, coverage: str = "family") -> int:
    base = LIMIT_HSA_FAMILY if coverage == "family" else LIMIT_HSA_SELF
    return base + LIMIT_HSA_CATCHUP_55 if age >= 55 else base


def find_entity(profile: dict, name: str) -> dict | None:
    for e in profile.get("entities", []):
        if e["name"] == name:
            return e
    return None


def find_entity_by_type(profile: dict, entity_type: str) -> tuple[str, dict] | None:
    """Find the first entity matching a given type. Returns (name, entity) or None."""
    for e in profile.get("entities", []):
        if e["type"] == entity_type:
            return (e["name"], e)
    return None


def resolve_entity(profile: dict, entity_name: str | None, *fallback_types: str) -> tuple[str, dict] | None:
    """Resolve an entity by name, or fall back to first entity matching any of the given types."""
    if entity_name:
        entity = find_entity(profile, entity_name)
        if entity:
            return (entity_name, entity)
    for t in fallback_types:
        result = find_entity_by_type(profile, t)
        if result:
            return result
    return None


# =============================================================================
# STRATEGY APPLICATION (Multi-Entity)
# =============================================================================

def apply_strategies(profile: dict, strategies: list[dict]) -> dict:
    """
    Apply strategy modifications. Entity-specific strategies reference
    an entity by name. Personal strategies apply at the taxpayer level.
    """
    age = profile.get("taxpayer_age", 40)

    adj = {
        "additional_above_the_line": 0,
        "additional_retirement_pretax": 0,
        "additional_charitable": 0,
        "additional_hsa": 0,
        "ptet_amount": 0,
        "utah_529_credit": 0,
        "se_health_ins_additional": 0,
        # Capital gain adjustments
        "ltcg_deferral": 0,        # Amount of LTCG deferred (QOZ, installment)
        "ltcg_offset": 0,          # Amount of LTCG offset (TLH, charitable stock)
        "installment_gain_recognized": 0,  # Gain recognized this year from installment
        # Defined benefit plan
        "db_plan_contribution": 0,
        # Per-entity overrides: entity_name -> modifications
        "entity_overrides": {},
        # Business deductions per entity
        "entity_deductions": {},
        # Credits from strategies
        "additional_credits": {},
        # Income adjustments
        "additional_medical_expenses": 0,
        "additional_student_loan": 0,
        "additional_educator": 0,
        "obbb_tips_deduction": 0,
        "obbb_overtime_deduction": 0,
        "obbb_auto_interest": 0,
        # Rental adjustments
        "rental_pal_override": False,
        "rental_reps_override": False,
        "rental_str_override": False,
        "rental_1031_deferred": 0,
        # Income timing
        "income_deferred": 0,
        "expenses_accelerated": 0,
        # Home sale exclusion
        "home_sale_exclusion": 0,
        # QCD exclusion
        "qcd_exclusion": 0,
        "strategies_applied": [],
    }

    # Load strategy registry for actionability enforcement and generic handlers
    opt_mode = profile.get("optimization_mode", "both")
    try:
        from strategy_registry import get_strategy as _get_strat
    except ImportError:
        _get_strat = None

    for strategy in strategies:
        sid = strategy.get("id", "")
        params = strategy.get("parameters", {})
        entity_name = strategy.get("entity", None)

        # In retroactive mode, block strategies whose deadline has passed
        if opt_mode == "retroactive" and _get_strat:
            reg = _get_strat(sid)
            if reg:
                act = reg.get("actionability", {})
                if act.get("retroactive_status") == "deadline_passed":
                    adj["strategies_applied"].append(sid)
                    continue

        # ----- PERSONAL-LEVEL STRATEGIES -----

        if sid == "RET_401K_MAX":
            current_total = sum(
                w.get("traditional_401k", 0) + w.get("roth_401k", 0)
                for w in profile.get("w2_income", [])
            )
            target = min(params.get("contribution", get_401k_limit(age)), get_401k_limit(age))
            additional = max(0, target - current_total)
            adj["additional_retirement_pretax"] += additional
            adj["additional_above_the_line"] += additional

        elif sid == "RET_HSA":
            current = profile.get("retirement", {}).get("hsa_contributions", 0)
            coverage = profile.get("retirement", {}).get("hdhp_coverage", "family")
            limit = get_hsa_limit(age, coverage)
            target = min(params.get("contribution", limit), limit)
            additional = max(0, target - current)
            adj["additional_hsa"] = additional
            adj["additional_above_the_line"] += additional

        elif sid == "RET_TRAD_IRA":
            current = profile.get("retirement", {}).get("traditional_ira_contributions", 0)
            limit = get_ira_limit(age)
            target = min(params.get("contribution", limit), limit)
            additional = max(0, target - current)
            adj["additional_retirement_pretax"] += additional
            adj["additional_above_the_line"] += additional

        elif sid == "RET_SOLO_401K":
            resolved = resolve_entity(profile, entity_name, "schedule_c")
            entity = resolved[1] if resolved else None
            current_401k = sum(
                w.get("traditional_401k", 0) + w.get("roth_401k", 0)
                for w in profile.get("w2_income", [])
            )
            employee = min(params.get("employee_deferral", 0), max(0, get_401k_limit(age) - current_401k))
            se_net = (entity.get("net_income", 0) or 0) if entity else 0
            max_employer = min(params.get("employer_contribution", 0), int(se_net * LIMIT_SEP_IRA_RATE))
            total = employee + max_employer
            if total > LIMIT_SOLO_401K_TOTAL:
                max_employer = max(0, LIMIT_SOLO_401K_TOTAL - employee)
            adj["additional_retirement_pretax"] += employee + max_employer
            adj["additional_above_the_line"] += employee + max_employer

        elif sid == "RET_SEP_IRA":
            resolved = resolve_entity(profile, entity_name, "schedule_c")
            entity = resolved[1] if resolved else None
            se_net = (entity.get("net_income", 0) or 0) if entity else 0
            max_sep = min(int(se_net * LIMIT_SEP_IRA_RATE), LIMIT_SEP_IRA_MAX)
            contribution = min(params.get("contribution", max_sep), max_sep)
            adj["additional_retirement_pretax"] += contribution
            adj["additional_above_the_line"] += contribution

        elif sid == "DED_CHARITABLE":
            adj["additional_charitable"] += params.get("cash", 0) + params.get("appreciated_stock", 0)

        elif sid == "UT_529":
            contribution = params.get("contribution", 0)
            adj["utah_529_credit"] = min(contribution * UTAH_RATE, 4_580)

        elif sid == "UT_PTET":
            adj["ptet_amount"] = params.get("amount", 0)

        elif sid == "SE_HEALTH_INS":
            adj["se_health_ins_additional"] = params.get("amount", 0)
            adj["additional_above_the_line"] += params.get("amount", 0)

        # ----- ENTITY-SPECIFIC STRATEGIES -----

        elif sid in ("SE_SCORP_ELECTION", "ENT_SCORP"):
            resolved = resolve_entity(profile, entity_name, "schedule_c")
            if resolved:
                ename_r, entity = resolved
                if entity["type"] == "schedule_c":
                    net = entity.get("net_income", 0) or 0
                    salary = params.get("salary", max(40_000, int(net * 0.4)))
                    salary = max(40_000, min(salary, net))
                    adj["entity_overrides"][ename_r] = {
                        "convert_to_scorp": True,
                        "salary": salary,
                        "distributions": net - salary,
                    }

        elif sid == "SE_SALARY_OPT":
            resolved = resolve_entity(profile, entity_name, "s_corp")
            if resolved:
                ename_r, entity = resolved
                if entity["type"] == "s_corp":
                    total = (entity.get("ordinary_income", 0) or 0) + (entity.get("distributions", 0) or 0)
                    salary = params.get("salary", max(40_000, int(total * 0.35)))
                    salary = max(40_000, min(salary, total))
                    adj["entity_overrides"][ename_r] = {
                        "salary_opt": True,
                        "salary": salary,
                        "distributions": total - salary,
                    }

        elif sid == "DED_HOME_OFFICE":
            resolved = resolve_entity(profile, entity_name, "schedule_c")
            if resolved:
                ename_r, _ = resolved
                amount = min(params.get("amount", 1500), HOME_OFFICE_SIMPLIFIED_RATE * HOME_OFFICE_SIMPLIFIED_MAX_SQFT)
                adj["entity_deductions"].setdefault(ename_r, 0)
                adj["entity_deductions"][ename_r] += amount

        elif sid == "DED_VEHICLE":
            resolved = resolve_entity(profile, entity_name, "schedule_c", "s_corp")
            if resolved:
                ename_r, _ = resolved
                miles = params.get("business_miles", 0)
                amount = int(miles * STANDARD_MILEAGE_RATE)
                adj["entity_deductions"].setdefault(ename_r, 0)
                adj["entity_deductions"][ename_r] += amount

        elif sid == "DED_SEC179":
            resolved = resolve_entity(profile, entity_name, "schedule_c", "s_corp")
            if resolved:
                ename_r, _ = resolved
                amount = min(params.get("amount", 0), 2_500_000)
                adj["entity_deductions"].setdefault(ename_r, 0)
                adj["entity_deductions"][ename_r] += amount

        elif sid == "DED_BONUS_DEPR":
            resolved = resolve_entity(profile, entity_name, "schedule_c", "s_corp", "rental")
            if resolved:
                ename_r, _ = resolved
                amount = params.get("amount", 0)
                adj["entity_deductions"].setdefault(ename_r, 0)
                adj["entity_deductions"][ename_r] += amount

        elif sid == "RENT_COST_SEG":
            resolved = resolve_entity(profile, entity_name, "rental")
            if resolved:
                ename_r, _ = resolved
                amount = params.get("depreciation_amount", 0)
                adj["entity_deductions"].setdefault(ename_r, 0)
                adj["entity_deductions"][ename_r] += amount

        # ----- CAPITAL GAIN STRATEGIES -----

        elif sid == "TIME_OZ":
            # Opportunity Zone: invest capital gains into QOZ fund within 180 days
            # Defers gain recognition; after 10+ years, appreciation is tax-free
            # For 2025: no basis step-up on deferred gain (that expired in 2026 rules)
            # but deferral until sale of QOZ investment
            amount = params.get("amount", 0)
            # Can't defer more than total LTCG from business sales
            total_sale_ltcg = sum(s.get("capital_gain", 0) for s in profile.get("business_sales", []))
            amount = min(amount, total_sale_ltcg)
            adj["ltcg_deferral"] += amount

        elif sid == "TIME_INSTALLMENT":
            # Installment sale: spread gain over multiple years
            # Only works if the sale was structured as installment (not all-cash)
            # Recognize only a portion of gain this year
            total_gain = params.get("total_gain", 0)
            years = params.get("years", 5)
            recognized_this_year = total_gain // years if years > 0 else total_gain
            adj["installment_gain_recognized"] = recognized_this_year
            # Defer the rest
            adj["ltcg_deferral"] += total_gain - recognized_this_year

        elif sid == "TIME_TLH":
            # Tax loss harvesting: realize losses to offset gains
            # Limited to actual unrealized losses in portfolio
            amount = params.get("loss_amount", 0)
            adj["ltcg_offset"] += amount

        elif sid == "RET_DB_PLAN":
            # Defined benefit plan: massive above-the-line deduction
            # Self-employed or S-Corp owner, age 50+ preferred but available to younger
            # Contribution limits depend on age and actuarial calculation
            # Rough range: $50K-$300K+ per year depending on age and plan design
            amount = params.get("contribution", 0)
            # Rough max based on age (actuarial limits)
            age_factor = min(age, 65)
            rough_max = int(50_000 + (age_factor - 30) * 5_000) if age > 30 else 50_000
            rough_max = max(50_000, min(rough_max, 300_000))
            amount = min(amount, rough_max)
            adj["db_plan_contribution"] = amount
            adj["additional_above_the_line"] += amount

        # ----- BUSINESS OWNER STRATEGIES -----

        elif sid == "BIZ_AUGUSTA":
            resolved = resolve_entity(profile, entity_name, "schedule_c", "s_corp")
            if resolved:
                ename_r, _ = resolved
                days = min(params.get("days", 14), 14)
                daily_rate = params.get("daily_rate", 2000)
                amount = days * daily_rate
                adj["entity_deductions"].setdefault(ename_r, 0)
                adj["entity_deductions"][ename_r] += amount

        elif sid == "BIZ_FAMILY_EMPLOY":
            resolved = resolve_entity(profile, entity_name, "schedule_c", "s_corp")
            if resolved:
                ename_r, _ = resolved
                num_children = min(params.get("num_children", 0), len(profile.get("dependents", [])))
                wage_per_child = min(params.get("wage_per_child", 0), STANDARD_DEDUCTION.get(profile["filing_status"], 15_750))
                amount = num_children * wage_per_child
                adj["entity_deductions"].setdefault(ename_r, 0)
                adj["entity_deductions"][ename_r] += amount

        elif sid == "BIZ_ACCOUNTABLE":
            resolved = resolve_entity(profile, entity_name, "s_corp")
            if resolved:
                ename_r, _ = resolved
                amount = params.get("amount", 0)
                adj["entity_deductions"].setdefault(ename_r, 0)
                adj["entity_deductions"][ename_r] += amount

        elif sid == "BIZ_HRA":
            resolved = resolve_entity(profile, entity_name, "s_corp", "schedule_c")
            if resolved:
                ename_r, _ = resolved
                amount = params.get("amount", 0)
                adj["entity_deductions"].setdefault(ename_r, 0)
                adj["entity_deductions"][ename_r] += amount

        # ----- ADDITIONAL CAPITAL GAIN STRATEGIES -----

        elif sid == "CG_QSBS_1202":
            # Section 1202: exclude gain from C-Corp stock held 5+ years
            # Only for C-Corps. Max $10M or 10x basis.
            amount = params.get("excluded_gain", 0)
            adj["ltcg_offset"] += amount

        elif sid == "CG_CRT":
            # Charitable Remainder Trust: transfer appreciated assets before sale
            # Avoids immediate LTCG. Receive income stream.
            amount = params.get("amount", 0)
            total_sale_ltcg = sum(s_.get("capital_gain", 0) for s_ in profile.get("business_sales", []))
            amount = min(amount, total_sale_ltcg)
            adj["ltcg_deferral"] += amount
            # Charitable deduction for remainder interest (~10-40% of trust value)
            payout_rate = params.get("payout_rate", 0.05)
            # Rough estimate: remainder = amount * (1 - payout_rate * years_expected)
            # Simplified: ~30% of trust value as charitable deduction
            adj["additional_charitable"] += int(amount * 0.30)

        elif sid == "CG_DAF":
            # Donor Advised Fund with appreciated stock
            cash = params.get("cash", 0)
            stock = params.get("appreciated_stock", 0)
            adj["additional_charitable"] += cash + stock
            # Appreciated stock donated avoids LTCG
            adj["ltcg_offset"] += stock

        elif sid == "CG_INSTALLMENT_NOTE":
            # Structured installment note for completed sales
            total_gain = params.get("total_gain", 0)
            years = params.get("years", 5)
            recognized = total_gain // years if years > 0 else total_gain
            adj["ltcg_deferral"] += total_gain - recognized

        # ----- ADDITIONAL RETIREMENT -----

        elif sid == "RET_SPOUSAL_IRA":
            current = profile.get("retirement", {}).get("traditional_ira_contributions", 0) or 0
            limit = get_ira_limit(profile.get("spouse_age", 40))
            target = min(params.get("contribution", limit), limit)
            additional = max(0, target - current)
            adj["additional_retirement_pretax"] += additional
            adj["additional_above_the_line"] += additional

        elif sid == "RET_SIMPLE_IRA":
            current_401k = sum(
                w.get("traditional_401k", 0) + w.get("roth_401k", 0)
                for w in profile.get("w2_income", [])
            )
            if 60 <= age <= 63:
                limit = LIMIT_SIMPLE_IRA + LIMIT_SIMPLE_IRA_CATCHUP_60_63
            elif age >= 50:
                limit = LIMIT_SIMPLE_IRA + LIMIT_SIMPLE_IRA_CATCHUP_50
            else:
                limit = LIMIT_SIMPLE_IRA
            # SIMPLE IRA shares the deferral limit with 401(k)
            target = min(params.get("contribution", limit), limit)
            additional = max(0, target - current_401k)
            adj["additional_retirement_pretax"] += additional
            adj["additional_above_the_line"] += additional

        elif sid == "RET_MEGA_BACKDOOR":
            # After-tax 401(k) contributions converted to Roth
            # No immediate tax deduction, but allows more in Roth
            # Total 401(k) limit is $70K minus employee + employer contributions
            # No tax effect in current year (after-tax in, Roth conversion)
            pass

        # ----- CREDITS -----

        elif sid == "CRD_CHILDCARE":
            expenses = params.get("expenses", 0)
            num = params.get("num_children", 0)
            adj["additional_credits"]["childcare"] = {"expenses": expenses, "num": num}

        elif sid == "CRD_AOTC":
            num_students = params.get("num_students", 1)
            adj["additional_credits"]["aotc"] = {"num_students": num_students}

        elif sid == "CRD_LLC":
            expenses = params.get("expenses", 10_000)
            adj["additional_credits"]["llc"] = {"expenses": expenses}

        elif sid == "CRD_SAVERS":
            contribution = params.get("contribution", SAVERS_MAX_CONTRIBUTION)
            adj["additional_credits"]["savers"] = {"contribution": contribution}

        elif sid == "CRD_SOLAR":
            cost = params.get("cost", 0)
            adj["additional_credits"]["solar"] = {"cost": cost}

        elif sid == "CRD_EV":
            adj["additional_credits"]["ev"] = {"amount": min(params.get("amount", EV_CREDIT_MAX), EV_CREDIT_MAX)}

        elif sid == "CRD_ENERGY_HOME":
            cost = params.get("cost", 0)
            adj["additional_credits"]["energy_home"] = {"cost": cost}

        elif sid == "CRD_EITC":
            adj["additional_credits"]["eitc"] = {}

        # ----- DEDUCTIONS (individual) -----

        elif sid == "DED_MEDICAL":
            adj["additional_medical_expenses"] = params.get("amount", 0)

        elif sid == "DED_STUDENT_LOAN":
            adj["additional_student_loan"] = params.get("amount", 0)

        elif sid == "DED_EDUCATOR":
            adj["additional_educator"] = min(params.get("amount", EDUCATOR_MAX), EDUCATOR_MAX)

        elif sid == "DED_QCD":
            # Qualified Charitable Distribution: IRA distribution direct to charity
            # Excluded from income entirely (not a deduction). Age 70½+ only.
            if age >= QCD_MIN_AGE:
                amount = min(params.get("amount", 0), QCD_MAX)
                adj["qcd_exclusion"] = amount

        # ----- OBBB PROVISIONS -----

        elif sid == "OBBB_TIPS":
            adj["obbb_tips_deduction"] = params.get("amount", 0)

        elif sid == "OBBB_OVERTIME":
            adj["obbb_overtime_deduction"] = params.get("amount", 0)

        elif sid == "OBBB_AUTO_INT":
            adj["obbb_auto_interest"] = params.get("amount", 0)

        # ----- RENTAL STRATEGIES -----

        elif sid == "RENT_PAL":
            adj["rental_pal_override"] = True

        elif sid == "RENT_REPS":
            adj["rental_reps_override"] = True

        elif sid == "RENT_STR":
            adj["rental_str_override"] = True

        elif sid == "RENT_1031":
            amount = params.get("amount", 0)
            adj["rental_1031_deferred"] += amount

        # ----- INCOME TIMING -----

        elif sid == "TIME_DEFER":
            adj["income_deferred"] = params.get("amount", 0)

        elif sid == "TIME_ACCEL_EXP":
            resolved = resolve_entity(profile, entity_name, "schedule_c", "s_corp")
            if resolved:
                ename_r, _ = resolved
                amount = params.get("amount", 0)
                adj["entity_deductions"].setdefault(ename_r, 0)
                adj["entity_deductions"][ename_r] += amount

        elif sid == "TIME_LTCG":
            # Characterization — ensure gains are long-term
            # This is advisory; calculator already handles LTCG vs STCG from profile
            pass

        elif sid == "TIME_NIIT":
            # NIIT planning — advisory strategy to reduce investment income below threshold
            # Actual reduction happens through other strategies (retirement, charitable)
            pass

        # ----- TIER 3: NEW STRATEGIES -----

        elif sid == "CG_PRIMARY_RESIDENCE":
            exclusion = HOME_SALE_EXCLUSION.get(profile["filing_status"], 250_000)
            gain = params.get("gain", 0)
            adj["home_sale_exclusion"] = min(gain, exclusion)

        elif sid == "BIZ_R_AND_D":
            resolved = resolve_entity(profile, entity_name, "schedule_c", "s_corp")
            if resolved:
                ename_r, entity = resolved
                qre = params.get("qualified_expenses", 0)
                # Cap QREs to entity's gross revenue (ordinary_income + officer_comp for S-Corp,
                # or net_income for Schedule C). Can't spend more on R&D than you earn.
                entity_gross = abs(entity.get("ordinary_income", 0) or 0) + abs(entity.get("officer_compensation", 0) or 0) + abs(entity.get("net_income", 0) or 0)
                qre = min(qre, max(entity_gross, 0))
                credit = int(qre * RD_CREDIT_RATE_ALT)
                adj["additional_credits"]["r_and_d"] = {"amount": credit, "entity": ename_r}

        elif sid == "BIZ_MEALS":
            resolved = resolve_entity(profile, entity_name, "schedule_c", "s_corp")
            if resolved:
                ename_r, _ = resolved
                total_meals = params.get("amount", 0)
                deductible = int(total_meals * MEALS_DEDUCTION_RATE)
                adj["entity_deductions"].setdefault(ename_r, 0)
                adj["entity_deductions"][ename_r] += deductible

        elif sid == "BIZ_RETIREMENT_MATCH":
            resolved = resolve_entity(profile, entity_name, "s_corp")
            if resolved:
                ename_r, entity = resolved
                match_amount = params.get("amount", 0)
                # Employer match is deductible to the business
                adj["entity_deductions"].setdefault(ename_r, 0)
                adj["entity_deductions"][ename_r] += match_amount

        elif sid == "TIME_HARVEST_GAINS":
            # Realize gains in low-income year to fill 0% bracket
            # Net effect: recognize gains now at 0% instead of later at 15%+
            # No current-year tax reduction — this is a forward planning strategy
            pass

        # Pass-through strategies (computed automatically or no current-year tax effect)
        elif sid in ("SE_QBI", "DED_STD_VS_ITEM", "DED_SALT",
                     "RET_BACKDOOR_ROTH", "RET_ROTH_IRA", "RET_ROTH_CONVERSION",
                     "ENT_C_CORP", "ENT_PTET", "ENT_HEALTH_INS"):
            pass

        # ---- GENERIC PATTERN HANDLER ----
        # For discovered strategies without custom handlers, apply by category pattern.
        # Only fires if the strategy has an amount parameter and is in the registry.
        else:
            amount = params.get("amount", 0) or params.get("contribution", 0) or params.get("excluded_gain", 0)
            if amount and _get_strat:
                reg = _get_strat(sid)
                if reg and not reg.get("calculator_implemented", True):
                    cat = reg.get("category", "")
                    if sid.startswith("EXC_") or "exclusion" in (reg.get("description", "")[:100]).lower():
                        # Income exclusion: reduce gross income
                        adj["qcd_exclusion"] += amount  # reuses exclusion field
                    elif sid.startswith("DEF_") or cat == "timing":
                        # Deferral: reduce recognized capital gains
                        adj["ltcg_deferral"] += amount
                    elif sid.startswith("CR") or cat == "credit":
                        # Tax credit: dollar-for-dollar reduction
                        adj["additional_credits"][sid] = {"amount": amount}
                    elif sid.startswith("DED_") or cat == "deduction":
                        # Above-the-line deduction
                        adj["additional_above_the_line"] += amount

        adj["strategies_applied"].append(sid)

    return adj


# =============================================================================
# MAIN TAX COMPUTATION (Multi-Entity)
# =============================================================================

def compute_tax(profile: dict, strategies: list[dict]) -> dict:
    filing_status = profile["filing_status"]
    age = profile.get("taxpayer_age", 40)

    adj = apply_strategies(profile, strategies)

    # -------------------------------------------------------------------------
    # W-2 INCOME
    # -------------------------------------------------------------------------
    w2_wages = sum(w.get("wages", 0) for w in profile.get("w2_income", []))
    w2_401k = sum(w.get("traditional_401k", 0) for w in profile.get("w2_income", []))

    # -------------------------------------------------------------------------
    # ENTITY INCOME (iterate over all entities)
    # -------------------------------------------------------------------------
    total_se_income = 0       # Subject to SE tax
    total_w2_from_entities = 0  # S-Corp salary added to W-2
    total_scorp_passthrough = 0
    total_partnership_income = 0
    total_rental_net = 0
    total_qbi = 0
    total_business_deductions = 0
    entity_details = []

    for entity in profile.get("entities", []):
        ename = entity["name"]
        etype = entity["type"]
        override = adj["entity_overrides"].get(ename, {})
        extra_deductions = adj["entity_deductions"].get(ename, 0)

        if etype == "schedule_c":
            net = entity.get("net_income", 0) or 0
            net -= extra_deductions
            total_business_deductions += extra_deductions

            if override.get("convert_to_scorp"):
                # S-Corp election: salary becomes W-2, pass-through is QBI
                salary = override["salary"]
                distributions = override["distributions"]
                total_w2_from_entities += salary
                total_scorp_passthrough += distributions
                total_qbi += distributions  # Pass-through is QBI, salary is not
                # No SE tax on this entity anymore
                entity_details.append({
                    "name": ename, "type": "schedule_c->s_corp",
                    "salary": salary, "distributions": distributions,
                    "se_income": 0, "qbi": distributions,
                })
            else:
                # Regular Schedule C: full net is SE income and QBI
                total_se_income += max(0, net)
                total_qbi += max(0, net)
                entity_details.append({
                    "name": ename, "type": "schedule_c",
                    "net_income": net, "se_income": max(0, net),
                    "qbi": max(0, net),
                })

        elif etype == "s_corp":
            ordinary = entity.get("ordinary_income", 0) or 0
            distributions = entity.get("distributions", 0) or 0
            officer_comp = entity.get("officer_compensation", 0) or 0
            # S-Corp rules:
            # - ordinary_income (K-1 box 1) is pass-through income on Schedule E
            # - officer_compensation is already included in W-2 wages — do NOT add again
            # - distributions are return of basis — NOT taxable income
            # - QBI = ordinary_income (K-1 pass-through, not salary)

            if override.get("salary_opt"):
                # Salary optimization: change the split between salary (W-2) and pass-through
                new_salary = override["salary"]
                old_salary = officer_comp
                salary_delta = new_salary - old_salary
                # More salary = more W-2, less ordinary pass-through
                total_w2_from_entities += salary_delta
                new_ordinary = ordinary - salary_delta
                total_scorp_passthrough += max(0, new_ordinary)
                total_qbi += max(0, new_ordinary)
                entity_details.append({
                    "name": ename, "type": "s_corp",
                    "salary": new_salary, "ordinary_income": max(0, new_ordinary),
                    "distributions": distributions,
                    "se_income": 0, "qbi": max(0, new_ordinary),
                })
            else:
                # Default: ordinary income passes through, officer comp already in W-2
                total_scorp_passthrough += ordinary
                total_qbi += ordinary
                entity_details.append({
                    "name": ename, "type": "s_corp",
                    "salary": officer_comp, "ordinary_income": ordinary,
                    "distributions": distributions,
                    "se_income": 0, "qbi": ordinary,
                })

        elif etype == "partnership":
            ordinary = entity.get("ordinary_income", 0) or 0
            guaranteed = entity.get("guaranteed_payments", 0) or 0
            total_partnership_income += ordinary + guaranteed
            total_qbi += ordinary  # Guaranteed payments are NOT QBI
            total_se_income += guaranteed  # Guaranteed payments are SE income
            entity_details.append({
                "name": ename, "type": "partnership",
                "ordinary_income": ordinary, "guaranteed_payments": guaranteed,
                "se_income": guaranteed, "qbi": ordinary,
            })

        elif etype == "rental":
            net = entity.get("net_income", 0) or 0
            net -= extra_deductions
            total_business_deductions += extra_deductions

            # Apply rental strategy overrides
            if net < 0:
                if adj["rental_reps_override"] or adj["rental_str_override"]:
                    # RE Professional or STR: losses are non-passive, fully deductible
                    total_rental_net += net
                elif adj["rental_pal_override"]:
                    # PAL: allow up to $25K loss, phased out $100K-$150K AGI
                    # We don't know AGI yet, so we apply the allowance and let it flow
                    pal_factor = 1.0  # Will be constrained in main computation
                    total_rental_net += net  # Apply full loss, PAL constraint below
                else:
                    # Default passive loss rules: loss may be suspended
                    total_rental_net += net
            else:
                total_rental_net += net

            entity_details.append({
                "name": ename, "type": "rental",
                "net_income": net,
            })

    # Total W-2 including entity salaries
    total_w2 = w2_wages + total_w2_from_entities

    # -------------------------------------------------------------------------
    # SELF-EMPLOYMENT TAX
    # -------------------------------------------------------------------------
    se_result = compute_se_tax(total_se_income, total_w2)
    se_tax = se_result["se_tax"]
    se_tax_deduction = se_result["se_tax_deduction"]

    # -------------------------------------------------------------------------
    # BUSINESS SALES (capital gains from selling business interests)
    # -------------------------------------------------------------------------
    business_sale_ltcg = 0
    business_sale_stcg = 0
    for sale in profile.get("business_sales", []):
        gain = sale.get("capital_gain", 0) or 0
        if sale.get("gain_type", "long_term") == "long_term":
            business_sale_ltcg += gain
        else:
            business_sale_stcg += gain

    # -------------------------------------------------------------------------
    # INVESTMENT INCOME (with strategy adjustments)
    # -------------------------------------------------------------------------
    inv = profile.get("investment_income", {})

    # Apply capital gain deferrals and offsets
    # Home sale exclusion (§121) applies to business_sales flagged as primary_residence
    home_exclusion = adj["home_sale_exclusion"]
    # QOZ deferral and installment sale reduce recognized LTCG
    effective_sale_ltcg = max(0, business_sale_ltcg - adj["ltcg_deferral"] - home_exclusion)
    # 1031 exchange defers rental property gains
    effective_sale_ltcg = max(0, effective_sale_ltcg - adj["rental_1031_deferred"])
    # Tax loss harvesting offsets gains
    ltcg_after_tlh = max(0, effective_sale_ltcg + (inv.get("capital_gains_long", 0) or 0) - adj["ltcg_offset"])

    cap_gains_long = ltcg_after_tlh
    cap_gains_short = (inv.get("capital_gains_short", 0) or 0) + business_sale_stcg
    interest = inv.get("interest_income", 0) or 0
    div_qualified = inv.get("dividend_income_qualified", 0) or 0
    div_ordinary = inv.get("dividend_income_ordinary", 0) or 0
    total_investment = cap_gains_long + cap_gains_short + interest + div_qualified + div_ordinary

    # -------------------------------------------------------------------------
    # GROSS INCOME & AGI
    # -------------------------------------------------------------------------
    other = profile.get("other_income", {})
    gross_income = (
        total_w2 +
        total_se_income +
        total_scorp_passthrough +
        total_partnership_income +
        total_rental_net +
        cap_gains_short + cap_gains_long +
        interest + div_qualified + div_ordinary +
        (other.get("social_security", 0) or 0) +
        (other.get("pension", 0) or 0) +
        (other.get("other", 0) or 0) -
        adj["income_deferred"] -
        adj["qcd_exclusion"]
    )

    # Above-the-line deductions
    existing_se_health = profile.get("self_employed_health_insurance", 0) or 0
    existing_hsa = profile.get("retirement", {}).get("hsa_contributions", 0) or 0
    existing_student_loan = profile.get("deductions", {}).get("student_loan_interest", 0) or 0
    existing_educator = profile.get("deductions", {}).get("educator_expenses", 0) or 0
    existing_ira = profile.get("retirement", {}).get("traditional_ira_contributions", 0) or 0

    # Student loan: compute with phase-out (including any additional from strategy)
    total_student_loan_interest = existing_student_loan + adj["additional_student_loan"]
    student_loan_deduction = compute_student_loan_deduction(
        total_student_loan_interest, gross_income, filing_status)  # Use gross as proxy for MAGI pre-ATL

    # Educator expenses
    total_educator = existing_educator + adj["additional_educator"]
    educator_deduction = min(total_educator, EDUCATOR_MAX)

    # OBBB above-the-line deductions
    obbb_tips = adj["obbb_tips_deduction"]
    obbb_overtime = adj["obbb_overtime_deduction"]
    obbb_auto_int = adj["obbb_auto_interest"]
    # Phase-out check for tips and overtime
    obbb_tips_threshold = OBBB_TIPS_PHASEOUT.get(filing_status, 75_000)
    obbb_overtime_threshold = OBBB_OVERTIME_PHASEOUT.get(filing_status, 75_000)
    # Simple phase-out: zero above threshold (OBBB uses W-2 wages)
    if total_w2 > obbb_tips_threshold:
        obbb_tips = 0
    if total_w2 > obbb_overtime_threshold:
        obbb_overtime = 0

    above_the_line = (
        se_tax_deduction +
        existing_se_health +
        existing_hsa +
        student_loan_deduction +
        educator_deduction +
        existing_ira +
        adj["additional_above_the_line"] +
        obbb_tips +
        obbb_overtime +
        obbb_auto_int
    )

    agi = gross_income - above_the_line

    # -------------------------------------------------------------------------
    # DEDUCTIONS
    # -------------------------------------------------------------------------
    ded = profile.get("deductions", {})
    salt_cap = compute_salt_cap(agi, filing_status)
    salt_deduction = min(ded.get("salt_paid", 0), salt_cap)

    total_charitable = (
        ded.get("charitable_cash", 0) +
        ded.get("charitable_noncash", 0) +
        adj["additional_charitable"]
    )
    total_charitable = min(total_charitable, int(agi * 0.6))

    # Medical expenses: only deductible above 7.5% AGI floor
    total_medical = (ded.get("medical_expenses", 0) or 0) + adj["additional_medical_expenses"]
    medical_deduction = max(0, total_medical - int(agi * 0.075))

    total_itemized = (
        medical_deduction +
        salt_deduction +
        ded.get("mortgage_interest", 0) +
        total_charitable
    )

    standard_ded = STANDARD_DEDUCTION.get(filing_status, 15_750)

    if total_itemized > standard_ded:
        chosen_deduction = total_itemized
        deduction_type = "itemized"
    else:
        chosen_deduction = standard_ded
        deduction_type = "standard"

    # -------------------------------------------------------------------------
    # QBI DEDUCTION
    # -------------------------------------------------------------------------
    # Check if any entity is SSTB
    any_sstb = any(e.get("is_sstb", False) for e in profile.get("entities", []))
    taxable_before_qbi = agi - chosen_deduction
    qbi_deduction = compute_qbi_deduction(total_qbi, taxable_before_qbi, filing_status, any_sstb)

    # -------------------------------------------------------------------------
    # TAXABLE INCOME & TAX
    # -------------------------------------------------------------------------
    taxable_income = max(0, agi - chosen_deduction - qbi_deduction)

    ordinary_taxable = max(0, taxable_income - cap_gains_long - div_qualified)
    income_tax_ordinary = compute_bracket_tax(ordinary_taxable, filing_status)
    income_tax_ltcg = compute_ltcg_tax(cap_gains_long + div_qualified, taxable_income, filing_status)
    income_tax = income_tax_ordinary + income_tax_ltcg

    # -------------------------------------------------------------------------
    # ADDITIONAL TAXES
    # -------------------------------------------------------------------------
    total_earned = total_w2 + se_result.get("se_earnings", 0)
    additional_medicare = compute_additional_medicare(total_earned, filing_status)
    niit = compute_niit(total_investment, agi, filing_status)

    # -------------------------------------------------------------------------
    # CREDITS
    # -------------------------------------------------------------------------
    num_children = sum(1 for d in profile.get("dependents", []) if d.get("age", 0) < 17)
    ctc = compute_child_tax_credit(num_children, agi, filing_status)

    # Child/Dependent Care Credit
    childcare_credit = 0
    if "childcare" in adj["additional_credits"]:
        cc = adj["additional_credits"]["childcare"]
        childcare_credit = compute_childcare_credit(cc["expenses"], cc["num"], agi)

    # American Opportunity Credit
    aotc = 0
    if "aotc" in adj["additional_credits"]:
        num_students = adj["additional_credits"]["aotc"].get("num_students", 1)
        raw = AOTC_MAX * num_students
        aotc = compute_education_credit_phaseout(raw, agi, filing_status, AOTC_PHASEOUT)

    # Lifetime Learning Credit
    llc_credit = 0
    if "llc" in adj["additional_credits"]:
        expenses = adj["additional_credits"]["llc"].get("expenses", 10_000)
        raw = min(expenses * 0.20, LLC_MAX)
        llc_credit = compute_education_credit_phaseout(raw, agi, filing_status, LLC_PHASEOUT)

    # Saver's Credit
    savers_credit = 0
    if "savers" in adj["additional_credits"]:
        contribution = adj["additional_credits"]["savers"]["contribution"]
        savers_credit = compute_savers_credit(contribution, agi, filing_status)

    # Clean Energy Credits
    solar_credit = 0
    if "solar" in adj["additional_credits"]:
        solar_credit = int(adj["additional_credits"]["solar"]["cost"] * SOLAR_CREDIT_RATE)

    ev_credit = 0
    if "ev" in adj["additional_credits"]:
        ev_credit = adj["additional_credits"]["ev"]["amount"]

    energy_home_credit = 0
    if "energy_home" in adj["additional_credits"]:
        energy_home_credit = min(
            int(adj["additional_credits"]["energy_home"]["cost"] * 0.30),
            ENERGY_HOME_MAX)

    # EITC
    eitc = 0
    if "eitc" in adj["additional_credits"]:
        total_earned = total_w2 + se_result.get("se_earnings", 0)
        num_eitc_children = sum(1 for d in profile.get("dependents", []) if d.get("age", 0) < 19 or (d.get("age", 0) < 24 and d.get("student", False)))
        eitc = compute_eitc(total_earned, total_investment, agi, filing_status, num_eitc_children)

    # R&D Credit
    rd_credit = 0
    if "r_and_d" in adj["additional_credits"]:
        rd_credit = adj["additional_credits"]["r_and_d"]["amount"]

    # Generic credits from discovered strategies
    named_credit_keys = {"childcare", "aotc", "llc", "savers", "solar", "ev", "energy_home", "eitc", "r_and_d"}
    generic_credits = sum(
        v.get("amount", 0) for k, v in adj["additional_credits"].items()
        if k not in named_credit_keys
    )

    total_credits = (ctc + childcare_credit + aotc + llc_credit + savers_credit +
                     solar_credit + ev_credit + energy_home_credit + eitc + rd_credit +
                     generic_credits)

    # -------------------------------------------------------------------------
    # FEDERAL TAX
    # -------------------------------------------------------------------------
    federal_tax = max(0, income_tax + se_tax + additional_medicare + niit - total_credits)

    # -------------------------------------------------------------------------
    # STATE TAX (Utah)
    # -------------------------------------------------------------------------
    utah_tax = max(0, agi * UTAH_RATE - adj["ptet_amount"] - adj["utah_529_credit"])

    # -------------------------------------------------------------------------
    # TOTAL
    # -------------------------------------------------------------------------
    total_tax = max(0, federal_tax + utah_tax)

    return {
        "total_tax": round(total_tax),
        "federal_tax": round(federal_tax),
        "state_tax": round(utah_tax),
        "breakdown": {
            "gross_income": round(gross_income),
            "w2_wages": round(total_w2),
            "se_income": round(total_se_income),
            "scorp_passthrough": round(total_scorp_passthrough),
            "partnership_income": round(total_partnership_income),
            "rental_income": round(total_rental_net),
            "investment_income": round(total_investment),
            "above_the_line_deductions": round(above_the_line),
            "agi": round(agi),
            "deduction_type": deduction_type,
            "deduction_amount": round(chosen_deduction),
            "itemized_total": round(total_itemized),
            "standard_deduction": standard_ded,
            "salt_deduction": round(salt_deduction),
            "salt_cap": round(salt_cap),
            "charitable_deduction": round(total_charitable),
            "qbi": round(total_qbi),
            "qbi_deduction": round(qbi_deduction),
            "taxable_income": round(taxable_income),
            "income_tax_ordinary": round(income_tax_ordinary),
            "income_tax_ltcg": round(income_tax_ltcg),
            "income_tax": round(income_tax),
            "se_tax": round(se_tax),
            "se_tax_deduction": round(se_tax_deduction),
            "additional_medicare": round(additional_medicare),
            "niit": round(niit),
            "child_tax_credit": round(ctc),
            "total_credits": round(total_credits),
            "entity_details": entity_details,
            "strategies_applied": adj["strategies_applied"],
        },
    }


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import json
    import sys

    profile_path = sys.argv[1] if len(sys.argv) > 1 else "profiles/sample.json"
    with open(profile_path) as f:
        profile = json.load(f)

    print("=" * 60)
    print("BASELINE (no strategies)")
    print("=" * 60)
    result = compute_tax(profile, [])
    print(json.dumps(result, indent=2))

    print("\n" + "=" * 60)
    print("WITH STRATEGIES")
    print("=" * 60)
    test_strategies = [
        {"id": "RET_401K_MAX", "parameters": {"contribution": 23_500}},
        {"id": "RET_HSA", "parameters": {"contribution": 8_550}},
        {"id": "SE_SCORP_ELECTION", "entity": "Consulting LLC", "parameters": {"salary": 50_000}},
        {"id": "SE_SALARY_OPT", "entity": "Marketing Agency Inc", "parameters": {"salary": 60_000}},
        {"id": "DED_HOME_OFFICE", "entity": "Consulting LLC", "parameters": {"amount": 1_500}},
    ]
    result2 = compute_tax(profile, test_strategies)
    print(json.dumps(result2, indent=2))

    print(f"\nBaseline: ${result['total_tax']:,}")
    print(f"Optimized: ${result2['total_tax']:,}")
    print(f"Savings: ${result['total_tax'] - result2['total_tax']:,}")
