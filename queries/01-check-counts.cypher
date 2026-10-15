// Check that the graph loaded: compare with the counts in the README.

// Nodes by label
MATCH (n)
RETURN labels(n)[0] AS label, count(*) AS nodes
ORDER BY label;

// Relationships by type
MATCH ()-[r]->()
RETURN type(r) AS relationship, count(*) AS edges
ORDER BY relationship;

// Blocked flags: 117 accounts and 54 sign-in media are blocked
MATCH (a:Account) WHERE a.is_blocked RETURN count(a) AS blocked_accounts;
MATCH (m:Medium) WHERE m.is_blocked RETURN count(m) AS blocked_media;
