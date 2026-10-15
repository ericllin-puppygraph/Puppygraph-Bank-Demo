"""Render caption bars, badges, cards and terminal-replay frames as PNGs with Playwright."""
import asyncio, html, json, sys
from pathlib import Path
from playwright.async_api import async_playwright

FONT = "Inter, Helvetica, Arial, sans-serif"


def caption_html(text):
    return f"""<html><body style="margin:0;width:1920px;height:120px;background:#16141f;display:flex;
    align-items:center;justify-content:center;font-family:{FONT}">
    <div style="color:#fff;font-size:34px;text-align:center;max-width:1760px;line-height:1.25">{text}</div></body></html>"""


def badge_html(text):
    return f"""<html><body style="margin:0;background:transparent">
    <div id="b" style="display:inline-block;background:#5b2a86;color:#fff;font:700 30px {FONT};
    padding:10px 22px;border-radius:12px;box-shadow:0 4px 14px rgba(0,0,0,.25)">{text}</div></body></html>"""


def card_html(title, sub, small=''):
    return f"""<html><body style="margin:0;width:1920px;height:1080px;background:#fff;display:flex;flex-direction:column;
    align-items:center;justify-content:center;font-family:{FONT};color:#1d1b2f">
    <div style="font-size:84px;font-weight:700;color:#5b2a86">{title}</div>
    <div style="font-size:38px;margin-top:22px;color:#3b3850">{sub}</div>
    <div style="font-size:26px;margin-top:40px;color:#6b6780;max-width:1500px;text-align:center">{small}</div></body></html>"""


TERM_CSS = f"""body{{margin:0;width:1920px;height:960px;background:#0f1117;font-family:'DejaVu Sans Mono',Menlo,monospace;color:#d6d9e0}}
.top{{height:56px;background:#1b1e27;display:flex;align-items:center;padding:0 24px;font:600 20px {FONT};color:#e8e8ef}}
.dots span{{display:inline-block;width:14px;height:14px;border-radius:50%;margin-right:8px}}
.top .t{{margin-left:20px}} .top .c{{margin-left:auto;margin-right:300px;font-weight:500;color:#aab}}
.body{{padding:18px 28px;font-size:19px;line-height:1.5;white-space:pre-wrap;word-break:break-all}}
.r{{color:#8fd18f}} .q{{color:#d6d9e0}} .n{{color:#7f8899}} .e{{color:#ff7b72}} .s{{color:#f2c94c}} .p{{color:#79c0ff}}"""


def term_html(lines, queries, elapsed, model):
    body = '\n'.join(lines)
    return f"""<html><head><style>{TERM_CSS}</style></head><body>
    <div class="top"><span class="dots"><span style="background:#ff5f57"></span><span style="background:#febc2e">
    </span><span style="background:#28c840"></span></span>
    <span class="t">{model} ⇄ PuppyGraph MCP server · tools: puppygraph_schema, puppygraph_query (read-only)</span>
    <span class="c">Cypher queries: {queries} &nbsp;&nbsp; elapsed: {elapsed:.0f} s</span></div>
    <div class="body">{body}</div></body></html>"""


def term_frames(log_path, max_lines=34):
    """Yield (t, html) for each event of a deck_agent session log."""
    events = [json.loads(l) for l in open(log_path)]
    model = next(e['model'] for e in events if e['kind'] == 'start')
    lines = ['<span class="p">$ python3 briefing/deck_agent.py --mcp-server puppygraph-mcp-server/build/index.js</span>',
             '<span class="n">task: briefing/prompt.md · audience: bank risk and compliance leadership</span>']
    q = 0
    for e in events:
        k = e['kind']
        if k == 'reasoning':
            lines.append(f'<span class="r">• {html.escape(e["text"])}</span>')
        elif k == 'tool_result' and e.get('tool') == 'puppygraph_schema':
            lines.append(f'<span class="q">→ puppygraph_schema()</span>')
            lines.append(f'<span class="n">  ← 5 node labels, 13 edge labels</span>')
        elif k == 'query':
            q += 1
            cy = html.escape(' '.join(e['cypher'].split()))
            if len(cy) > 150:
                cy = cy[:147] + '…'
            lines.append(f'<span class="q">→ puppygraph_query: {cy}</span>')
            if e['ok']:
                lines.append(f'<span class="n">  ← {e["rows"]} row{"s" if e["rows"] != 1 else ""}</span>')
            else:
                err = (e.get('error') or '')
                msg = err.split('"error":')[-1].split('",')[0].strip(' "') if '"error"' in err else err[:120]
                lines.append(f'<span class="e">  ← ERROR {html.escape(msg[:140])}</span>')
        elif k == 'submit_rejected':
            lines.append(f'<span class="e">→ submit_deck: rejected, {len(e["missing"])} appendix queries not yet run verbatim</span>')
        elif k == 'submit_deck':
            lines.append(f'<span class="s">→ submit_deck("{html.escape(e["title"])}") · {e["findings"]} findings · accepted</span>')
        else:
            continue
        yield e['t'], term_html(lines[-max_lines:], q, e['t'], model)


async def shoot(items, out_dir):
    """items: list of (filename, html, (w, h) or None for element screenshot)."""
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 1920, 'height': 1080})
        for name, doc, size in items:
            await pg.set_content(doc)
            if size:
                await pg.set_viewport_size({'width': size[0], 'height': size[1]})
                await pg.screenshot(path=str(out / name), omit_background=True)
            else:
                await pg.locator('#b').screenshot(path=str(out / name), omit_background=True)
        await b.close()
