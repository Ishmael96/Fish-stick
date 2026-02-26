import os, uuid, random, textwrap
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, abort
from werkzeug.utils import secure_filename
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Use a directory inside the project (works on Render)
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
REPORT_DIR = os.path.join(BASE_DIR, 'reports')
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

ALLOWED = {'pdf', 'doc', 'docx', 'txt'}

# ── Colours ──────────────────────────────────────────────────────────────────
W, H      = A4
BLUE      = colors.HexColor('#009bde')
RED       = colors.HexColor('#e8452c')
ORANGE    = colors.HexColor('#f5a623')
GREEN     = colors.HexColor('#5ba829')
PURPLE    = colors.HexColor('#7b3fa0')
GREY      = colors.HexColor('#555555')
LGREY     = colors.HexColor('#f7f7f7')
LINE      = colors.HexColor('#e0e0e0')
CYAN_HL   = colors.HexColor('#cdf0ff')
CAUTION   = colors.HexColor('#e8f4fb')
WHITE     = colors.white
BLACK     = colors.HexColor('#1a1a1a')

SRC_COL = [
    colors.HexColor('#e8452c'), colors.HexColor('#9b27af'),
    colors.HexColor('#673ab7'), colors.HexColor('#2e7d32'),
    colors.HexColor('#388e3c'), colors.HexColor('#b07d00'),
    colors.HexColor('#5d4037'), colors.HexColor('#1565c0'),
    colors.HexColor('#00838f'), colors.HexColor('#d84315'),
    colors.HexColor('#37474f'), colors.HexColor('#006064'),
    colors.HexColor('#880e4f'),
]

PRIMARY_SOURCES = [
    ("Submitted to Eaton Business School",                   "Student Paper",   "1%"),
    ('Karim Feroz, Kembley Lingelbach. "Research Methods in IT and Information Systems", Routledge, 2026',
                                                             "Publication",     "1%"),
    ("Submitted to The University of the West of Scotland",  "Student Paper",   "1%"),
    ("Submitted to King's College",                          "Student Paper",   "1%"),
    ("mathematics.foi.hr",                                   "Internet Source", "1%"),
    ("ojs.literacyinstitute.org",                            "Internet Source", "1%"),
    ("Submitted to Deakin University",                       "Student Paper",  "<1%"),
    ("www.ncl.ac.uk",                                        "Internet Source","<1%"),
    ("oulurepo.oulu.fi",                                     "Internet Source","<1%"),
    ("www.mdpi.com",                                         "Internet Source","<1%"),
    ("norma.ncirl.ie",                                       "Internet Source","<1%"),
    ("repository.uwtsd.ac.uk",                               "Internet Source","<1%"),
    ('Bano, Nabiya. "HYPER-IMPULSIVE CONSUMPTION OF FAST FASHION", Bilkent Universitesi',
                                                             "Publication",    "<1%"),
]

# ══════════════════════════════════════════════════════════════════════════════
#  DRAWING HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def header_footer(c, label, sid):
    """Replica turnitin header + footer on every page."""
    c.saveState()
    # ── top rule ──
    c.setStrokeColor(LINE); c.setLineWidth(0.5)
    c.line(18*mm, H-13*mm, W-18*mm, H-13*mm)
    # ── logo badge (blue rounded rect + white bold text) ──
    c.setFillColor(BLUE)
    c.roundRect(18*mm, H-12*mm, 8*mm, 7*mm, 1.2*mm, fill=1, stroke=0)
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 6.5)
    c.drawCentredString(22*mm, H-8.8*mm, "t]")
    # ── "turnitin" wordmark ──
    c.setFillColor(BLUE); c.setFont("Helvetica-Bold", 8)
    c.drawString(28*mm, H-8.5*mm, "turnitin")
    # ── centre label ──
    c.setFillColor(GREY); c.setFont("Helvetica", 7)
    c.drawCentredString(W/2, H-8.5*mm, label)
    # ── right submission id ──
    c.setFont("Helvetica", 6.5)
    c.drawRightString(W-18*mm, H-8.5*mm, f"Submission ID  {sid}")

    # ── bottom rule ──
    c.line(18*mm, 13*mm, W-18*mm, 13*mm)
    c.setFillColor(BLUE)
    c.roundRect(18*mm, 6*mm, 8*mm, 7*mm, 1.2*mm, fill=1, stroke=0)
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 6.5)
    c.drawCentredString(22*mm, 9.2*mm, "t]")
    c.setFillColor(BLUE); c.setFont("Helvetica-Bold", 8)
    c.drawString(28*mm, 9*mm, "turnitin")
    c.setFillColor(GREY); c.setFont("Helvetica", 7)
    c.drawCentredString(W/2, 9*mm, label)
    c.setFont("Helvetica", 6.5)
    c.drawRightString(W-18*mm, 9*mm, f"Submission ID  {sid}")
    c.restoreState()


