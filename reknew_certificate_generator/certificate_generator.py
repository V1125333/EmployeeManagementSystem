"""
ReKnew Certificate Generator  — v1.7
--------------------------------------
Two templates:
  Single dark template — fluid glass background (bg_dark.png).

All shared drawing helpers (medal, wordmark, signature, etc.) adapt
their colours automatically based on the active template.
"""

import io
import math
from datetime import date
from pathlib import Path

from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.colors import HexColor, white, black, Color
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from PIL import Image as PILImage
import numpy as np

# ─────────────────────────────────────────────────────────────
#  Paths
# ─────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
FONTS_DIR  = BASE_DIR / "fonts"
ASSETS_DIR = BASE_DIR / "assets"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

LOGO_ICON_PATH  = ASSETS_DIR / "reknew_logo_icon.png"
SIGNATURE_PATH  = ASSETS_DIR / "signature.png"
BG_DARK_PATH    = ASSETS_DIR / "bg_dark.png"
WORDMARK_PATH   = ASSETS_DIR / "reknew_wordmark.png"

# ─────────────────────────────────────────────────────────────
#  Shared colour tokens
# ─────────────────────────────────────────────────────────────
# Colours for dark template
DARK_BG       = HexColor("#101727")
WHITE_TEXT    = HexColor("#FFFFFF")
OFFWHITE_TEXT = HexColor("#E8E8E8")
DIM_WHITE     = HexColor("#888EA8")    # secondary text on dark
RULE_DARK     = HexColor("#2A3050")
OG_START      = HexColor("#F7941D")
OG_END        = HexColor("#E8472A")


# ─────────────────────────────────────────────────────────────
#  Certificate types
# ─────────────────────────────────────────────────────────────
CERT_TYPES = [
    "ReKnew AI Cloud Practitioner",
    "ReKnew AI Cloud Architect",
    "ReKnew AI Foundational Engineer",
    "ReKnew Context Engineer",
    "ReKnew Context Architect",
    "ReKnew Snowflake AI Practitioner",
    "ReKnew DataBricks AI Practitioner",
]

# ─────────────────────────────────────────────────────────────
#  Font registration
# ─────────────────────────────────────────────────────────────
_fonts_registered = False

def register_fonts():
    global _fonts_registered
    if _fonts_registered:
        return
    specs = {
        "Poppins":          "Poppins-Regular.ttf",
        "Poppins-Bold":     "Poppins-Bold.ttf",
        "Poppins-Medium":   "Poppins-Medium.ttf",
        "Poppins-Light":    "Poppins-Light.ttf",
        "Caladea":          "Caladea-Regular.ttf",
        "Caladea-Bold":     "Caladea-Bold.ttf",
        "Caladea-Italic":   "Caladea-Italic.ttf",
        "Serif":            "DejaVuSerif.ttf",
        "Serif-Bold":       "DejaVuSerif-Bold.ttf",
        # New branded fonts
        "Bricolage":        "BricolageGrotesque-Regular.ttf",
        "Bricolage-Bold":   "BricolageGrotesque-Bold.ttf",
        "Bricolage-SB":     "BricolageGrotesque-SemiBold.ttf",
        "Raleway":          "Raleway-Regular.ttf",
        "Raleway-Bold":     "Raleway-Bold.ttf",
        "Raleway-SB":       "Raleway-SemiBold.ttf",
        "Raleway-Light":    "Raleway-Light.ttf",
    }
    for name, fname in specs.items():
        p = FONTS_DIR / fname
        if p.exists():
            try:
                pdfmetrics.registerFont(TTFont(name, str(p)))
            except Exception:
                pass
    _fonts_registered = True


def F(preferred, fallback="Helvetica"):
    try:
        pdfmetrics.getFont(preferred)
        return preferred
    except Exception:
        return fallback


def FH(fallback="Helvetica-Bold"):
    """Heading font: Bricolage Grotesque → Poppins-Bold → fallback."""
    for name in ("Bricolage-Bold", "Bricolage", "Poppins-Bold"):
        try:
            pdfmetrics.getFont(name)
            return name
        except Exception:
            pass
    return fallback


