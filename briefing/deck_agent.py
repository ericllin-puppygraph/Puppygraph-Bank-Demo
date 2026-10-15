#!/usr/bin/env python3
"""Let an OpenAI model explore the bank graph through PuppyGraph's MCP server and write the briefing.

The model sees only the MCP server's read-only query and schema tools plus a local
submit_deck tool. Every tool call is logged to a JSONL session log, and a deck is
accepted only if each appendix query was actually run in the session.

Usage:
  python3 briefing/deck_agent.py --mcp-server /path/to/puppygraph-mcp-server/build/index.js
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI

HERE = Path(__file__).resolve().parent
MCP_TOOLS = ('puppygraph_schema', 'puppygraph_query')
MAX_RESULT_CHARS = 12000

FIGURE = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['id', 'headline', 'chart', 'callout_value', 'callout_text', 'body', 'queries', 'derivation'],
    'properties': {
        'id': {'type': 'string', 'description': 'Appendix id such as A1'},
        'headline': {'type': 'string', 'description': 'Slide title stating the finding as a sentence'},
        'chart': {
            'type': 'object',
            'additionalProperties': False,
            'required': ['title', 'orientation', 'categories', 'series'],
            'properties': {
                'title': {'type': 'string'},
                'orientation': {'type': 'string', 'enum': ['vertical', 'horizontal']},
                'categories': {'type': 'array', 'items': {'type': 'string'}},
                'series': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'additionalProperties': False,
                        'required': ['name', 'values'],
                        'properties': {'name': {'type': 'string'},
                                       'values': {'type': 'array', 'items': {'type': 'number'}}},
                    },
                },
            },
        },
        'callout_value': {'type': 'string', 'description': 'Large number shown next to the chart'},
        'callout_text': {'type': 'string'},
        'body': {'type': 'string', 'description': 'Two to four sentences of interpretation'},
        'queries': {
            'type': 'array',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['label', 'cypher'],
                'properties': {'label': {'type': 'string'}, 'cypher': {'type': 'string'}},
            },
        },
        'derivation': {'type': 'string', 'description': 'Query results and arithmetic behind every number'},
    },
}

DECK = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['title', 'subtitle', 'audience', 'data_note', 'key_numbers', 'findings',
                 'recommendations', 'appendix'],
    'properties': {
        'title': {'type': 'string'},
        'subtitle': {'type': 'string'},
        'audience': {'type': 'string'},
        'data_note': {'type': 'string'},
        'key_numbers': {
            'type': 'array',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['value', 'label', 'detail'],
                'properties': {'value': {'type': 'string'}, 'label': {'type': 'string'},
                               'detail': {'type': 'string'}},
            },
        },
        'findings': {'type': 'array', 'items': FIGURE},
        'recommendations': {
            'type': 'array',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['title', 'detail'],
                'properties': {'title': {'type': 'string'}, 'detail': {'type': 'string'}},
            },
        },
        'appendix': {
            'type': 'object',
            'additionalProperties': False,
            'required': ['graph', 'key_paths', 'baselines', 'assumptions'],
            'properties': {
                'graph': {'type': 'string'},
                'key_paths': {'type': 'string'},
                'baselines': {'type': 'string'},
                'assumptions': {'type': 'array', 'items': {'type': 'string'}},
            },
        },
    },
}

SUBMIT_TOOL = {
    'type': 'function',
    'name': 'submit_deck',
    'description': 'Submit the finished briefing deck. Call once, after every number has been queried.',
    'parameters': DECK,
    'strict': True,
}


def normalize(query):
    return ' '.join(query.split()).rstrip(';')


class Session:
    def __init__(self, log_path):
        self.log = open(log_path, 'w')
        self.started = time.time()
        self.queries_ok = set()
        self.query_count = 0

    def write(self, kind, **fields):
        record = {'t': round(time.time() - self.started, 2), 'kind': kind, **fields}
        self.log.write(json.dumps(record, default=str) + '\n')
        self.log.flush()
        if kind == 'query':
            status = f"{fields['rows']} rows" if fields.get('ok') else 'ERROR'
            print(f"  run_cypher ({status}): {normalize(fields['cypher'])[:110]}")
        elif kind == 'reasoning':
            print(f"• {fields['text']}")
        elif kind != 'tool_result':
            print(f'[{kind}] {str(fields)[:160]}')


def missing_queries(deck, session):
    return [f"{fig['id']}: {q['label']}" for fig in deck['findings'] for q in fig['queries']
            if normalize(q['cypher']) not in session.queries_ok]


async def call_mcp(mcp, session, name, args):
    result = await mcp.call_tool(name, args)
    text = '\n'.join(c.text for c in result.content if getattr(c, 'type', '') == 'text')
    if name == 'puppygraph_query':
        session.query_count += 1
        ok = not result.is_error
        rows = None
        try:
            payload = json.loads(text)
            ok = ok and not payload['metadata'].get('error')
            rows = len(payload['data'])
        except (json.JSONDecodeError, KeyError, TypeError):
            ok = False
        if ok:
            session.queries_ok.add(normalize(args.get('query', '')))
        session.write('query', cypher=args.get('query', ''), ok=ok, rows=rows,
                      error=None if ok else text[:400])
    else:
        session.write('tool_result', tool=name, chars=len(text))
    if name == 'puppygraph_query' and len(text) > MAX_RESULT_CHARS:
        text = text[:MAX_RESULT_CHARS] + '\n... (truncated; aggregate or LIMIT the query)'
    return text


async def run(args):
    client = OpenAI()
    prompt = (HERE / 'prompt.md').read_text()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    session = Session(out_dir / 'session-log.jsonl')
    server = StdioServerParameters(
        command='node', args=[args.mcp_server],
        env={**os.environ, 'PUPPYGRAPH_READ_ONLY': 'true'})
    async with stdio_client(server) as (read, write), ClientSession(read, write) as mcp:
        await mcp.initialize()
        listed = {t.name: t for t in (await mcp.list_tools()).tools}
        tools = [{'type': 'function', 'name': n, 'description': listed[n].description,
                  'parameters': listed[n].input_schema} for n in MCP_TOOLS]
        tools.append(SUBMIT_TOOL)
        session.write('start', model=args.model, tools=[t['name'] for t in tools])

        pending = [{'role': 'user', 'content': prompt}]
        previous = None
        deck = None
        for _ in range(args.max_turns):
            response = client.responses.create(
                model=args.model, input=pending, tools=tools, previous_response_id=previous,
                reasoning={'effort': args.effort, 'summary': 'auto'})
            previous = response.id
            pending = []
            for item in response.output:
                if item.type == 'reasoning':
                    for part in item.summary or []:
                        heading = part.text.strip().split('\n')[0].strip('*# ')
                        session.write('reasoning', text=heading)
                elif item.type == 'message':
                    text = ''.join(c.text for c in item.content if c.type == 'output_text')
                    session.write('message', text=text)
                elif item.type == 'function_call':
                    call_args = json.loads(item.arguments or '{}')
                    if item.name == 'submit_deck':
                        missing = missing_queries(call_args, session)
                        if missing:
                            output = ('Rejected: these appendix queries were not run successfully in this '
                                      'session, verbatim. Run them, then resubmit: ' + '; '.join(missing))
                            session.write('submit_rejected', missing=missing)
                        else:
                            deck = call_args
                            output = 'Deck accepted.'
                            session.write('submit_deck', title=deck['title'],
                                          findings=len(deck['findings']), queries=session.query_count)
                    else:
                        output = await call_mcp(mcp, session, item.name, call_args)
                    pending.append({'type': 'function_call_output', 'call_id': item.call_id,
                                    'output': output})
            if deck or not pending:
                break
    if not deck:
        sys.exit('The model stopped without an accepted deck; see session-log.jsonl')
    (out_dir / 'deck_spec.json').write_text(json.dumps(deck, indent=2) + '\n')
    print(f"Deck spec written to {out_dir / 'deck_spec.json'} after {session.query_count} queries, "
          f'{time.time() - session.started:.0f} s')


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--mcp-server', required=True, help='Path to puppygraph-mcp-server build/index.js')
    parser.add_argument('--model', default='gpt-5.5')
    parser.add_argument('--effort', default='medium')
    parser.add_argument('--max-turns', type=int, default=80)
    parser.add_argument('--out-dir', default=str(HERE / 'output'))
    asyncio.run(run(parser.parse_args()))


if __name__ == '__main__':
    main()