def wrapped_lines(text, max_chars):
    lines = []
    for para in text.split('\n\n'):
        lines.extend(textwrap.wrap(para.replace('\n', ' '), max_chars))
        lines.append('')
    return lines


def draw_text_body(c, paragraphs, sid, start_page, mode, cyan_set=None, src_map=None):
    """
    Draw document body across pages with highlighting.
    mode='sim'  → coloured source highlights
    mode='ai'   → cyan AI highlights
    """
    CHAR_W   = 5.05        # approx pts per char at size 9
    LINE_H   = 5.6 * mm
    LEFT     = 22 * mm
    RIGHT    = W - 22 * mm
    MAX_W    = RIGHT - LEFT
    BOTTOM   = 20 * mm
    TOP_Y    = H - 26 * mm

    page = start_page
    y    = TOP_Y
    header_footer(c, f"Page {page} of 22 - AI Writing Submission", sid)

    word_idx = 0

    for para in paragraphs:
        words = para.split()
        if not words:
            y -= LINE_H * 0.6
            if y < BOTTOM:
                c.showPage(); page += 1; y = TOP_Y
                header_footer(c, f"Page {page} of 22 - AI Writing Submission", sid)
            continue

        is_heading = len(para) < 90 and (para.isupper() or para.endswith(':'))
        font = "Helvetica-Bold" if is_heading else "Helvetica"

        # wrap words into visual lines
        line_buf  = []
        line_w    = 0.0

        def flush_line(buf, wi_start):
            nonlocal y, page
            if y < BOTTOM:
                c.showPage(); page += 1; y = TOP_Y
                header_footer(c, f"Page {page} of 22 - AI Writing Submission", sid)
            cx = LEFT
            for k, w in enumerate(buf):
                ww = (len(w) + 1) * CHAR_W
                wi = wi_start + k
                # draw highlight rect
                if mode == 'sim' and src_map and wi in src_map:
                    col = SRC_COL[src_map[wi] % len(SRC_COL)]
                    c.saveState()
                    c.setFillColor(col)
                    c.setFillAlpha(0.22)
                    c.rect(cx - 1, y - 1.5, ww, 4.8*mm, fill=1, stroke=0)
                    c.restoreState()
                    c.setFillColor(col)
                elif mode == 'ai' and cyan_set and wi in cyan_set:
                    c.saveState()
                    c.setFillColor(CYAN_HL)
                    c.setFillAlpha(0.7)
                    c.rect(cx - 1, y - 1.5, ww, 4.8*mm, fill=1, stroke=0)
                    c.restoreState()
                    c.setFillColor(BLACK)
                else:
                    c.setFillColor(BLACK)
                c.setFont(font, 9)
                c.drawString(cx, y, w)
                cx += ww
            y -= LINE_H

        for word in words:
            ww = (len(word) + 1) * CHAR_W
            if line_w + ww > MAX_W and line_buf:
                flush_line(line_buf, word_idx - len(line_buf))
                line_buf  = [word]
                line_w    = ww
            else:
                line_buf.append(word)
                line_w   += ww
            word_idx += 1

        if line_buf:
            flush_line(line_buf, word_idx - len(line_buf))

        y -= 3 * mm   # paragraph gap
        if y < BOTTOM:
            c.showPage(); page += 1; y = TOP_Y
            header_footer(c, f"Page {page} of 22 - AI Writing Submission", sid)


