import base64
import json
import os.path
import pprint
import re
import zlib
from pathlib import Path
# import os
# import codecs
import sys
import typing
from typing import Optional, Type, Any
from io import BufferedReader

# from pprint import pprint

VERBOSE = False

test_file = "test_pdfs/batch_1/dummy.pdf"

WHITESPACE = b"[ \r\n\t\x0c\x00]"
LINEBREAK = b'(\r\n|[\r\n])'
py_native_types = int | float | bool | str | bytes | list | set | dict | tuple | None


def list_bytes(b: bytes) -> list[bytes]:
    return [b[i:i + 1] for i in range(len(b))]


def cls(class_name):
    if isinstance(class_name, str):
        return getattr(sys.modules[__name__], class_name)
    else:
        return class_name


def decode_int(numeric_bytes):
    return int(numeric_bytes.decode('utf-8'))


class PdfObj:
    Pattern: Optional[re.Pattern] = None
    Trivial = False

    def __init__(self, raw_data: bytes, b_start: int = 0, parent: Optional['PdfObj'] = None):
        self.raw = raw_data
        self.b_start = b_start
        self.parent = parent
        self.data: Any = None
        self.b_size = len(raw_data)
        self.convert()
        self.report()

    def count_parents(self) -> int:
        if self.parent is None:
            return 0
        else:
            return self.parent.count_parents() + 1

    def report(self, finished=False):
        if VERBOSE:
            if not self.Trivial:  # isinstance(self, (PdfWhitespaces, PdfLiteralStringOther)):
                if isinstance(self, NestablePdfObj) and not finished:
                    print(
                        " " * self.count_parents()
                        + f"{self.b_start:>08x} "
                        + f"{self.__class__.__name__ + '()':<25} "
                        + "..."
                    )
                else:
                    print(
                        " " * self.count_parents()
                        + f"{self.b_start:>08x} "
                        + f"{self.__class__.__name__ + '()':<25} "
                        + f"{self.__repr__()}"
                    )

    @classmethod
    def match(cls, next_bytes: bytes) -> tuple[bool, int]:
        """ Return the number of characters that match the class' Pattern (or 0 if no match) """
        # print(f"Checking {cls.__name__} for a match of {cls.Pattern} against {next_bytes[:4]}")
        assert cls.Pattern is not None, f"{cls.__name__} does not have a Pattern to match in match()"
        match = cls.Pattern.match(next_bytes)
        if match is None:
            return False, 0
        else:
            # print(f"Matched {cls.Pattern} to {next_bytes} with the result {match.group()}")
            return True, len(match.group())

    def __repr__(self):
        return f"{self.data}"

    def convert(self):
        pass

    def get_structure_location(self, get_full=True):
        if get_full and self.parent is not None:
            return self.parent.get_structure_location() + "." + self.__class__.__name__
        else:
            return self.__class__.__name__

    def to_json(self) -> py_native_types:
        """
        Convert data to a JSON encodable python object
        """
        def convert_to_python_type(in_data):
            if isinstance(in_data, PdfObj):
                return convert_to_python_type(in_data.to_json())
            elif isinstance(in_data, dict):
                for k, v in in_data.items():
                    if not isinstance(convert_to_python_type(k), typing.Hashable):
                        print(f"Cannot hash the dict key: {convert_to_python_type(k)}")
                return dict((convert_to_python_type(k), convert_to_python_type(v)) for k, v in in_data.items())
            elif isinstance(in_data, list):
                return list(convert_to_python_type(k) for k in in_data)
            elif isinstance(in_data, tuple):
                return tuple(convert_to_python_type(k) for k in in_data)
            elif isinstance(in_data, bytes):
                return base64.b64encode(in_data).decode('utf-8')
            else:
                return in_data

        return convert_to_python_type(self.data)


