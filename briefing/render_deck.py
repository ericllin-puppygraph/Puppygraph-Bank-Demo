#!/usr/bin/env python3
"""Render a deck spec (from deck_agent.py) to PDF and PowerPoint.

Usage:
  python3 briefing/render_deck.py briefing/output/deck_spec.json --out briefing/output/bank-risk-briefing
writes bank-risk-briefing.pdf, bank-risk-briefing.pptx and one PNG per slide (for the video).
"""
import argparse
import asyncio
import html
import json
from pathlib import Path

from playwright.async_api import async_playwright
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Emu, Pt

W, H = 1600, 900
INK = '#1d1b2f'
MUTED = '#5f5b73'
ACCENT = '#5b2a86'        # PuppyGraph purple
SERIES = ['#5b2a86', '#e0663c', '#2a9d8f', '#8a8799']
CARD = '#f4f2f8'
FOOTER = 'Synthetic LDBC FinBench data · queried through PuppyGraph'


def esc(text):
    return html.escape(str(text))


def fit(text, base, floor, budget):
    """Shrink a font size as text grows past a character budget."""
    n = len(text)
    return base if n <= budget else max(floor, round(base * (budget / n) ** 0.5, 1))


# ---------------------------------------------------------------- HTML / PDF

def svg_bars(chart, width, height):
    cats, series = chart['categories'], chart['series']
    vmax = max((v for s in series for v in s['values']), default=1) or 1
    horizontal = chart['orientation'] == 'horizontal'
    out = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg" '
           f'font-family="Inter, Helvetica, Arial, sans-serif">']
    legend_h = 34 if len(series) > 1 else 0
    for i, s in enumerate(series if len(series) > 1 else []):
        x = 10 + i * 260
        out.append(f'<rect x="{x}" y="6" width="14" height="14" rx="3" fill="{SERIES[i % 4]}"/>'
                   f'<text x="{x + 22}" y="18" font-size="16" fill="{MUTED}">{esc(s["name"])}</text>')
    top = legend_h + 10
    if horizontal:
        label_w = min(330, max(120, 9 * max(len(c) for c in cats)))
        plot_w = width - label_w - 80
        band = (height - top) / len(cats)
        bar_h = min(34, band * 0.7 / len(series))
        for ci, cat in enumerate(cats):
            y0 = top + ci * band + (band - bar_h * len(series)) / 2
            out.append(f'<text x="{label_w - 12}" y="{top + ci * band + band / 2 + 6}" font-size="17" '
                       f'text-anchor="end" fill="{INK}">{esc(cat)}</text>')
            for si, s in enumerate(series):
                v = s['values'][ci] if ci < len(s['values']) else 0
                w = plot_w * v / vmax
                y = y0 + si * bar_h
                out.append(f'<rect x="{label_w}" y="{y}" width="{max(w, 1)}" height="{bar_h - 4}" rx="3" '
                           f'fill="{SERIES[si % 4]}"/>'
                           f'<text x="{label_w + w + 8}" y="{y + bar_h / 2 + 3}" font-size="16" '
                           f'fill="{INK}" font-weight="600">{fmt(v)}</text>')
    else:
        top += 34                                   # room for the value label above the tallest bar
        bottom = 64
        plot_h = height - top - bottom
        band = width / len(cats)
        bar_w = min(90, band * 0.7 / len(series))
        for ci, cat in enumerate(cats):
            x0 = ci * band + (band - bar_w * len(series)) / 2
            for si, s in enumerate(series):
                v = s['values'][ci] if ci < len(s['values']) else 0
                h = plot_h * v / vmax
                x = x0 + si * bar_w
                out.append(f'<rect x="{x + 2}" y="{top + plot_h - h}" width="{bar_w - 4}" height="{max(h, 1)}" '
                           f'rx="3" fill="{SERIES[si % 4]}"/>'
                           f'<text x="{x + bar_w / 2}" y="{top + plot_h - h - 8}" font-size="17" '
                           f'text-anchor="middle" fill="{INK}" font-weight="600">{fmt(v)}</text>')
            size = fit(cat, 16, 11, 22)
            out.append(f'<foreignObject x="{ci * band}" y="{top + plot_h + 8}" width="{band}" height="{bottom}">'
                       f'<div xmlns="http://www.w3.org/1999/xhtml" style="font-size:{size}px;color:{INK};'
                       f'text-align:center;line-height:1.2">{esc(cat)}</div></foreignObject>')
        out.append(f'<line x1="0" x2="{width}" y1="{top + plot_h}" y2="{top + plot_h}" stroke="#c9c5d6"/>')
    out.append('</svg>')
    return ''.join(out)