# ══════════════════════════════════════════════════════════════════════════════
#  COVER PAGE (shared by both reports)
# ══════════════════════════════════════════════════════════════════════════════
def draw_cover(c, meta, cover_label):
    sid = meta['submission_id']
    header_footer(c, cover_label, sid)

    y = H - 55*mm
    # name
    c.setFont("Helvetica-Bold", 18); c.setFillColor(BLACK)
    c.drawString(22*mm, y, "User User"); y -= 10*mm
    # filename
    c.setFont("Helvetica-Bold", 13)
    fname = meta['filename']
    if len(fname) > 55: fname = fname[:52] + '...'
    c.drawString(22*mm, y, fname); y -= 6*mm
    # repo lines
    for lbl in ["No Repository", "No Repository", "Turnitin"]:
        c.setFont("Helvetica", 8); c.setFillColor(GREY)
        c.drawString(26*mm, y, f"  {lbl}"); y -= 5*mm
    y -= 4*mm
    # divider
    c.setStrokeColor(LINE); c.setLineWidth(0.5)
    c.line(22*mm, y, W-22*mm, y); y -= 12*mm
    # Document Details heading
    c.setFont("Helvetica-Bold", 11); c.setFillColor(BLACK)
    c.drawString(22*mm, y, "Document Details"); y -= 12*mm

    def kv(k, v):
        nonlocal y
        c.setFont("Helvetica", 7.5); c.setFillColor(GREY)
        c.drawString(22*mm, y, k); y -= 5*mm
        c.setFont("Helvetica-Bold", 8.5); c.setFillColor(BLACK)
        c.drawString(22*mm, y, str(v)); y -= 10*mm

    kv("Submission ID",    meta['submission_id'])
    kv("Submission Date",  meta['date'])
    kv("Download Date",    meta['date'])
    kv("File Name",        meta['filename'])
    kv("File Size",        "258.8 KB")

    # stats box right
    bx = W/2 + 15*mm; by = H - 90*mm; bw = 60*mm; bh = 30*mm
    c.setStrokeColor(LINE); c.setLineWidth(0.5)
    c.rect(bx, by, bw, bh)
    sy = by + bh - 9*mm
    for s in [f"{meta['pages']} Pages",
              f"{meta['word_count']:,} Words",
              f"{meta['char_count']:,} Characters"]:
        c.setFont("Helvetica-Bold", 9); c.setFillColor(BLACK)
        c.drawString(bx + 4*mm, sy, s); sy -= 9*mm


# ══════════════════════════════════════════════════════════════════════════════
#  SIMILARITY REPORT
# ══════════════════════════════════════════════════════════════════════════════
def build_similarity_pdf(meta, path):
    c   = canvas.Canvas(path, pagesize=A4)
    sid = meta['submission_id']

    # — Page 1: Cover —
    draw_cover(c, meta, "Page 1 of 22 - Cover Page")
    c.showPage()

    # — Pages 2-N: Document body with highlighted matches —
    paras    = [p.strip() for p in meta['text'].split('\n') if p.strip()]
    words    = meta['text'].split()
    n        = len(words)
    n_hl     = max(1, int(n * 0.07))
    hl_idx   = sorted(random.sample(range(n), min(n_hl, n)))
    src_map  = {idx: i % 13 for i, idx in enumerate(hl_idx)}
    draw_text_body(c, paras, sid, 2, 'sim', src_map=src_map)

    # — Last page: Originality report summary —
    c.showPage()
    _sim_summary(c, meta)
    c.save()


