"""Record the PuppyGraph UI part of the demo video in one continuous take.

Start from the catalog-only schema (bash scripts/start.sh schema-catalog-only.json) with an AI
provider configured, then run:
  python3 record_ui.py take1                   # catalog, PuppyGraph AI ontology, query scenes
  python3 record_ui.py take1q --queries-only   # re-record only the query scenes on the current graph
Writes take/<name>/video.webm and take/<name>/events.json (seconds since recording start).
"""
import asyncio, json, sys, time, urllib.request, base64
from pathlib import Path
from playwright.async_api import async_playwright

NAME = sys.argv[1] if len(sys.argv) > 1 else 'take1'
QUERIES_ONLY = '--queries-only' in sys.argv
OUT = Path('take') / NAME
OUT.mkdir(parents=True, exist_ok=True)
AUTH = 'Basic ' + base64.b64encode(b'puppygraph:puppygraph123').decode()

PROMPT = ("Build a graph schema for the bank tables in the duckdb_data catalog. Model people, companies, accounts, "
          "loans and sign-in media as nodes, and account ownership, transfers, withdrawals, loan applications, "
          "loan deposits, repayments, guarantees, investments and media sign-ins as edges. Keep every column as an "
          "attribute, including create_time and amounts. Name each edge after both ends, like PERSON_OWNS_ACCOUNT. "
          "Then apply it.")

# Labels the queries are written with, keyed by source table; replaced by the AI's labels after the take.
CANONICAL = {'person': 'Person', 'company': 'Company', 'account': 'Account', 'loan': 'Loan', 'medium': 'Medium',
             'medium_sign_in_account': 'MEDIUM_SIGNS_IN_ACCOUNT', 'account_transfer': 'ACCOUNT_TRANSFERS_ACCOUNT',
             'loan_deposit_account': 'LOAN_DEPOSITS_ACCOUNT', 'person_guarantee_person': 'PERSON_GUARANTEES_PERSON',
             'person_apply_loan': 'PERSON_APPLIES_LOAN'}
NEEDED_ATTRS = {'account_transfer': {'create_time', 'amount'}, 'loan_deposit_account': {'create_time'},
                'person': {'is_blocked', 'person_name'}, 'account': {'is_blocked'}, 'medium': {'is_blocked'},
                'loan': {'loan_amount'}}


def label_map(s):
    """Map canonical labels to the labels the AI chose, via each element's source table."""
    actual, attrs = {}, {}
    for el in s.get('node', []) + s.get('edge', []):
        table = el['dataSourceGroup']['externalDataSource']['table']
        actual[table] = el['label']
        attrs[table] = {a['name'] for a in el.get('attribute', [])} | {i['name'] for i in el.get('id', [])}
    missing = [t for t in CANONICAL if t not in actual]
    missing += [f'{t}.{a}' for t, need in NEEDED_ATTRS.items() for a in need - attrs.get(t, set())]
    return {CANONICAL[t]: actual[t] for t in CANONICAL if t in actual}, missing


def apply_map(cypher, mapping):
    import re
    return re.sub(r'(?<=:)([A-Za-z_]+)', lambda m: mapping.get(m.group(1), m.group(1)), cypher)

QUERIES = [
    ('q1', 'graph', """MATCH path = (m:Medium)-[:MEDIUM_SIGNS_IN_ACCOUNT]->(src:Account)
             -[t1:ACCOUNT_TRANSFERS_ACCOUNT]->(a1:Account)-[t2:ACCOUNT_TRANSFERS_ACCOUNT]->(a2:Account)
WHERE m.is_blocked AND t2.create_time > t1.create_time AND a2 <> src
RETURN path
LIMIT 25"""),
    ('q2', 'graph', """MATCH path = (a:Account)-[t1:ACCOUNT_TRANSFERS_ACCOUNT]->(b:Account)-[t2:ACCOUNT_TRANSFERS_ACCOUNT]->(c:Account)-[t3:ACCOUNT_TRANSFERS_ACCOUNT]->(a)
WHERE a <> b AND b <> c AND a <> c
  AND t1.create_time < t2.create_time AND t2.create_time < t3.create_time
RETURN path"""),
    ('q3', 'table', """MATCH (l:Loan)-[d:LOAN_DEPOSITS_ACCOUNT]->(a:Account)-[t:ACCOUNT_TRANSFERS_ACCOUNT]->(b:Account)
WHERE b.is_blocked AND t.create_time > d.create_time
RETURN count(DISTINCT l) AS loans,
       count(DISTINCT a) AS payout_accounts,
       count(DISTINCT b) AS blocked_recipients"""),
    ('q4', 'table', """MATCH chain = (g:Person)-[:PERSON_GUARANTEES_PERSON*1..5]->(x:Person)
MATCH (x)-[:PERSON_APPLIES_LOAN]->(l:Loan)
WITH g, count(DISTINCT x) AS people_backed, count(DISTINCT l) AS loans_backed,
     sum(l.loan_amount) AS loan_amount_backed, max(length(chain)) AS deepest_chain
RETURN g.person_name AS guarantor, people_backed, loans_backed,
       loan_amount_backed, deepest_chain
ORDER BY loan_amount_backed DESC
LIMIT 10"""),
]


def schema():
    req = urllib.request.Request('http://localhost:8081/schemajson', headers={'Authorization': AUTH})
    return json.load(urllib.request.urlopen(req))


