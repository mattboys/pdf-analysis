import re
# import os
# import codecs
import sys
from typing import Optional, Type, Any
from io import BufferedReader
from pprint import pprint

test_file = "test.pdf"

WHITESPACE = b"[ \r\n\t\x0c\x00]"
LINEBREAK = b'(\r\n|[\r\n])'


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

    def __init__(self, raw_data: bytes, b_start: int = 0, parent: Optional['PdfObj'] = None):
        self.raw = raw_data
        self.b_start = b_start
        self.parent = parent
        self.data: Any = None
        self.b_size = len(raw_data)
        self.convert()
        if not isinstance(self, (PdfWhitespaces, PdfLiteralStringOther) ) :
            print(f"{self.b_start:>8}: {self.__class__.__name__ + '()':<20} '{self.data}'")

    @classmethod
    def match(cls, next_bytes: bytes) -> (bool, int):
        """ Return the number of characters that match the class' Pattern (or 0 if no match) """
        # print(f"Checking {cls.__name__} for a match of {cls.Pattern} against {next_bytes[:4]}")
        assert cls.Pattern is not None, f"{cls.__name__} does not have a Pattern to match in match()"
        match = cls.Pattern.match(next_bytes)
        if match is None:
            return False, 0
        else:
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

    def match_end(self, next_bytes: bytes) -> (bool, int):
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
        print(f"{self.b_start:>8}: {self.__class__.__name__ + '()':<20} '{self.data}'")
        self.b_size = pos + len(next_bytes) - self.b_start
        return self.parent


class PdfName(PdfObj):
    Pattern = re.compile(b'/[^/ \r\n\t\x0c\x00\[\]<>]+')

    def convert(self):
        self.data = self.raw[1:].decode('utf-8')  # TODO: Replace slash characters


class PdfHexadecimalString(PdfObj):
    """ See 7.3.4.3 """
    Pattern = re.compile(b'<([0-9a-fA-F]+)>')

    def convert(self):
        self.data = self.Pattern.match(self.raw).group(1).decode('utf-8')


class PdfNumber(PdfObj):
    Pattern = re.compile(b'[+-]?\d*\.?\d')

    def convert(self):
        self.data = self.raw.decode('utf-8')


class PdfHeader(PdfObj):
    Pattern = re.compile(rb"%PDF-([12]\.\d)")

    def convert(self):
        version = self.Pattern.match(self.raw).group(1)
        self.data = f"Version from header: {version.decode('utf-8')}"


class PdfComment(PdfObj):
    Pattern = re.compile(b"%(?!PDF|%EOF)(.*)" + LINEBREAK)

    def convert(self):
        def decode(b):
            try:
                return b.decode('utf-8')
            except UnicodeDecodeError:
                return "?"

        self.data = "".join([decode(b) for b in list_bytes(self.raw)]).rstrip().lstrip("%")


class PdfWhitespaces(PdfObj):
    Pattern = re.compile(b"[ \r\n\t\x0c\x00]+")

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
    Pattern = re.compile(b"([\r\n]|\r\n)+")


class PdfBool(PdfObj):
    Pattern = re.compile(b"true|false")

    def convert(self):
        match = self.Pattern.match(self.raw).group()
        if match == b'true':
            self.data = True
        elif match == b'false':
            self.data = False


class PdfStream(PdfObj):
    Pattern = re.compile(b"stream" + LINEBREAK + b"(.*?)" + b"endstream" + LINEBREAK, re.DOTALL)
    def convert(self):
        # TODO: Decode streams
        trimmed_data = self.Pattern.match(self.raw).group(2)
        info_dict = self.parent.data["object"]
        self.data = f"{len(trimmed_data)} bytes of stream data: {trimmed_data[:10]} ... {trimmed_data[-10:]}"

class PdfReference(PdfObj):
    Pattern = re.compile(b'(\d+) (\d+) R')

    def convert(self):
        match = self.Pattern.match(self.raw)
        self.data = (
            decode_int(match.group(1)),
            decode_int(match.group(2)),
        )


class PdfNull(PdfObj):
    Pattern = re.compile(b"null")


class PdfLiteralStringParenthesis(PdfObj):
    Pattern = re.compile(b'[)(]')

    def convert(self):
        self.data = self.Pattern.match(self.raw).group().decode('utf-8')


class PdfLiteralStringEscape(PdfObj):
    """ See 7.3.4.2 - Table 3
    """
    Pattern = re.compile(br'(\\[nrtbf)(\\])|(\\\d{1,3})')
    #
    # @classmethod
    # def match(cls, next_bytes: bytes) -> (bool, int):
    #     """ Return the number of characters that match the class' Pattern (or 0 if no match) """
    #     print(f"Matching {next_bytes}\n against {cls.Pattern}")
    #     match = cls.Pattern.match(next_bytes)
    #     print(match)
    #     return super().match(next_bytes)

    def convert(self):
        print(self.raw)
        code = self.Pattern.match(self.raw).group().decode('utf-8')
        code = code[1:]
        if code.isnumeric():
            self.data = chr(int(code, 8))
        else:
            self.data = {
                "n": "\n",
                "r": "\r",
                "t": "\t",
                "b": chr(0x08),  # BACKSPACE
                "f": "\f",
                "\\": "\\"
            }.get(code)


class PdfLiteralStringOther(PdfObj):
    Pattern = re.compile(b'.', re.DOTALL)

    def convert(self):
        self.data = self.Pattern.match(self.raw).group().decode('utf-8')


