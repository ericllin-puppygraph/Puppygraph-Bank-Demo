-- Build the bank schema from the LDBC FinBench SF0.01 snapshot CSVs.
-- Run from the repository root (scripts/load.py does this).
-- Source files are pipe-delimited with a header row and are not modified.

CREATE SCHEMA IF NOT EXISTS bank;

-- Nodes ----------------------------------------------------------------------

CREATE OR REPLACE TABLE bank.person AS
SELECT personId::BIGINT          AS person_id,
       personName                AS person_name,
       isBlocked::BOOLEAN        AS is_blocked,
       createTime::TIMESTAMP     AS create_time,
       gender,
       birthday::DATE            AS birthday,
       country,
       city
FROM read_csv('data/finbench-sf0.01/Person.csv', delim = '|', header = true);

CREATE OR REPLACE TABLE bank.company AS
SELECT companyId::BIGINT         AS company_id,
       companyName               AS company_name,
       isBlocked::BOOLEAN        AS is_blocked,
       createTime::TIMESTAMP     AS create_time,
       country,
       city,
       business,
       url
FROM read_csv('data/finbench-sf0.01/Company.csv', delim = '|', header = true);

-- The source header spells the account type column "accoutType".
CREATE OR REPLACE TABLE bank.account AS
SELECT accountId::BIGINT         AS account_id,
       createTime::TIMESTAMP     AS create_time,
       isBlocked::BOOLEAN        AS is_blocked,
       accoutType                AS account_type,
       nickname,
       freqLoginType             AS freq_login_type,
       make_timestamp(lastLoginTime::BIGINT * 1000) AS last_login_time,
       accountLevel              AS account_level
FROM read_csv('data/finbench-sf0.01/Account.csv', delim = '|', header = true);

CREATE OR REPLACE TABLE bank.loan AS
SELECT loanId::BIGINT            AS loan_id,
       loanAmount::DOUBLE        AS loan_amount,
       balance::DOUBLE           AS balance,
       createTime::TIMESTAMP     AS create_time,
       loanUsage                 AS loan_usage,
       interestRate::DOUBLE      AS interest_rate
FROM read_csv('data/finbench-sf0.01/Loan.csv', delim = '|', header = true);

-- A medium is a device or channel used to sign in (phone, POS, NFC, ...).
CREATE OR REPLACE TABLE bank.medium AS
SELECT mediumId::BIGINT          AS medium_id,
       mediumType                AS medium_type,
       isBlocked::BOOLEAN        AS is_blocked,
       createTime::TIMESTAMP     AS create_time,
       make_timestamp(lastLoginTime::BIGINT * 1000) AS last_login_time,
       riskLevel                 AS risk_level
FROM read_csv('data/finbench-sf0.01/Medium.csv', delim = '|', header = true);

-- Edges ----------------------------------------------------------------------
-- FinBench allows several edges between the same pair (for example repeated
-- transfers), so every edge table gets a generated, deterministic edge_id.

CREATE OR REPLACE TABLE bank.person_own_account AS
SELECT 'POA' || row_number() OVER (ORDER BY createTime, personId, accountId) AS edge_id,
       personId::BIGINT AS person_id, accountId::BIGINT AS account_id,
       createTime::TIMESTAMP AS create_time
FROM read_csv('data/finbench-sf0.01/PersonOwnAccount.csv', delim = '|', header = true);

CREATE OR REPLACE TABLE bank.company_own_account AS
SELECT 'COA' || row_number() OVER (ORDER BY createTime, companyId, accountId) AS edge_id,
       companyId::BIGINT AS company_id, accountId::BIGINT AS account_id,
       createTime::TIMESTAMP AS create_time
FROM read_csv('data/finbench-sf0.01/CompanyOwnAccount.csv', delim = '|', header = true);

-- The free-text "comment" column (generated filler prose) is not loaded.
CREATE OR REPLACE TABLE bank.account_transfer AS
SELECT 'TR' || row_number() OVER (ORDER BY createTime, fromId, toId, orderNum) AS edge_id,
       fromId::BIGINT AS from_account_id, toId::BIGINT AS to_account_id,
       amount::DOUBLE AS amount, createTime::TIMESTAMP AS create_time,
       orderNum::VARCHAR AS order_num, payType AS pay_type, goodsType AS goods_type
FROM read_csv('data/finbench-sf0.01/AccountTransferAccount.csv', delim = '|', header = true);

