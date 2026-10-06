"""Exception hierarchy for PDF Shrink."""


class PDFShrinkError(Exception):
    """Base exception for all PDF Shrink errors."""
    pass


class PasswordRequired(PDFShrinkError):
    """Raised when a PDF is encrypted and requires a password."""

    def __init__(self, path: str, message: str = "PDF terkunci sandi"):
        self.path = path
        super().__init__(message)


class InvalidPDF(PDFShrinkError):
    """Raised when a file is not a valid PDF or is corrupt."""

    def __init__(self, path: str, message: str = "File tidak valid"):
        self.path = path
        super().__init__(message)


class TargetUnreachable(PDFShrinkError):
    """Raised when the target size range cannot be achieved.

    Attributes:
        smallest_bytes: The smallest file size achievable.
        target_max_kb: The requested maximum size in KB.
    """

    def __init__(
        self,
        path: str,
        smallest_bytes: int,
        target_max_kb: int,
        message: str | None = None,
    ):
        self.path = path
        self.smallest_bytes = smallest_bytes
        self.target_max_kb = target_max_kb
        if message is None:
            smallest_kb = smallest_bytes // 1024
            message = (
                f"Tidak bisa mencapai target {target_max_kb} KB. "
                f"Ukuran terkecil: {smallest_kb} KB"
            )
        super().__init__(message)
