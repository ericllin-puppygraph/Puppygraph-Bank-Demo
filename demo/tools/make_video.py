"""Compose the demo video from the UI takes, the briefing agent's session log and the deck slides.

Usage:
  python3 make_video.py <briefing-dir> [--take take/take2] [--queries-take take/take2q] [--out demo.mp4]

<briefing-dir> holds session-log.jsonl, deck_spec.json and the rendered deck (render_deck.py --out
<briefing-dir>/deck/bank-risk-briefing, which writes the slide PNGs).
"""
import asyncio, json, subprocess, sys
from pathlib import Path
import cards

HERE = Path(__file__).resolve().parent
BUILD = HERE / 'build'

def arg(flag, default):
    return Path(sys.argv[sys.argv.index(flag) + 1]) if flag in sys.argv else default


FINAL = Path(sys.argv[1])
TAKE = arg('--take', HERE / 'take' / 'take2')
TAKEQ = arg('--queries-take', TAKE)
OUT = arg('--out', HERE / 'puppygraph-bank-demo.mp4')
SLIDES = FINAL / 'deck' / 'bank-risk-briefing-slides'
FPS = 30


def ev(take, name):
    return next(e['t'] for e in json.load(open(take / 'events.json')) if e['name'] == name)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print(' '.join(map(str, cmd))); print(r.stderr[-3000:]); sys.exit(1)


CAP = {}


def cap(text):
    if text not in CAP:
        CAP[text] = f'cap{len(CAP):02d}.png'
    return BUILD / CAP[text]


def segment(i, src, start, end, speed, caption, badge=None, crop=None):
    """Cut [start,end] of src, speed it up, add the caption bar and an optional speed badge."""
    out = BUILD / f'seg{i:02d}.mp4'
    vf = []
    if crop:
        vf.append(f'crop={crop}')
    vf += ['scale=1920:960:flags=lanczos', f'setpts=PTS/{speed}', 'fps=30',
           'pad=1920:1080:0:0:color=0x16141f']
    inputs = ['-ss', f'{start:.2f}', '-to', f'{end:.2f}', '-i', str(src), '-i', str(cap(caption))]
    graph = f"[0:v]{','.join(vf)}[v];[v][1:v]overlay=0:960[c]"
    last = 'c'
    if badge:
        inputs += ['-i', str(BUILD / badge)]
        graph += f";[c][2:v]overlay=W-w-36:28[d]"
        last = 'd'
    run(['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', graph, '-map', f'[{last}]',
         '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-r', str(FPS), str(out)])
    return out


def stills(i, frames, caption, badge=None):
    """frames: list of (png, seconds) shown 1920x960 above the caption bar."""
    lst = BUILD / f'stills{i:02d}.txt'
    with open(lst, 'w') as f:
        for png, dur in frames:
            f.write(f"file '{png}'\nduration {dur:.3f}\n")
        f.write(f"file '{frames[-1][0]}'\n")
    out = BUILD / f'seg{i:02d}.mp4'
    inputs = ['-f', 'concat', '-safe', '0', '-i', str(lst), '-i', str(cap(caption))]
    graph = ("[0:v]scale=1920:960:force_original_aspect_ratio=decrease,pad=1920:960:(ow-iw)/2:(oh-ih)/2:color=0x16141f,"
             "fps=30,pad=1920:1080:0:0:color=0x16141f[v];[v][1:v]overlay=0:960[c]")
    last = 'c'
    if badge:
        inputs += ['-i', str(BUILD / badge)]
        graph += ";[c][2:v]overlay=W-w-36:28[d]"
        last = 'd'
    run(['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', graph, '-map', f'[{last}]',
         '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-r', str(FPS), str(out)])
    return out


def card_segment(i, png, seconds):
    out = BUILD / f'seg{i:02d}.mp4'
    run(['ffmpeg', '-v', 'error', '-y', '-loop', '1', '-t', f'{seconds}', '-i', str(png), '-vf', 'fps=30',
         '-c:v', 'libx264', '-crf', '20', '-pix_fmt', 'yuv420p', str(out)])
    return out


