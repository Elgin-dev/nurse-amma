from pathlib import Path
import pymupdf


def extract_pdf_text(file_path: str) -> dict:
    """
    Extract text from a digital PDF.

    Returns the extracted text and page-level information.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError("PDF file was not found.")

    if path.suffix.lower() != ".pdf":
        raise ValueError("The supplied file is not a PDF.")

    pages = []
    all_text = []

    with pymupdf.open(path) as document:

        if document.needs_pass:
            raise ValueError("Password-protected PDFs are not supported.")

        if document.page_count == 0:
            raise ValueError("The PDF contains no pages.")

        for page_number, page in enumerate(document, start=1):
            text = page.get_text("text").strip()

            pages.append(
                {
                    "page_number": page_number,
                    "text": text,
                }
            )

            if text:
                all_text.append(text)

    return {
        "page_count": len(pages),
        "pages": pages,
        "text": "\n\n".join(all_text),
    }