def FS(fallback="Helvetica"):
    """Standard/small text font: Raleway → Poppins → fallback."""
    for name in ("Raleway", "Poppins"):
        try:
            pdfmetrics.getFont(name)
            return name
        except Exception:
            pass
    return fallback


def FSL(fallback="Helvetica"):
    """Light/small text: Raleway-Light → Poppins-Light → fallback."""
    for name in ("Raleway-Light", "Raleway", "Poppins-Light"):
        try:
            pdfmetrics.getFont(name)
            return name
        except Exception:
            pass
    return fallback


# ─────────────────────────────────────────────────────────────
#  Image helpers
# ─────────────────────────────────────────────────────────────

def _pil_to_reader(pil_img: PILImage.Image) -> ImageReader:
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def draw_image(c: canvas.Canvas, path: Path, x, y, w, h):
    if not path.exists():
        return
    img = PILImage.open(path).convert("RGBA")
    c.drawImage(_pil_to_reader(img), x, y, width=w, height=h, mask="auto")


# ─────────────────────────────────────────────────────────────
#  Signature PNG — invert to white for dark template
# ─────────────────────────────────────────────────────────────

_sig_cache = {}

def draw_signature_image(c: canvas.Canvas, x, y, w, h, dark_mode=False):
    """Draw the signature PNG, optionally inverted to white for dark bg."""
    cache_key = "white" if dark_mode else "dark"
    if cache_key not in _sig_cache:
        if not SIGNATURE_PATH.exists():
            _sig_cache[cache_key] = None
        else:
            img = PILImage.open(SIGNATURE_PATH).convert("RGBA")
            arr = np.array(img, dtype=np.uint8)
            if dark_mode:
                # Recolour ink to white
                arr[:, :, 0] = 255
                arr[:, :, 1] = 255
                arr[:, :, 2] = 255
            _sig_cache[cache_key] = _pil_to_reader(PILImage.fromarray(arr))

    reader = _sig_cache[cache_key]
    if reader:
        c.drawImage(reader, x, y, width=w, height=h, mask="auto")


# ─────────────────────────────────────────────────────────────
#  Drawing helpers
# ─────────────────────────────────────────────────────────────

def ctext(c, text, font, size, y, page_w, color=None, char_space=0):
    if color:
        c.setFillColor(color)
    c.setFont(font, size)
    if char_space:
        c._charSpace = char_space
    w = pdfmetrics.stringWidth(text, font, size)
    c.drawString((page_w - w) / 2, y, text)
    if char_space:
        c._charSpace = 0


def hline(c, y, x0, x1, color=None, width=0.5):
    if color is None: color = HexColor("#D4D4D4")
    c.setStrokeColor(color)
    c.setLineWidth(width)
    c.line(x0, y, x1, y)


def star_path(c, cx, cy, r_out, r_in, n=5):
    p = c.beginPath()
    for i in range(n * 2):
        a = math.pi / n * i - math.pi / 2
        r = r_out if i % 2 == 0 else r_in
        px, py = cx + r * math.cos(a), cy + r * math.sin(a)
        if i == 0: p.moveTo(px, py)
        else:      p.lineTo(px, py)
    p.close()
    c.drawPath(p, fill=1, stroke=0)


# ─────────────────────────────────────────────────────────────
#  re·knew wordmark  (logo icon between "re" and "knew")
# ─────────────────────────────────────────────────────────────

