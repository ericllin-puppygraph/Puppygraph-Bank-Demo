// How far do guarantee chains spread credit exposure? For each person who
// guarantees someone, follow the chain up to five guarantees deep and add up
// the loans of everyone they end up backing.

MATCH chain = (g:Person)-[:PERSON_GUARANTEES_PERSON*1..5]->(x:Person)
MATCH (x)-[:PERSON_APPLIES_LOAN]->(l:Loan)
WITH g, count(DISTINCT x) AS people_backed, count(DISTINCT l) AS loans_backed,
     sum(l.loan_amount) AS loan_amount_backed, max(length(chain)) AS deepest_chain
RETURN g.person_name AS guarantor, people_backed, loans_backed,
       loan_amount_backed, deepest_chain
ORDER BY loan_amount_backed DESC
LIMIT 10;

// Graph view: the longest person guarantee chains
MATCH chain = (g:Person)-[:PERSON_GUARANTEES_PERSON*5]->(x:Person)
RETURN chain
LIMIT 20;

// The same for companies
MATCH chain = (g:Company)-[:COMPANY_GUARANTEES_COMPANY*1..5]->(x:Company)
MATCH (x)-[:COMPANY_APPLIES_LOAN]->(l:Loan)
WITH g, count(DISTINCT x) AS companies_backed, count(DISTINCT l) AS loans_backed,
     sum(l.loan_amount) AS loan_amount_backed, max(length(chain)) AS deepest_chain
RETURN g.company_name AS guarantor, companies_backed, loans_backed,
       loan_amount_backed, deepest_chain
ORDER BY loan_amount_backed DESC
LIMIT 10;
