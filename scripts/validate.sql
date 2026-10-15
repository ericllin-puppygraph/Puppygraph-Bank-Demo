-- Fail the load if any edge points at a missing node or a row count drifts
-- from the published FinBench SF0.01 snapshot.

CREATE OR REPLACE TEMP TABLE expected_counts AS
SELECT * FROM (VALUES
  ('person', 785), ('company', 386), ('account', 2055), ('loan', 1376), ('medium', 978),
  ('person_own_account', 1384), ('company_own_account', 671),
  ('account_transfer', 8132), ('account_withdraw', 9182),
  ('account_repay_loan', 2747), ('loan_deposit_account', 2758),
  ('person_apply_loan', 927), ('company_apply_loan', 449),
  ('person_guarantee_person', 377), ('company_guarantee_company', 202),
  ('person_invest_company', 1304), ('company_invest_company', 679),
  ('medium_sign_in_account', 2489)
) AS t(table_name, expected);

CREATE OR REPLACE TEMP TABLE actual_counts AS
SELECT 'person' AS table_name, count(*) AS actual FROM bank.person
UNION ALL SELECT 'company' AS table_name, count(*) AS actual FROM bank.company
UNION ALL SELECT 'account' AS table_name, count(*) AS actual FROM bank.account
UNION ALL SELECT 'loan' AS table_name, count(*) AS actual FROM bank.loan
UNION ALL SELECT 'medium' AS table_name, count(*) AS actual FROM bank.medium
UNION ALL SELECT 'person_own_account' AS table_name, count(*) AS actual FROM bank.person_own_account
UNION ALL SELECT 'company_own_account' AS table_name, count(*) AS actual FROM bank.company_own_account
UNION ALL SELECT 'account_transfer' AS table_name, count(*) AS actual FROM bank.account_transfer
UNION ALL SELECT 'account_withdraw' AS table_name, count(*) AS actual FROM bank.account_withdraw
UNION ALL SELECT 'account_repay_loan' AS table_name, count(*) AS actual FROM bank.account_repay_loan
UNION ALL SELECT 'loan_deposit_account' AS table_name, count(*) AS actual FROM bank.loan_deposit_account
UNION ALL SELECT 'person_apply_loan' AS table_name, count(*) AS actual FROM bank.person_apply_loan
UNION ALL SELECT 'company_apply_loan' AS table_name, count(*) AS actual FROM bank.company_apply_loan
UNION ALL SELECT 'person_guarantee_person' AS table_name, count(*) AS actual FROM bank.person_guarantee_person
UNION ALL SELECT 'company_guarantee_company' AS table_name, count(*) AS actual FROM bank.company_guarantee_company
UNION ALL SELECT 'person_invest_company' AS table_name, count(*) AS actual FROM bank.person_invest_company
UNION ALL SELECT 'company_invest_company' AS table_name, count(*) AS actual FROM bank.company_invest_company
UNION ALL SELECT 'medium_sign_in_account' AS table_name, count(*) AS actual FROM bank.medium_sign_in_account;

CREATE OR REPLACE TEMP TABLE validation_errors AS
SELECT table_name || ' has ' || actual || ' rows, expected ' || expected AS problem, actual AS n
FROM expected_counts JOIN actual_counts USING (table_name)
WHERE actual <> expected
UNION ALL
SELECT 'dangling ' || check_name AS problem, n FROM (
  SELECT 'person_own_account' AS check_name, count(*) AS n FROM bank.person_own_account e
    WHERE e.person_id NOT IN (SELECT person_id FROM bank.person) OR e.account_id NOT IN (SELECT account_id FROM bank.account)
  UNION ALL SELECT 'company_own_account', count(*) FROM bank.company_own_account e
    WHERE e.company_id NOT IN (SELECT company_id FROM bank.company) OR e.account_id NOT IN (SELECT account_id FROM bank.account)
  UNION ALL SELECT 'account_transfer', count(*) FROM bank.account_transfer e
    WHERE e.from_account_id NOT IN (SELECT account_id FROM bank.account) OR e.to_account_id NOT IN (SELECT account_id FROM bank.account)
  UNION ALL SELECT 'account_withdraw', count(*) FROM bank.account_withdraw e
    WHERE e.from_account_id NOT IN (SELECT account_id FROM bank.account) OR e.to_account_id NOT IN (SELECT account_id FROM bank.account)
  UNION ALL SELECT 'account_repay_loan', count(*) FROM bank.account_repay_loan e
    WHERE e.account_id NOT IN (SELECT account_id FROM bank.account) OR e.loan_id NOT IN (SELECT loan_id FROM bank.loan)
  UNION ALL SELECT 'loan_deposit_account', count(*) FROM bank.loan_deposit_account e
    WHERE e.loan_id NOT IN (SELECT loan_id FROM bank.loan) OR e.account_id NOT IN (SELECT account_id FROM bank.account)
  UNION ALL SELECT 'person_apply_loan', count(*) FROM bank.person_apply_loan e
    WHERE e.person_id NOT IN (SELECT person_id FROM bank.person) OR e.loan_id NOT IN (SELECT loan_id FROM bank.loan)
  UNION ALL SELECT 'company_apply_loan', count(*) FROM bank.company_apply_loan e
    WHERE e.company_id NOT IN (SELECT company_id FROM bank.company) OR e.loan_id NOT IN (SELECT loan_id FROM bank.loan)
  UNION ALL SELECT 'person_guarantee_person', count(*) FROM bank.person_guarantee_person e
    WHERE e.guarantor_person_id NOT IN (SELECT person_id FROM bank.person) OR e.guaranteed_person_id NOT IN (SELECT person_id FROM bank.person)
  UNION ALL SELECT 'company_guarantee_company', count(*) FROM bank.company_guarantee_company e
    WHERE e.guarantor_company_id NOT IN (SELECT company_id FROM bank.company) OR e.guaranteed_company_id NOT IN (SELECT company_id FROM bank.company)
  UNION ALL SELECT 'person_invest_company', count(*) FROM bank.person_invest_company e
    WHERE e.investor_person_id NOT IN (SELECT person_id FROM bank.person) OR e.company_id NOT IN (SELECT company_id FROM bank.company)
  UNION ALL SELECT 'company_invest_company', count(*) FROM bank.company_invest_company e
    WHERE e.investor_company_id NOT IN (SELECT company_id FROM bank.company) OR e.company_id NOT IN (SELECT company_id FROM bank.company)
  UNION ALL SELECT 'medium_sign_in_account', count(*) FROM bank.medium_sign_in_account e
    WHERE e.medium_id NOT IN (SELECT medium_id FROM bank.medium) OR e.account_id NOT IN (SELECT account_id FROM bank.account)
) WHERE n > 0;

-- Abort the transaction with a readable message on the first problem.
SELECT CASE WHEN count(*) > 0
            THEN error('Validation failed: ' || string_agg(problem || ' (' || n || ')', ', '))
       END
FROM validation_errors;
