# PuppyGraph Banking Risk Demo

Find risk hidden in the connections between customers, accounts, devices, loans and guarantees using **PuppyGraph**, **DuckDB** and the [LDBC FinBench](https://ldbcouncil.org/benchmarks/finbench/datasets/) synthetic banking dataset.

The demo loads FinBench's 18 relational tables into DuckDB and queries them as a graph, with no ETL into a graph database. Start from the data connection alone and let **PuppyGraph AI** build the graph schema, or upload the ready-made `schema.json`. Then follow money, loans and guarantees across several hops.

## What this demo shows

Each table on its own looks harmless: a transfer, a sign-in, a loan payout, a guarantee. The risk is in the paths that join them. The included queries answer:

1. **Blocked-device exposure.** Which accounts and customers received money, directly or one hop later, from accounts used on a blocked sign-in device?
2. **Round-tripping.** Where does money leave an account and come back to it through other accounts, each transfer later than the one before?
3. **Loan proceeds.** Which loans had their proceeds moved on to a blocked account after payout?
4. **Guarantee chains.** How far does a chain of guarantees spread credit exposure across people and companies?

The [`briefing/`](briefing/) folder goes one step further. An LLM connects to PuppyGraph through the [PuppyGraph MCP server](https://github.com/puppygraph/puppygraph-mcp-server), explores the graph with read-only Cypher, and writes a briefing deck for risk leadership. Every number in the deck links to the exact query behind it.

| Output | File |
| --- | --- |
| Demo video (about 2 minutes) | [`demo/puppygraph-bank-demo.mp4`](demo/puppygraph-bank-demo.mp4) |
| Briefing deck, PDF | [`briefing/output/bank-risk-briefing.pdf`](briefing/output/bank-risk-briefing.pdf) |
| Briefing deck, PowerPoint | [`briefing/output/bank-risk-briefing.pptx`](briefing/output/bank-risk-briefing.pptx) |

## How it works

`scripts/load.py` reads the FinBench SF0.01 snapshot CSVs into 18 DuckDB tables in the `bank` schema. PuppyGraph reads those tables through a DuckDB catalog and serves them as a graph for Cypher and Gremlin. DuckDB runs as an embedded database file; PuppyGraph runs in Docker.

| Graph label | Source table | Meaning | Count |
| --- | --- | --- | ---: |
| `Person` | `person` | Individual customers | 785 |
| `Company` | `company` | Business customers | 386 |
| `Account` | `account` | Bank accounts; 117 are blocked | 2,055 |
| `Loan` | `loan` | Loans with amount, balance and purpose | 1,376 |
| `Medium` | `medium` | Devices and channels used to sign in; 54 are blocked | 978 |
| `PERSON_OWNS_ACCOUNT` | `person_own_account` | Person → Account | 1,384 |
| `COMPANY_OWNS_ACCOUNT` | `company_own_account` | Company → Account | 671 |
| `ACCOUNT_TRANSFERS_ACCOUNT` | `account_transfer` | Account → Account, with amount and time | 8,132 |
| `ACCOUNT_WITHDRAWS_ACCOUNT` | `account_withdraw` | Account → Account (card or cash withdrawal) | 9,182 |
| `ACCOUNT_REPAYS_LOAN` | `account_repay_loan` | Account → Loan | 2,747 |
| `LOAN_DEPOSITS_ACCOUNT` | `loan_deposit_account` | Loan → Account (payout) | 2,758 |
| `PERSON_APPLIES_LOAN` | `person_apply_loan` | Person → Loan, with lender | 927 |
| `COMPANY_APPLIES_LOAN` | `company_apply_loan` | Company → Loan, with lender | 449 |
| `PERSON_GUARANTEES_PERSON` | `person_guarantee_person` | Guarantor → guaranteed person | 377 |
| `COMPANY_GUARANTEES_COMPANY` | `company_guarantee_company` | Guarantor → guaranteed company | 202 |
| `PERSON_INVESTS_COMPANY` | `person_invest_company` | Person → Company, with share | 1,304 |
| `COMPANY_INVESTS_COMPANY` | `company_invest_company` | Company → Company, with share | 679 |
| `MEDIUM_SIGNS_IN_ACCOUNT` | `medium_sign_in_account` | Medium → Account, with location | 2,489 |

The graph has **5,580 nodes and 31,301 edges**. The label names in `schema.json` are the ones PuppyGraph AI chose when it built the schema in the demo video, so the queries work with either route below.

## Getting started

### Prerequisites

- Python 3.9 or newer, with `pip` and `venv`.
- Docker with Docker Compose, such as [Docker Desktop](https://docs.docker.com/desktop/).
- Bash and `curl` for the macOS/Linux commands below.
- Internet access for dependencies, and free ports `8081`, `8182` and `7687`.

The repository pins PuppyGraph `1.15.0`, DuckDB Python `1.4.3` and DuckDB JDBC `1.4.3.0`.

### Set up and load the data

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 scripts/load.py
```

The loader creates `data/bank_demo.db`, checks every row count and every edge endpoint, and reports:

```text
Validation passed:
  785 people, 386 companies, 2055 accounts (117 blocked)
  1376 loans, 978 sign-in media (54 blocked)
  31301 relationships across 13 edge tables, including 8132 transfers
```

### Start PuppyGraph

Open Docker Desktop and wait for it to start. Then choose a route.

**Route A: ready-made graph.** This starts PuppyGraph and uploads the full `schema.json`:

```bash
bash scripts/start.sh
```

**Route B: build the graph with PuppyGraph AI**, as in the video. This uploads only the DuckDB connection, so the graph starts empty:

```bash
bash scripts/start.sh schema-catalog-only.json
```

Then add an AI provider: open **Settings → AI Providers**, add an OpenAI or Anthropic provider with your key, and make it the default. Alternatively, enter a Claude API key on the **AI** page. Open **AI** and send:

> Build a graph schema for the bank tables in the duckdb_data catalog. Model people, companies, accounts, loans and sign-in media as nodes, and account ownership, transfers, withdrawals, loan applications, loan deposits, repayments, guarantees, investments and media sign-ins as edges. Keep every column as an attribute, including create_time and amounts. Name each edge after both ends, like PERSON_OWNS_ACCOUNT. Then apply it.

Approve each proposed node and edge, or turn on **Auto-confirm**. The AI chooses its own label names, and they can vary between runs. If yours differ from the ones above, adjust the queries or upload `schema.json` with `bash scripts/start.sh`. Asking it to keep `create_time` matters: without timestamps on the edges, the money-trail queries cannot check the order of transfers.

The first start may take several minutes. Open [http://localhost:8081](http://localhost:8081) and sign in with username **`puppygraph`** and password **`puppygraph123`**. These are local demo credentials, and the ports bind to `127.0.0.1` only.

Open **Query → Cypher** and run one statement at a time. Use the **Table** view for counts, and the **Graph** view for queries that return paths.

## Query walkthrough

Every money trail below requires each transfer to happen **after** the one before it (`create_time`), so a path is a sequence that money could actually have followed. "Blocked" is a status flag in the data, not proof of wrongdoing. Treat every result as exposure to review.

### 1. Check that the graph loaded

File: [`queries/01-check-counts.cypher`](queries/01-check-counts.cypher)

Counts every node label and relationship type; compare them with the table above. There are 117 blocked accounts and 54 blocked sign-in media.

### 2. Blocked-device exposure

File: [`queries/02-blocked-device-exposure.cypher`](queries/02-blocked-device-exposure.cypher)

```cypher
MATCH path = (m:Medium)-[:MEDIUM_SIGNS_IN_ACCOUNT]->(src:Account)
             -[t1:ACCOUNT_TRANSFERS_ACCOUNT]->(a1:Account)-[t2:ACCOUNT_TRANSFERS_ACCOUNT]->(a2:Account)
WHERE m.is_blocked AND t2.create_time > t1.create_time AND a2 <> src
RETURN path
LIMIT 60;
```

Starting from blocked devices, the query follows the accounts they signed in to, then two time-ordered transfers. Results:

- **25** blocked devices signed in to **32** accounts that start such a trail.
- Those accounts sent money to **71** accounts, and the money then reached **169** accounts at the second hop.
- The second-hop accounts belong to **92 people and 61 companies**.

These customers are two transfers away from the device, so a review of sign-in records alone would not surface them.

### 3. Round-tripping

File: [`queries/03-round-trip-transfers.cypher`](queries/03-round-trip-transfers.cypher)

```cypher
MATCH path = (a:Account)-[t1:ACCOUNT_TRANSFERS_ACCOUNT]->(b:Account)-[t2:ACCOUNT_TRANSFERS_ACCOUNT]->(c:Account)-[t3:ACCOUNT_TRANSFERS_ACCOUNT]->(a)
WHERE a <> b AND b <> c AND a <> c
  AND t1.create_time < t2.create_time AND t2.create_time < t3.create_time
RETURN path;
```

The query returns **9** time-ordered loops in which money leaves an account and returns through two others. They cover **8 starting accounts**; one loop appears twice because two separate transfers made its middle hop. Two of the loops pass through a blocked account. The table version in the file lists the amounts out and back and the dates.

### 4. Loan proceeds that reach blocked accounts

File: [`queries/04-loan-proceeds-to-blocked.cypher`](queries/04-loan-proceeds-to-blocked.cypher)

```cypher
MATCH (l:Loan)-[d:LOAN_DEPOSITS_ACCOUNT]->(a:Account)-[t:ACCOUNT_TRANSFERS_ACCOUNT]->(b:Account)
WHERE b.is_blocked AND t.create_time > d.create_time
RETURN count(DISTINCT l) AS loans,
       count(DISTINCT a) AS payout_accounts,
       count(DISTINCT b) AS blocked_recipients;
```

Of the **1,107** loans with a recorded payout, **184** paid out to an account that later sent money directly to a blocked account. That is **112** payout accounts sending to **68** different blocked accounts. The graph view in the file adds the borrower, so each path reads borrower → loan → payout account → blocked account.

### 5. Guarantee chains

File: [`queries/05-guarantee-chains.cypher`](queries/05-guarantee-chains.cypher)

```cypher
MATCH chain = (g:Person)-[:PERSON_GUARANTEES_PERSON*1..5]->(x:Person)
MATCH (x)-[:PERSON_APPLIES_LOAN]->(l:Loan)
WITH g, count(DISTINCT x) AS people_backed, count(DISTINCT l) AS loans_backed,
     sum(l.loan_amount) AS loan_amount_backed, max(length(chain)) AS deepest_chain
RETURN g.person_name AS guarantor, people_backed, loans_backed,
       loan_amount_backed, deepest_chain
ORDER BY loan_amount_backed DESC
LIMIT 10;
```

For each guarantor, the query follows the chain up to five guarantees deep and adds up the loans of everyone at the end of it. The top guarantor backs, through a five-step chain, **5 people with 18 loans**. The file repeats the query for companies, and shows the longest chains in graph view.

## The AI briefing

[`briefing/deck_agent.py`](briefing/deck_agent.py) lets an OpenAI model act as a risk analyst. It starts the PuppyGraph MCP server in read-only mode and offers the model two of its tools, `puppygraph_schema` and `puppygraph_query`, plus a local `submit_deck` tool. The task is in [`briefing/prompt.md`](briefing/prompt.md).

The model reads the schema, runs its own Cypher queries and submits a deck spec. The spec is rejected unless every query cited in the appendix ran successfully, verbatim, in the same session. Every step is logged to `session-log.jsonl`. [`briefing/render_deck.py`](briefing/render_deck.py) turns the spec into the PDF and PowerPoint, with editable native charts in the PowerPoint.

To rerun it against your own running demo:

```bash
git clone https://github.com/puppygraph/puppygraph-mcp-server
(cd puppygraph-mcp-server && npm ci && npm run build)
python3 -m pip install -r briefing/requirements.txt
python3 -m playwright install chromium
export OPENAI_API_KEY=...
python3 briefing/deck_agent.py --mcp-server puppygraph-mcp-server/build/index.js
python3 briefing/render_deck.py briefing/output/deck_spec.json
```

The model writes a different deck each run. The checked-in deck in `briefing/output/` is the run shown in the video: gpt-5.5 ran 45 Cypher queries in 263 seconds. One query hit an unsupported Cypher feature and was rewritten, and the first submission was rejected until six cited queries had been run verbatim. Its four findings:

| Finding | Headline number |
| --- | --- |
| Accounts used from blocked devices sent money that reached other accounts within three time-ordered hops | 41 → **418** accounts |
| Time-ordered transfer loops of two to four hops return money to the account it left | **63** loops, 45 starting accounts |
| Loans whose proceeds reached a blocked account within one to three transfers after payout | **503** of 1,107 paid-out loans |
| Guarantee chains up to four deep widen guarantor-to-borrower exposure | 579 direct → **1,041** pairs |

To check a deck, rerun every appendix query and compare the results with each finding's derivation text:

```bash
python3 briefing/verify_deck.py briefing/output/deck_spec.json
```

You can also give [`briefing/prompt.md`](briefing/prompt.md) to any MCP client connected to the PuppyGraph MCP server, such as Claude Desktop or the ChatGPT desktop app. The `submit_deck` check and the renderer are specific to this script.

## The demo video

[`demo/puppygraph-bank-demo.mp4`](demo/puppygraph-bank-demo.mp4) (about 2 minutes) shows the whole flow:

1. PuppyGraph connected to the DuckDB catalog, with no graph schema yet.
2. PuppyGraph AI building the schema from the prompt above (sped up 8×), checking edge counts against the source tables.
3. The four walkthrough questions answered in the Query page.
4. gpt-5.5 exploring the graph through the PuppyGraph MCP server, replayed from the real session log (24×).
5. The finished briefing deck.

The tools in [`demo/tools/`](demo/tools/) recreate it with Playwright and ffmpeg. `record_ui.py` records the UI and maps the queries to whatever labels the AI chooses, using each label's source table. `make_video.py` adds captions, speed-ups and the terminal replay.

## Understanding the data

- **Source:** the LDBC FinBench SF0.01 `snapshot` files: 18 pipe-delimited CSVs, unmodified, in [`data/finbench-sf0.01/`](data/finbench-sf0.01/). The `incremental` and `raw` folders of the release are not used.
- **Synthetic:** FinBench is generated data designed for benchmarking. Names, amounts and dates are synthetic. Amounts are large and should not be read as realistic balances.
- **Renamed columns:** the loader converts camelCase to snake_case and fixes the source spelling `accoutType` → `account_type`. Login times stored as epoch milliseconds become timestamps.
- **Dropped columns:** the free-text `comment` on transfers, the company `description` and the account `phonenum` and `email` columns are generated filler text and are not loaded.
- **Edge ids:** FinBench allows several edges between the same pair, such as repeated transfers. Each edge table gets a deterministic `edge_id`, numbered by time and endpoints.
- **Blocked flags:** 117 accounts and 54 sign-in media are blocked. No person or company is blocked in SF0.01.

## Stop or reload the demo

Stop PuppyGraph with `docker compose stop`, and restart an unchanged setup with `docker compose start`.

To rebuild the data and reapply the mapping:

```bash
docker compose stop
source .venv/bin/activate
python3 scripts/load.py
bash scripts/start.sh
```

Always stop PuppyGraph before writing to its DuckDB file. Loading and validation run in one transaction, so a failure rolls back all table changes.

## Repository structure

| Path | Purpose |
| --- | --- |
| `data/finbench-sf0.01/` | Original FinBench SF0.01 snapshot CSVs |
| `scripts/load.py`, `load.sql`, `validate.sql` | Build and validate the DuckDB tables |
| `scripts/start.sh` | Start PuppyGraph and upload a schema |
| `schema.json` | Full graph mapping: 5 node labels and 13 edge labels |
| `schema-catalog-only.json` | Data connection only, for building the graph with PuppyGraph AI |
| `docker-compose.yaml` | Local PuppyGraph container |
| `queries/` | Cypher walkthrough |
| `briefing/` | AI briefing agent, deck renderer and checker, and the deck from the video with its session log |
| `demo/` | Demo video, the schema PuppyGraph AI generated in it (`puppygraph-ai-schema.json`) and the tools that recorded and edited it (`demo/tools/`) |

## Troubleshooting

| Problem | Action |
| --- | --- |
| Python or DuckDB unavailable | Use `python3`, activate `.venv` and install `requirements.txt`. |
| Docker unavailable or ports in use | Start Docker Desktop and stop other applications using ports 8081, 8182 and 7687. |
| Database missing or locked | Run the loader with PuppyGraph stopped and other database connections closed. |
| Schema upload fails | Rerun `bash scripts/start.sh` and check `docker compose logs --tail=60 puppygraph`. |
| JDBC driver download fails | Check that the container can reach `repo.maven.apache.org`. |
| PuppyGraph AI asks for a Claude key | Add a provider under **Settings → AI Providers**, or enter the key on the AI page. |
| A query returns an "Unsupported" error | PuppyGraph supports most of openCypher. `EXISTS {}` subqueries and duration functions are not supported, `UNION` can only combine scalar values (return `id(n)` instead of `n`), and `collect(DISTINCT ...)` must be the only aggregation in its query. |

## Data source and attribution

The data is the [LDBC Financial Benchmark (FinBench)](https://ldbcouncil.org/benchmarks/finbench/) SF0.01 dataset, [sf0.01.tar.gz](https://datasets.ldbcouncil.org/finbench/sf0.01.tar.gz), from the [Graph Data Council (LDBC)](https://ldbcouncil.org/). The data was produced with the [FinBench data generator](https://github.com/ldbc/ldbc_finbench_datagen), released under the Apache License 2.0. The CSV files are included unmodified; the tables and edge ids are derived by this demo.

## Further reading

- [PuppyGraph with DuckDB](https://docs.puppygraph.com/getting-started/querying-duckdb-data-as-a-graph/)
- [Graph modeling](https://docs.puppygraph.com/modeling/building-a-graph/)
- [PuppyGraph MCP server](https://github.com/puppygraph/puppygraph-mcp-server)
- [LDBC FinBench specification](https://ldbcouncil.org/ldbc_finbench_docs/)
