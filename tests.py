import glob
import json
from pathlib import Path
from pprint import pprint

from pdf_parser import parse


def parse_to_json(pdf_filename: Path, output_filename: Path | None = None):
    if output_filename is None:
        output_filename = pdf_filename.with_suffix(".json")
    pdf = parse(pdf_filename)
    json_pdf = pdf.to_json()
    with open(output_filename, "w") as fh:
        json.dump(json_pdf, fh, indent=4)   


def get_all_pdfs(input_dir: Path):
    test_inputs = input_dir.glob("*.pdf")
    return test_inputs


def retest_selection(selection_dir: Path, input_dir: Path, success_dir: Path, fail_dir: Path):
    files_to_test = []
    for old_file in selection_dir.glob("*"):
        old_file.unlink()
        pdf_filename = input_dir / old_file.with_suffix(".pdf").name
        files_to_test.append(pdf_filename)

    test_list(files_to_test, success_dir, fail_dir)
    
    for pdf in files_to_test:
        parse_to_json(pdf, output_successes / pdf.with_suffix(".json").name)


def test_list(test_inputs, success_dir: Path, fail_dir: Path, skip_done):
    for pdf in test_inputs:
        test_and_sort_result(pdf, success_dir, fail_dir, skip_done)


def test_and_sort_result(pdf: Path, success_dir: Path, fail_dir: Path, skip_done):
    """
    Attempt to parse the PDF to JSON.
     Place a success json file in the success directory
       or a failure txt file in the failure directory.
    """
    success_output = success_dir / pdf.with_suffix(".json").name
    fail_output = fail_dir / pdf.with_suffix(".txt").name
    if success_output.exists():
        if skip_done:
            return
        success_output.unlink()
    if fail_output.exists():
        fail_output.unlink()
    
    try:
        parse_to_json(pdf, success_output)
        print(f"✅ PASS: {pdf}")
    except Exception as e:
        with open(fail_output, "w") as fh:
            fh.write(f"{e}\n")
            fh.write(f"Exception type: {type(e)}\n")
            if hasattr(e, "__notes__"):
                fh.write(f"-------- NOTES --------\n")
                for note in e.__notes__:
                    fh.write(f"{note}\n")
            fh.write("\n")
        print(f"❌ FAIL: {pdf}")


def test_all(testing_dir: Path, success_dir: Path, fail_dir: Path, skip_done=False):
    """
    Test all PDFs in the testing directory.
    """
    if not skip_done:
        # Empty directories
        for file in output_successes.glob("*"):
            file.unlink()
    for file in output_failures.glob("*"):
        file.unlink()
    test_list(get_all_pdfs(testing_dir), success_dir, fail_dir, skip_done)



if __name__ == '__main__':

    testing_resources = Path("testing_resources/")

    input_directory = testing_resources / Path("test_pdfs/")
    output_successes = testing_resources / Path("successes/")
    output_failures = testing_resources / Path("failures/")

    # Create directories
    output_successes.mkdir(exist_ok=True, parents=True)
    output_failures.mkdir(exist_ok=True, parents=True)

    test_all(input_directory, output_successes, output_failures, skip_done=True)