class NestablePdfObj(PdfObj):
    Contexts: list[Type[PdfObj]] = []
    EndingPattern: Optional[re.Pattern] = None

    def get_contexts(self):
        return [cls(c) for c in self.Contexts]

    # def __init_subclass__(cls, **kwargs):
    #     print(f"Creating subclass for: {cls.__name__}")
    #     for i, c in enumerate(cls.get_contexts()):
    #         if isinstance(c, str):
    #             if cls.__name__ == c:
    #                 cls.get_contexts()[i] = cls
    #             else:
    #                 cls.get_contexts()[i] = getattr(sys.modules[__name__], c)

    def match_end(self, next_bytes: bytes) -> tuple[bool, int]:
        assert self.EndingPattern is not None, f"{self.__class__.__name__} is missing an EndingPattern"
        match = self.EndingPattern.match(next_bytes)
        if match is None:
            return False, 0
        else:
            return True, len(match.group())

    def convert(self):
        self.data = []

    def add(self, child_obj: PdfObj) -> PdfObj:
        if isinstance(child_obj, PdfWhitespaces):
            return self
        else:
            if isinstance(self.data, list):
                self.data.append(child_obj)
            return self.get_next(child_obj)

    def get_next(self, child_obj):
        if isinstance(child_obj, NestablePdfObj):
            return child_obj
        else:
            return self

    def finish(self, next_bytes: bytes, pos: int):
        self.report(finished=True)
        self.b_size = pos + len(next_bytes) - self.b_start
        return self.parent


class PdfName(PdfObj):
    Pattern = re.compile(rb'/[^/ \r\n\t\x0c\x00\[\]<>()]+')

    def convert(self):
        # print(self.raw)
        self.data = self.raw[1:].decode('utf-8')  # TODO: Replace slash characters


class PdfHexadecimalString(PdfObj):
    """ See 7.3.4.3 """
    Pattern = re.compile(rb'<([0-9a-fA-F]*)>')

    def convert(self):
        self.data = self.Pattern.match(self.raw).group(1).decode('utf-8')


class PdfNumber(PdfObj):
    Pattern = re.compile(rb'[+-]?\d*\.?\d')

    def convert(self):
        self.data = self.raw.decode('utf-8')


class PdfHeader(PdfObj):
    Pattern = re.compile(rb"%PDF-([12]\.\d)")

    def convert(self):
        version = self.Pattern.match(self.raw).group(1)
        self.data = f"Version from header: {version.decode('utf-8')}"


class PdfComment(PdfObj):
    Pattern = re.compile(rb"%(?!PDF|%EOF)(.*)" + LINEBREAK)

    def convert(self):
        try:
            self.data = self.raw.decode('utf-8').lstrip("%").rstrip()
        except UnicodeDecodeError:
            self.data = self.raw

        # def decode(b):
        #     try:
        #         return b.decode('utf-8')
        #     except UnicodeDecodeError:
        #         return "?"
        #
        # self.data = "".join([decode(b) for b in list_bytes(self.raw)]).rstrip().lstrip("%")


class PdfWhitespaces(PdfObj):
    Pattern = re.compile(rb"[ \r\n\t\x0c\x00]+")
    Trivial = True

    def convert(self):
        self.data = ""
        decoder = {
            b' ': "SP",
            b'\r': "CR",
            b'\n': "LF",
            b'\t': "TB",
            b'\x0c': "FF",
            b'\x00': "NUL",
        }
        self.data = " ".join([decoder.get(b, "?") for b in list_bytes(self.raw)])


class PdfLinebreak(PdfObj):
    Pattern = re.compile(rb"([\r\n]|\r\n)+")
    Trivial = True


class PdfBool(PdfObj):
    Pattern = re.compile(rb"true|false")

    def convert(self):
        match = self.Pattern.match(self.raw).group()
        if match == b'true':
            self.data = True
        elif match == b'false':
            self.data = False


class PdfStramData(PdfObj):
    Pattern = re.compile(rb'.*', re.DOTALL)
    Trivial = True

    def convert(self):
        self.data = self.raw


class PdfStream(NestablePdfObj):
    # Pattern = re.compile(rb"stream" + LINEBREAK + b"(.*?)" + b"endstream" + LINEBREAK, re.DOTALL)
    Pattern = re.compile(rb"stream" + LINEBREAK)
    Contexts = [PdfStramData]
    EndingPattern = re.compile(rb"(.*?)endstream" + LINEBREAK, re.DOTALL)

    def add(self, child_obj: PdfObj) -> PdfObj:
        self.data += child_obj.data
        return self

    def finish(self, next_bytes: bytes, pos: int):
        self.data += self.EndingPattern.match(next_bytes).group(0)
        self.b_size = pos + len(next_bytes) - self.b_start
        self.report()
        return self.parent

    def convert(self):
        self.data = b""

    def __repr__(self):
        return f"{len(self.data)} bytes of stream data: {self.data[:10]} ... {self.data[-10:]}"


