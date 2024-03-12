

class PdfObj:
    def __init__(self):
        self.attributes = {}
        self.meta = None
        self.data: PdfObj | None | int | float | str | list | dict = None

    def as_python(self):
        if isinstance(self.data, PdfObj):
            return self.data.as_python()
        else:
            return self.data

    def as_pdf(self):
        ...