# TODO Stings
class PdfLiteralString(NestablePdfObj):
    """ See 7.3.4.2 """
    Pattern = re.compile(b"\(")
    EndingPattern = re.compile(b"\)")
    Contexts = [PdfLiteralStringParenthesis, PdfLiteralStringEscape, PdfLiteralStringOther]

    def __init__(self, *args):
        super().__init__(*args)
        self._unpaired_parenthesis = 0
        self.data = ""

    def match_end(self, next_bytes: bytes) -> (bool, int):
        if self._unpaired_parenthesis > 0:
            return False, 0
        else:
            return super().match_end(next_bytes)

    def add(self, child_obj: PdfObj) -> PdfObj:
        self.data += child_obj.data
        if isinstance(child_obj, PdfLiteralStringParenthesis):
            if child_obj.data == "(":
                self._unpaired_parenthesis += 1
            elif child_obj.data == ")":
                self._unpaired_parenthesis -= 1
                if self._unpaired_parenthesis < 0:
                    print("ERROR: String literal contains unbalanced unescaped parenthesis.")
                    self._unpaired_parenthesis = 0
            else:
                assert False, "Unrecognised character"
        return self.get_next(child_obj)


class PdfList(NestablePdfObj):
    Pattern = re.compile(b"\[")
    EndingPattern = re.compile(b"]")
    Contexts = [PdfLiteralString, PdfBool, PdfWhitespaces, PdfName, PdfReference, PdfNumber, PdfHexadecimalString,
                PdfNull, "PdfList", "PdfDict"]


class PdfDict(NestablePdfObj):
    Pattern = re.compile(b"<<" + LINEBREAK + b"*")
    EndingPattern = re.compile(b">>" + LINEBREAK + b"*")
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


class PdfRefObj(NestablePdfObj):
    Contexts = [PdfBool, PdfDict, PdfStream, PdfList, PdfWhitespaces, PdfNumber, PdfNull, PdfHexadecimalString]
    Pattern = re.compile(b'(\d+) (\d+) obj' + LINEBREAK)
    EndingPattern = re.compile(b'endobj' + LINEBREAK)

    def convert(self):
        match = self.Pattern.match(self.raw)
        self.data = {
            "reference": (decode_int(match.group(1)), decode_int(match.group(2))),
            "object": None,
            "data stream": None,
        }

    def add(self, child_obj: PdfObj) -> PdfObj:
        if isinstance(child_obj, PdfStream):
            assert self.data["data stream"] is None, "Reference Object should not have multiple data streams"
            self.data["data stream"] = child_obj
        elif isinstance(child_obj, PdfWhitespaces):
            pass
        else:
            assert self.data["object"] is None, "Reference Object should not have multiple objects"
            self.data["object"] = child_obj
        return self.get_next(child_obj)


class PdfCrossReferenceTableSpec(PdfObj):
    Pattern = re.compile(b"(\d+) (\d+) *" + LINEBREAK)

    def convert(self):
        m = self.Pattern.match(self.raw)
        self.data = {
            "object number of first entry": decode_int(m.group(1)),
            "number of entries": decode_int(m.group(2)),
        }


class PdfCrossReferenceTableEntry(PdfObj):
    Pattern = re.compile(b"(\d{10}) (\d{5}) ([nf])" + WHITESPACE + b'*' + LINEBREAK)

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
    Pattern = re.compile(b'xref' + LINEBREAK)
    EndingPattern = re.compile(b'trailer')

    def match_end(self, next_bytes: bytes) -> (bool, int):
        return super().match_end(next_bytes)[0], 0


class PdfCrossRefOffset(PdfObj):
    """ See 7.5.5 """
    Pattern = re.compile(b'startxref' + LINEBREAK + b'(\d+)' + LINEBREAK)

    def convert(self):
        self.data = self.Pattern.match(self.raw).group(1)


class PdfTrailerDict(NestablePdfObj):
    """ See 7.5.5 """
    Pattern = re.compile(b'trailer' + LINEBREAK)
    EndingPattern = re.compile(b'%%EOF')
    Contexts = [PdfDict, PdfCrossRefOffset]


class PdfDoc(NestablePdfObj):
    Contexts = [PdfHeader, PdfComment, PdfRefObj, PdfWhitespaces, PdfCrossReferenceTable, PdfTrailerDict]

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


def parse(filename):
    pdf = PdfDoc(filename)
    current = pdf
    with open(filename, "rb") as fh:
        fh: BufferedReader
        while current:
            pos = fh.tell()
            matched_end, read_length = current.match_end(fh.peek())
            if matched_end:
                current = current.finish(fh.read(read_length), pos)
            else:
                peek = fh.peek()
                for next_class in current.get_contexts():
                    # next_class: Type[PdfObj]
                    matched, read_length = next_class.match(peek)
                    if matched:
                        current = current.add(next_class(fh.read(read_length), pos, current))
                        break
                else:
                    print("PARSE ERROR:")
                    print(f"Byte position:   {pos}")
                    print(f"Current context: {current.get_structure_location()}")
                    print(f"{'(raw)':<25} {fh.peek()[:20]}")
                    for next_class in current.get_contexts():
                        next_class = cls(next_class)
                        print(f"{next_class.__name__:<25} {next_class.Pattern.pattern}")
                    current = None
    return pdf


if __name__ == "__main__":
    parse(test_file)
    #
    # test = PdfList(b"", 0, None)
    # for c in test.get_contexts():
    #     print(f"{c}, {type(c)}")
    # test_regex(PdfWhitespace, b"   hello\nworld\n")

    # with open(test_file, "rb") as fh:
    #     pdf_doc = PdfDoc.read(fh)
    # print(pdf_doc)
