import glob

from reader import parse


def test_all():
    test_inputs = glob.glob("test_pdfs/batch_2/*.pdf")
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
    test_all()
    # parse('test_pdfs\TestPDFfile.pdf')
    # parse('test_pdfs\sample.pdf')