def _sim_summary(c, meta):
    sid = meta['submission_id']
    header_footer(c, "Page 22 of 22 - Originality Report", sid)

    y = H - 30*mm; L = 22*mm
    # filename + ORIGINALITY REPORT label
    c.setFont("Helvetica-Bold", 11); c.setFillColor(BLACK)
    fname = meta['filename']
    if len(fname) > 60: fname = fname[:57] + '...'
    c.drawString(L, y, fname); y -= 8*mm
    c.setFont("Helvetica-Bold", 9); c.setFillColor(RED)
    c.drawString(L, y, "ORIGINALITY REPORT"); y -= 14*mm

    # — Big score numbers —
    scores = [
        (f"{meta['sim_index']}%", "SIMILARITY INDEX",  RED),
        (f"{meta['internet_pct']}%","INTERNET SOURCES", GREEN),
        (f"{meta['pub_pct']}%",    "PUBLICATIONS",      PURPLE),
        (f"{meta['student_pct']}%","STUDENT PAPERS",    ORANGE),
    ]
    sx = L
    for val, lbl, col in scores:
        c.setFont("Helvetica-Bold", 30); c.setFillColor(col)
        c.drawString(sx, y, val)
        c.setFont("Helvetica", 6.5); c.setFillColor(GREY)
        c.drawString(sx, y - 6*mm, lbl)
        sx += 38*mm
    y -= 22*mm

    # divider
    c.setStrokeColor(LINE); c.setLineWidth(0.5)
    c.line(L, y, W-22*mm, y); y -= 8*mm
    # PRIMARY SOURCES heading
    c.setFont("Helvetica-Bold", 8); c.setFillColor(RED)
    c.drawString(L, y, "PRIMARY SOURCES"); y -= 10*mm

    for i, (src, typ, pct) in enumerate(PRIMARY_SOURCES):
        if y < 28*mm: break
        col = SRC_COL[i % len(SRC_COL)]
        sq  = 5*mm
        # coloured square with number
        c.setFillColor(col)
        c.roundRect(L, y - sq + 2*mm, sq, sq, 0.8*mm, fill=1, stroke=0)
        c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 6.5)
        c.drawCentredString(L + sq/2, y - sq + 3.5*mm, str(i+1))
        # source name
        c.setFillColor(col); c.setFont("Helvetica", 8)
        disp = src if len(src) < 80 else src[:77] + '...'
        c.drawString(L + 7*mm, y, disp)
        # type label
        c.setFillColor(GREY); c.setFont("Helvetica", 7)
        c.drawString(L + 7*mm, y - 4.5*mm, typ)
        # percentage right
        c.setFont("Helvetica-Bold", 10); c.setFillColor(BLACK)
        c.drawRightString(W-22*mm, y - 1*mm, pct)
        y -= 13*mm
        # thin rule between sources
        c.setStrokeColor(LINE); c.setLineWidth(0.3)
        c.line(L, y + 2*mm, W-22*mm, y + 2*mm)

    # footer settings
    y -= 6*mm
    c.setFont("Helvetica", 7); c.setFillColor(GREY)
    c.drawString(L, y, "Exclude quotes    Off          Exclude matches    Off")
    y -= 5*mm
    c.drawString(L, y, "Exclude bibliography    On")


# ══════════════════════════════════════════════════════════════════════════════
#  AI WRITING REPORT
# ══════════════════════════════════════════════════════════════════════════════
def build_ai_pdf(meta, path):
    c   = canvas.Canvas(path, pagesize=A4)
    sid = meta['submission_id']

    # — Page 1: Cover —
    draw_cover(c, meta, "Page 1 of 22 - Cover Page")
    c.showPage()

    # — Page 2: AI Writing Overview —
    _ai_overview(c, meta)
    c.showPage()

    # — Pages 3+: Document with cyan highlights —
    paras  = [p.strip() for p in meta['text'].split('\n') if p.strip()]
    words  = meta['text'].split()
    n      = len(words)
    n_cyan = int(n * (meta['ai_pct'] / 100))
    all_i  = list(range(n)); random.shuffle(all_i)
    cyan_set = set(all_i[:n_cyan])
    draw_text_body(c, paras, sid, 3, 'ai', cyan_set=cyan_set)
    c.save()


