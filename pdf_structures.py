native_types = int | float | bool | str | bytes | list | set | dict | tuple | None


class PdfObj:
    def __init__(self):
        self.attributes = {}
        self.meta = None
        self.data: PdfObj | native_types = None

    def as_python(self) -> native_types:
        if isinstance(self.data, PdfObj):
            return self.data.as_python()
        else:
            return self.data

    def as_pdf(self):
        ...


class PdfTokenFactory:
    ...