def draw_wordmark(c, cx, y, page_w, size=30, dark=False):
    register_fonts()
    # Use Bricolage-Bold to match official re·knew wordmark style
    font   = F("Bricolage-Bold", "Helvetica-Bold")
    color  = white
    c.setFont(font, size)

    re_txt   = "re"
    knew_txt = "knew"
    # Tight gap matching official logo: letters sit nearly touching the icon
    # Official logo analysis: ~1.4% of total width = ~0.03 * size
    gap    = size * 0.03
    icon_h = size * 0.52    # slightly taller icon relative to text
    icon_w = icon_h

    re_w   = pdfmetrics.stringWidth(re_txt,   font, size)
    knew_w = pdfmetrics.stringWidth(knew_txt, font, size)
    total_w = re_w + gap + icon_w + gap + knew_w
    x0 = cx - total_w / 2

    c.setFillColor(color)
    c.drawString(x0, y, re_txt)

    icon_x = x0 + re_w + gap
    icon_y = y + size * 0.06   # vertically centred with text
    if LOGO_ICON_PATH.exists():
        draw_image(c, LOGO_ICON_PATH, icon_x, icon_y, icon_w, icon_h)
    else:
        c.setFillColor(HexColor("#E03A2E"))
        tp = c.beginPath()
        tp.moveTo(icon_x,              icon_y + icon_h)
        tp.lineTo(icon_x + icon_w,     icon_y + icon_h)
        tp.lineTo(icon_x + icon_w / 2, icon_y)
        tp.close()
        c.drawPath(tp, fill=1, stroke=0)

    c.setFillColor(color)
    c.drawString(icon_x + icon_w + gap, y, knew_txt)


# ─────────────────────────────────────────────────────────────
#  Medal / ribbon icon
# ─────────────────────────────────────────────────────────────

def draw_medal(c, cx, cy, radius=13, dark=False):
    stroke_col = HexColor("#C8971A")
    fill_col   = white if dark else white
    star_col   = HexColor("#1A1F2E")

    if dark:
        # On dark bg: medal uses orange/gold tones
        stroke_col = HexColor("#C8971A")
        fill_col   = HexColor("#1A1F2E")
        star_col   = HexColor("#C8971A")

    rw = radius * 0.55
    rh = radius * 0.90
    rx = cx - rw / 2
    ry_top = cy - radius

    c.setFillColor(stroke_col)
    c.rect(rx, ry_top - rh, rw, rh, fill=1, stroke=0)

    notch_depth = rh * 0.38
    vp = c.beginPath()
    vp.moveTo(rx,      ry_top - rh)
    vp.lineTo(cx,      ry_top - rh + notch_depth)
    vp.lineTo(rx + rw, ry_top - rh)
    vp.close()
    c.setFillColor(HexColor("#101727") if dark else white)
    c.drawPath(vp, fill=1, stroke=0)

    c.setFillColor(fill_col)
    c.setStrokeColor(stroke_col)
    c.setLineWidth(1.5)
    c.circle(cx, cy, radius, fill=1, stroke=1)

    c.setFillColor(star_col)
    star_path(c, cx, cy, r_out=radius * 0.54, r_in=radius * 0.22)


# ─────────────────────────────────────────────────────────────
#  Signature block
# ─────────────────────────────────────────────────────────────

def draw_signature_block(c, right_x, baseline_y, dark=False):
    register_fonts()
    sig_name  = "Murali Sajja"
    role_text = "Chief Executive Officer"
    name_font = F("Poppins-Bold", "Helvetica-Bold")
    role_font = F("Poppins",      "Helvetica")

    primary_col   = white
    secondary_col = DIM_WHITE

    # Role — sits at baseline
    c.setFont(role_font, 10)
    role_w = pdfmetrics.stringWidth(role_text, role_font, 10)
    c.setFillColor(secondary_col)
    c.drawString(right_x - role_w, baseline_y, role_text)

    # Printed name — one line up
    c.setFont(name_font, 13)
    name_w = pdfmetrics.stringWidth(sig_name, name_font, 13)
    c.setFillColor(primary_col)
    c.drawString(right_x - name_w, baseline_y + 16, sig_name)

    # Signature image — tight above printed name (was +34, now +30)
    sig_img_h = 42
    sig_img_w = sig_img_h * 3.29
    sig_img_x = right_x - sig_img_w
    sig_img_y = baseline_y + 30

    draw_signature_image(c, sig_img_x, sig_img_y, sig_img_w, sig_img_h,
                         dark_mode=dark)


# ─────────────────────────────────────────────────────────────
#  Date block
# ─────────────────────────────────────────────────────────────

def draw_date_block(c, x, baseline_y, date_str, dark=False):
    register_fonts()
    primary_col   = white
    secondary_col = DIM_WHITE

    c.setFont(F("Poppins", "Helvetica"), 9.5)
    c.setFillColor(secondary_col)
    c.drawString(x, baseline_y + 18, "Date of Issue")

    c.setFont(F("Poppins-Bold", "Helvetica-Bold"), 14)
    c.setFillColor(primary_col)
    c.drawString(x, baseline_y, date_str)


