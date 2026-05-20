"""
report_pdf.py
─────────────
ReportLab PDF generators for govManage.

Exports:
    build_compliance_report_pdf(report_data: dict) -> bytes
    build_risk_report_pdf(report_data: dict)       -> bytes
    build_policy_pack_pdf(pack_doc: dict)          -> bytes   (delegates to app._build_pdf_bytes)
    clean_text(val)                                            (shared Unicode sanitiser)

All functions return b"" if reportlab is not installed.
"""

from __future__ import annotations

import io
from typing import Any, Dict, List

# ── ReportLab ─────────────────────────────────────────────────────────────────
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors as rl_colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, PageBreak,
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    _ok = True
except Exception:
    _ok = False


# ── Shared colour palette (matches app.py) ────────────────────────────────────

if _ok:
    INDIGO   = rl_colors.HexColor('#4f46e5')
    DARK_BG  = rl_colors.HexColor('#1e293b')
    SLATE    = rl_colors.HexColor('#334155')
    MUTED    = rl_colors.HexColor('#64748b')
    LIGHT_BG = rl_colors.HexColor('#f8fafc')
    EMERALD  = rl_colors.HexColor('#10b981')
    AMBER    = rl_colors.HexColor('#f59e0b')
    ROSE     = rl_colors.HexColor('#ef4444')
    VIOLET   = rl_colors.HexColor('#7c3aed')
    GRID_CLR = rl_colors.HexColor('#e2e8f0')
    WHITE    = rl_colors.white


# ── Unicode / Latin-1 sanitiser (shared with app.py) ─────────────────────────

def clean_text(val: Any) -> Any:
    """Recursively strip non-Latin-1 characters so ReportLab doesn't crash."""
    if isinstance(val, str):
        replacements = {
            '‑': '-', '‒': '-', '–': '-', '—': '-',
            '−': '-', '‘': "'", '’': "'", '‚': "'",
            '“': '"', '”': '"', '„': '"', '‟': '"',
            ' ': ' ', ' ': ' ', ' ': ' ',
            '•': '*', '‣': '>', '⁃': '-', '●': '*',
            '…': '...', '·': '.', '→': '->',
            '✓': 'v', '✔': 'v', '✕': 'x', '✖': 'x',
        }
        for old, new in replacements.items():
            val = val.replace(old, new)
        val = val.encode('latin-1', errors='ignore').decode('latin-1')
        return val
    elif isinstance(val, list):
        return [clean_text(i) for i in val]
    elif isinstance(val, dict):
        return {k: clean_text(v) for k, v in val.items()}
    return val


# ── Shared style factory ──────────────────────────────────────────────────────

def _make_styles():
    """Return a dict of named ParagraphStyle objects."""
    return {
        'title': ParagraphStyle(
            'RPTitle', fontName='Helvetica-Bold', fontSize=20,
            textColor=DARK_BG, spaceAfter=4, wordWrap='CJK'),
        'subtitle': ParagraphStyle(
            'RPSub', fontName='Helvetica', fontSize=9,
            textColor=MUTED, spaceAfter=10, wordWrap='CJK'),
        'h2': ParagraphStyle(
            'RPH2', fontName='Helvetica-Bold', fontSize=12,
            textColor=INDIGO, spaceBefore=14, spaceAfter=4, wordWrap='CJK'),
        'h3': ParagraphStyle(
            'RPH3', fontName='Helvetica-Bold', fontSize=10,
            textColor=SLATE, spaceBefore=8, spaceAfter=3, wordWrap='CJK'),
        'body': ParagraphStyle(
            'RPBody', fontName='Helvetica', fontSize=9.5,
            textColor=SLATE, spaceAfter=4, leading=14, wordWrap='CJK'),
        'bullet': ParagraphStyle(
            'RPBullet', fontName='Helvetica', fontSize=9.5,
            textColor=SLATE, spaceAfter=3, leading=13,
            leftIndent=14, bulletIndent=0, wordWrap='CJK'),
        'th': ParagraphStyle(
            'RPTH', fontName='Helvetica-Bold', fontSize=9,
            textColor=WHITE, leading=11, wordWrap='CJK'),
        'td': ParagraphStyle(
            'RPTD', fontName='Helvetica', fontSize=8.5,
            textColor=SLATE, leading=11, wordWrap='CJK'),
        'td_bold': ParagraphStyle(
            'RPTDBold', fontName='Helvetica-Bold', fontSize=8.5,
            textColor=SLATE, leading=11, wordWrap='CJK'),
        'score': ParagraphStyle(
            'RPScore', fontName='Helvetica-Bold', fontSize=22,
            textColor=INDIGO, spaceAfter=2, alignment=TA_CENTER, wordWrap='CJK'),
        'score_label': ParagraphStyle(
            'RPScoreLabel', fontName='Helvetica', fontSize=8,
            textColor=MUTED, spaceAfter=0, alignment=TA_CENTER, wordWrap='CJK'),
        'badge': ParagraphStyle(
            'RPBadge', fontName='Helvetica-Bold', fontSize=9,
            textColor=WHITE, alignment=TA_CENTER, wordWrap='CJK'),
    }