class PdfReference(PdfObj):
    Pattern = re.compile(rb'(\d+) (\d+) R')

    def convert(self):
        match = self.Pattern.match(self.raw)
        self.data = f"R {decode_int(match.group(1))} {decode_int(match.group(2))}"
        # (
        #     decode_int(match.group(1)),
        #     decode_int(match.group(2)),
        # )


class PdfNull(PdfObj):
    Pattern = re.compile(rb"null")


class PdfLiteralStringParenthesis(PdfObj):
    Pattern = re.compile(rb'[)(]')
    Trivial = True

    def convert(self):
        self.data = self.Pattern.match(self.raw).group()  # .decode('utf-8')


class PdfLiteralStringEscape(PdfObj):
    """ See 7.3.4.2 - Table 3
    """
    Pattern = re.compile(rb'(\\[nrtbf)(\\])|(\\\d{1,3})')
    Trivial = True

    #
    # @classmethod
    # def match(cls, next_bytes: bytes) -> (bool, int):
    #     """ Return the number of characters that match the class' Pattern (or 0 if no match) """
    #     print(f"Matching {next_bytes}\n against {cls.Pattern}")
    #     match = cls.Pattern.match(next_bytes)
    #     print(match)
    #     return super().match(next_bytes)

    def convert(self):
        # print(self.raw)
        code = self.Pattern.match(self.raw).group()  # .decode('utf-8')
        code = code[1:]
        if code.decode('utf-8').isnumeric():
            self.data = chr(int(code, 8)).encode("utf-8")
        else:
            conversion = {
                b"n": b"\n",
                b"r": b"\r",
                b"t": b"\t",
                b"b": b'\x08',  # BACKSPACE
                b"f": b"\f",
                b"(": b"(",
                b")": b")",
                b"\\": b"\\",
            }
            self.data = conversion[code]


class PdfLiteralStringOther(PdfObj):
    Pattern = re.compile(rb'.', re.DOTALL)
    Trivial = True

    def convert(self):
        # print(self.raw)
        self.data = self.Pattern.match(self.raw).group()  # .decode('utf-8')


# TODO Stings
class PdfLiteralString(NestablePdfObj):
    """ See 7.3.4.2 """
    Pattern = re.compile(rb"\(")
    EndingPattern = re.compile(rb"\)")
    Contexts = [PdfLiteralStringParenthesis, PdfLiteralStringEscape, PdfLiteralStringOther]

    def __init__(self, *args):
        super().__init__(*args)
        self._unpaired_parenthesis = 0
        self.data = b""

    def match_end(self, next_bytes: bytes) -> tuple[bool, int]:
        if self._unpaired_parenthesis > 0:
            return False, 0
        else:
            return super().match_end(next_bytes)

    def add(self, child_obj: PdfObj) -> PdfObj:
        self.data += child_obj.data
        if isinstance(child_obj, PdfLiteralStringParenthesis):
            if child_obj.data == b"(":
                self._unpaired_parenthesis += 1
            elif child_obj.data == b")":
                self._unpaired_parenthesis -= 1
                if self._unpaired_parenthesis < 0:
                    print("ERROR: String literal contains unbalanced unescaped parenthesis.")
                    self._unpaired_parenthesis = 0
            else:
                assert False, "Unrecognised character"
        return self.get_next(child_obj)

    def finish(self, next_bytes: bytes, pos: int):
        try:
            self.data = self.data.decode('utf-8')
        except UnicodeDecodeError:
            # Encrypted string so leave as bytes
            pass
        return super().finish(next_bytes, pos)


class PdfList(NestablePdfObj):
    Pattern = re.compile(rb"\[")
    EndingPattern = re.compile(rb"]")
    Contexts = [PdfLiteralString, PdfBool, PdfWhitespaces, PdfName, PdfReference, PdfNumber, PdfHexadecimalString,
                PdfNull, "PdfList", "PdfDict"]


class PdfDict(NestablePdfObj):
    Pattern = re.compile(rb"<<")  # + LINEBREAK + b"*")
    EndingPattern = re.compile(rb">>")  # + LINEBREAK + b"*")
    Contexts = [PdfLiteralString, PdfBool, PdfWhitespaces, PdfName, PdfReference, PdfNumber, PdfHexadecimalString,
                PdfList, PdfNull, "PdfDict"]

    def __init__(self, *args):
        super().__init__(*args)
        self._unpaired_key: Optional[PdfObj] = None
        self.data = {}

    def add(self, child_obj: PdfObj):
        if isinstance(child_obj, PdfWhitespaces):
            return self
        if self._unpaired_key is None:
            self._unpaired_key = child_obj
        else:
            self.data[self._unpaired_key] = child_obj
            self._unpaired_key = None
        return self.get_next(child_obj)