def _ai_overview(c, meta):
    sid = meta['submission_id']
    ai  = meta['ai_pct']
    header_footer(c, "Page 2 of 22 - AI Writing Overview", sid)

    y = H - 30*mm; L = 22*mm

    # Big heading
    c.setFont("Helvetica-Bold", 24); c.setFillColor(BLACK)
    c.drawString(L, y, f"{ai}% detected as AI"); y -= 8*mm
    c.setFont("Helvetica", 8.5); c.setFillColor(GREY)
    c.drawString(L, y, "The percentage indicates the combined amount of likely AI-generated text as")
    y -= 5*mm
    c.drawString(L, y, "well as likely AI-generated text that was also likely AI-paraphrased.")

    # Caution box (right)
    bx = W/2 + 5*mm; by = H - 56*mm; bw = W/2 - 27*mm; bh = 26*mm
    c.setFillColor(CAUTION)
    c.setStrokeColor(colors.HexColor('#b8d9ec')); c.setLineWidth(0.8)
    c.roundRect(bx, by, bw, bh, 2*mm, fill=1, stroke=1)
    c.setFont("Helvetica-Bold", 8); c.setFillColor(colors.HexColor('#005a8b'))
    c.drawString(bx+3*mm, by+bh-7*mm, "Caution: Review required.")
    c.setFont("Helvetica", 7); c.setFillColor(GREY)
    caution = [
        "It is essential to understand the limitations",
        "of AI detection before making decisions about",
        "a student's work. We encourage you to learn",
        "more about Turnitin's AI detection capabilities.",
    ]
    cy = by + bh - 14*mm
    for ln in caution:
        c.drawString(bx+3*mm, cy, ln); cy -= 4.5*mm

    y -= 20*mm
    # divider
    c.setStrokeColor(LINE); c.setLineWidth(0.5)
    c.line(L, y, W-22*mm, y); y -= 10*mm

    # Detection Groups
    c.setFont("Helvetica-Bold", 10); c.setFillColor(BLACK)
    c.drawString(L, y, "Detection Groups"); y -= 12*mm

    # Group 1 — AI-generated only
    c.setFillColor(BLUE)
    c.circle(L+4*mm, y+2*mm, 4.5*mm, fill=1, stroke=0)
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 5.5)
    c.drawCentredString(L+4*mm, y+0.8*mm, "AI")
    c.setFont("Helvetica-Bold", 9); c.setFillColor(BLUE)
    c.drawString(L+11*mm, y+3*mm, f"27   AI-generated only   {ai}%")
    c.setFont("Helvetica", 7.5); c.setFillColor(GREY)
    c.drawString(L+11*mm, y-2*mm, "Likely AI-generated text from a large-language model.")
    y -= 14*mm

    # Group 2 — AI-paraphrased
    c.setFillColor(PURPLE)
    c.circle(L+4*mm, y+2*mm, 4.5*mm, fill=1, stroke=0)
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 5.5)
    c.drawCentredString(L+4*mm, y+0.8*mm, "AI")
    c.setFont("Helvetica-Bold", 9); c.setFillColor(PURPLE)
    c.drawString(L+11*mm, y+3*mm, "0   AI-generated text that was AI-paraphrased   0%")
    c.setFont("Helvetica", 7.5); c.setFillColor(GREY)
    c.drawString(L+11*mm, y-2*mm, "Likely AI-generated text that was likely revised using an AI-paraphrase tool")
    y -= 5*mm
    c.drawString(L+11*mm, y-2*mm, "or word spinner.")
    y -= 16*mm

    # divider
    c.setStrokeColor(LINE); c.line(L, y, W-22*mm, y); y -= 6*mm

    # Disclaimer
    c.setFont("Helvetica-Bold", 7); c.setFillColor(GREY)
    c.drawString(L, y, "Disclaimer"); y -= 5*mm
    disc = ("Our AI writing assessment is designed to help educators identify text that might be prepared "
            "by a generative AI tool. Our AI writing assessment may not always be accurate (i.e., our AI "
            "models may produce either false positive results or false negative results), so it should not "
            "be used as the sole basis for adverse actions against a student. It takes further scrutiny and "
            "human judgment in conjunction with an organization's application of its specific academic "
            "policies to determine whether any academic misconduct has occurred.")
    c.setFont("Helvetica", 6.8); c.setFillColor(GREY)
    for ln in textwrap.wrap(disc, 110):
        c.drawString(L, y, ln); y -= 4.5*mm
    y -= 8*mm

    # divider
    c.setStrokeColor(LINE); c.line(L, y, W-22*mm, y); y -= 10*mm

    # FAQ
    c.setFont("Helvetica-Bold", 11); c.setFillColor(BLACK)
    c.drawString(L, y, "Frequently Asked Questions"); y -= 10*mm

    faqs = [
        ("How should I interpret Turnitin's AI writing percentage and false positives?",
         "The percentage shown in the AI writing report is the amount of qualifying text within the "
         "submission that Turnitin's AI writing detection model determines was either likely AI-generated "
         "text from a large-language model or likely AI-generated text that was likely revised using an "
         "AI paraphrase tool or word spinner.\n\n"
         "False positives (incorrectly flagging human-written text as AI-generated) are a possibility "
         "in AI models. AI detection scores under 20% have a higher likelihood of false positives.\n\n"
         "The AI writing percentage should not be the sole basis to determine whether misconduct has "
         "occurred. The reviewer/instructor should use the percentage as a means to start a formative "
         "conversation with their student."),
        ("What does 'qualifying text' mean?",
         "Our model only processes qualifying text in the form of long-form writing. Qualifying text "
         "that has been determined to be likely AI-generated will be highlighted in cyan in the "
         "submission, and likely AI-generated and then likely AI-paraphrased will be highlighted purple.\n\n"
         "Non-qualifying text, such as bullet points and annotated bibliographies, will not be processed."),
    ]

    for q, a in faqs:
        if y < 35*mm: break
        c.setFont("Helvetica-Bold", 8); c.setFillColor(BLACK)
        c.drawString(L, y, q); y -= 6*mm
        c.setFont("Helvetica", 7.5); c.setFillColor(GREY)
        for ln in textwrap.wrap(a.replace('\n\n', '  '), 105):
            if y < 30*mm: break
            c.drawString(L, y, ln); y -= 4.8*mm
        y -= 6*mm


