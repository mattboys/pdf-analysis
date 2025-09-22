# pdf-analysis

A pure-python parser for PDF files.

## CLI: pdf-to-json

Convert a PDF into a structured JSON representation.

Usage:

```bash
python pdf-to-json.py <pdf_filename> [output_filename] [--decompress]
```

- **pdf_filename**: Path to the input PDF.
- **output_filename** (optional): Path to write JSON. If omitted, a `.json` file is created next to the PDF (same name).
- **--decompress** (optional): Decompresses stream objects to files in a directory named `<output_stem>_streams` before writing JSON; references in JSON will point to those files.

Examples (PowerShell / cmd):

```bash
# Write alongside the PDF as report.json
python pdf-to-json.py .\testing_resources\test_pdfs\report.pdf

# Specify an explicit output path
python pdf-to-json.py .\testing_resources\test_pdfs\report.pdf .\testing_resources\test_pdfs\report.parsed.json

# Decompress embedded streams to files alongside the JSON
python pdf-to-json.py .\testing_resources\test_pdfs\report.pdf .\testing_resources\test_pdfs\report.parsed.json --decompress
```

Notes:
- The script reads the PDF, parses it via `pdf_parser.parse`, and writes pretty-printed JSON (`indent=4`).
- Use `python pdf-to-json.py -h` for the auto-generated help.

