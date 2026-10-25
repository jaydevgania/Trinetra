"""
Trinetra Chaos Console — Hackathon Pitch Deck Generator
Produces: D:\VJTI\Trinetra_Pitch_Deck.pptx
"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt
import copy

# ── Palette ──────────────────────────────────────────────────────────────────
BG_DARK      = RGBColor(0x0D, 0x11, 0x17)   # near-black navy
BG_CARD      = RGBColor(0x14, 0x1A, 0x24)   # card surface
ACCENT_CYAN  = RGBColor(0x00, 0xD4, 0xFF)   # primary accent
ACCENT_GOLD  = RGBColor(0xFF, 0xC7, 0x00)   # crown / awards
ACCENT_GREEN = RGBColor(0x00, 0xE5, 0x7A)   # healthy / safe
ACCENT_RED   = RGBColor(0xFF, 0x4D, 0x4D)   # danger / crash
WHITE        = RGBColor(0xFF, 0xFF, 0xFF)
GREY_MID     = RGBColor(0x8A, 0x9B, 0xAA)
GREY_LIGHT   = RGBColor(0xCC, 0xD6, 0xE0)

W = Inches(13.33)   # widescreen 16:9
H = Inches(7.5)

prs = Presentation()
prs.slide_width  = W
prs.slide_height = H

BLANK_LAYOUT = prs.slide_layouts[6]   # truly blank

# ── Helper utilities ─────────────────────────────────────────────────────────

def add_slide():
    sl = prs.slides.add_slide(BLANK_LAYOUT)
    fill_bg(sl, BG_DARK)
    return sl

def fill_bg(slide, color):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color

def box(slide, l, t, w, h, color=None, alpha=None):
    shape = slide.shapes.add_shape(
        1,  # MSO_SHAPE_TYPE.RECTANGLE
        Inches(l), Inches(t), Inches(w), Inches(h)
    )
    shape.line.fill.background()   # no border
    if color:
        shape.fill.solid()
        shape.fill.fore_color.rgb = color
    else:
        shape.fill.background()
    return shape

def txt(slide, text, l, t, w, h,
        size=18, bold=False, color=WHITE, align=PP_ALIGN.LEFT,
        italic=False, wrap=True):
    txb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    txb.word_wrap = wrap
    tf = txb.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    return txb

def accent_line(slide, l, t, w, color=ACCENT_CYAN, thickness=0.04):
    box(slide, l, t, w, thickness, color)

def slide_num(slide, n):
    txt(slide, str(n), 12.8, 7.1, 0.4, 0.3,
        size=9, color=GREY_MID, align=PP_ALIGN.RIGHT)

def footer(slide, label=""):
    box(slide, 0, 7.2, 13.33, 0.3, BG_CARD)
    txt(slide, "TRINETRA CHAOS CONSOLE  |  Innovise 2026  —  Blockchain PS3",
        0.3, 7.22, 9, 0.25, size=8, color=GREY_MID)
    if label:
        txt(slide, label, 9.5, 7.22, 3.5, 0.25,
            size=8, color=ACCENT_CYAN, align=PP_ALIGN.RIGHT)

def add_bullet(tf, text, size=15, color=WHITE, bold=False, indent=False):
    p = tf.add_paragraph()
    p.alignment = PP_ALIGN.LEFT
    p.space_before = Pt(4)
    run = p.add_run()
    run.text = ("    " if indent else "") + text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color

def card(slide, l, t, w, h, title, body_lines,
         title_color=ACCENT_CYAN, body_size=13):
    """Dark card with title + bullet body"""
    box(slide, l, t, w, h, BG_CARD)
    # top accent strip
    box(slide, l, t, w, 0.04, title_color)
    txt(slide, title, l+0.15, t+0.1, w-0.3, 0.35,
        size=13, bold=True, color=title_color)
    txb = slide.shapes.add_textbox(
        Inches(l+0.15), Inches(t+0.5),
        Inches(w-0.3),  Inches(h-0.6))
    txb.word_wrap = True
    tf = txb.text_frame
    tf.word_wrap = True
    first = True
    for line in body_lines:
        if first:
            p = tf.paragraphs[0]
            first = False
        else:
            p = tf.add_paragraph()
        p.space_before = Pt(3)
        run = p.add_run()
        run.text = line
        run.font.size = Pt(body_size)
        run.font.color.rgb = GREY_LIGHT

# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 1  —  TITLE
# ═══════════════════════════════════════════════════════════════════════════
sl = add_slide()

# gradient-ish top strip
box(sl, 0, 0, 13.33, 0.08, ACCENT_CYAN)

# Big background word
bg_txb = sl.shapes.add_textbox(Inches(-0.3), Inches(1.5), Inches(14), Inches(4))
bg_tf  = bg_txb.text_frame
bg_p   = bg_tf.paragraphs[0]
bg_r   = bg_p.add_run()
bg_r.text = "TRINETRA"
bg_r.font.size  = Pt(200)
bg_r.font.bold  = True
bg_r.font.color.rgb = RGBColor(0x18, 0x22, 0x2E)  # very subtle

# Crown emoji + title
txt(sl, "👑", 0.5, 0.9, 1.5, 1.2, size=60, align=PP_ALIGN.CENTER)

txt(sl, "TRINETRA CHAOS CONSOLE", 1.8, 1.1, 10, 1.0,
    size=44, bold=True, color=ACCENT_CYAN)
txt(sl, "Adaptive Consensus Under Network Failures & Malicious Validators",
    1.8, 2.15, 10, 0.6, size=20, color=GREY_LIGHT, italic=True)

accent_line(sl, 1.8, 2.85, 9.5, ACCENT_GOLD, 0.055)

txt(sl, "A flight simulator for blockchain consensus —",
    1.8, 3.05, 10, 0.5, size=17, color=WHITE)
txt(sl, "crash your validators, inject Byzantine attacks,\nand earn a certified Resilience Score before you deploy.",
    1.8, 3.5, 10, 0.8, size=17, color=GREY_LIGHT)

txt(sl, "Innovise 2026  ·  Blockchain Track PS3", 1.8, 5.2, 8, 0.4,
    size=13, color=GREY_MID)

box(sl, 0, 7.2, 13.33, 0.3, BG_CARD)
slide_num(sl, 1)

# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 2  —  THE PROBLEM
# ═══════════════════════════════════════════════════════════════════════════
sl = add_slide()
box(sl, 0, 0, 13.33, 0.08, ACCENT_RED)
footer(sl, "THE PROBLEM")
slide_num(sl, 2)

txt(sl, "The Problem", 0.5, 0.2, 8, 0.6, size=32, bold=True, color=ACCENT_RED)
accent_line(sl, 0.5, 0.85, 5, ACCENT_RED)

txt(sl, "Distributed systems fail in the real world —", 0.5, 1.0, 12, 0.5,
    size=19, bold=True, color=WHITE)
txt(sl, "but nobody tests them under real chaos before deploying.",
    0.5, 1.45, 12, 0.5, size=19, color=GREY_LIGHT)

# 3 problem cards
problems = [
    ("💥  Server Crashes",
     ["Leader node dies mid-block", "Does the cluster elect a new leader?", "Or does it freeze forever?"]),
    ("🔌  Network Partitions",
     ["Two groups of nodes can't talk", "Do they split into 2 ledgers?", "Split-brain = double-spend = catastrophe"]),
    ("🤥  Byzantine Validators",
     ["A corrupt node lies to peers", "Sends different data to different nodes", "Equivocation attack = hidden fork"]),
]
for i, (title, lines) in enumerate(problems):
    card(sl, 0.4 + i*4.3, 2.1, 4.1, 3.5, title, lines,
         title_color=ACCENT_RED, body_size=14)

txt(sl, "🏦  Real Stakes: RBI's CBDC network, interbank settlement, supply-chain ledgers — all run distributed consensus with no chaos testing.",
    0.5, 5.8, 12.3, 0.6, size=13, color=ACCENT_GOLD, italic=True)

# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 3  —  OUR SOLUTION
# ═══════════════════════════════════════════════════════════════════════════
sl = add_slide()
box(sl, 0, 0, 13.33, 0.08, ACCENT_CYAN)
footer(sl, "OUR SOLUTION")
slide_num(sl, 3)

txt(sl, "Our Solution", 0.5, 0.2, 8, 0.6, size=32, bold=True, color=ACCENT_CYAN)
accent_line(sl, 0.5, 0.85, 5, ACCENT_CYAN)

txt(sl, "✈️  A Flight Simulator for Blockchain Consensus", 0.5, 1.05, 12, 0.5,
    size=22, bold=True, color=WHITE)

cols = [
    ("🔬  Simulate", ACCENT_CYAN,
     ["5-node Raft cluster", "Real Ed25519 cryptography", "Merkle-chained blocks", "150 tx/sec synthetic load"]),
    ("💣  Chaos", ACCENT_RED,
     ["Leader crash & recover", "Network partition", "Byzantine equivocation", "Gray failure (slow leader)", "Latency storms"]),
    ("📊  Certify", ACCENT_GREEN,
     ["Live Resilience Score A–F", "MTTR < 400ms proven", "17 automated safety tests", "Published formula — no black box"]),
]
for i, (title, color, lines) in enumerate(cols):
    card(sl, 0.4 + i*4.3, 1.8, 4.1, 4.0, title, lines,
         title_color=color, body_size=14)

txt(sl, "No vendor lock-in.  No cloud dependency.  Runs 100% offline.  Open-source.",
    0.5, 6.1, 12, 0.4, size=13, color=GREY_MID, align=PP_ALIGN.CENTER)

# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 4  —  HOW IT WORKS (Architecture)
# ═══════════════════════════════════════════════════════════════════════════
sl = add_slide()
box(sl, 0, 0, 13.33, 0.08, ACCENT_GOLD)
footer(sl, "ARCHITECTURE")
slide_num(sl, 4)

txt(sl, "How It Works", 0.5, 0.2, 8, 0.55, size=32, bold=True, color=ACCENT_GOLD)
accent_line(sl, 0.5, 0.8, 5, ACCENT_GOLD)

# Architecture diagram (text-based boxes + arrows)
layers = [
    (0.4,  1.0, 12.5, 0.7, ACCENT_CYAN,   "WEB DASHBOARD  (HTML + Chart.js + Canvas topology)  —  Live drag-and-drop Scenario Composer · Tx Studio · Voice Narration · Dark/Light Theme"),
    (0.4,  1.85, 12.5, 0.7, ACCENT_GOLD,  "FASTAPI  REST + WebSocket (10 Hz push)  —  /inject, /scenario, /manual-tx, /chaos-*, /metrics, /report"),
    (0.4,  2.7,  5.9,  2.3, ACCENT_GREEN, "CONSENSUS ENGINE\nRaft (PreVote · Leader Transfer · Gray Failure)\nAdaptive Timeouts (Jacobson/Karels SRTT)\nByzantine Gossip + Echo Quorum"),
    (6.45, 2.7,  6.45, 2.3, ACCENT_RED,   "CHAOS ENGINE\nChaos Monkey (1000 Jepsen schedules)\nGeo-Latency Presets (Mumbai / Frankfurt / Virginia)\nPartition · Equivocation · Latency Storm"),
    (0.4,  5.15, 5.9,  1.5, GREY_MID,    "LEDGER LAYER\nSigned Txs · Merkle Blocks · TokenLedger\nInvariant Checker · Continuous Fork Detection"),
    (6.45, 5.15, 6.45, 1.5, GREY_MID,    "OBSERVABILITY\nPrometheus /metrics · Resilience Score\nWireshark RPC Tracer · HTML/JSON Report\nGrafana Dashboard"),
]
for (l, t, w, h, color, label) in layers:
    box(sl, l, t, w, h, BG_CARD)
    box(sl, l, t, w, 0.05, color)
    txb = sl.shapes.add_textbox(Inches(l+0.15), Inches(t+0.1), Inches(w-0.3), Inches(h-0.15))
    txb.word_wrap = True
    tf = txb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    run = p.add_run()
    first_line = label.split('\n')[0]
    run.text = first_line
    run.font.size = Pt(12)
    run.font.bold = True
    run.font.color.rgb = color
    for extra in label.split('\n')[1:]:
        ep = tf.add_paragraph()
        er = ep.add_run()
        er.text = extra
        er.font.size = Pt(11)
        er.font.color.rgb = GREY_LIGHT

# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 5  —  LIVE DEMO WALK-THROUGH
# ═══════════════════════════════════════════════════════════════════════════
sl = add_slide()
box(sl, 0, 0, 13.33, 0.08, ACCENT_GREEN)
footer(sl, "LIVE DEMO")
slide_num(sl, 5)

txt(sl, "Live Demo — What You'll See", 0.5, 0.2, 12, 0.55,
    size=32, bold=True, color=ACCENT_GREEN)
accent_line(sl, 0.5, 0.8, 10, ACCENT_GREEN)

steps = [
    ("1", ACCENT_CYAN,   "Cluster Starts",
     "5 nodes online · Crown 👑 on N0 · 150 tx/sec · all Ledger blocks same height"),
    ("2", ACCENT_RED,    "Crash the Leader",
     "Click 'Crash N0' → heartbeats stop → Narrator: 'Heartbeat stream terminated'"),
    ("3", ACCENT_GOLD,   "Election Fires",
     "N2 wins PreVote in ~320ms → Crown moves → MTTR card updates live"),
    ("4", ACCENT_GREEN,  "Recovery",
     "Click 'Recover All' → N0 rejoins as Follower → downloads missing blocks → all 5 in sync"),
    ("5", ACCENT_CYAN,   "Byzantine Attack",
     "Enable Hardened Mode → inject Equivocation → Echo Quorum blocks the fork → invariants ✅"),
    ("6", ACCENT_GOLD,   "Resilience Score",
     "Run Autopilot → all 6 chapters auto-play → Score card: A 87.5/100"),
]

row_h = 0.82
for i, (num, color, title, desc) in enumerate(steps):
    t = 1.0 + i * row_h
    box(sl, 0.4, t, 0.55, 0.62, color)
    txt(sl, num, 0.4, t+0.1, 0.55, 0.45, size=22, bold=True,
        color=BG_DARK, align=PP_ALIGN.CENTER)
    txt(sl, title, 1.05, t+0.02, 3.2, 0.35, size=13, bold=True, color=color)
    txt(sl, desc,  1.05, t+0.35, 11.7, 0.35, size=12, color=GREY_LIGHT)

# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 6  —  KEY FEATURES
# ═══════════════════════════════════════════════════════════════════════════
sl = add_slide()
box(sl, 0, 0, 13.33, 0.08, ACCENT_CYAN)
footer(sl, "FEATURES")
slide_num(sl, 6)

txt(sl, "14 Advanced Features", 0.5, 0.2, 12, 0.55,
    size=32, bold=True, color=ACCENT_CYAN)
accent_line(sl, 0.5, 0.8, 7, ACCENT_CYAN)

features = [
    ("🎙️  Live Narrator",      "Real-time plain-English captions of every consensus event",      ACCENT_CYAN),
    ("🔊  Voice Narration",     "Web Speech API reads events aloud — accessibility + wow factor", ACCENT_CYAN),
    ("🤖  Autopilot Demo",      "6-chapter choreographed demo — one button, full story",          ACCENT_GOLD),
    ("⏸️  Pause / Step / Replay","Freeze time, step one tick, replay any chaos sequence",         ACCENT_GOLD),
    ("🌍  Geo-Latency Presets", "Single DC · Mumbai–Frankfurt–Virginia real-world delays",        ACCENT_GREEN),
    ("📊  Resilience Score",    "Published formula A–F grade — not a black box",                  ACCENT_GREEN),
    ("🎭  Scenario Composer",   "Drag-and-drop chaos event sequencer — build your own attack",    ACCENT_CYAN),
    ("💸  Tx Studio",           "Sign & submit manual transactions · see cryptographic receipt",  ACCENT_CYAN),
    ("🕵️  Gray Failure Detect", "Slow leader detection via EWMA jitter — hardest failure type",   ACCENT_RED),
    ("🧬  Merkle Proof Viewer", "Visual tree + inclusion proof for any transaction",               ACCENT_GOLD),
    ("📡  Wireshark Tracer",    "Packet-level RPC ring buffer — see every heartbeat & vote",      ACCENT_GOLD),
    ("🦊  Chaos Monkey",        "1000 Jepsen-style randomized schedules in virtual time",         ACCENT_RED),
    ("📈  Prometheus + Grafana","Export /metrics, pre-built Grafana dashboard JSON",              ACCENT_GREEN),
    ("🌗  Dark / Light Theme",  "Obsidian Eye dark + clean light — pitch-ready in any room",      GREY_LIGHT),
]

cols_n = 2
per_col = 7
col_w = 6.3
for i, (name, desc, color) in enumerate(features):
    col = i // per_col
    row = i % per_col
    l = 0.4 + col * (col_w + 0.4)
    t = 1.0 + row * 0.82
    box(sl, l, t, col_w, 0.72, BG_CARD)
    box(sl, l, t, 0.04, 0.72, color)
    txt(sl, name, l+0.15, t+0.05, col_w-0.2, 0.32, size=12, bold=True, color=color)
    txt(sl, desc, l+0.15, t+0.36, col_w-0.2, 0.3,  size=10.5, color=GREY_LIGHT)

# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 7  —  TECHNICAL DEPTH
# ═══════════════════════════════════════════════════════════════════════════
sl = add_slide()
box(sl, 0, 0, 13.33, 0.08, ACCENT_GOLD)
footer(sl, "TECHNICAL DEPTH")
slide_num(sl, 7)

txt(sl, "Technical Depth", 0.5, 0.2, 8, 0.55, size=32, bold=True, color=ACCENT_GOLD)
accent_line(sl, 0.5, 0.8, 6, ACCENT_GOLD)

left_items = [
    ("Ed25519 Cryptography (PyNaCl)",
     "Every transaction and block header carries a real digital signature.\nForgery is computationally infeasible."),
    ("Raft — Full Paper Implementation",
     "PreVote (prevents disruptive elections) · Leader Transfer (TimeoutNow)\nLog matching invariant checked continuously."),
    ("Jacobson/Karels RTT Estimator",
     "SRTT / RTTVAR / RTO — same algorithm used in TCP.\nAdaptive election timeouts track jitter per-follower."),
    ("Binary Merkle Trees",
     "SHA-256 canonical hashing · Merkle inclusion proofs\nAny tx verifiable without reading the full block."),
]
right_items = [
    ("Byzantine Echo Quorum",
     "4-of-5 signed-header protocol — Hardened Mode blocks equivocation.\nEquivProof generation + peer blacklisting."),
    ("Gray Failure Detection",
     "EWMA jitter tracking flags a slow leader before it causes churn.\nPlanned leader transfer triggers TimeoutNow gracefully."),
    ("Continuous Invariant Checker",
     "Election safety · log matching · chain integrity · state-root agreement\nChecked every simulation tick — no silent corruption."),
    ("Resilience Score Formula",
     "Score = 40×(1−Churn/MaxChurn) + 30×(1−MTTR/MaxMTTR) + 20×Avail + 10×(1−Forks/Max)\nPublished, auditable, A–F graded."),
]

for i, (title, body) in enumerate(left_items):
    t = 1.05 + i * 1.5
    txt(sl, "▸  " + title, 0.5, t, 6.1, 0.38, size=13, bold=True, color=ACCENT_GOLD)
    txt(sl, body, 0.5, t+0.38, 6.1, 0.9, size=11.5, color=GREY_LIGHT)

for i, (title, body) in enumerate(right_items):
    t = 1.05 + i * 1.5
    txt(sl, "▸  " + title, 6.8, t, 6.1, 0.38, size=13, bold=True, color=ACCENT_CYAN)
    txt(sl, body, 6.8, t+0.38, 6.1, 0.9, size=11.5, color=GREY_LIGHT)

accent_line(sl, 6.5, 1.0, 0.04, GREY_MID, 5.5)

# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 8  —  RESULTS & BENCHMARKS
# ═══════════════════════════════════════════════════════════════════════════
sl = add_slide()
box(sl, 0, 0, 13.33, 0.08, ACCENT_GREEN)
footer(sl, "RESULTS")
slide_num(sl, 8)

txt(sl, "Results & Benchmarks", 0.5, 0.2, 10, 0.55, size=32, bold=True, color=ACCENT_GREEN)
accent_line(sl, 0.5, 0.8, 7, ACCENT_GREEN)

# Big KPI numbers
kpis = [
    ("87.5", "/ 100", "Resilience Score", ACCENT_GOLD),
    ("<400", "ms",    "MTTR (Leader Crash)", ACCENT_GREEN),
    ("150+", "tx/s",  "Sustained Throughput", ACCENT_CYAN),
    ("17",   "tests", "All Passing (CI Gate)", ACCENT_GREEN),
]
for i, (num, unit, label, color) in enumerate(kpis):
    l = 0.4 + i * 3.2
    box(sl, l, 1.1, 3.0, 2.0, BG_CARD)
    box(sl, l, 1.1, 3.0, 0.06, color)
    txt(sl, num, l, 1.3, 3.0, 1.0, size=52, bold=True,
        color=color, align=PP_ALIGN.CENTER)
    txt(sl, unit, l, 2.2, 3.0, 0.38, size=16,
        color=WHITE, align=PP_ALIGN.CENTER)
    txt(sl, label, l, 2.6, 3.0, 0.38, size=11,
        color=GREY_MID, align=PP_ALIGN.CENTER)

# Comparison table
txt(sl, "Adaptive vs. Static Timeout Comparison", 0.5, 3.25, 8, 0.4,
    size=16, bold=True, color=WHITE)

headers = ["Metric", "Static Mode", "Adaptive Mode (Ours)", "Improvement"]
col_ws  = [3.5, 2.5, 3.2, 2.8]
col_ls  = [0.4, 3.9, 6.4, 9.6]
rows    = [
    ["Resilience Score", "57.8 / 100", "87.5 / 100", "+51% ✅"],
    ["Election Churn",   "618 / min",  "3 / min",    "-99.5% ✅"],
    ["p95 Latency",      "48 ms",      "48 ms",       "Maintained ✅"],
    ["CI Gate (≥80)",    "FAIL ✗",     "PASS ✓",      ""],
]

for j, (hdr, cw, cl) in enumerate(zip(headers, col_ws, col_ls)):
    box(sl, cl, 3.7, cw-0.05, 0.38, ACCENT_CYAN if j == 2 else BG_CARD)
    txt(sl, hdr, cl+0.1, 3.72, cw-0.15, 0.34, size=12, bold=True,
        color=BG_DARK if j == 2 else ACCENT_CYAN)

for ri, row in enumerate(rows):
    bg = RGBColor(0x17, 0x21, 0x2E) if ri % 2 == 0 else BG_CARD
    for j, (cell, cw, cl) in enumerate(zip(row, col_ws, col_ls)):
        box(sl, cl, 4.1 + ri*0.45, cw-0.05, 0.42, bg)
        color = ACCENT_GREEN if "✅" in cell else (ACCENT_RED if "✗" in cell else WHITE)
        txt(sl, cell, cl+0.1, 4.12+ri*0.45, cw-0.15, 0.38, size=12, color=color)

# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 9  —  WHY WE WIN TOP 1
# ═══════════════════════════════════════════════════════════════════════════
sl = add_slide()
box(sl, 0, 0, 13.33, 0.08, ACCENT_GOLD)
footer(sl, "WHY TOP 1")
slide_num(sl, 9)

txt(sl, "Why Trinetra Wins Top 1", 0.5, 0.2, 12, 0.55,
    size=32, bold=True, color=ACCENT_GOLD)
accent_line(sl, 0.5, 0.8, 10, ACCENT_GOLD)

diff = [
    ("Most hackathon projects...", ACCENT_RED,
     ["Fake random numbers for 'consensus'",
      "No real cryptography — hashes only",
      "Single happy-path demo",
      "No automated tests",
      "Black-box score with no formula"]),
    ("Trinetra delivers...", ACCENT_GREEN,
     ["Real Raft — PreVote + Leader Transfer + Gray Failure",
      "Ed25519 digital signatures on every block & tx",
      "8 named scenarios + drag-and-drop Scenario Composer",
      "17 pytest tests + GitHub Actions CI gate",
      "Published, auditable Resilience Score formula"]),
]

for i, (title, color, pts) in enumerate(diff):
    l = 0.5 + i * 6.7
    txt(sl, title, l, 1.0, 6.3, 0.45, size=17, bold=True, color=color)
    for j, pt in enumerate(pts):
        prefix = "✗  " if color == ACCENT_RED else "✅  "
        txt(sl, prefix + pt, l, 1.55 + j*0.72, 6.3, 0.6,
            size=13.5, color=GREY_LIGHT if color == ACCENT_RED else WHITE)

# VS divider
box(sl, 6.55, 1.0, 0.04, 4.5, GREY_MID)
txt(sl, "VS", 6.25, 3.05, 0.85, 0.5, size=20, bold=True,
    color=GREY_MID, align=PP_ALIGN.CENTER)

txt(sl, "🏆  Judges can verify every claim live on screen — no slides, just working software.",
    0.5, 6.0, 12.3, 0.45, size=14, bold=True, color=ACCENT_GOLD, align=PP_ALIGN.CENTER)

# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 10  —  REAL WORLD APPLICATIONS
# ═══════════════════════════════════════════════════════════════════════════
sl = add_slide()
box(sl, 0, 0, 13.33, 0.08, ACCENT_CYAN)
footer(sl, "MARKET")
slide_num(sl, 10)

txt(sl, "Real-World Applications", 0.5, 0.2, 12, 0.55,
    size=32, bold=True, color=ACCENT_CYAN)
accent_line(sl, 0.5, 0.8, 8, ACCENT_CYAN)

markets = [
    ("🏦  CBDC & Banking",      ACCENT_GOLD,
     ["RBI's Digital Rupee network", "Interbank settlement (RTGS)", "Cross-border payment rails"]),
    ("⛓️  Enterprise Blockchain", ACCENT_CYAN,
     ["Hyperledger Fabric pre-deploy testing", "Supply-chain ledger certification", "Trade finance networks"]),
    ("☁️  Cloud Infrastructure",  ACCENT_GREEN,
     ["Distributed database chaos testing", "Kubernetes etcd cluster validation", "SRE resilience certification"]),
    ("📋  Compliance & Audit",    ACCENT_RED,
     ["Certifiable Resilience Score report", "Regulator-friendly HTML/JSON export", "ISO 22301 business continuity"]),
]
for i, (title, color, pts) in enumerate(markets):
    l = 0.4 + i * 3.2
    box(sl, l, 1.15, 3.0, 4.5, BG_CARD)
    box(sl, l, 1.15, 3.0, 0.06, color)
    txt(sl, title, l+0.15, 1.25, 2.8, 0.5, size=12.5, bold=True, color=color)
    for j, pt in enumerate(pts):
        txt(sl, "•  " + pt, l+0.15, 1.85 + j*0.75, 2.75, 0.62,
            size=12, color=GREY_LIGHT)

txt(sl, "Total Addressable Market:  Distributed systems testing & blockchain DevSecOps  —  est. \$4.2B by 2028",
    0.5, 5.85, 12.3, 0.45, size=13, color=GREY_MID, italic=True, align=PP_ALIGN.CENTER)

# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 11  —  CLOSING / CALL TO ACTION
# ═══════════════════════════════════════════════════════════════════════════
sl = add_slide()
box(sl, 0, 0, 13.33, 0.08, ACCENT_CYAN)
box(sl, 0, 7.2, 13.33, 0.3, BG_CARD)
slide_num(sl, 11)

# Big BG word
bg_txb = sl.shapes.add_textbox(Inches(-0.2), Inches(2.0), Inches(14), Inches(4))
bg_tf  = bg_txb.text_frame
bg_p   = bg_tf.paragraphs[0]
bg_r   = bg_p.add_run()
bg_r.text = "TOP 1"
bg_r.font.size  = Pt(230)
bg_r.font.bold  = True
bg_r.font.color.rgb = RGBColor(0x18, 0x22, 0x2E)

txt(sl, "👑", 5.9, 0.5, 1.5, 1.2, size=60, align=PP_ALIGN.CENTER)

txt(sl, "Try it live →  http://127.0.0.1:8000", 1.5, 1.6, 10.3, 0.6,
    size=18, color=ACCENT_CYAN, align=PP_ALIGN.CENTER)

txt(sl, "TRINETRA CHAOS CONSOLE", 1.0, 2.35, 11.3, 0.8,
    size=42, bold=True, color=WHITE, align=PP_ALIGN.CENTER)

txt(sl, "Real crypto.  Real Raft.  Real resilience.",
    1.0, 3.15, 11.3, 0.55, size=22, color=GREY_LIGHT,
    italic=True, align=PP_ALIGN.CENTER)

accent_line(sl, 2.0, 3.8, 9.33, ACCENT_GOLD, 0.055)

ctas = [
    "One button → Autopilot runs all 6 chaos chapters",
    "Live dashboard → Crown moves when leader changes",
    "Resilience Score → A 87.5/100 · Published formula",
]
for i, cta in enumerate(ctas):
    txt(sl, "✅  " + cta, 2.5, 4.0 + i*0.52, 8.33, 0.45,
        size=15, color=WHITE, align=PP_ALIGN.CENTER)

txt(sl, "Innovise 2026  ·  Blockchain Track PS3  ·  Adaptive Consensus Under Network Failures & Malicious Validators",
    0.5, 6.8, 12.33, 0.35, size=9, color=GREY_MID, align=PP_ALIGN.CENTER)

# ── Save ─────────────────────────────────────────────────────────────────────
out = r"D:\VJTI\Trinetra_Pitch_Deck.pptx"
prs.save(out)
print(f"Saved: {out}")
print(f"Slides: {len(prs.slides)}")