class PdfIndirectObj(NestablePdfObj):
    """ See: 7.3.10 """
    Contexts = [PdfBool, PdfDict, PdfStream, PdfList, PdfWhitespaces, PdfNumber, PdfNull, PdfHexadecimalString,
                PdfName, PdfLiteralString]
    Pattern = re.compile(rb'(\d+)' + WHITESPACE + rb'(\d+) obj')
    EndingPattern = re.compile(rb'endobj' + WHITESPACE + b'*' + LINEBREAK)

    def convert(self):
        match = self.Pattern.match(self.raw)
        self.data: Any = {
            # "reference": (decode_int(match.group(1)), decode_int(match.group(2))),
            "reference": f"R {decode_int(match.group(1))} {decode_int(match.group(2))}",
            "object": None,
            # "data stream": None,
        }

    def add(self, child_obj: PdfObj) -> PdfObj:
        if isinstance(child_obj, PdfStream):
            assert "data stream" not in self.data, "Reference Object should not have multiple data streams"
            self.data["data stream"] = child_obj
        elif isinstance(child_obj, PdfWhitespaces):
            pass
        else:
            assert self.data["object"] is None, (f"Reference Object should not have multiple objects "
                                                 f"{self.data['reference']}")
            self.data["object"] = child_obj
        return self.get_next(child_obj)


class PdfCrossReferenceTableSpec(PdfObj):
    Pattern = re.compile(rb"(\d+) (\d+) *" + LINEBREAK)
    Trivial = True

    def convert(self):
        m = self.Pattern.match(self.raw)
        self.data = {
            "object number of first entry": decode_int(m.group(1)),
            "number of entries": decode_int(m.group(2)),
        }


class PdfCrossReferenceTableEntry(PdfObj):
    Pattern = re.compile(rb"(\d{10}) (\d{5}) ([nf])" + WHITESPACE + b'*' + LINEBREAK)
    Trivial = True

    def convert(self):
        m = self.Pattern.match(self.raw)
        self.data = {
            "byte offset": decode_int(m.group(1)),
            "generation number": decode_int(m.group(2)),
            "in-use": m.group(3) == b'n'
        }


class PdfCrossReferenceTable(NestablePdfObj):
    """ See 7.5.4 """
    Contexts = [PdfCrossReferenceTableSpec, PdfCrossReferenceTableEntry]
    Pattern = re.compile(rb'xref' + LINEBREAK)
    EndingPattern = re.compile(rb'trailer')

    def match_end(self, next_bytes: bytes) -> tuple[bool, int]:
        return super().match_end(next_bytes)[0], 0


class PdfCrossRefOffset(PdfObj):
    """ See 7.5.5 """
    Pattern = re.compile(rb'startxref' + LINEBREAK + rb'(\d+?)' + WHITESPACE + b'*' + LINEBREAK)

    def convert(self):
        self.data = decode_int(self.Pattern.match(self.raw).group(2))


class PdfEndOfFileMarker(PdfObj):
    Pattern = re.compile(rb'%%EOF' + LINEBREAK)

    def convert(self):
        self.data = self.raw.decode("utf-8")


class PdfTrailerDict(NestablePdfObj):
    """ See 7.5.5 """
    Pattern = re.compile(rb'trailer' + LINEBREAK)
    EndingPattern = re.compile(rb'%%EOF')
    Contexts = [PdfDict, PdfCrossRefOffset, PdfWhitespaces]

    def finish(self, next_bytes: bytes, pos: int):
        self.add(PdfEndOfFileMarker(next_bytes, pos, self))
        return super().finish(next_bytes, pos)


class PdfDoc(NestablePdfObj):
    Contexts = [PdfHeader, PdfComment, PdfIndirectObj, PdfWhitespaces, PdfCrossReferenceTable, PdfTrailerDict,
                PdfCrossRefOffset, PdfEndOfFileMarker]

    def match_end(self, next_bytes: bytes):
        return len(next_bytes) == 0, 0


