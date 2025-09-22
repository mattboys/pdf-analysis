from textwrap import fill

from pdf_parser import *

DIVISIONS = 70 * 30
WRAP_LEN = 70


def chart_content(pdf: PdfDoc):
    output = ""
    key = {}
    errors = []
    division_size = pdf.b_size / DIVISIONS
    for obj in pdf.data:
        s = int(obj.b_size / division_size)
        if s == 0:
            continue

        if type(obj) in [PdfHeader, PdfComment]:
            output += "🟩" * s
            key["🟩"] = "Comment"
        elif type(obj) in [PdfWhitespaces]:
            output += "⬜" * s
            key["⬜"] = "Whitespace"
        elif type(obj) in [PdfCrossReferenceTable, PdfTrailerDict, PdfCrossRefOffset, PdfEndOfFileMarker]:
            output += "🟥" * s
            key["🟥"] = "Data Index"
        elif type(obj) in [PdfIndirectObj]:
            in_obj = obj.data["object"]
            if type(in_obj) in [PdfStream]:
                output += "🟫" * s
                key["🟫"] = "Compressed"
            elif type(in_obj) in [PdfList]:
                output += "🟪" * s
                key["🟪"] = "List"
            elif type(in_obj) in [PdfNumber, PdfBool, PdfNull, PdfHexadecimalString]:
                output += "🟦" * s
                key["🟦"] = "Primitive"
            elif type(in_obj) in [PdfWhitespaces]:
                output += "⬜" * s
                key["⬜"] = "Whitespace"
            elif type(in_obj) in [PdfDict]:
                for name in in_obj.data:
                    if name.data == "Type":
                        in_type = in_obj.data[name].data
                        if in_type in ["Catalog"]:
                            output += "🔴" * s
                            key["🔴"] = "Catalog"
                        elif in_type in ["Outlines", "Pages"]:
                            output += "🟣" * s
                            key["🟣"] = "Document Structure"
                        elif in_type in ["Page"]:
                            output += "🔵" * s
                            key["🔵"] = "Page"
                        elif in_type in ["Font", "FontDescriptor"]:
                            output += "🟤" * s
                            key["🟤"] = "Font"
                        else:
                            output += "🟡" * s
                            key["🟡"] = "Other indirect data"
                            errors.append(f"Dict->Type:{in_type}")
                        break
                    if name.data == "Filter":
                        output += "🟠" * s
                        key["🟠"] = "Compressed Data"
                        break
                    if name.data == "Length":
                        output += "⚫" * s
                        key["⚫"] = "Stream Data"
                        break
                    if name.data == "Creator":
                        output += "🟢" * s
                        key["🟢"] = "Author info"
                        break
                else:
                    output += "🟨" * s
                    # key["🟨"] = "Unspecified Dict"
                    errors.append(f"🟨 Unspecified Dict with content: {in_obj.data}")
            else:
                errors.append(f"{type(in_obj)}")
        else:
            errors.append(f"{type(obj)}")
    print(fill(output, WRAP_LEN))
    print("KEY:")
    for k, v in key.items():
        print(f"  {k}\t{v}")
    print("")
    if errors:
        print("ERRORS:")
    for e in errors:
        print(f"? {e}")


if __name__ == "__main__":
    chart_content(parse('test_pdfs/batch_1/sample2.pdf'))
