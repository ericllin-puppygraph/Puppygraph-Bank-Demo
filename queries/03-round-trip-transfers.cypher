// Where does money leave an account and come back to it through two other
// accounts, with each transfer later than the one before (round-tripping)?

// Graph view
MATCH path = (a:Account)-[t1:ACCOUNT_TRANSFERS_ACCOUNT]->(b:Account)-[t2:ACCOUNT_TRANSFERS_ACCOUNT]->(c:Account)-[t3:ACCOUNT_TRANSFERS_ACCOUNT]->(a)
WHERE a <> b AND b <> c AND a <> c
  AND t1.create_time < t2.create_time AND t2.create_time < t3.create_time
RETURN path;

// Table view: one row per loop, starting account first
MATCH (a:Account)-[t1:ACCOUNT_TRANSFERS_ACCOUNT]->(b:Account)-[t2:ACCOUNT_TRANSFERS_ACCOUNT]->(c:Account)-[t3:ACCOUNT_TRANSFERS_ACCOUNT]->(a)
WHERE a <> b AND b <> c AND a <> c
  AND t1.create_time < t2.create_time AND t2.create_time < t3.create_time
RETURN a.account_id AS start_account, b.account_id AS via_1, c.account_id AS via_2,
       t1.amount AS amount_out, t3.amount AS amount_back,
       t1.create_time AS left_at, t3.create_time AS returned_at,
       a.is_blocked OR b.is_blocked OR c.is_blocked AS touches_blocked_account
ORDER BY left_at;
