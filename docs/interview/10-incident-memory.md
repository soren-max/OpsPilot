# Incident Memory

Status: **Knowledge projection and hybrid retrieval implemented in M6**

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

## What changed in M6?

M6 feeds `IncidentKnowledgeRecord` into a Qdrant adapter behind the retrieval port, adds deterministic
offline Dense/Sparse/Hybrid RRF evaluation, and returns provenance-bearing `RetrievedKnowledge`.
Historical results remain separate from current Incident Evidence.
