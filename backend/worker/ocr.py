"""OCR engines (guide 7.1 step 4). Returns text lines with boxes and a page confidence.

OCR_ENGINE=tesseract is what is built today (Hindi + English, runs offline).
OCR_ENGINE=paddle falls back to Tesseract with a warning until the PaddleOCR adapter is
added; the guide lists PaddleOCR as primary and Tesseract as fallback.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PIL import Image

from app.core.config import get_settings

log = logging.getLogger(__name__)


@dataclass
class OcrLine:
    text: str
    bbox: list[float]  # pixels in the OCR image
    confidence: float  # 0..1


@dataclass
class OcrResult:
    lines: list[OcrLine]
    confidence: float | None  # mean word confidence of the page, 0..1


def tesseract_lang(document_language: str) -> str:
    return "eng" if document_language == "en" else "hin+eng"


RETRY_BELOW_CONFIDENCE = 0.75  # pages read worse than this are checked for rotation


def get_ocr(document_language: str):
    engine = get_settings().ocr_engine.lower()
    if engine != "tesseract":
        log.warning("OCR_ENGINE=%s is not built yet, using Tesseract", engine)
    lang = tesseract_lang(document_language)
    return lambda image: ocr_upright(image, lang)


def ocr_upright(image: Image.Image, lang: str) -> OcrResult:
    """OCR the page; if it reads badly, detect rotation (e.g. sideways charts), rotate, retry.

    Boxes are always in the coordinates of the ORIGINAL (unrotated) image, so highlights
    land in the right place on the page as the user sees it.
    """
    best, best_ccw = tesseract_ocr(image, lang), 0
    if _good(best):
        return best
    # Orientation detection is fast but often undecided on charts; if it gives no answer or
    # the wrong one, try the remaining orientations and keep whichever reads best.
    detected = detect_rotation(image)
    candidates = ([detected] if detected else []) + [a for a in (90, 270, 180) if a != detected]
    for ccw in candidates:
        result = tesseract_ocr(image.rotate(ccw, expand=True), lang)  # PIL rotates CCW too
        if (result.confidence or 0) > (best.confidence or 0):
            best, best_ccw = result, ccw
        if _good(best):
            break
    if best_ccw:
        w, h = image.size
        clockwise = (360 - best_ccw) % 360
        for line in best.lines:
            line.bbox = _unrotate_bbox(line.bbox, clockwise, w, h)
    return best


def _good(result: OcrResult) -> bool:
    return result.confidence is not None and result.confidence >= RETRY_BELOW_CONFIDENCE


def detect_rotation(image: Image.Image) -> int:
    """Degrees (0/90/180/270) to turn the page COUNTER-clockwise to make it upright.

    This is Tesseract OSD's "Rotate" value. 0 if unknown.
    """
    import pytesseract

    try:
        osd = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT)
    except pytesseract.TesseractError:
        return 0  # too little text to decide
    return int(osd.get("rotate", 0)) % 360


def _unrotate_bbox(bbox: list[float], angle: int, w: int, h: int) -> list[float]:
    """Map a box from the image rotated clockwise by `angle` back to the original image."""
    x0, y0, x1, y1 = bbox
    if angle == 90:  # rotated image is h wide, w tall: (x, y) came from (y, h - x)
        pts = [(y0, h - x0), (y1, h - x1)]
    elif angle == 180:
        pts = [(w - x0, h - y0), (w - x1, h - y1)]
    elif angle == 270:
        pts = [(w - y0, x0), (w - y1, x1)]
    else:
        return bbox
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return [min(xs), min(ys), max(xs), max(ys)]


def tesseract_ocr(image: Image.Image, lang: str) -> OcrResult:
    import pytesseract

    data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)
    # Group words into lines: (block, paragraph, line) identifies one text line.
    lines: dict[tuple[int, int, int], list[int]] = {}
    for i, word in enumerate(data["text"]):
        if word.strip() and float(data["conf"][i]) >= 0:
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines.setdefault(key, []).append(i)

    out: list[OcrLine] = []
    all_conf: list[float] = []
    for idx in lines.values():
        confs = [float(data["conf"][i]) / 100 for i in idx]
        all_conf.extend(confs)
        x0 = min(data["left"][i] for i in idx)
        y0 = min(data["top"][i] for i in idx)
        x1 = max(data["left"][i] + data["width"][i] for i in idx)
        y1 = max(data["top"][i] + data["height"][i] for i in idx)
        text = " ".join(data["text"][i].strip() for i in idx)
        out.append(OcrLine(text, [x0, y0, x1, y1], sum(confs) / len(confs)))

    page_conf = round(sum(all_conf) / len(all_conf), 3) if all_conf else None
    return OcrResult(out, page_conf)
