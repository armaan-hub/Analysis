from core.deep_research_export import to_branded_pdf, to_branded_docx
import zipfile
import io


SOURCES = [
    {"source": "Federal Tax Authority", "url": "https://tax.gov.ae/article-31", "excerpt": "VAT zero-rated rules"},
    {"source": "Local PDF", "page": 12, "excerpt": "Internal note"},
]


def test_pdf_appendix_contains_url():
    pdf_bytes = to_branded_pdf("# Body\nContent here", SOURCES, "Test query")
    assert b"https://tax.gov.ae/article-31" in pdf_bytes


def test_docx_appendix_contains_url():
    docx_bytes = to_branded_docx("# Body\nContent here", SOURCES, "Test query")
    # DOCX is a ZIP; extract document.xml to check for hyperlink
    with zipfile.ZipFile(io.BytesIO(docx_bytes), 'r') as z:
        doc_xml = z.read('word/document.xml')
        assert b"tax.gov.ae" in doc_xml
        assert b"article-31" in doc_xml

