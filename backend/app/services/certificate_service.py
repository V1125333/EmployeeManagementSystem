"""
Certificate PDF generation and serial number tracking.
"""

from __future__ import annotations

import io
import json
import math
import re
import threading
from datetime import date, datetime
from pathlib import Path

from PIL import Image as PILImage
import qrcode
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from app.core.config import settings
from app.schemas.certificate import CERT_TYPES, CertificateGenerateRequest

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
REGISTRY_FILE = DATA_DIR / "certificate_serial_registry.json"
ISSUED_FILE = DATA_DIR / "issued_certificates.json"
ASSETS_DIR = Path(__file__).resolve().parents[1] / "certificate_assets"
FONTS_DIR = ASSETS_DIR / "fonts"
IMAGES_DIR = ASSETS_DIR / "images"
BG_DARK_PATH = IMAGES_DIR / "bg_dark.png"
LOGO_ICON_PATH = IMAGES_DIR / "reknew_logo_icon.png"
SIGNATURE_PATH = IMAGES_DIR / "signature.png"
_lock = threading.Lock()
_fonts_registered = False
_signature_cache: ImageReader | None = None


def _registry_key(certificate_type: str, cohort_code: str, year: int) -> str:
    return f"ALL|{cohort_code.strip().upper()}|{int(year)}"


def _load_registry() -> dict[str, int]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_FILE.exists():
        return {}
    try:
        data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
        return {str(k): int(v) for k, v in data.items()}
    except (OSError, ValueError, TypeError):
        return {}