# ─────────────────────────────────────────────────────────────
#  Orange horizontal rule (used in dark template)
# ─────────────────────────────────────────────────────────────

def orange_rule(c, y, page_w, width=400, stroke_w=1.2, opacity=0.75):
    """Draw a centred orange gradient-ish line."""
    x0 = (page_w - width) / 2
    x1 = x0 + width
    c.setStrokeColor(OG_START)
    c.setLineWidth(stroke_w)
    c.setStrokeAlpha(opacity)
    c.line(x0, y, x1, y)
    c.setStrokeAlpha(1.0)


# ─────────────────────────────────────────────────────────────
#  DARK TEMPLATE  (constellation background)
# ─────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────
#  Dark template — fluid glass background from bg_dark.png
# ─────────────────────────────────────────────────────────────

# Text colours for the dark/fluid bg
DIM_LIGHT   = HexColor("#C8B89A")   # secondary text (warm cream)
ORANGE_NAME = HexColor("#EB7228")   # name + programme text


def build_dark(c, PW, PH, full_name, cert_type, duration,
               cert_id, date_str):
    """Fluid glass background certificate — warm text on dark."""
    margin = 30
    GOLD   = HexColor("#E8C87A")
    GOLD_R = HexColor("#B87830")

    # ── 1. Fluid background image ────────────────────────────
    if BG_DARK_PATH.exists():
        bg_img = PILImage.open(BG_DARK_PATH).convert("RGB")
        c.drawImage(_pil_to_reader(bg_img), 0, 0,
                    width=PW, height=PH, preserveAspectRatio=False)
    else:
        c.setFillColor(HexColor("#0A0808"))
        c.rect(0, 0, PW, PH, fill=1, stroke=0)

    # ── 2. Thin gold border ──────────────────────────────────
    c.setStrokeColor(GOLD_R)
    c.setLineWidth(1.2)
    c.setStrokeAlpha(0.6)
    c.rect(margin - 4, margin - 4,
           PW - 2*(margin-4), PH - 2*(margin-4), fill=0, stroke=1)
    c.setStrokeAlpha(1.0)

    # ── Layout: bottom-up from page bottom ─────────────────────
    date_baseline = margin + 48          # bottom row (fixed)
    sig_top   = date_baseline + 72       # top of signature image
    dur_y     = sig_top + 24             # Duration
    prog_y    = dur_y  + 34              # Programme name
    comp_y    = prog_y + 32              # "has successfully completed"
    rule_y    = comp_y + 22              # gold rule
    name_y    = rule_y + 18             # name baseline
    cert_y    = name_y + 68             # "this is to certify"
    heading_y = cert_y + 44             # CERTIFICATE OF COMPLETION

    # ── 3. TOP-RIGHT: logo icon — bigger ────────────────────
    icon_size = 72                       # increased from 56
    icon_x = PW - margin - icon_size - 6
    icon_y = PH - margin - icon_size - 4
    draw_image(c, LOGO_ICON_PATH, icon_x, icon_y, icon_size, icon_size)

    # ── 4. re·knew wordmark — tight kerning, centred above heading ─
    wm_font = F("Bricolage-Bold", "Helvetica-Bold")
    wm_size = 30
    wm_y    = heading_y + 38            # wordmark sits 38pt above heading baseline
    wm_gap  = wm_size * 0.03            # tight gap matching official logo
    wm_ih   = wm_size * 0.52
    wm_iw   = wm_ih
    wm_re_w = pdfmetrics.stringWidth("re",   wm_font, wm_size)
    wm_kn_w = pdfmetrics.stringWidth("knew", wm_font, wm_size)
    wm_total = wm_re_w + wm_gap + wm_iw + wm_gap + wm_kn_w
    wm_x0   = PW/2 - wm_total/2

    c.setFont(wm_font, wm_size)
    c.setFillColor(white)
    c.drawString(wm_x0, wm_y, "re")
    draw_image(c, LOGO_ICON_PATH,
               wm_x0 + wm_re_w + wm_gap,
               wm_y + wm_size * 0.06,
               wm_iw, wm_ih)
    c.setFillColor(white)
    c.drawString(wm_x0 + wm_re_w + wm_gap + wm_iw + wm_gap, wm_y, "knew")

    # ── 5. CERTIFICATE OF COMPLETION — Bricolage Bold ────────
    c._charSpace = 3.0
    ctext(c, "CERTIFICATE OF COMPLETION",
          F("Bricolage-Bold","Helvetica-Bold"), 19, heading_y, PW, GOLD)
    c._charSpace = 0

    # ── 6. "This is to certify that" — Raleway Light ─────────
    ctext(c, "This is to certify that",
          F("Raleway-Light","Helvetica"), 13, cert_y, PW, DIM_LIGHT)

    # ── 7. Recipient name — Bricolage Bold, unchanged size 50 ─
    name_font = F("Bricolage-Bold","Helvetica-Bold")
    name_size = 50
    while pdfmetrics.stringWidth(full_name, name_font, name_size) > PW * 0.78 and name_size > 26:
        name_size -= 1
    ctext(c, full_name, name_font, name_size, name_y, PW, white)

    # ── 8. Gold rule below name ───────────────────────────────
    hline(c, rule_y, margin + 20, PW - margin - 20, GOLD_R, 0.8)

    # ── 9. "has successfully completed" — Raleway ────────────
    ctext(c, "has successfully completed the program",
          F("Raleway","Helvetica"), 13, comp_y, PW, DIM_LIGHT)

    # ── 10. Programme name — Bricolage Bold ──────────────────
    prog_font = F("Bricolage-Bold","Helvetica-Bold")
    prog_size = 22
    while pdfmetrics.stringWidth(cert_type, prog_font, prog_size) > PW * 0.72 and prog_size > 13:
        prog_size -= 1
    ctext(c, cert_type, prog_font, prog_size, prog_y, PW, ORANGE_NAME)

    # ── 11. Duration — Raleway Light ─────────────────────────
    ctext(c, f"Duration: {duration}",
          F("Raleway-Light","Helvetica"), 13, dur_y, PW, DIM_LIGHT)

    # ── 12. Bottom row ───────────────────────────────────────
    medal_cx      = margin + 46
    medal_cy      = date_baseline + 12
    draw_medal(c, medal_cx, medal_cy, radius=13, dark=True)
    draw_date_block(c, medal_cx + 22, date_baseline, date_str, dark=True)
    draw_signature_block(c, PW - margin - 42, date_baseline, dark=True)

    # Cert ID removed — not shown on certificate
