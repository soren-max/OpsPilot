# Incident Memory

Status: **Knowledge projection implemented in M1C; retrieval planned for M6**

## Why does ActionRequest not contain incident_id?

The Action domain is reusable for maintenance and operator-triggered work that has no incident.
An application-layer `IncidentActionLink` relates a generic task and its fingerprint to an
Incident. Workers and executors remain unaware of Incident ORM while the timeline retains full
traceability.

## Why can only resolved incidents enter memory?

Active investigations contain competing hypotheses and incomplete observations. Indexing them as
trusted history would amplify provisional claims. A resolved or closed incident with a diagnosis
can produce a deterministic record; open incidents are rejected.

## Why is RAG not “put every log in a vector database”?

Volume is not knowledge. Raw logs contain duplicates, secrets, transient noise, and weak
provenance. Useful retrieval needs curated sources, access control, filters, time and service
context, source references, evaluation, and explicit evidence semantics. M1C creates that stable
projection without prematurely binding the domain to a vector product.

## What changes in M6?

M6 can feed `IncidentKnowledgeRecord` into an adapter behind `KnowledgeRetriever`, add indexing
and retrieval evaluation, and return provenance-bearing Retrieved Evidence. Incident and Action
schemas do not need to change.