def _doc(buf: io.BytesIO) -> SimpleDocTemplate:
    return SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=18*mm, bottomMargin=18*mm,
    )


def _divider(story: list, color=None):
    story.append(Spacer(1, 2*mm))
    story.append(HRFlowable(
        width='100%', thickness=0.5,
        color=color or GRID_CLR, spaceAfter=3*mm))


def _kpi_table(story: list, kpis: List[Dict[str, Any]], s: dict):
    """Render a row of KPI boxes."""
    row = []
    for kpi in kpis:
        cell = [
            Paragraph(str(kpi['value']), s['score']),
            Paragraph(kpi['label'], s['score_label']),
        ]
        row.append(cell)
    tbl = Table([row], colWidths=[42*mm] * len(kpis))
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_BG),
        ('BOX', (0, 0), (-1, -1), 0.4, GRID_CLR),
        ('INNERGRID', (0, 0), (-1, -1), 0.4, GRID_CLR),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 4*mm))


def _bullet_list(story: list, items: List[str], s: dict, prefix: str = '*'):
    for item in items:
        story.append(Paragraph(f'{prefix}  {item}', s['bullet']))


def _section_header(story: list, title: str, s: dict, accent=None):
    story.append(Paragraph(title, s['h2']))
    story.append(HRFlowable(
        width='100%', thickness=1.5,
        color=accent or INDIGO, spaceAfter=3*mm))


# ── Score colour helper ───────────────────────────────────────────────────────

def _score_color(score: int):
    if score >= 80:
        return EMERALD
    if score >= 60:
        return AMBER
    return ROSE


def _severity_color(sev: str):
    s = sev.strip().lower()
    if s == 'high':
        return ROSE
    if s == 'medium':
        return AMBER
    return EMERALD


# ── 1. Compliance Report PDF ──────────────────────────────────────────────────

def build_compliance_report_pdf(report_data: Dict[str, Any]) -> bytes:
    """
    Generate a professional A4 PDF for a compliance gap report.
    report_data: the JSON dict returned by /api/reports/compliance
    Returns raw PDF bytes, or b"" if reportlab unavailable.
    """
    if not _ok:
        return b""

    report_data = clean_text(report_data)
    s = _make_styles()
    buf = io.BytesIO()
    story: list = []

    title     = report_data.get('report_title', 'Compliance Gap Report')
    gen_at    = report_data.get('generated_at', '')
    fw_ids    = ', '.join(report_data.get('framework_ids', []))
    overall   = report_data.get('compliance_scores', {}).get('overall', 0)
    maturity  = report_data.get('maturity_level', 'N/A')
    next_rev  = report_data.get('next_review_date', 'N/A')

    # ── Cover header ──────────────────────────────────────────────────────────
    story.append(Paragraph(title, s['title']))
    meta = f"Generated: {gen_at}  |  Frameworks: {fw_ids or 'N/A'}"
    story.append(Paragraph(meta, s['subtitle']))

    # ── KPI strip ─────────────────────────────────────────────────────────────
    _kpi_table(story, [
        {'value': f"{overall}%", 'label': 'Overall Score'},
        {'value': maturity,      'label': 'Maturity Level'},
        {'value': next_rev,      'label': 'Next Review'},
        {'value': str(len(report_data.get('critical_gaps', []))), 'label': 'Critical Gaps'},
    ], s)

    _divider(story)

    # ── Executive Summary ─────────────────────────────────────────────────────
    _section_header(story, '1. Executive Summary', s, INDIGO)
    story.append(Paragraph(report_data.get('executive_summary', ''), s['body']))
    story.append(Spacer(1, 2*mm))

    # ── Framework Scores table ────────────────────────────────────────────────
    fw_scores = report_data.get('compliance_scores', {}).get('by_framework', [])
    if fw_scores:
        _section_header(story, '2. Framework Compliance Breakdown', s, EMERALD)
        tdata = [[
            Paragraph('Framework', s['th']),
            Paragraph('Score', s['th']),
            Paragraph('Status', s['th']),
        ]]
        for fw in fw_scores:
            score_val = fw.get('score', 0)
            status    = fw.get('status', 'N/A')
            tdata.append([
                Paragraph(fw.get('framework', ''), s['td_bold']),
                Paragraph(f"{score_val}%", s['td']),
                Paragraph(status, s['td']),
            ])
        tbl = Table(tdata, colWidths=[90*mm, 30*mm, 50*mm])
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), EMERALD),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, rl_colors.HexColor('#f0fdf4')]),
            ('GRID', (0, 0), (-1, -1), 0.4, GRID_CLR),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 4*mm))

    # ── Key Findings ─────────────────────────────────────────────────────────
    findings = report_data.get('key_findings', [])
    if findings:
        _section_header(story, '3. Key Findings', s, INDIGO)
        _bullet_list(story, findings, s)
        story.append(Spacer(1, 2*mm))

    # ── Critical Gaps ─────────────────────────────────────────────────────────
    gaps = report_data.get('critical_gaps', [])
    if gaps:
        _section_header(story, '4. Critical Gaps', s, ROSE)
        for gap in gaps:
            story.append(Paragraph(f'*  {gap}', s['bullet']))
        story.append(Spacer(1, 2*mm))

    # ── Recommendations ───────────────────────────────────────────────────────
    recs = report_data.get('recommendations', [])
    if recs:
        _section_header(story, '5. Recommendations', s, VIOLET)
        _bullet_list(story, recs, s)
        story.append(Spacer(1, 2*mm))

    # ── Action Plan table ─────────────────────────────────────────────────────
    actions = report_data.get('action_plan', [])
    if actions:
        _section_header(story, '6. Action Plan', s, AMBER)
        adata = [[
            Paragraph('Priority', s['th']),
            Paragraph('Action', s['th']),
            Paragraph('Timeline', s['th']),
            Paragraph('Owner', s['th']),
        ]]
        for a in actions:
            pri = a.get('priority', '')
            pri_color = ROSE if pri == 'High' else AMBER if pri == 'Medium' else EMERALD
            adata.append([
                Paragraph(pri, s['td_bold']),
                Paragraph(a.get('action', ''), s['td']),
                Paragraph(a.get('timeline', ''), s['td']),
                Paragraph(a.get('owner', ''), s['td']),
            ])
        atbl = Table(adata, colWidths=[22*mm, 90*mm, 30*mm, 28*mm])
        atbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), AMBER),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, rl_colors.HexColor('#fffbeb')]),
            ('GRID', (0, 0), (-1, -1), 0.4, GRID_CLR),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(atbl)

    doc = _doc(buf)
    doc.build(story)
    return buf.getvalue()


