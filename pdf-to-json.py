import json
from pathlib import Path
from pdf_parser import parse, decompress
from argparse import ArgumentParser

def parse_to_json(pdf_filename: Path, output_filename: Path | None = None, do_decompress: bool = False):
    if output_filename is None:
        output_filename = pdf_filename.with_suffix(".json")
    pdf = parse(pdf_filename)
    if do_decompress:
        streams_dir = output_filename.parent / f"{output_filename.stem}_streams"
        streams_dir.mkdir(parents=True, exist_ok=True)
        pdf = decompress(pdf, streams_dir)
    json_pdf = pdf.to_json()
    with open(output_filename, "w") as fh:
        json.dump(json_pdf, fh, indent=4)    


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("pdf_filename", type=Path)
    parser.add_argument("output_filename", type=Path, nargs="?", default=None)
    parser.add_argument("--decompress", action="store_true", help="Decompress streams to files before writing JSON")
    
    args = parser.parse_args()
    parse_to_json(args.pdf_filename, args.output_filename, args.decompress)
