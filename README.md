# pdf-analysis

A pure-python parser for PDF files.

## CLI: pdf-to-json

Convert a PDF into a structured JSON representation.

Usage:

```bash
python pdf-to-json.py <pdf_filename> [output_filename]
```

- **pdf_filename**: Path to the input PDF.
- **output_filename** (optional): Path to write JSON. If omitted, a `.json` file is created next to the PDF (same name).

Examples (PowerShell / cmd):

```bash
# Write alongside the PDF as report.json
python pdf-to-json.py .\testing_resources\test_pdfs\report.pdf

# Specify an explicit output path
python pdf-to-json.py .\testing_resources\test_pdfs\report.pdf .\testing_resources\test_pdfs\report.parsed.json
```

Notes:
- The script reads the PDF, parses it via `pdf_parser.parse`, and writes pretty-printed JSON (`indent=4`).
- Both arguments are positional; there are no flags. Use `python pdf-to-json.py -h` for the auto-generated help.