# ══════════════════════════════════════════════════════════════════════════════
#  TEXT EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════
def extract_text(path, filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    try:
        if ext == 'txt':
            with open(path, 'r', errors='ignore') as f:
                return f.read()
        if ext == 'pdf':
            from pypdf import PdfReader
            r = PdfReader(path)
            return '\n'.join(pg.extract_text() or '' for pg in r.pages)
        if ext in ('doc', 'docx'):
            import docx
            d = docx.Document(path)
            return '\n'.join(p.text for p in d.paragraphs)
    except Exception:
        pass
    return "Document text content placeholder."


# ══════════════════════════════════════════════════════════════════════════════
#  FLASK ROUTES
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    f = request.files['file']
    if not f or f.filename == '':
        return jsonify({'error': 'Empty file'}), 400
    ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
    if ext not in ALLOWED:
        return jsonify({'error': 'File type not allowed'}), 400

    sid  = uuid.uuid4().hex[:12]
    subid = f"trn:oid:::{random.randint(10000,99999)}:{random.randint(100000000,999999999)}"
    fn   = secure_filename(f.filename)
    fpath = os.path.join(UPLOAD_DIR, sid + '_' + fn)
    f.save(fpath)

    text       = extract_text(fpath, fn)
    word_count = len(text.split())
    char_count = len(text)
    pages      = max(1, word_count // 250)

    meta = {
        'submission_id': subid,
        'filename':      fn,
        'date':          datetime.utcnow().strftime('%b %d, %Y, %I:%M %p UTC'),
        'word_count':    word_count,
        'char_count':    char_count,
        'pages':         pages,
        'sim_index':     random.randint(5, 12),
        'internet_pct':  random.randint(1, 5),
        'pub_pct':       random.randint(1, 4),
        'student_pct':   random.randint(1, 6),
        'ai_pct':        random.randint(78, 93),
        'text':          text,
        'sid':           sid,
    }

    sim_path = os.path.join(REPORT_DIR, f'{sid}_similarity.pdf')
    ai_path  = os.path.join(REPORT_DIR, f'{sid}_ai.pdf')
    build_similarity_pdf(meta, sim_path)
    build_ai_pdf(meta, ai_path)

    return jsonify({
        'success':      True,
        'sid':          sid,
        'filename':     fn,
        'submission_id':subid,
        'date':         meta['date'],
        'word_count':   word_count,
        'char_count':   char_count,
        'pages':        pages,
        'sim_index':    meta['sim_index'],
        'internet_pct': meta['internet_pct'],
        'pub_pct':      meta['pub_pct'],
        'student_pct':  meta['student_pct'],
        'ai_pct':       meta['ai_pct'],
    })


@app.route('/download/<sid>/<rtype>')
def download(sid, rtype):
    if rtype not in ('similarity', 'ai'):
        abort(404)
    fname = f'{sid}_similarity.pdf' if rtype == 'similarity' else f'{sid}_ai.pdf'
    path  = os.path.join(REPORT_DIR, fname)
    if not os.path.exists(path):
        abort(404)
    dl_name = 'Similarity_Report.pdf' if rtype == 'similarity' else 'AI_Writing_Report.pdf'
    return send_file(path, as_attachment=True, download_name=dl_name)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
