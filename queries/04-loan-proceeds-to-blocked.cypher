// Which loans had their proceeds moved on to a blocked account after the
// loan was paid out?

// Table view
MATCH (l:Loan)-[d:LOAN_DEPOSITS_ACCOUNT]->(a:Account)-[t:ACCOUNT_TRANSFERS_ACCOUNT]->(b:Account)
WHERE b.is_blocked AND t.create_time > d.create_time
RETURN count(DISTINCT l) AS loans,
       count(DISTINCT a) AS payout_accounts,
       count(DISTINCT b) AS blocked_recipients;

// Baseline: loans with a recorded payout
MATCH (l:Loan)-[:LOAN_DEPOSITS_ACCOUNT]->(:Account)
RETURN count(DISTINCT l) AS loans_paid_out;

// Graph view: borrower -> loan -> payout account -> blocked account
MATCH path = (borrower)-[:PERSON_APPLIES_LOAN|COMPANY_APPLIES_LOAN]->(l:Loan)
             -[d:LOAN_DEPOSITS_ACCOUNT]->(a:Account)-[t:ACCOUNT_TRANSFERS_ACCOUNT]->(b:Account)
WHERE b.is_blocked AND t.create_time > d.create_time
RETURN path
LIMIT 50;