# ── 2. Risk Report PDF ────────────────────────────────────────────────────────

def build_risk_report_pdf(report_data: Dict[str, Any]) -> bytes:
    """
    Generate a professional A4 PDF for a risk assessment report.
    report_data: the JSON dict returned by /api/reports/risk
    Returns raw PDF bytes, or b"" if reportlab unavailable.
    """
    if not _ok:
        return b""

    report_data = clean_text(report_data)
    s = _make_styles()
    buf = io.BytesIO()
    story: list = []

    title       = report_data.get('report_title', 'Risk Assessment Report')
    gen_at      = report_data.get('generated_at', '')
    posture     = report_data.get('risk_posture', 'N/A')
    risk_score  = report_data.get('overall_risk_score', 0)

    # ── Cover header ──────────────────────────────────────────────────────────
    story.append(Paragraph(title, s['title']))
    meta = f"Generated: {gen_at}  |  Risk Posture: {posture}  |  Score: {risk_score}/100"
    story.append(Paragraph(meta, s['subtitle']))

    # ── KPI strip ─────────────────────────────────────────────────────────────
    risk_items  = report_data.get('risk_items', [])
    high_cnt    = sum(1 for r in risk_items if r.get('severity', '').lower() == 'high')
    med_cnt     = sum(1 for r in risk_items if r.get('severity', '').lower() == 'medium')
    low_cnt     = sum(1 for r in risk_items if r.get('severity', '').lower() == 'low')

    _kpi_table(story, [
        {'value': f"{risk_score}/100", 'label': 'Risk Score'},
        {'value': posture,             'label': 'Posture'},
        {'value': str(high_cnt),       'label': 'High Risks'},
        {'value': str(med_cnt + low_cnt), 'label': 'Med/Low Risks'},
    ], s)

    _divider(story)

    # ── Executive Summary ─────────────────────────────────────────────────────
    _section_header(story, '1. Executive Summary', s, INDIGO)
    story.append(Paragraph(report_data.get('executive_summary', ''), s['body']))
    story.append(Spacer(1, 2*mm))

    # ── Key Findings ──────────────────────────────────────────────────────────
    findings = report_data.get('key_findings', [])
    if findings:
        _section_header(story, '2. Key Findings', s, INDIGO)
        _bullet_list(story, findings, s)
        story.append(Spacer(1, 2*mm))

    # ── High Priority Risks ───────────────────────────────────────────────────
    hi_risks = report_data.get('high_priority_risks', [])
    if hi_risks:
        _section_header(story, '3. High-Priority Risks', s, ROSE)
        for r in hi_risks:
            story.append(Paragraph(f'*  {r}', s['bullet']))
        story.append(Spacer(1, 2*mm))

    # ── Risk Items detail table ───────────────────────────────────────────────
    if risk_items:
        _section_header(story, '4. Risk Register', s, AMBER)
        rdata = [[
            Paragraph('Risk ID', s['th']),
            Paragraph('Title', s['th']),
            Paragraph('Type', s['th']),
            Paragraph('Severity', s['th']),
            Paragraph('Mitigation', s['th']),
        ]]
        for r in risk_items:
            sev = r.get('severity', 'Low')
            rdata.append([
                Paragraph(r.get('risk_id', ''), s['td_bold']),
                Paragraph(r.get('title', ''), s['td']),
                Paragraph(r.get('risk_type', ''), s['td']),
                Paragraph(sev, s['td']),
                Paragraph(r.get('mitigation', ''), s['td']),
            ])
        rtbl = Table(rdata, colWidths=[18*mm, 35*mm, 22*mm, 18*mm, 77*mm])
        rtbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), AMBER),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, rl_colors.HexColor('#fffbeb')]),
            ('GRID', (0, 0), (-1, -1), 0.4, GRID_CLR),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(rtbl)
        story.append(Spacer(1, 4*mm))

    # ── Risk Treatment Plan ───────────────────────────────────────────────────
    treatment_plan = report_data.get('risk_treatment_plan', [])
    if treatment_plan:
        _section_header(story, '5. Risk Treatment Plan', s, VIOLET)
        tdata = [[
            Paragraph('Risk ID', s['th']),
            Paragraph('Risk', s['th']),
            Paragraph('Treatment', s['th']),
            Paragraph('Action', s['th']),
            Paragraph('Timeline', s['th']),
        ]]
        for t in treatment_plan:
            tdata.append([
                Paragraph(t.get('risk_id', ''), s['td_bold']),
                Paragraph(t.get('risk', ''), s['td']),
                Paragraph(t.get('treatment', ''), s['td']),
                Paragraph(t.get('action', ''), s['td']),
                Paragraph(t.get('timeline', ''), s['td']),
            ])
        ttbl = Table(tdata, colWidths=[18*mm, 35*mm, 22*mm, 65*mm, 30*mm])
        ttbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), VIOLET),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, rl_colors.HexColor('#f5f3ff')]),
            ('GRID', (0, 0), (-1, -1), 0.4, GRID_CLR),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(ttbl)
        story.append(Spacer(1, 4*mm))

    # ── Residual Risks ─────────────────────────────────────────────────────────
    residuals = report_data.get('residual_risks', [])
    if residuals:
        _section_header(story, '6. Residual Risks', s, ROSE)
        _bullet_list(story, residuals, s)
        story.append(Spacer(1, 2*mm))

    # ── Recommendations ───────────────────────────────────────────────────────
    recs = report_data.get('recommendations', [])
    if recs:
        _section_header(story, '7. Recommendations', s, INDIGO)
        _bullet_list(story, recs, s)
        story.append(Spacer(1, 2*mm))

    # ── Governance Actions table ──────────────────────────────────────────────
    gov_actions = report_data.get('governance_actions', [])
    if gov_actions:
        _section_header(story, '8. Governance Actions', s, EMERALD)
        gdata = [[
            Paragraph('Action', s['th']),
            Paragraph('Owner', s['th']),
            Paragraph('Due Date', s['th']),
        ]]
        for g in gov_actions:
            gdata.append([
                Paragraph(g.get('action', ''), s['td']),
                Paragraph(g.get('owner', ''), s['td_bold']),
                Paragraph(g.get('due_date', ''), s['td']),
            ])
        gtbl = Table(gdata, colWidths=[110*mm, 35*mm, 25*mm])
        gtbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), EMERALD),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, rl_colors.HexColor('#f0fdf4')]),
            ('GRID', (0, 0), (-1, -1), 0.4, GRID_CLR),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(gtbl)

    doc = _doc(buf)
    doc.build(story)
    return buf.getvalue()


# ── 3. Policy Pack PDF (thin re-export) ───────────────────────────────────────

def build_policy_pack_pdf(pack_doc: Dict[str, Any]) -> bytes:
    """
    Delegate to app._build_pdf_bytes so there's a single import point
    for callers that don't want to import from app.py directly.
    """
    try:
        from app import _build_pdf_bytes
        return _build_pdf_bytes(pack_doc)
    except Exception:
        return b""
