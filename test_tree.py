from pdf_parser import parse


pdf = parse("testing_resources\\test_pdfs\\000006.pdf")
print(pdf.types_tree())