async def main():
    events = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        # Pre-step (not recorded): sign in and forget any earlier chat session.
        ctx0 = await browser.new_context()
        pg0 = await ctx0.new_page()
        await pg0.goto('http://localhost:8081')
        await pg0.fill('input[type="text"]', 'puppygraph')
        await pg0.fill('input[type="password"]', 'puppygraph123')
        await pg0.keyboard.press('Enter')
        await pg0.wait_for_timeout(3000)
        await pg0.goto('http://localhost:8081/#/ai'); await pg0.wait_for_timeout(1500)
        await pg0.evaluate("localStorage.removeItem('puppyChatSessionId')")
        await ctx0.storage_state(path=str(OUT / 'state.json'))
        await ctx0.close()

        ctx = await browser.new_context(viewport={'width': 1920, 'height': 960}, storage_state=str(OUT / 'state.json'),
                                        record_video_dir=str(OUT), record_video_size={'width': 1920, 'height': 960})
        page = await ctx.new_page()
        t0 = time.monotonic()
        mark = lambda name, **kw: (events.append({'name': name, 't': round(time.monotonic() - t0, 2), **kw}),
                                   print(f'{time.monotonic() - t0:7.1f}  {name} {kw or ""}', flush=True))

        if QUERIES_ONLY:
            mapping, missing = label_map(schema())
            assert not missing, missing
        # Scene 0: connected catalog, no graph yet
        if not QUERIES_ONLY:
          await page.goto('http://localhost:8081/#/schema')
          await page.wait_for_selector('text=Build Your Graph Schema')
          await page.wait_for_timeout(500)
          mark('graph_page')
          await page.wait_for_timeout(3500)
          await page.get_by_role('button', name='Add Node').first.click()
          await page.wait_for_timeout(1500)
          mark('catalog_dialog')
          for label in ('duckdb_data', 'bank'):
              await page.get_by_text(label, exact=True).first.click()
              await page.wait_for_timeout(1200)
          mark('catalog_tables')
          await page.screenshot(path=str(OUT / 'catalog.png'))
          await page.wait_for_timeout(2000)
          await page.mouse.move(960, 560)
          for _ in range(6):
              await page.mouse.wheel(0, 90)
              await page.wait_for_timeout(450)
          await page.wait_for_timeout(2500)
          await page.get_by_role('button', name='Cancel').first.click()
          await page.wait_for_timeout(800)

          # Scene 1: PuppyGraph AI builds the ontology
          await page.goto('http://localhost:8081/#/ai')
          box = page.locator('textarea').first
          await box.wait_for()
          await page.wait_for_timeout(1500)
          mark('ai_page')
          await box.click()
          await box.type(PROMPT, delay=12)
          await page.wait_for_timeout(800)
          mark('prompt_typed')
          await page.keyboard.press('Enter')
          mark('prompt_sent')
          approvals = 0
          last_change, last_body = time.monotonic(), ''
          while time.monotonic() - t0 < 1500:
              await page.wait_for_timeout(700)
              approve = page.get_by_role('button', name='Approve', exact=True)
              if await approve.count():
                  await page.wait_for_timeout(900)      # let the viewer see the proposed change
                  await approve.first.click()
                  approvals += 1
                  mark('approve', n=approvals)
              body = await page.inner_text('body')
              if body != last_body:
                  last_body, last_change = body, time.monotonic()
              idle = time.monotonic() - last_change
              s = schema()
              if len(s.get('edge', [])) >= 13 and idle > 12:
                  break
          built = schema()
          (OUT / 'ai_schema.json').write_text(json.dumps(built, indent=1))
          mapping, missing = label_map(built)
          mark('ontology_done', nodes=[n['label'] for n in built.get('node', [])],
               edges=[e['label'] for e in built.get('edge', [])], missing=missing)
          if missing:
              print('TAKE UNUSABLE: missing', missing, flush=True)
          await page.wait_for_timeout(1500)
          await page.screenshot(path=str(OUT / 'ontology.png'))
          await page.wait_for_timeout(3000)
          mark('ontology_shown')

        # Scenes 2-5: questions in the Query page
        await page.goto('http://localhost:8081/#/query')
        editor = page.locator('.cm-content').first
        await editor.wait_for()
        await page.wait_for_timeout(1200)
        for name, view, cypher in QUERIES:
            await editor.click()
            await page.keyboard.press('Control+A')
            await page.keyboard.press('Delete')
            await page.keyboard.insert_text(apply_map(cypher, mapping))
            await page.wait_for_timeout(1500)
            mark(f'{name}_typed')
            async with page.expect_response(lambda r: r.url.endswith('/submitCypher'), timeout=120000):
                await page.get_by_role('button', name='Execute').first.click()
            await page.wait_for_timeout(600)
            mark(f'{name}_result')
            tab = 'Graph' if view == 'graph' else 'Table'
            await page.get_by_role('tab', name=tab).first.click()
            await page.wait_for_timeout(9000 if view == 'graph' else 6000)
            await page.screenshot(path=str(OUT / f'{name}.png'))
            mark(f'{name}_shown')
        mark('end')
        await page.wait_for_timeout(1000)
        video = page.video
        await ctx.close()
        Path(await video.path()).rename(OUT / 'video.webm')
        await browser.close()
    (OUT / 'events.json').write_text(json.dumps(events, indent=1))


asyncio.run(main())