# ─────────────────────────────────────────────────────────────
#  Dispatcher
# ─────────────────────────────────────────────────────────────

def build_certificate(buffer, first_name, surname, cert_type, duration,
                      cohort_code, year, serial_number,
                      issued_date=None, template="dark"):
    register_fonts()
    PW, PH = landscape(A4)

    if issued_date is None:
        issued_date = date.today()

    full_name = f"{first_name.strip()} {surname.strip()}"
    cert_id   = f"RK-{cohort_code.upper()}-{year}-{str(serial_number).zfill(3)}"
    date_str  = issued_date.strftime("%B %-d, %Y")

    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    build_dark(c, PW, PH, full_name, cert_type, duration, cert_id, date_str)
    c.save()


# ─────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────

def generate_certificate_pdf(first_name, surname, cert_type, duration,
                              cohort_code, year, serial_number,
                              issued_date=None, output_path=None,
                              template="dark") -> bytes:
    buf = io.BytesIO()
    build_certificate(buf, first_name.strip(), surname.strip(),
                      cert_type, duration, cohort_code,
                      year, serial_number, issued_date, template)
    pdf_bytes = buf.getvalue()
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(pdf_bytes)
    return pdf_bytes


def build_filename(first_name, surname, cert_type, template="dark", ext="pdf"):
    clean = lambda s: s.strip().replace(" ", "_").replace("/", "-")
    suffix = "_Dark" if template == "dark" else ""
    return f"RK_Certificate_{clean(first_name)}_{clean(surname)}_{clean(cert_type)}{suffix}.{ext}"
