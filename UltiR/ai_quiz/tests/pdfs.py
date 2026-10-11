"""Build small synthetic PDFs for the tests. Standard library only."""


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(pages: list[list[str]]) -> bytes:
    """A born-digital PDF with one list of text lines per page (ASCII or Latin-1).

    A page given as an empty list has no text at all, like a scanned page.
    """
    objects: list[bytes] = []
    n = len(pages)
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    for i, lines in enumerate(pages):
        ops = ["BT", "/F1 11 Tf", "14 TL", "72 760 Td"] if lines else []
        for line in lines:
            ops.append(f"({_escape(line)}) Tj")
            ops.append("T*")
        if lines:
            ops.append("ET")
        stream = "\n".join(ops).encode("latin-1")
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>".encode()
        )
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


# A three-page handout. Every sentence is on one page only, so tests can check page numbers.
HANDOUT = [
    [
        "CV301 Computer Vision          Lecture 7: Feature Matching",
        "A local feature is an image pattern that differs from its immediate neighbourhood.",
        "Feature matching links the same physical point across two or more images.",
        "The detector finds keypoints and the descriptor summarises the patch around each keypoint.",
        "1",
    ],
    [
        "CV301 Computer Vision          Lecture 7: Feature Matching",
        "The ratio test compares the distance to the nearest neighbour with the distance to the second nearest.",
        "A match is accepted only when that ratio is below a threshold such as 0.8.",
        "Lowering the threshold removes incorrect matches faster than correct ones.",
        "2",
    ],
    [
        "CV301 Computer Vision          Lecture 7: Feature Matching",
        "RANSAC repeatedly fits a model to a minimal random sample of matches.",
        "Four correspondences determine a homography and seven determine a fundamental matrix.",
        "The number of iterations grows quickly when the inlier fraction drops.",
        "3",
    ],
]

HEADER = "CV301 Computer Vision"


def handout_pdf() -> bytes:
    return make_pdf(HANDOUT)


def scanned_pdf(pages: int = 3) -> bytes:
    """Pages with no text layer."""
    return make_pdf([[] for _ in range(pages)])