CREATE OR REPLACE TABLE bank.account_withdraw AS
SELECT 'WD' || row_number() OVER (ORDER BY createTime, fromId, toId, amount) AS edge_id,
       fromId::BIGINT AS from_account_id, toId::BIGINT AS to_account_id,
       amount::DOUBLE AS amount, createTime::TIMESTAMP AS create_time
FROM read_csv('data/finbench-sf0.01/AccountWithdrawAccount.csv', delim = '|', header = true);

CREATE OR REPLACE TABLE bank.account_repay_loan AS
SELECT 'RP' || row_number() OVER (ORDER BY createTime, accountId, loanId, amount) AS edge_id,
       accountId::BIGINT AS account_id, loanId::BIGINT AS loan_id,
       amount::DOUBLE AS amount, createTime::TIMESTAMP AS create_time
FROM read_csv('data/finbench-sf0.01/AccountRepayLoan.csv', delim = '|', header = true);

CREATE OR REPLACE TABLE bank.loan_deposit_account AS
SELECT 'DP' || row_number() OVER (ORDER BY createTime, loanId, accountId, amount) AS edge_id,
       loanId::BIGINT AS loan_id, accountId::BIGINT AS account_id,
       amount::DOUBLE AS amount, createTime::TIMESTAMP AS create_time
FROM read_csv('data/finbench-sf0.01/LoanDepositAccount.csv', delim = '|', header = true);

CREATE OR REPLACE TABLE bank.person_apply_loan AS
SELECT 'PAL' || row_number() OVER (ORDER BY createTime, personId, loanId) AS edge_id,
       personId::BIGINT AS person_id, loanId::BIGINT AS loan_id,
       createTime::TIMESTAMP AS create_time, org AS lender
FROM read_csv('data/finbench-sf0.01/PersonApplyLoan.csv', delim = '|', header = true);

CREATE OR REPLACE TABLE bank.company_apply_loan AS
SELECT 'CAL' || row_number() OVER (ORDER BY createTime, companyId, loanId) AS edge_id,
       companyId::BIGINT AS company_id, loanId::BIGINT AS loan_id,
       createTime::TIMESTAMP AS create_time, org AS lender
FROM read_csv('data/finbench-sf0.01/CompanyApplyLoan.csv', delim = '|', header = true);

CREATE OR REPLACE TABLE bank.person_guarantee_person AS
SELECT 'PGP' || row_number() OVER (ORDER BY createTime, fromId, toId) AS edge_id,
       fromId::BIGINT AS guarantor_person_id, toId::BIGINT AS guaranteed_person_id,
       createTime::TIMESTAMP AS create_time, relation
FROM read_csv('data/finbench-sf0.01/PersonGuaranteePerson.csv', delim = '|', header = true);

CREATE OR REPLACE TABLE bank.company_guarantee_company AS
SELECT 'CGC' || row_number() OVER (ORDER BY createTime, fromId, toId) AS edge_id,
       fromId::BIGINT AS guarantor_company_id, toId::BIGINT AS guaranteed_company_id,
       createTime::TIMESTAMP AS create_time, relation
FROM read_csv('data/finbench-sf0.01/CompanyGuaranteeCompany.csv', delim = '|', header = true);

CREATE OR REPLACE TABLE bank.person_invest_company AS
SELECT 'PIC' || row_number() OVER (ORDER BY createTime, investorId, companyId) AS edge_id,
       investorId::BIGINT AS investor_person_id, companyId::BIGINT AS company_id,
       ratio::DOUBLE AS ratio, createTime::TIMESTAMP AS create_time
FROM read_csv('data/finbench-sf0.01/PersonInvestCompany.csv', delim = '|', header = true);

CREATE OR REPLACE TABLE bank.company_invest_company AS
SELECT 'CIC' || row_number() OVER (ORDER BY createTime, investorId, companyId) AS edge_id,
       investorId::BIGINT AS investor_company_id, companyId::BIGINT AS company_id,
       ratio::DOUBLE AS ratio, createTime::TIMESTAMP AS create_time
FROM read_csv('data/finbench-sf0.01/CompanyInvestCompany.csv', delim = '|', header = true);

CREATE OR REPLACE TABLE bank.medium_sign_in_account AS
SELECT 'SI' || row_number() OVER (ORDER BY createTime, mediumId, accountId) AS edge_id,
       mediumId::BIGINT AS medium_id, accountId::BIGINT AS account_id,
       createTime::TIMESTAMP AS create_time, location
FROM read_csv('data/finbench-sf0.01/MediumSignInAccount.csv', delim = '|', header = true);
