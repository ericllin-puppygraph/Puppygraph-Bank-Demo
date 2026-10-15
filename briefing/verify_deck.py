#!/usr/bin/env python3
"""Re-run every appendix query of a deck spec against PuppyGraph and print the results.

Compare each result with the finding's "Results and derivation" text.

Usage:
  python3 briefing/verify_deck.py briefing/output/deck_spec.json
"""
import json
import sys

from neo4j import GraphDatabase


def main():
    deck = json.load(open(sys.argv[1]))
    driver = GraphDatabase.driver('bolt://localhost:7687', auth=('puppygraph', 'puppygraph123'))
    failures = 0
    with driver.session() as session:
        for finding in deck['findings']:
            print(f"\n=== {finding['id']} · {finding['headline']}")
            print(f"derivation: {finding['derivation']}")
            for query in finding['queries']:
                try:
                    rows = [dict(r) for r in session.run(query['cypher'])]
                    shown = rows[:12]
                    print(f"\n-- {query['label']} ({len(rows)} rows)")
                    for row in shown:
                        print('   ', json.dumps(row, default=str))
                    if len(rows) > len(shown):
                        print(f'    ... {len(rows) - len(shown)} more')
                except Exception as exc:  # report and keep checking the rest
                    failures += 1
                    print(f"\n-- {query['label']}: FAILED {exc}")
    driver.close()
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
