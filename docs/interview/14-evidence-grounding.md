# Evidence Grounding

## What makes evidence grounded?

Every normalized observation records its source, opaque source reference, observed time,
collection time, collector, bounded content, metadata, and deduplication fingerprint. The M3B LLM
diagnosis returns evidence IDs, which trace through Incident Evidence to the source system and are
validated against the current incident context.

## Why not put raw logs into Graph State?

Raw logs are large, sensitive, and unstable. Checkpointing them duplicates the observability
system, increases prompt/context cost, and makes replay nondeterministic. Graph State contains only
evidence IDs; the Incident database holds bounded business records; source systems retain raw data.

## How is context explosion prevented?

Typed query limits reduce source volume before retrieval. Adapters enforce byte/series/entry
limits. Normalizers select values and excerpts. The investigator consumes the bounded Incident
Evidence projection rather than raw responses.

## How does replay avoid duplicate evidence?

The workflow start time anchors its collection window. Opaque query references and normalized
timestamps stay stable across node retry, allowing the existing M1C Incident fingerprint to return
the original Evidence record.
