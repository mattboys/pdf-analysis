import json
from pathlib import Path
from pdf_parser import parse
from argparse import ArgumentParser

def parse_to_json(pdf_filename: Path, output_filename: Path | None = None):
    if output_filename is None:
        output_filename = pdf_filename.with_suffix(".json")
    pdf = parse(pdf_filename)
    json_pdf = pdf.to_json()
    with open(output_filename, "w") as fh:
        json.dump(json_pdf, fh, indent=4)    


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("pdf_filename", type=Path)
    parser.add_argument("output_filename", type=Path, nargs="?", default=None)
    args = parser.parse_args()
    parse_to_json(args.pdf_filename, args.output_filename)
