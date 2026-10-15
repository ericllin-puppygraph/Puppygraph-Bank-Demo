#!/usr/bin/env python3
"""Build and validate the bank tables from the bundled FinBench snapshot in one transaction."""
import os
from pathlib import Path
import sys

try:
    import duckdb
except ImportError:
    sys.exit('Install the dependency first: python3 -m pip install -r requirements.txt')

ROOT = Path(__file__).resolve().parents[1]
NODES = ('person', 'company', 'account', 'loan', 'medium')
EDGES = ('person_own_account', 'company_own_account', 'account_transfer', 'account_withdraw',
         'account_repay_loan', 'loan_deposit_account', 'person_apply_loan', 'company_apply_loan',
         'person_guarantee_person', 'company_guarantee_company', 'person_invest_company',
         'company_invest_company', 'medium_sign_in_account')


def main():
    os.chdir(ROOT)
    output = ROOT / 'data' / 'bank_demo.db'
    # Stop PuppyGraph before opening this database for writing.
    with duckdb.connect(str(output)) as connection:
        connection.execute('BEGIN TRANSACTION')
        try:
            connection.execute((ROOT / 'scripts' / 'load.sql').read_text())
            connection.execute((ROOT / 'scripts' / 'validate.sql').read_text())
            counts = {
                table: connection.execute(f'SELECT count(*) FROM bank.{table}').fetchone()[0]
                for table in NODES + EDGES
            }
            blocked_accounts = connection.execute(
                'SELECT count(*) FROM bank.account WHERE is_blocked').fetchone()[0]
            blocked_media = connection.execute(
                'SELECT count(*) FROM bank.medium WHERE is_blocked').fetchone()[0]
            connection.execute('COMMIT')
        except Exception:
            connection.execute('ROLLBACK')
            raise
    print('Validation passed:')
    print(f"  {counts['person']} people, {counts['company']} companies, "
          f"{counts['account']} accounts ({blocked_accounts} blocked)")
    print(f"  {counts['loan']} loans, {counts['medium']} sign-in media ({blocked_media} blocked)")
    print(f"  {sum(counts[e] for e in EDGES)} relationships across {len(EDGES)} edge tables, "
          f"including {counts['account_transfer']} transfers")
    print(f'Database: {output}')


if __name__ == '__main__':
    try:
        main()
    except (duckdb.Error, OSError) as exc:
        sys.exit(f'Loading failed: {exc}')