def test_regex(pdf_obj: PdfObj, sample_text):
    reg = pdf_obj.Pattern
    print(f"Searching for {reg}")
    print(f"in sample {sample_text}")
    matches = re.match(reg, sample_text)
    if matches is None:
        print("No matches")
    else:
        print(f"Found: {matches.group()}")


class ParseError(Exception):
    pass


def parse(filename) -> PdfDoc:
    file_size = os.path.getsize(filename)
    pdf = PdfDoc(b"")
    current = pdf
    with open(filename, "rb") as fh:
        fh: BufferedReader
        while current:
            # Get the next section of the buffer
            pos = fh.tell()
            peek = fh.peek()
            # Get more buffer if running low
            if len(peek) < 1024:
                peek = fh.read()
                peek += fh.read()
                fh.seek(pos)
            print(f"{pos}/{file_size}\t", end="\r")
            # if pos == prev_pos:
            #     assert False, f"Not seeking error at {pos}"
            # prev_pos = pos

            matched_end, read_length = current.match_end(peek)
            if matched_end:
                current = current.finish(fh.read(read_length), pos)
            else:
                for next_class in current.get_contexts():
                    # next_class: Type[PdfObj]
                    matched, read_length = next_class.match(peek)
                    if matched:
                        current = current.add(next_class(fh.read(read_length), pos, current))
                        break
                else:
                    e = ParseError(f"Could not parse symbols at byte position {pos:x} for file {filename}")
                    e.add_note(f"Byte position:   {pos:x}")
                    e.add_note(f"Current context: {current.get_structure_location()}")
                    e.add_note(f"Current data: {current.data}")
                    e.add_note(f"{'Buffer':<25} {fh.peek()[:20]}")
                    e.add_note(f"Possible matches:")
                    for next_class in current.get_contexts():
                        next_class = cls(next_class)
                        e.add_note(f"{next_class.__name__:<25} {next_class.Pattern.pattern}")
                    raise e
                    # current = None
        if len(fh.peek()) != 0:
            raise ParseError(f"Ended before the end of the file! Buffer position is: {fh.tell()}").add_note(
                f"Next data: {fh.peek()[:20]}"
            )
    return pdf

def decompress(pdf: PdfObj, save_dir):
    for p in pdf.data:
        if isinstance(p, PdfIndirectObj):
            if "data stream" in p.data:
                out_fn = save_dir / Path(f"{p.data['reference']}.bin")

                filter = None
                for pdf_key, pdf_value in p.data["object"].data.items():
                    if pdf_key.data == "Filter":
                        filter = pdf_value.data
                        break
                
                if filter == "FlateDecode":
                    
                    print(f"Decoding with FlateDecode to {out_fn}")
                    with open(out_fn, "wb") as fh:
                        fh.write(zlib.decompress(p.data["data stream"].data))
                    p.data["data stream"] = out_fn.as_posix()
                # elif filter == b"ASCIIHexDecode":
                #     p.data["data stream decompressed"] = ascii_hex_decode(p.data["data stream"].data)
                # elif filter == b"ASCII85Decode":
                #     p.data["data stream decompressed"] = ascii85_decode(p.data["data stream"].data)
                # elif filter == b"LZWDecode":
                #     p.data["data stream decompressed"] = lzw_decode(p.data["data stream"].data) 
                elif filter is None:
                    print("Decoding without filter")
                    out_fn = out_fn.with_suffix(".txt")
                    with open(out_fn, "wb") as fh:
                        fh.write(p.data["data stream"].data)
                    p.data["data stream"] = out_fn.as_posix()
                else:
                    print(f"Decompressing with filter {filter} is not implemented.")
    return pdf

if __name__ == "__main__":
    
    test_file = "test_pdfs/test01.pdf"
    out_dir = Path("test_pdfs/test01_decompressed")
    out_dir.mkdir(exist_ok=True)
    for old_file in Path(out_dir).glob("*"):
        old_file.unlink()
    pdf = parse(test_file)
    pdf = decompress(pdf, out_dir)
    with open(out_dir / "test01_decompressed.json", "w") as fh:
        json.dump(pdf.to_json(), fh, indent=4)


    #
    # test = PdfList(b"", 0, None)
    # for c in test.get_contexts():
    #     print(f"{c}, {type(c)}")
    # test_regex(PdfWhitespace, b"   hello\nworld\n")

    # with open(test_file, "rb") as fh:
    #     pdf_doc = PdfDoc.read(fh)
    # print(pdf_doc)
