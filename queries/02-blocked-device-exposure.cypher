// Which accounts and customers received money, directly or one hop later,
// from accounts used on a blocked sign-in device?
// Each transfer must happen after the previous one, so the path is a money trail.

// Graph view: blocked device -> account it signed in to -> two time-ordered transfers
MATCH path = (m:Medium)-[:MEDIUM_SIGNS_IN_ACCOUNT]->(src:Account)
             -[t1:ACCOUNT_TRANSFERS_ACCOUNT]->(a1:Account)-[t2:ACCOUNT_TRANSFERS_ACCOUNT]->(a2:Account)
WHERE m.is_blocked AND t2.create_time > t1.create_time AND a2 <> src
RETURN path
LIMIT 60;

// Table view: how far the exposure spreads
MATCH (m:Medium)-[:MEDIUM_SIGNS_IN_ACCOUNT]->(src:Account)
      -[t1:ACCOUNT_TRANSFERS_ACCOUNT]->(a1:Account)-[t2:ACCOUNT_TRANSFERS_ACCOUNT]->(a2:Account)
WHERE m.is_blocked AND t2.create_time > t1.create_time AND a2 <> src
RETURN count(DISTINCT m) AS blocked_devices,
       count(DISTINCT src) AS device_accounts,
       count(DISTINCT a1) AS first_hop_accounts,
       count(DISTINCT a2) AS second_hop_accounts;

// Customers who own a second-hop account
MATCH (m:Medium)-[:MEDIUM_SIGNS_IN_ACCOUNT]->(src:Account)
      -[t1:ACCOUNT_TRANSFERS_ACCOUNT]->(a1:Account)-[t2:ACCOUNT_TRANSFERS_ACCOUNT]->(a2:Account)
      <-[:PERSON_OWNS_ACCOUNT|COMPANY_OWNS_ACCOUNT]-(owner)
WHERE m.is_blocked AND t2.create_time > t1.create_time AND a2 <> src
RETURN labels(owner)[0] AS owner_type, count(DISTINCT owner) AS owners;