def main():
    BUILD.mkdir(exist_ok=True)
    video, vq = TAKE / 'video.webm', TAKEQ / 'video.webm'
    log = FINAL / 'session-log.jsonl'
    events = [json.loads(l) for l in open(log)]
    queries = sum(e['kind'] == 'query' for e in events)
    elapsed = max(e['t'] for e in events)
    rejected = any(e['kind'] == 'submit_rejected' for e in events)

    T = dict(ai=ev(TAKE, 'ai_page'), sent=ev(TAKE, 'prompt_sent'), done=ev(TAKE, 'ontology_done'),
             shown=ev(TAKE, 'ontology_shown'))
    q = {n: ev(TAKEQ, n) for n in ['q1_typed', 'q1_result', 'q1_shown', 'q2_typed', 'q2_result', 'q2_shown',
                                    'q3_typed', 'q3_result', 'q3_shown', 'q4_typed', 'q4_result', 'q4_shown']}

    C = {
        'c0': 'Connected to relational data: a DuckDB copy of the LDBC FinBench banking dataset, 18 tables.',
        'c1': 'People, companies, accounts, loans and sign-in devices, plus every transfer, guarantee and investment. No graph schema yet.',
        'c2': 'Ask PuppyGraph AI to build the graph schema straight from the catalog.',
        'g1': 'Once built, the graph shows which customers received money from accounts used on blocked devices…',
        'g2': '…where money leaves an account and comes back to it through others (round-tripping)…',
        'g3': '…whether loan proceeds move on to blocked accounts after payout…',
        'g4': '…and how far guarantee chains spread credit exposure, with no ETL into a separate graph database.',
        'c3': 'Ontology generated: 5 node types and 13 relationship types, with counts checked against the source tables.',
        'q1a': 'Which customers are exposed to accounts used on a blocked device, even two transfers away?',
        'q1b': 'Blocked devices → their accounts → two time-ordered transfers: 169 accounts and 153 customers reached.',
        'q2a': 'Where does money come back to the account it left?',
        'q2b': '9 time-ordered loops return money to where it started; 2 pass through a blocked account.',
        'q3': '184 loans were paid out to accounts that then sent money to one of 68 blocked accounts.',
        'q4': 'Guarantee chains run five deep: the top guarantor indirectly backs 5 people and 18 loans.',
        'a1': f"Next, gpt-5.5 connects through PuppyGraph's MCP server (read-only) and explores the graph with its own Cypher.",
        'a2': ('Every number it cites must come from a query it ran; its first draft was rejected until it had run them.'
               if rejected else 'Every number it cites must come from a query it ran in this session.'),
        'a3': f'After {queries} queries and {elapsed:.0f} seconds it submits the briefing; the renderer turns it into PDF and PowerPoint.',
        'd1': 'The finished briefing for risk leadership. Every figure links to the exact Cypher query and result in the appendix.',
    }
    items = [(CAP.setdefault(t, f'cap{k}.png'), cards.caption_html(t), (1920, 120)) for k, t in C.items()]
    items += [('badge8.png', cards.badge_html('▶▶ 8× speed'), None),
              ('badge20.png', cards.badge_html('▶▶ 24× speed'), None),
              ('closing.png', cards.card_html('PuppyGraph', 'Query your relational data as a graph. No ETL.',
                                              'Data: LDBC FinBench SF0.01 (synthetic banking data) in DuckDB · '
                                              'github.com/ericllin-puppygraph/Puppygraph-Bank-Demo'), (1920, 1080))]
    # terminal frames
    term = []
    for k, (t, doc) in enumerate(cards.term_frames(log)):
        name = f'term{k:03d}.png'
        items.append((name, doc, (1920, 960)))
        term.append((BUILD / name, t))
    asyncio.run(cards.shoot(items, BUILD))

    segs = []
    n = iter(range(100))
    segs.append(segment(next(n), video, 0.6, 8.6, 1.3, C['c0']))
    segs.append(segment(next(n), video, 8.6, T['ai'] - 0.3, 1.3, C['c1']))
    segs.append(segment(next(n), video, T['ai'] - 0.3, T['sent'] + 1.5, 1.6, C['c2']))
    g0, g_end = T['sent'] + 1.5, T['done']
    step = (g_end - g0) / 4
    for k in range(4):
        segs.append(segment(next(n), video, g0 + k * step, g0 + (k + 1) * step, 8, C[f'g{k + 1}'], 'badge8.png'))
    segs.append(segment(next(n), video, T['done'], T['shown'] + 0.8, 1.0, C['c3']))
    # queries: editor at full frame, then zoom into the graph area
    segs.append(segment(next(n), vq, q['q1_typed'] - 1.2, q['q1_result'] + 0.6, 1.0, C['q1a']))
    segs.append(segment(next(n), vq, q['q1_result'] + 1.6, q['q1_shown'], 1.3, C['q1b'], crop='1000:500:560:350'))
    segs.append(segment(next(n), vq, q['q2_typed'] - 1.0, q['q2_result'] + 0.6, 1.0, C['q2a']))
    segs.append(segment(next(n), vq, q['q2_result'] + 1.6, q['q2_shown'], 1.3, C['q2b'], crop='1000:500:500:350'))
    segs.append(segment(next(n), vq, q['q3_typed'] - 0.8, q['q3_shown'] - 0.5, 1.0, C['q3']))
    segs.append(segment(next(n), vq, q['q4_typed'] - 0.8, q['q4_shown'], 1.0, C['q4']))
    # agent replay at 20x, captions in thirds
    speed = 24
    frames = []
    for k, (png, t) in enumerate(term):
        nxt = term[k + 1][1] if k + 1 < len(term) else t + 40
        frames.append((png, max((nxt - t) / speed, 0.12)))
    total = sum(d for _, d in frames)
    thirds, acc, part = [[], [], []], 0, 0
    for fr in frames:
        if acc > total * (part + 1) / 3 and part < 2:
            part += 1
        thirds[part].append(fr)
        acc += fr[1]
    for k, key in enumerate(['a1', 'a2', 'a3']):
        if thirds[k]:
            segs.append(stills(next(n), thirds[k], C[key], 'badge20.png'))
    # deck
    pngs = sorted(SLIDES.glob('slide-*.png'))
    n_findings = len(json.load(open(FINAL / 'deck_spec.json'))['findings'])
    pick = [0, 1, 2, 3, 4, 5, 2 + n_findings, 2 + n_findings + 2, 2 + n_findings + 3]
    deck_frames = [(pngs[i], 2.0 if i else 2.6) for i in dict.fromkeys(pick) if i < len(pngs)]
    segs.append(stills(next(n), deck_frames, C['d1']))
    segs.append(card_segment(next(n), BUILD / 'closing.png', 4.5))

    lst = BUILD / 'concat.txt'
    lst.write_text(''.join(f"file '{s}'\n" for s in segs))
    out = OUT
    run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(lst), '-c', 'copy',
         '-movflags', '+faststart', str(out)])
    dur = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(out)],
                         capture_output=True, text=True).stdout.strip()
    print(f'wrote {out} · {float(dur):.1f} s · {out.stat().st_size / 1e6:.1f} MB')


main()