def _save_registry(registry: dict[str, int]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY_FILE.write_text(
        json.dumps(registry, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _load_issued_certificates() -> dict[str, dict]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not ISSUED_FILE.exists():
        return {}
    try:
        data = json.loads(ISSUED_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, ValueError, TypeError):
        pass
    return {}


def _save_issued_certificates(records: dict[str, dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ISSUED_FILE.write_text(
        json.dumps(records, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def list_counters() -> list[dict]:
    registry = _load_registry()
    counters = []
    for key, last_issued in registry.items():
        parts = key.split("|")
        if len(parts) != 3:
            continue
        cert_type, cohort_code, year = parts
        counters.append({
            "certificate_type": "All programmes" if cert_type == "ALL" else cert_type,
            "cohort_code": cohort_code,
            "year": int(year),
            "last_issued": last_issued,
        })
    return counters


def peek_next_serial(certificate_type: str, cohort_code: str, year: int) -> int:
    with _lock:
        registry = _load_registry()
        return registry.get(_registry_key(certificate_type, cohort_code, year), 0) + 1


def consume_next_serial(certificate_type: str, cohort_code: str, year: int) -> int:
    with _lock:
        registry = _load_registry()
        key = _registry_key(certificate_type, cohort_code, year)
        next_serial = registry.get(key, 0) + 1
        registry[key] = next_serial
        _save_registry(registry)
        return next_serial


def certificate_id(cohort_code: str, year: int, serial_number: int | None) -> str:
    if serial_number is None:
        return ""
    return f"RK-{cohort_code.strip().upper()}-{year}-{serial_number:03d}"


def certificate_verify_url(cert_id: str) -> str:
    return f"{settings.CERTIFICATE_VERIFY_BASE_URL.rstrip('/')}/{cert_id}"


def format_certificate_date(value: date) -> str:
    return f"{value.strftime('%B')} {value.day}, {value.year}"


def format_programme_period(start_date: date, end_date: date) -> str:
    return f"Start Date: {format_certificate_date(start_date)}  |  End Date: {format_certificate_date(end_date)}"


def build_filename(first_name: str, surname: str, certificate_type: str) -> str:
    def clean(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip()).strip("_")

    return (
        f"RK_Certificate_{clean(first_name)}_{clean(surname)}_"
        f"{clean(certificate_type)}.pdf"
    )


def register_fonts() -> None:
    global _fonts_registered
    if _fonts_registered:
        return

    font_specs = {
        "Bricolage": "BricolageGrotesque-Regular.ttf",
        "Bricolage-Bold": "BricolageGrotesque-Bold.ttf",
        "Bricolage-SB": "BricolageGrotesque-SemiBold.ttf",
        "Raleway": "Raleway-Regular.ttf",
        "Raleway-Light": "Raleway-Light.ttf",
        "Poppins": "Poppins-Regular.ttf",
        "Poppins-Bold": "Poppins-Bold.ttf",
    }
    for name, filename in font_specs.items():
        path = FONTS_DIR / filename
        if path.exists():
            try:
                pdfmetrics.registerFont(TTFont(name, str(path)))
            except Exception:
                pass
    _fonts_registered = True


def font(preferred: str, fallback: str = "Helvetica") -> str:
    try:
        pdfmetrics.getFont(preferred)
        return preferred
    except Exception:
        return fallback


def heading_font() -> str:
    for name in ("Bricolage-Bold", "Bricolage-SB", "Poppins-Bold"):
        try:
            pdfmetrics.getFont(name)
            return name
        except Exception:
            continue
    return "Helvetica-Bold"


def standard_font(light: bool = False) -> str:
    choices = ("Raleway-Light", "Raleway", "Poppins") if light else ("Raleway", "Poppins")
    for name in choices:
        try:
            pdfmetrics.getFont(name)
            return name
        except Exception:
            continue
    return "Helvetica"


def pil_to_reader(image: PILImage.Image) -> ImageReader:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return ImageReader(buffer)


def draw_image(c: canvas.Canvas, path: Path, x: float, y: float, w: float, h: float) -> None:
    if not path.exists():
        return
    image = PILImage.open(path).convert("RGBA")
    c.drawImage(pil_to_reader(image), x, y, width=w, height=h, mask="auto")


def signature_reader() -> ImageReader | None:
    global _signature_cache
    if _signature_cache is not None:
        return _signature_cache
    if not SIGNATURE_PATH.exists():
        return None

    image = PILImage.open(SIGNATURE_PATH).convert("RGBA")
    alpha = image.getchannel("A")
    white_ink = PILImage.new("RGBA", image.size, (255, 255, 255, 0))
    white_ink.putalpha(alpha)
    _signature_cache = pil_to_reader(white_ink)
    return _signature_cache


def centered_text(
    c: canvas.Canvas,
    text: str,
    font_name: str,
    size: float,
    y: float,
    page_w: float,
    color,
    char_space: float = 0,
) -> None:
    c.setFillColor(color)
    c.setFont(font_name, size)
    if char_space:
        c._charSpace = char_space
    width = pdfmetrics.stringWidth(text, font_name, size)
    c.drawString((page_w - width) / 2, y, text)
    if char_space:
        c._charSpace = 0


def star_path(c: canvas.Canvas, cx: float, cy: float, r_out: float, r_in: float) -> None:
    path = c.beginPath()
    for i in range(10):
        angle = math.pi / 5 * i - math.pi / 2
        radius = r_out if i % 2 == 0 else r_in
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        if i == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
    path.close()
    c.drawPath(path, fill=1, stroke=0)


def draw_medal(c: canvas.Canvas, cx: float, cy: float, radius: float = 13) -> None:
    gold = HexColor("#C8971A")
    bg = HexColor("#101727")
    ribbon_w = radius * 0.55
    ribbon_h = radius * 0.90
    ribbon_x = cx - ribbon_w / 2
    ribbon_top = cy - radius

    c.setFillColor(gold)
    c.rect(ribbon_x, ribbon_top - ribbon_h, ribbon_w, ribbon_h, fill=1, stroke=0)

    notch = ribbon_h * 0.38
    path = c.beginPath()
    path.moveTo(ribbon_x, ribbon_top - ribbon_h)
    path.lineTo(cx, ribbon_top - ribbon_h + notch)
    path.lineTo(ribbon_x + ribbon_w, ribbon_top - ribbon_h)
    path.close()
    c.setFillColor(bg)
    c.drawPath(path, fill=1, stroke=0)

    c.setFillColor(bg)
    c.setStrokeColor(gold)
    c.setLineWidth(1.5)
    c.circle(cx, cy, radius, fill=1, stroke=1)
    c.setFillColor(gold)
    star_path(c, cx, cy, radius * 0.54, radius * 0.22)


def draw_date_block(c: canvas.Canvas, x: float, baseline_y: float, date_text: str) -> None:
    c.setFont(font("Poppins", "Helvetica"), 9.5)
    c.setFillColor(HexColor("#888EA8"))
    c.drawString(x, baseline_y + 18, "Date of Issue")

    c.setFont(font("Poppins-Bold", "Helvetica-Bold"), 14)
    c.setFillColor(white)
    c.drawString(x, baseline_y, date_text)


def draw_signature_block(c: canvas.Canvas, right_x: float, baseline_y: float) -> None:
    name = "Murali Sajja"
    role = "Chief Executive Officer"
    name_font = font("Poppins-Bold", "Helvetica-Bold")
    role_font = font("Poppins", "Helvetica")

    c.setFont(role_font, 10)
    c.setFillColor(HexColor("#888EA8"))
    c.drawRightString(right_x, baseline_y, role)

    c.setFont(name_font, 13)
    c.setFillColor(white)
    c.drawRightString(right_x, baseline_y + 16, name)

    reader = signature_reader()
    if reader:
        sig_h = 42
        sig_w = sig_h * 3.29
        c.drawImage(reader, right_x - sig_w, baseline_y + 30, width=sig_w, height=sig_h, mask="auto")


def draw_wordmark(c: canvas.Canvas, y: float, page_w: float) -> None:
    wordmark_font = heading_font()
    size = 30
    gap = size * 0.03
    icon_h = size * 0.52
    icon_w = icon_h
    re_text = "re"
    knew_text = "knew"
    re_w = pdfmetrics.stringWidth(re_text, wordmark_font, size)
    knew_w = pdfmetrics.stringWidth(knew_text, wordmark_font, size)
    total_w = re_w + gap + icon_w + gap + knew_w
    x0 = page_w / 2 - total_w / 2

    c.setFont(wordmark_font, size)
    c.setFillColor(white)
    c.drawString(x0, y, re_text)
    draw_image(c, LOGO_ICON_PATH, x0 + re_w + gap, y + size * 0.06, icon_w, icon_h)
    c.drawString(x0 + re_w + gap + icon_w + gap, y, knew_text)


def qr_reader(value: str) -> ImageReader:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=1,
    )
    qr.add_data(value)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#101727", back_color="#FFFFFF").convert("RGBA")
    return pil_to_reader(image)


def draw_verification_qr(c: canvas.Canvas, cert_id: str, page_w: float, bottom_y: float) -> None:
    size = 38
    x = page_w / 2 - size / 2
    c.drawImage(
        qr_reader(certificate_verify_url(cert_id)),
        x,
        bottom_y,
        width=size,
        height=size,
        mask="auto",
    )


def generate_certificate_pdf(
    request: CertificateGenerateRequest,
    serial_number: int | None,
) -> bytes:
    register_fonts()
    page_w, page_h = landscape(A4)
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))

    margin = 30
    gold = HexColor("#E8C87A")
    gold_rule = HexColor("#B87830")
    muted = HexColor("#C8B89A")
    orange = HexColor("#EB7228")

    if BG_DARK_PATH.exists():
        c.drawImage(str(BG_DARK_PATH), 0, 0, width=page_w, height=page_h, preserveAspectRatio=False)
    else:
        c.setFillColor(HexColor("#0A0808"))
        c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    c.setStrokeColor(gold_rule)
    c.setLineWidth(1.2)
    c.setStrokeAlpha(0.6)
    c.rect(margin - 4, margin - 4, page_w - 2 * (margin - 4), page_h - 2 * (margin - 4), fill=0, stroke=1)
    c.setStrokeAlpha(1)

    date_baseline = margin + 48
    sig_top = date_baseline + 72
    duration_y = sig_top + 24
    programme_y = duration_y + 34
    completed_y = programme_y + 32
    rule_y = completed_y + 22
    name_y = rule_y + 18
    certify_y = name_y + 68
    heading_y = certify_y + 44

    icon_size = 72
    draw_image(
        c,
        LOGO_ICON_PATH,
        page_w - margin - icon_size - 6,
        page_h - margin - icon_size - 4,
        icon_size,
        icon_size,
    )

    draw_wordmark(c, heading_y + 38, page_w)

    centered_text(
        c,
        "CERTIFICATE OF COMPLETION",
        heading_font(),
        19,
        heading_y,
        page_w,
        gold,
        char_space=3,
    )
    centered_text(c, "This is to certify that", standard_font(light=True), 13, certify_y, page_w, muted)

    full_name = f"{request.first_name.strip()} {request.surname.strip()}"
    name_font = heading_font()
    name_size = 50
    while pdfmetrics.stringWidth(full_name, name_font, name_size) > page_w * 0.78 and name_size > 26:
        name_size -= 1
    centered_text(c, full_name, name_font, name_size, name_y, page_w, white)

    c.setStrokeColor(gold_rule)
    c.setLineWidth(0.8)
    c.line(margin + 20, rule_y, page_w - margin - 20, rule_y)

    centered_text(c, "has successfully completed the program", standard_font(), 13, completed_y, page_w, muted)

    programme_font = heading_font()
    program_size = 23
    while pdfmetrics.stringWidth(request.certificate_type, programme_font, program_size) > page_w * 0.72 and program_size > 13:
        program_size -= 1
    centered_text(c, request.certificate_type, programme_font, program_size, programme_y, page_w, orange)
    centered_text(
        c,
        format_programme_period(request.start_date, request.end_date),
        standard_font(light=True),
        12,
        duration_y,
        page_w,
        muted,
    )

    issued = format_certificate_date(request.issued_date)

    medal_cx = margin + 46
    medal_cy = date_baseline + 12
    draw_medal(c, medal_cx, medal_cy)
    draw_date_block(c, medal_cx + 22, date_baseline, issued)
    draw_signature_block(c, page_w - margin - 42, date_baseline)

    if request.include_certificate_number and serial_number is not None:
        cert_id = certificate_id(request.cohort_code, request.year, serial_number)
        cert_y = margin + 18
        qr_y = cert_y + 12
        draw_verification_qr(c, cert_id, page_w, qr_y)

        c.setFont(font("Poppins", "Helvetica"), 8)
        c.setFillColor(HexColor("#888EA8"))
        c.drawCentredString(page_w / 2, cert_y, cert_id)

    c.save()
    return buffer.getvalue()


def validate_certificate_type(certificate_type: str) -> None:
    if certificate_type not in CERT_TYPES:
        raise ValueError("Unsupported certificate type")


def record_issued_certificate(
    request: CertificateGenerateRequest,
    serial_number: int,
    cert_id: str,
) -> dict:
    record = {
        "certificate_id": cert_id,
        "recipient_name": f"{request.first_name.strip()} {request.surname.strip()}",
        "certificate_type": request.certificate_type,
        "start_date": request.start_date.isoformat(),
        "end_date": request.end_date.isoformat(),
        "cohort_code": request.cohort_code.strip().upper(),
        "year": request.year,
        "serial_number": serial_number,
        "issued_date": request.issued_date.isoformat(),
        "status": "valid",
        "created_at": datetime.utcnow().isoformat(),
    }
    with _lock:
        records = _load_issued_certificates()
        records[cert_id] = record
        _save_issued_certificates(records)
    return record


def get_certificate_verification(cert_id: str) -> dict | None:
    records = _load_issued_certificates()
    return records.get(cert_id)
