# Taxpayer Profile Schema

The profile JSON describes a taxpayer's complete financial picture for a single tax year.

## Required Fields

```json
{
  "taxpayer_age": 39,
  "filing_status": "married_joint",    // married_joint, single, head_of_household, married_separate
  "state": "UT",                       // Two-letter state code
  "optimization_mode": "retroactive",  // retroactive, forward, or both
  "current_date": "2026-03-30",        // Today's date (for actionability checks)
  "tax_year": 2025                     // Tax year being optimized
}
```

## Income Sources

### W-2 Income
```json
{
  "w2_income": [
    {
      "employer": "Employer Name",
      "wages": 75000,
      "traditional_401k": 10000,       // Employee deferrals
      "roth_401k": 0
    }
  ]
}
```

### Business Entities
```json
{
  "entities": [
    {
      "name": "My Business LLC",
      "type": "schedule_c",            // schedule_c, s_corp, partnership, rental
      "net_income": 92000              // Schedule C net profit
    },
    {
      "name": "My S-Corp Inc",
      "type": "s_corp",
      "ordinary_income": 55000,        // K-1 box 1 (pass-through)
      "officer_compensation": 45000,   // Already in W-2 wages above
      "distributions": 60000,          // Return of basis, NOT taxable
      "is_sstb": false                 // Specified Service Trade or Business?
    },
    {
      "name": "Investment Partnership",
      "type": "partnership",
      "ordinary_income": -5000,        // K-1 ordinary income (can be negative)
      "guaranteed_payments": 0         // Subject to SE tax
    },
    {
      "name": "123 Main St",
      "type": "rental",
      "net_income": 24000              // Net rental income after expenses
    }
  ]
}
```

### Business Sales (Capital Gains)
```json
{
  "business_sales": [
    {
      "name": "Business Name",
      "capital_gain": 900000,
      "gain_type": "long_term",        // long_term or short_term
      "date_sold": "2025-01-01",
      "entity_type": "s_corp"
    }
  ]
}
```

### Investment Income
```json
{
  "investment_income": {
    "capital_gains_long": 0,
    "capital_gains_short": 0,
    "interest_income": 2500,
    "dividend_income_qualified": 3000,
    "dividend_income_ordinary": 200
  }
}
```

### Other Income
```json
{
  "other_income": {
    "social_security": 0,
    "pension": 0,
    "other": 0
  }
}
```

## Deductions & Insurance

```json
{
  "self_employed_health_insurance": 8928,
  "deductions": {
    "salt_paid": 15000,              // State and local taxes paid
    "mortgage_interest": 12000,
    "charitable_cash": 5000,
    "charitable_noncash": 500,
    "medical_expenses": 0,           // Only deductible above 7.5% AGI
    "student_loan_interest": 0,
    "educator_expenses": 0
  }
}
```

## Retirement
```json
{
  "retirement": {
    "traditional_ira_contributions": 0,
    "hsa_contributions": 0,
    "hdhp_coverage": "family",       // family or self
    "has_hdhp": true                 // Required for HSA
  }
}
```

## Dependents
```json
{
  "dependents": [
    {"name": "Child 1", "age": 15, "relationship": "child"},
    {"name": "Child 2", "age": 10, "relationship": "child"}
  ]
}
```

## Optional Fields
- `spouse_age` — for spousal IRA calculations
- `has_home_office` — for home office deduction
- `home_office_sqft` — square footage of office

## Example
See `sample.json` for a complete working example.
