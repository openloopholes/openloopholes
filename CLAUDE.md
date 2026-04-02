# OpenLoopholes.com — Claude Code Guide

## What This Is
An AI-powered tax optimization engine that finds legal tax savings. It applies Karpathy's autoresearch pattern: an LLM proposes strategy changes, a deterministic calculator scores them. The proposer never grades its own homework.

## Quick Start
```bash
cd loop-runner
pip3 install -r requirements.txt
export OPENROUTER_API_KEY=your_key  # or ANTHROPIC_API_KEY
python3 run.py --profile profiles/sample.json --iterations 50
python3 chart.py
python3 generate_report.py
```

## Key Files
- `loop-runner/run.py` — main optimization loop
- `loop-runner/tax_calculator.py` — deterministic tax calculator (the eval harness, never modified by LLM)
- `loop-runner/ai_provider.py` — AI provider abstraction (OpenRouter, Anthropic, OpenClaw)
- `loop-runner/strategy_registry.py` — loads/filters strategies from JSON files
- `loop-runner/strategies/` — 1,454 strategy JSON files (one per strategy)
- `loop-runner/generate_report.py` — CPA-ready HTML report
- `loop-runner/chart.py` — staircase chart (PNG + interactive HTML)
- `loop-runner/find_loopholes.py` — combination scanner for strategy synergies
- `loop-runner/discover_strategies.py` — scans IRC sections for new strategies
- `loop-runner/parse_return.py` — PDF tax return parser (prototype)
- `loop-runner/parse_tax_code.py` — IRC Title 26 XML parser
- `prompts/iteration-loop-system-prompt.md` — prompt template (static parts)
- `prompts/final-validation-system-prompt.md` — validation prompt

## AI Provider Configuration
Set environment variables:
```bash
# Option 1: OpenRouter (recommended, cheapest)
export OPENROUTER_API_KEY=your_key

# Option 2: Anthropic
export ANTHROPIC_API_KEY=your_key

# Option 3: OpenClaw (uses your configured model automatically)
# First, enable chat completions in your OpenClaw config:
#   "gateway": { "http": { "endpoints": { "chatCompletions": { "enabled": true } } } }
# Then set your bearer token:
# export OPENCLAW_API_KEY=your_bearer_token

# Optional: override models (OpenClaw defaults to "openclaw/default")
export LOOP_MODEL=google/gemini-3.1-flash-lite-preview
export VALIDATION_MODEL=google/gemini-3-flash-preview
```

## Adding a New Strategy
Create a JSON file in `loop-runner/strategies/`:
```json
{
  "id": "NEW_STRATEGY_ID",
  "name": "Human-Readable Name",
  "category": "deduction|credit|retirement|business|...",
  "jurisdiction": "federal|state:XX",
  "description": "What this strategy does",
  "irc_reference": "IRC section",
  "parameters": {"amount": {"type": "int", "description": "..."}},
  "eligibility": {"description": "Who qualifies"},
  "actionability": {"retroactive_status": "available|deadline_passed|depends", "forward_status": "available"}
}
```
If it needs scoring, add a handler in `tax_calculator.py`. Otherwise the generic pattern handler scores it by category.

## Adding a New State
Create strategy files with `"jurisdiction": "state:XX"` for state-specific strategies.

## Common Tasks
- **Run optimizer**: `python3 run.py --profile profiles/your-profile.json --iterations 200`
- **Generate chart**: `python3 chart.py`
- **Generate report**: `python3 generate_report.py`
- **Find loopholes**: `python3 find_loopholes.py --profile profiles/your-profile.json`
- **Discover strategies**: `python3 discover_strategies.py --subtitle A`
- **Parse tax return**: `python3 parse_return.py ../tax-documents/return.pdf --output profiles/name.json`
- **Parse tax code**: `python3 parse_tax_code.py --download`