def fmt(v):
    if abs(v) >= 1e9:
        return f'{v / 1e9:.1f}B'
    if abs(v) >= 1e6:
        return f'{v / 1e6:.1f}M'
    if float(v).is_integer():
        return f'{int(v):,}'
    return f'{v:,.2f}'


CSS = f"""
@page {{ size: {W}px {H}px; margin: 0 }}
* {{ box-sizing: border-box }}
body {{ margin: 0; font-family: Inter, Helvetica, Arial, sans-serif; color: {INK} }}
.slide {{ width: {W}px; height: {H}px; position: relative; overflow: hidden; page-break-after: always;
          padding: 64px 80px 70px; background: white }}
h1 {{ font-size: 44px; margin: 0 0 28px; line-height: 1.15; letter-spacing: -0.5px }}
.footer {{ position: absolute; left: 80px; right: 80px; bottom: 26px; font-size: 14px; color: {MUTED};
           display: flex; justify-content: space-between; border-top: 1px solid #e4e1ec; padding-top: 10px }}
.title {{ background: {ACCENT}; color: white; display: flex; flex-direction: column; justify-content: center }}
.title h1 {{ font-size: 62px; max-width: 1300px }}
.title .sub {{ font-size: 26px; opacity: .9; margin-bottom: 60px; max-width: 1300px }}
.title .meta {{ font-size: 19px; opacity: .85; max-width: 1300px; line-height: 1.5 }}
.title .footer {{ color: rgba(255,255,255,.75); border-color: rgba(255,255,255,.3) }}
.grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 26px }}
.card {{ background: {CARD}; border-radius: 14px; padding: 26px 28px; height: 330px; border-top: 5px solid {ACCENT} }}
.card .v {{ font-size: 54px; font-weight: 700; color: {ACCENT}; margin-bottom: 10px; line-height: 1.05 }}
.card .l {{ font-size: 21px; font-weight: 650; margin-bottom: 10px }}
.card .d {{ font-size: 17px; color: {MUTED}; line-height: 1.4 }}
.finding {{ display: flex; gap: 48px }}
.finding .chart {{ width: 900px }}
.finding .chart .ct {{ font-size: 19px; font-weight: 600; color: {MUTED}; margin-bottom: 12px }}
.finding .side {{ flex: 1; padding-top: 20px }}
.finding .cv {{ font-size: 58px; font-weight: 700; color: {ACCENT}; line-height: 1 }}
.finding .ctext {{ font-size: 21px; font-weight: 600; margin: 12px 0 26px; line-height: 1.35 }}
.finding .body {{ font-size: 18px; color: {MUTED}; line-height: 1.5 }}
.fig {{ position: absolute; left: 80px; bottom: 64px; font-size: 15px; color: {MUTED} }}
.rec {{ display: grid; grid-template-columns: 64px 470px 1fr; gap: 0 26px; align-items: start;
        padding: 20px 0; border-bottom: 1px solid #e4e1ec }}
.rec .n {{ width: 48px; height: 48px; border-radius: 50%; background: {ACCENT}; color: white; font-size: 22px;
           font-weight: 700; display: flex; align-items: center; justify-content: center }}
.rec .t {{ font-size: 23px; font-weight: 650; line-height: 1.3; padding-top: 8px }}
.rec .d {{ font-size: 18px; color: {MUTED}; line-height: 1.45; padding-top: 8px }}
.divider {{ background: {CARD}; display: flex; flex-direction: column; justify-content: center }}
.divider h1 {{ font-size: 56px; color: {ACCENT} }}
.divider p {{ font-size: 22px; color: {MUTED}; max-width: 1100px; line-height: 1.5 }}
.a0 h2 {{ font-size: 20px; color: {ACCENT}; margin: 18px 0 6px }}
.a0 p, .a0 li {{ font-size: 16px; line-height: 1.45; margin: 0 }}
.appx {{ display: flex; gap: 36px }}
.appx .qs {{ width: 940px }}
.appx .ql {{ font-size: 16px; font-weight: 650; margin: 0 0 6px }}
.appx pre {{ background: #f6f5f9; border: 1px solid #e4e1ec; border-radius: 8px; padding: 10px 14px; margin: 0 0 14px;
            white-space: pre-wrap; word-break: break-word; font-family: 'JetBrains Mono', Menlo, monospace }}
.appx .der {{ flex: 1 }}
.appx .der h3 {{ font-size: 18px; margin: 0 0 8px; color: {ACCENT} }}
.appx .der p {{ margin: 0; color: {INK}; line-height: 1.45 }}
"""


