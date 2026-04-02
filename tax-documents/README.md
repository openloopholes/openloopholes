# Tax Documents

Place your tax return PDFs and supporting documents here.

**This entire directory is gitignored.** Your documents will never be committed to version control.

## Supported Files
- Tax return PDFs (1040, K-1s, W-2s, 1099s, etc.)
- Any supporting documents for the PDF parser

## Usage
```bash
cd loop-runner
python3 parse_return.py ../tax-documents/your-return.pdf --output profiles/your-name.json
```

The parser will extract your financial data into a structured JSON profile that the optimizer can use.
