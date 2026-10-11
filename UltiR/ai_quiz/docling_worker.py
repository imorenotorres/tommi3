"""Run Docling on one PDF and write down what it found, as plain data.

This file is a program, not part of the web application. The full reader
(docling_reader.py) starts it with the Python interpreter named in
AI_QUIZ_DOCLING_PYTHON, in a process of its own and without network access.
It imports nothing from the platform and decides nothing: sorting the items
into pages, checking formulas and choosing figures is done by the caller,
where it can be tested without Docling.

    python -I docling_worker.py <pdf> <out_dir> <models_dir> <device> <threads>

Writes <out_dir>/result.json and one PNG per picture (p0001.png, ...).
Exit code 0 on success; anything else is a failure, with the reason on stderr.

OCR is off: the tool reads born-digital PDFs only. Models come from
<models_dir>, which must already hold them; nothing is fetched.
"""

import json
import os
import sys
import time
from pathlib import Path

RESULT_VERSION = 1


def _prov(item) -> list[dict]:
    out = []
    for p in getattr(item, "prov", None) or []:
        span = getattr(p, "charspan", None)
        out.append({"page": p.page_no, "charspan": [int(span[0]), int(span[1])] if span else None})
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 6:
        print(__doc__, file=sys.stderr)
        return 2
    pdf, out_dir, models_dir = Path(argv[1]), Path(argv[2]), Path(argv[3])
    device, threads = argv[4], int(argv[5])

    # Before Docling and its libraries are imported: they read these at import time.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    import importlib.metadata as metadata

    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling_core.types.doc import DocItemLabel, PictureItem, TableItem

    devices = {"auto": AcceleratorDevice.AUTO, "cpu": AcceleratorDevice.CPU, "cuda": AcceleratorDevice.CUDA}
    options = PdfPipelineOptions()
    options.do_ocr = False
    options.do_formula_enrichment = True
    options.generate_picture_images = True
    options.images_scale = 2.0
    options.artifacts_path = str(models_dir)
    options.accelerator_options = AcceleratorOptions(device=devices[device], num_threads=threads)

    started = time.monotonic()
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
    result = converter.convert(str(pdf))
    doc = result.document

    items, pictures = [], 0
    for item, _level in doc.iterate_items():
        entry = {"prov": _prov(item)}
        if isinstance(item, PictureItem):
            pictures += 1
            entry.update(kind="picture", caption=item.caption_text(doc) or "", file=None, width=None, height=None)
            image = item.get_image(doc)
            if image is not None:
                entry["file"] = f"p{pictures:04d}.png"
                entry["width"], entry["height"] = image.size
                image.save(out_dir / entry["file"], "PNG")
        elif isinstance(item, TableItem):
            rows = [[(cell.text or "") for cell in row] for row in item.data.grid]
            entry.update(kind="table", rows=rows)
        else:
            label = getattr(item, "label", None)
            entry.update(
                kind="formula" if label == DocItemLabel.FORMULA else "text",
                label=str(getattr(label, "value", label) or ""),
                text=getattr(item, "text", "") or "",
                orig=getattr(item, "orig", "") or "",
            )
        items.append(entry)

    data = {
        "version": RESULT_VERSION,
        "docling": metadata.version("docling"),
        "status": str(getattr(result.status, "value", result.status)),
        "n_pages": len(doc.pages),
        "seconds": round(time.monotonic() - started, 1),
        "items": items,
    }
    (out_dir / "result.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