def query_pages(finding, budget=1500):
    """Split a finding's queries into appendix pages of roughly equal text length."""
    pages, current, size = [], [], 0
    for q in finding['queries']:
        n = len(q['cypher']) + 120
        if current and size + n > budget:
            pages.append(current)
            current, size = [], 0
        current.append(q)
        size += n
    return pages + [current] if current else pages


def query_size(chunk, width):
    """Largest font size (px) at which a page of queries, wrapped to width, fits the appendix column."""
    for size in (16, 15, 14, 13, 12, 11, 10):
        per_line = max(1, int((width - 30) / (size * 0.61)))
        lines = sum(3 + sum(max(1, -(-len(line) // per_line)) for line in q['cypher'].strip().splitlines())
                    for q in chunk)
        if lines * size * 1.45 <= 640:
            return size
    return 10


def footer(page, appendix=False):
    left = ('Appendix · ' if appendix else '') + FOOTER
    return f'<div class="footer"><span>{esc(left)}</span><span>{page}</span></div>'


def build_html(deck):
    slides = []
    page = 1
    slides.append(
        f'<section class="slide title"><h1 style="font-size:{fit(deck["title"], 62, 40, 70)}px">{esc(deck["title"])}</h1>'
        f'<div class="sub">{esc(deck["subtitle"])}</div>'
        f'<div class="meta">Audience: {esc(deck["audience"])}<br><br>Data note: {esc(deck["data_note"])}</div>'
        f'{footer(page)}</section>')
    page += 1
    cards = ''.join(
        f'<div class="card"><div class="v" style="font-size:{fit(k["value"], 54, 34, 12)}px">{esc(k["value"])}</div>'
        f'<div class="l">{esc(k["label"])}</div><div class="d">{esc(k["detail"])}</div></div>'
        for k in deck['key_numbers'][:6])
    slides.append(f'<section class="slide"><h1>{len(deck["key_numbers"][:6])} numbers risk leadership should know'
                  f'</h1><div class="grid">{cards}</div>{footer(page)}</section>')
    for i, f in enumerate(deck['findings'], 1):
        page += 1
        body_size = fit(f['body'], 18, 14, 420)
        slides.append(
            f'<section class="slide"><h1 style="font-size:{fit(f["headline"], 44, 32, 70)}px">{esc(f["headline"])}</h1>'
            f'<div class="finding"><div class="chart"><div class="ct">{esc(f["chart"]["title"])}</div>'
            f'{svg_bars(f["chart"], 900, 560)}</div>'
            f'<div class="side"><div class="cv" style="font-size:{fit(f["callout_value"], 58, 36, 10)}px">'
            f'{esc(f["callout_value"])}</div>'
            f'<div class="ctext">{esc(f["callout_text"])}</div>'
            f'<div class="body" style="font-size:{body_size}px">{esc(f["body"])}</div></div></div>'
            f'<div class="fig">Fig {i} · query in appendix {esc(f["id"])}</div>{footer(page)}</section>')
    page += 1
    recs = deck['recommendations']
    rows = ''.join(
        f'<div class="rec"><div class="n">{i}</div><div class="t">{esc(r["title"])}</div>'
        f'<div class="d" style="font-size:{fit(r["detail"], 18, 14, 230)}px">{esc(r["detail"])}</div></div>'
        for i, r in enumerate(recs, 1))
    slides.append(f'<section class="slide"><h1>{len(recs)} moves that cut the most connected risk</h1>{rows}'
                  f'{footer(page)}</section>')
    page += 1
    slides.append(
        '<section class="slide divider"><h1>Appendix: how every number was derived</h1>'
        '<p>All numbers come from read-only openCypher queries run in this session against the PuppyGraph '
        'graph, through PuppyGraph\'s MCP server. Percentages are derived explicitly from query results.</p>'
        f'{footer(page, True)}</section>')
    page += 1
    a = deck['appendix']
    text = a['graph'] + a['key_paths'] + a['baselines'] + ''.join(a['assumptions'])
    size = fit(text, 17, 12, 2600)
    slides.append(
        f'<section class="slide a0"><h1 style="font-size:36px">A0 · The graph and the assumptions</h1>'
        f'<div style="font-size:{size}px"><h2>Graph</h2><p style="font-size:inherit">{esc(a["graph"])}</p>'
        f'<h2>Key paths</h2><p style="font-size:inherit">{esc(a["key_paths"])}</p>'
        f'<h2>Baselines</h2><p style="font-size:inherit">{esc(a["baselines"])}</p>'
        f'<h2>Assumptions and caveats</h2><ul style="margin:0;padding-left:22px">'
        + ''.join(f'<li style="font-size:inherit">{esc(x)}</li>' for x in a['assumptions'])
        + f'</ul></div>{footer(page, True)}</section>')
    for i, f in enumerate(deck['findings'], 1):
        chunks = query_pages(f)
        for c, chunk in enumerate(chunks):
            page += 1
            width = 940 if c == 0 else 1440
            qsize = query_size(chunk, width)
            queries = ''.join(f'<div class="ql">{esc(q["label"])}</div>'
                              f'<pre style="font-size:{qsize}px">{esc(q["cypher"].strip())}</pre>'
                              for q in chunk)
            cont = f' (continued, {c + 1}/{len(chunks)})' if c else ''
            der = (f'<h3>Results and derivation</h3><p style="font-size:{fit(f["derivation"], 17, 12, 900)}px">'
                   f'{esc(f["derivation"])}</p>') if c == 0 else ''
            slides.append(
                f'<section class="slide"><h1 style="font-size:30px">{esc(f["id"])} · Fig {i}: '
                f'{esc(f["chart"]["title"])}{cont}</h1>'
                f'<div class="appx"><div class="qs" style="width:{width}px">{queries}</div>'
                f'<div class="der">{der}</div></div>'
                f'{footer(page, True)}</section>')
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>' \
           + ''.join(slides) + '</body></html>'


async def render_pdf(doc, out):
    html_path = out.with_suffix('.html')
    html_path.write_text(doc)
    png_dir = out.parent / (out.name + '-slides')
    png_dir.mkdir(exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': W, 'height': H})
        await page.goto(html_path.resolve().as_uri())
        await page.pdf(path=str(out.with_suffix('.pdf')), width=f'{W}px', height=f'{H}px',
                       print_background=True)
        overflow = await page.evaluate(
            """() => [...document.querySelectorAll('.slide')].map((s, i) =>
                 [...s.querySelectorAll('*')].some(e => e.getBoundingClientRect().bottom
                   > s.getBoundingClientRect().bottom - 60 && !e.closest('.footer')) ? i + 1 : 0).filter(Boolean)""")
        for i, slide in enumerate(await page.query_selector_all('.slide'), 1):
            await slide.screenshot(path=str(png_dir / f'slide-{i:02d}.png'))
        await browser.close()
    html_path.unlink()
    return overflow


# ---------------------------------------------------------------- PowerPoint

def px(v):
    return Emu(int(v * 12700 * 0.75))   # 1 CSS px = 0.75 pt


def rgb(hex_color):
    return RGBColor.from_string(hex_color.lstrip('#'))


def text_box(slide, x, y, w, h, text, size, color=INK, bold=False, font='Helvetica', align=None):
    box = slide.shapes.add_textbox(px(x), px(y), px(w), px(h))
    frame = box.text_frame
    frame.word_wrap = True
    for i, line in enumerate(str(text).split('\n')):
        para = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
        para.text = line
        if align:
            para.alignment = align
        for run in para.runs:
            run.font.size = Pt(size * 0.75)
            run.font.bold = bold
            run.font.color.rgb = rgb(color)
            run.font.name = font
    return box


def ppt_footer(slide, page, appendix=False):
    text_box(slide, 80, 852, 1200, 30, ('Appendix · ' if appendix else '') + FOOTER, 14, MUTED)
    text_box(slide, 1440, 852, 80, 30, str(page), 14, MUTED, align=PP_ALIGN.RIGHT)


def rect(slide, x, y, w, h, fill, shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    s = slide.shapes.add_shape(shape, px(x), px(y), px(w), px(h))
    s.fill.solid()
    s.fill.fore_color.rgb = rgb(fill)
    s.line.fill.background()
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = 0.05
    return s


def build_pptx(deck, out):
    prs = Presentation()
    prs.slide_width, prs.slide_height = px(W), px(H)
    blank = prs.slide_layouts[6]
    page = 1

    s = prs.slides.add_slide(blank)
    rect(s, 0, 0, W, H, ACCENT, MSO_SHAPE.RECTANGLE)
    text_box(s, 80, 120, 1300, 330, deck['title'], fit(deck['title'], 62, 40, 70), '#ffffff', True)
    text_box(s, 80, 470, 1300, 80, deck['subtitle'], 26, '#ffffff')
    text_box(s, 80, 580, 1300, 230, f"Audience: {deck['audience']}\n\nData note: {deck['data_note']}", 19, '#ffffff')
    text_box(s, 80, 852, 1200, 30, FOOTER, 14, '#ffffff')

    page += 1
    s = prs.slides.add_slide(blank)
    nums = deck['key_numbers'][:6]
    text_box(s, 80, 56, 1440, 70, f'{len(nums)} numbers risk leadership should know', 44, INK, True)
    for i, k in enumerate(nums):
        x, y = 80 + (i % 3) * 489, 170 + (i // 3) * 356
        rect(s, x, y, 463, 330, CARD)
        rect(s, x, y, 463, 6, ACCENT, MSO_SHAPE.RECTANGLE)
        text_box(s, x + 24, y + 22, 420, 70, k['value'], fit(k['value'], 54, 34, 12), ACCENT, True)
        text_box(s, x + 24, y + 104, 420, 60, k['label'], 21, INK, True)
        text_box(s, x + 24, y + 170, 420, 150, k['detail'], 17, MUTED)
    ppt_footer(s, page)

    for i, f in enumerate(deck['findings'], 1):
        page += 1
        s = prs.slides.add_slide(blank)
        text_box(s, 80, 56, 1440, 110, f['headline'], fit(f['headline'], 44, 32, 70), INK, True)
        chart = f['chart']
        text_box(s, 80, 180, 900, 30, chart['title'], 19, MUTED, True)
        data = CategoryChartData()
        data.categories = chart['categories']
        for ser in chart['series']:
            data.add_series(ser['name'], ser['values'])
        kind = XL_CHART_TYPE.BAR_CLUSTERED if chart['orientation'] == 'horizontal' else XL_CHART_TYPE.COLUMN_CLUSTERED
        gframe = s.shapes.add_chart(kind, px(80), px(215), px(900), px(560), data)
        c = gframe.chart
        c.has_title = False
        c.has_legend = len(chart['series']) > 1
        if c.has_legend:
            c.legend.position = XL_LEGEND_POSITION.TOP
            c.legend.include_in_layout = False
        plot = c.plots[0]
        plot.has_data_labels = True
        plot.data_labels.font.size = Pt(12)
        plot.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
        for si, ser in enumerate(plot.series):
            ser.format.fill.solid()
            ser.format.fill.fore_color.rgb = rgb(SERIES[si % 4])
        c.value_axis.visible = False
        c.value_axis.has_major_gridlines = False
        c.category_axis.tick_labels.font.size = Pt(11)
        if chart['orientation'] == 'horizontal':
            c.category_axis.reverse_order = True
        text_box(s, 1028, 210, 492, 80, f['callout_value'], fit(f['callout_value'], 58, 36, 10), ACCENT, True)
        text_box(s, 1028, 300, 492, 110, f['callout_text'], 21, INK, True)
        text_box(s, 1028, 430, 492, 340, f['body'], fit(f['body'], 18, 14, 420), MUTED)
        text_box(s, 80, 800, 600, 30, f"Fig {i} · query in appendix {f['id']}", 15, MUTED)
        ppt_footer(s, page)

    page += 1
    s = prs.slides.add_slide(blank)
    recs = deck['recommendations']
    text_box(s, 80, 56, 1440, 70, f'{len(recs)} moves that cut the most connected risk', 44, INK, True)
    row_h = min(140, 660 / max(len(recs), 1))
    for i, r in enumerate(recs, 1):
        y = 160 + (i - 1) * row_h
        circle = rect(s, 80, y + 6, 48, 48, ACCENT, MSO_SHAPE.OVAL)
        circle.text_frame.text = str(i)
        para = circle.text_frame.paragraphs[0]
        para.alignment = PP_ALIGN.CENTER
        para.runs[0].font.size = Pt(16)
        para.runs[0].font.bold = True
        circle.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        text_box(s, 160, y + 8, 460, row_h - 10, r['title'], 23, INK, True)
        text_box(s, 650, y + 8, 870, row_h - 10, r['detail'], fit(r['detail'], 18, 14, 230), MUTED)
    ppt_footer(s, page)

    page += 1
    s = prs.slides.add_slide(blank)
    rect(s, 0, 0, W, H, CARD, MSO_SHAPE.RECTANGLE)
    text_box(s, 80, 300, 1300, 90, 'Appendix: how every number was derived', 56, ACCENT, True)
    text_box(s, 80, 420, 1100, 140,
             'All numbers come from read-only openCypher queries run in this session against the PuppyGraph '
             "graph, through PuppyGraph's MCP server. Percentages are derived explicitly from query results.",
             22, MUTED)
    ppt_footer(s, page, True)

    page += 1
    s = prs.slides.add_slide(blank)
    a = deck['appendix']
    text_box(s, 80, 56, 1440, 60, 'A0 · The graph and the assumptions', 36, INK, True)
    body = (f"Graph\n{a['graph']}\n\nKey paths\n{a['key_paths']}\n\nBaselines\n{a['baselines']}\n\n"
            'Assumptions and caveats\n' + '\n'.join('• ' + x for x in a['assumptions']))
    text_box(s, 80, 130, 1440, 700, body, fit(body, 17, 12, 2600), INK)
    ppt_footer(s, page, True)

    for i, f in enumerate(deck['findings'], 1):
        chunks = query_pages(f)
        for c, chunk in enumerate(chunks):
            page += 1
            s = prs.slides.add_slide(blank)
            cont = f' (continued, {c + 1}/{len(chunks)})' if c else ''
            text_box(s, 80, 56, 1440, 60, f"{f['id']} · Fig {i}: {f['chart']['title']}{cont}", 30, INK, True)
            width = 940 if c == 0 else 1440
            qsize = query_size(chunk, width)
            queries = '\n\n'.join(f"{q['label']}\n{q['cypher'].strip()}" for q in chunk)
            text_box(s, 80, 130, width, 700, queries, qsize, INK, font='Menlo')
            if c == 0:
                text_box(s, 1056, 130, 464, 30, 'Results and derivation', 18, ACCENT, True)
                text_box(s, 1056, 166, 464, 660, f['derivation'], fit(f['derivation'], 17, 12, 900), INK)
            ppt_footer(s, page, True)

    prs.save(str(out.with_suffix('.pptx')))
    return page


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('spec')
    parser.add_argument('--out', default='briefing/output/bank-risk-briefing')
    args = parser.parse_args()
    deck = json.loads(Path(args.spec).read_text())
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    overflow = asyncio.run(render_pdf(build_html(deck), out))
    pages = build_pptx(deck, out)
    print(f'saved {out.with_suffix(".pdf")} and {out.with_suffix(".pptx")} · {pages} slides')
    if overflow:
        print(f'warning: content may overflow on slides {overflow}')


if __name__ == '__main__':
    main()
