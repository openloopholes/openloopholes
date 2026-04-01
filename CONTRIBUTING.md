# Contributing to OpenLoopholes

Thank you for helping make tax optimization accessible to everyone. This project deals with tax law, so contributions require extra care.

## How to Contribute

### Proposing a New Strategy
1. **Open a GitHub Issue or Discussion first** — describe the strategy, who it benefits, and cite the IRC section
2. Community and maintainers vet the strategy publicly before any code is written
3. Once approved, create the strategy JSON file and submit a PR

### Strategy PR Requirements

Every strategy PR **must** include:

- **IRC citation**: Reference to the specific Internal Revenue Code section (e.g., IRC §401(k))
- **Legal basis**: Brief explanation of why this strategy is legal and established
- **Eligibility rules**: Who qualifies and who doesn't
- **Source**: Link to IRS publication, court case, or authoritative tax reference that supports the strategy
- **Test case**: Example profile where this strategy produces savings

### What We Will NOT Accept

- **Unverified or aggressive positions** — if the strategy hasn't been tested in Tax Court or isn't supported by IRS guidance, it doesn't belong here
- **Strategies that rely on non-disclosure** — if it only works because the IRS doesn't know about it, it's not a loophole, it's evasion
- **Anything illegal** — tax evasion, unreported income, fraudulent deductions, or strategies that rely on hiding information from the IRS. If it isn't defensible in Tax Court, it doesn't belong here.
- **Expired provisions** — strategies must be current for the supported tax year
- **Strategies without IRC references** — every strategy JSON must have an `irc_reference` field

## Adding a Strategy

Create a JSON file in `loop-runner/strategies/`:

```json
{
  "id": "NEW_STRATEGY_ID",
  "name": "Human-Readable Name",
  "category": "deduction|credit|retirement|business|entity|capital_gain|rental|timing",
  "jurisdiction": "federal|state:XX",
  "eligibility_type": "profile|opportunity",
  "eligibility": {
    "description": "Who qualifies for this strategy",
    "requires_entity_type": null,
    "min_age": null,
    "max_age": null
  },
  "parameters": {
    "amount": {"type": "int", "description": "dollar amount"}
  },
  "entity_specific": false,
  "entity_types": null,
  "conflicts": [],
  "actionability": {
    "retroactive_status": "available|deadline_passed|depends",
    "retroactive_note": "When this must be done",
    "forward_status": "available"
  },
  "description": "2-3 sentences explaining the strategy",
  "irc_reference": "IRC section",
  "deadline": "When action must be taken",
  "savings_potential": "high|medium|low|niche",
  "benefits": "individual|business|investor|employer|estate",
  "calculator_implemented": false
}
```

If the strategy needs precise scoring, add a handler in `loop-runner/tax_calculator.py`. Otherwise the generic pattern handler will score it by category (exclusion, deduction, credit, or deferral).

## Adding a State

Create strategy files with `"jurisdiction": "state:XX"` for state-specific strategies. They automatically appear for users in that state.

## Code Changes

- Follow existing patterns — look at how similar code works before adding new code
- Don't break the calculator — it's the immutable eval harness
- Don't hardcode models or API keys — use `ai_provider.py`
- Test with `python3 run.py --profile profiles/sample.json --iterations 10` before submitting

## Review Process

- All PRs require at least one maintainer approval
- Strategy PRs are reviewed for legal accuracy, not just code quality
- Discussions happen in the open — no private strategy vetting

## Code of Conduct

Be respectful. This project helps people keep more of their money. Don't gatekeep, don't shame, don't be a jerk.
