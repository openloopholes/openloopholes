# OpenLoopholes.com

We fed the entire US tax code to an AI. It found 1,454 legal tax strategies the IRS hopes you never notice.

> **Disclaimer:** This is educational software, not tax advice. Every strategy must be verified by a qualified CPA or tax attorney before implementation. You are solely responsible for your tax filings. See [LICENSE](LICENSE) for full terms.

## 100% Legal. Zero Evasion.

Every strategy in this project is grounded in the Internal Revenue Code as written. We find deductions, credits, exclusions, deferrals, and elections that are **explicitly permitted by law** — including provisions that Congress may not have intended to interact the way they do, but that are fully legal as written.

This project will **never** support tax evasion, unreported income, fraudulent deductions, or any strategy that relies on hiding information from the IRS. If a strategy isn't defensible in Tax Court with a straight face, it doesn't belong here.

## What This Is

An open source tax optimization engine that finds legal tax savings for anyone — W-2 employees, small business owners, investors, retirees. We parsed all 4 million words of the Internal Revenue Code (2,160 IRC sections) and built an AI discovery engine that identified **1,454 legal tax strategies**. An LLM proposes strategy changes; a deterministic calculator scores them. The system keeps improvements and discards regressions — the same hill-climbing approach as [Karpathy's autoresearch](https://github.com/karpathy/autoresearch), but applied to tax law.

**Tax Year 2025** — reflects the One Big Beautiful Bill Act (signed July 4, 2025).

## Quick Start

```bash
git clone https://github.com/openloopholes/openloopholes.git
cd openloopholes/loop-runner
pip3 install -r requirements.txt

# Set your AI provider (REQUIRED — pick one)
export OPENROUTER_API_KEY=your_key    # OpenRouter (cheapest, ~$0.25/run)
# export ANTHROPIC_API_KEY=your_key   # Anthropic (Claude)
# Or start OpenClaw                   # OpenClaw (local)

# Windows (cmd):    set OPENROUTER_API_KEY=your_key
# Windows (PS):     $env:OPENROUTER_API_KEY="your_key"

# Run optimizer on the sample profile
python3 run.py --profile profiles/sample.json --iterations 50

# Generate results
python3 chart.py
python3 generate_report.py
```

## Architecture

```
                    Strategy Registry (1,454 JSON files)
                         |  pre-filter by profile + state
                         v
LLM (configurable)          Python Tax Calculator
        proposes                      scores
   strategy changes    ──────>    computes liability
                       <──────    keep or discard
```

The LLM never estimates tax liability. The calculator is the immutable eval harness — same pattern as Karpathy's `prepare.py` / `evaluate_bpb`. The proposer never grades its own homework.

## Project Structure

```
loop-runner/
  run.py                 # Main optimization loop
  tax_calculator.py      # Deterministic tax calculator (the eval harness)
  ai_provider.py         # AI provider abstraction (OpenRouter, Anthropic, OpenClaw)
  strategy_registry.py   # Strategy loader, filter, and prompt builder
  chart.py               # Staircase chart generator (PNG + interactive HTML)
  generate_report.py     # CPA-ready HTML report generator
  find_loopholes.py      # Combination scanner — finds strategy stacking synergies
  discover_strategies.py # Strategy discovery engine (scans IRC for new strategies)
  parse_return.py        # PDF tax return parser (prototype)
  parse_tax_code.py      # IRC Title 26 XML parser
  strategies/            # Strategy registry (one JSON file per strategy)
    ...                  # 1,454 strategy files (71 hand-built + 1,383 AI-discovered)
  tax_code/              # Parsed IRC Title 26 (included — public government data)
    raw/                 # Downloaded XML from uscode.house.gov
    sections/            # One text file per IRC section (~2,160 files)
    index.json           # Section index with metadata
  profiles/
    sample.json          # Example profile (MFJ, multi-entity)
    SCHEMA.md            # Profile field documentation
  requirements.txt       # Python dependencies

prompts/
  iteration-loop-system-prompt.md    # Prompt template (static parts, strategies injected at runtime)
  final-validation-system-prompt.md  # Final validation prompt (appended with state rules)
  state-utah.md                      # Utah state tax rules (appended to validation prompt)

tax-documents/           # Your tax return PDFs (gitignored — never committed)
results/                 # Generated output (gitignored)
logs/                    # Run logs with timestamps (gitignored, one file per session)

CLAUDE.md                # Claude Code setup guide
openclaw.config.json     # OpenClaw skills configuration
.gitignore               # Protects personal data from being committed
```

## AI Provider Configuration

OpenLoopholes.com works with any OpenAI-compatible API. Set environment variables to choose your provider:

```bash
# Option 1: OpenRouter (recommended — cheapest, any model)
export OPENROUTER_API_KEY=your_key

# Option 2: Anthropic (Claude models)
export ANTHROPIC_API_KEY=your_key

# Option 3: OpenClaw (uses your local gateway + configured model)
# First, enable chat completions in your OpenClaw config:
#   "gateway": { "http": { "endpoints": { "chatCompletions": { "enabled": true } } } }
# Then set your bearer token:
# export OPENCLAW_API_KEY=your_bearer_token

# Optional: override models
export LOOP_MODEL=google/gemini-3.1-flash-lite-preview      # iteration loop
export VALIDATION_MODEL=google/gemini-3-flash-preview        # final validation
export DISCOVERY_MODEL=google/gemini-3-flash-preview          # strategy discovery
```

Auto-detection: if `AI_PROVIDER` is not set, the system checks for available API keys in order: OpenRouter, Anthropic, OpenClaw.

> **Windows users:** Replace `export` with `set` (cmd) or `$env:VAR="value"` (PowerShell) for all environment variable commands.

**Run time:** A typical 200-iteration optimization takes 2-10 minutes depending on your model. The loop makes many small LLM calls, so faster models (Gemini Flash-Lite, Haiku) complete significantly quicker than larger models (Sonnet, Opus, GPT-4). The deterministic calculator and loophole finder run instantly — no LLM needed.

**Model considerations:** Different models produce different results — this is expected. The deterministic calculator is the scoring safeguard: no model can hallucinate savings, because every strategy is scored by the same math. However, the final validation step (eligibility checks, legal risk flags, action steps) is only as good as the model running it. Stronger models catch more issues; weaker models may miss eligibility problems or produce less detailed action steps. **Regardless of which model you use, always have a qualified CPA or tax attorney review the final report before acting on any strategy.**

## Creating Your Profile

### Option 1: From a tax return PDF (recommended)

Place your tax return PDF in the `tax-documents/` folder at the project root. This folder is included in the repo but gitignored — your documents will never be committed to version control.

```bash
# Copy your return into the tax-documents/ folder
cp ~/Downloads/my-2025-return.pdf ../tax-documents/

# Parse it into a profile (uses pymupdf4llm + your configured AI provider)
python3 parse_return.py ../tax-documents/my-2025-return.pdf

# Profile saved to profiles/my-2025-return.json — review it
cat profiles/my-2025-return.json

# Run the optimizer
python3 run.py --profile profiles/my-2025-return.json --iterations 200
```

The parser converts your PDF to markdown (via pymupdf4llm), then sends it to your configured AI provider to extract the structured profile. Review the output — AI extraction can miss details on complex returns.

### Option 2: Manually
Copy `profiles/sample.json` and edit the values. See `profiles/SCHEMA.md` for field documentation.

### Option 3: Let AI help
If using Claude Code or OpenClaw, ask it to build your profile conversationally:
> "Help me create a tax profile. I'm married filing jointly, age 42, live in California, have an S-Corp and two kids..."

**Privacy:** Your profile and tax documents stay on your machine. The `tax-documents/` and `profiles/` directories are gitignored — nothing personal is ever committed.

## How It Works

### 1. Optimization Loop
```bash
python3 run.py --profile profiles/sample.json --iterations 200
```
The LLM proposes one strategy change per iteration. The deterministic calculator scores it. Keep improvements, discard regressions. Converges automatically after 20 consecutive discards.

After the loop converges, a **final validation call** sends the winning strategy set to a stronger LLM model for rigorous review: eligibility verification, conflict detection, legal risk assessment, and action steps for each strategy. The validation flags issues (e.g., "HSA requires HDHP enrollment") and produces the data for the CPA-ready report.

### 2. Strategy Registry
Each strategy is a JSON file in `strategies/`. At runtime, strategies are filtered to those relevant to the user's profile and state, then assembled into the LLM prompt.

Adding a new strategy = adding one JSON file. See `CLAUDE.md` for the schema.

### 3. Tax Code Ingestion
The full IRC (Title 26) is included in the repo — 2,160 sections, 4,054,967 words. No download needed.

To refresh with newer legislation:
```bash
python3 parse_tax_code.py --download
```

### 4. Strategy Discovery
```bash
python3 discover_strategies.py --all
```
Scans IRC sections with an LLM to find deductions, credits, exclusions, and exemptions not yet in the registry. Deduplicates against existing strategies.

### 5. Loophole Finder
```bash
python3 find_loopholes.py --profile profiles/sample.json
```
Tests pairs of strategies to find synergies — combinations where the combined savings exceed the sum of individual savings. Purely deterministic (no LLM calls).

### 6. Report Generation
```bash
python3 chart.py              # Staircase chart
python3 generate_report.py    # CPA-ready HTML report
```

## Optimization Modes

- **retroactive** — only proposes strategies still actionable before the filing deadline. The calculator enforces deadlines as the gatekeeper.
- **forward** — all strategies available for the next tax year
- **both** — shows retroactive + forward, labeled by actionability

## Strategy Coverage

| Category | Strategies | Calculator Handlers |
|----------|-----------|-------------------|
| Deductions & Exclusions | 932 | 24 + generic |
| Timing & Deferrals | 137 | 8 + generic |
| Credits | 108 | 9 + generic |
| Retirement | 21 | 13 |
| Rental | 10 | 5 |
| Capital Gains | 9 | 6 |
| Business | 7 | 6 |
| Entity | 5 | 4 |
| SE Tax | 4 | 4 |
| OBBB | 3 | 3 |
| Other | 218 | generic |

71 strategies have dedicated calculator handlers. The remaining 1,383 use generic pattern-based handlers (exclusion → reduce income, credit → reduce tax, deferral → defer gains, deduction → reduce AGI).

## Using with Claude Code

See `CLAUDE.md` for setup instructions and common commands.

## Using with OpenClaw

See `openclaw.config.json` for skill definitions. OpenClaw auto-detects the project and provides skills for optimization, chart generation, report generation, and strategy discovery.

## Contributing

### Add a Strategy
1. Create a JSON file in `loop-runner/strategies/`
2. (Optional) Add a calculator handler in `tax_calculator.py` for precise scoring
3. The strategy automatically appears in prompts for matching profiles

### Add a State
Create strategy files with `"jurisdiction": "state:XX"` for state-specific strategies (PTET elections, state credits, etc.). They automatically appear for users in that state.

### Improve the Calculator
The calculator in `tax_calculator.py` is the eval harness. Add handlers for discovered strategies to improve scoring accuracy. The generic handlers work but dedicated handlers are more precise.

## What We Tried That Didn't Work

### LLM-as-estimator (v1)
The first version had the LLM both propose strategies AND estimate the resulting tax liability. The LLM hallucinated negative tax liability (-$169,820) and gamed its own metric. Fix: Karpathy's pattern — immutable external eval harness.

### LLM Ignoring Deadlines
The prompt told the LLM not to propose expired strategies, but it did anyway. Fix: the calculator enforces actionability as the gatekeeper. Expired strategies have no effect regardless of what the LLM proposes.

### LLM Estimating Per-Strategy Savings
The validation LLM estimated per-strategy savings that didn't add up. Fix: marginal savings computed deterministically by running the calculator with and without each strategy.

## Which Commands Need an API Key?

| Command | API Key Required? |
|---------|------------------|
| `run.py` | Yes — LLM proposes strategies |
| `discover_strategies.py` | Yes — LLM scans IRC sections |
| `parse_return.py` | Yes — LLM extracts profile from PDF |
| `chart.py` | No — reads results locally |
| `generate_report.py` | No — reads results locally |
| `find_loopholes.py` | No — pure calculator math |
| `parse_tax_code.py` | No — downloads/parses XML |
| `tax_calculator.py` | No — deterministic computation |

**Logs:** Every run creates a timestamped log file in `logs/` (e.g., `logs/openloopholes_20260401_152345.log`). Contains all console output plus debug details (LLM calls, response times, errors). Useful for troubleshooting.

## Current Limitations

- **State coverage**: Only Utah state strategies are implemented. Federal strategies work for all US taxpayers, but state-specific strategies (PTET elections, state credits, state deductions) are only available for Utah. Adding a state = adding strategy JSON files with `"jurisdiction": "state:XX"`.
- **Tax code corpus**: We have the IRC (Title 26) — the statutory law. We do NOT yet have Treasury Regulations (26 CFR), Revenue Rulings, Private Letter Rulings, or Tax Court opinions. The IRC is ~20% of what matters for discovering novel strategies.
- **Discovery approach**: The current discovery engine scans IRC sections individually. It finds strategies within a single section but does not systematically search for cross-section interactions — which is where the most novel loopholes live.
- **Calculator precision**: 71 strategies have dedicated calculator handlers. The remaining 1,383 use generic pattern-based handlers that approximate the tax effect by category (exclusion, deduction, credit, deferral). Dedicated handlers are more accurate.
- **PDF parsing**: The tax return parser is a prototype. Complex multi-page returns with many K-1s may have extraction errors. Always verify the output profile against your actual return.

## Roadmap

### V2: Full Legal Corpus
Expand beyond the IRC to include the full tax authority stack:
- **Treasury Regulations (26 CFR)** — the IRS's interpretation of the code, often 3-5x longer than the IRC itself. Available as structured XML from ecfr.gov.
- **Revenue Rulings & Procedures** — IRS guidance on specific situations
- **Private Letter Rulings (PLRs)** — IRS responses to individual taxpayer questions. Gold mines for edge cases.
- **Tax Court opinions** — judicial interpretations that create precedent

### V3: Cross-Section Discovery Engine
The real loopholes emerge from interactions between IRC sections, not from reading any single section. The V3 architecture:

1. **Knowledge graph** — build a graph where nodes are IRC sections and edges are cross-references. The IRC constantly references itself ("as described in section 179(d)(1)..."). These are explicit graph edges.
2. **Interaction discovery loop** — for each pair of cross-referenced sections, ask: "Does the interaction between Section X and Section Y create any tax benefit that would not exist from either section alone?"
3. **Validation against authority** — check candidate strategies against Treasury Regs, Revenue Rulings, and Tax Court cases. The absence of authority closing a gap is the signal that a novel strategy exists.
4. **Continuous learning** — as new legislation passes, new regulations are issued, or new court opinions drop, the system re-runs discovery across affected sections.

### All 50 States
Add state-specific strategy files for all 50 states. Each state has its own PTET rules, credits, deductions, and rate structures. Priority: CA, TX, NY, FL (covers ~40% of filers).

### Dedicated Calculator Handlers
Add precise calculator handlers for the highest-impact discovered strategies, replacing the generic pattern-based approximations.

## License

MIT — see [LICENSE](LICENSE) for full terms including tax disclaimer.

## Disclaimer

This software provides **educational information only** about tax strategies based on the Internal Revenue Code. It does **not** constitute tax, legal, or accounting advice.

- Every strategy must be verified by a qualified CPA, Enrolled Agent, or tax attorney
- Tax law is complex, changes frequently, and varies by individual circumstances
- Strategies identified by this software may not apply to your specific situation
- You are solely responsible for your tax filings and any decisions made based on this software

The authors and contributors of OpenLoopholes accept no liability for any tax penalties, interest, or other consequences arising from the use of this software.
