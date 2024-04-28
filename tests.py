import glob
import json
from pathlib import Path

from reader import parse

test_files = Path("test_pdfs/")
successes = Path("successes/")
if not successes.is_dir():
    successes.mkdir()
fails = Path("fails/")
if not fails.is_dir():
    fails.mkdir()


def parse_to_json(pdf_filename: Path):
    success_output = successes / pdf_filename.with_suffix(".json").name
    fail_output = fails / pdf_filename.with_suffix(".txt").name
    try:
        pdf = parse(pdf_filename)
        json_pdf = pdf.to_json()
        with open(success_output, "w") as fh:
            json.dump(json_pdf, fh, indent=4)
    except Exception as e:
        with open(fail_output, "w") as fh:
            fh.write(f"{e}\n")
            fh.write(f"Exception type: {type(e)}\n")
            if hasattr(e, "__notes__"):
                fh.write(f"-------- NOTES --------\n")
                for note in e.__notes__:
                    fh.write(f"{note}\n")
            fh.write("\n")


def test_all():
    test_inputs = glob.glob("test_pdfs/batch* /*.pdf")
    test_list(test_inputs)


def test_to_file():
    # test_inputs = glob.glob("test_pdfs/*.pdf")
    for old_file in successes.glob("*.json"):
        old_file.unlink()
    for old_file in fails.glob("*.txt"):
        old_file.unlink()

    for pdf in Path("test_pdfs").glob("*.pdf"):
        parse_to_json(pdf)


def test_fails():
    files_to_test = []
    for old_file in fails.glob("*.txt"):
        old_file.unlink()
        pdf_filename = test_files / old_file.with_suffix(".pdf").name
        files_to_test.append(pdf_filename)
    for pdf in files_to_test:
        parse_to_json(pdf)


def test_list(test_inputs):
    pass_list = []
    fail_list = []
    for pdf in test_inputs:
        try:
            parse(pdf)
            print(f"PASS: {pdf}")
            pass_list.append(pdf)
        except Exception as e:
            print(f"FAIL: {pdf}")
            fail_list.append((pdf, e))
    print("")
    print(f"RESULTS:")
    print(f"\t{len(fail_list)} errors.")
    for pdf, e in fail_list:
        print(f"\t\t{pdf}")
        print(f"\t\t\t{e}")
    print(f"\t{len(pass_list)}/{len(test_inputs)} passed")


if __name__ == '__main__':
    test_fails()
    # test_to_file()
