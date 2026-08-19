# Structured Output

Status: **Implemented**

## Concept

Structured output converts model intent into schema-validated data rather than executable text.

## Where in OpsPilot

`backend/app/domain/actions/models.py` defines strict action-specific Pydantic models.

## Why

Policy and adapters need typed, bounded inputs that reject unknown fields.

## Trade-offs

Every new capability requires a new schema and migration plan.

## Failure Modes

Action/parameter mismatch, unsafe identifiers, schema drift, and overly broad parameter unions.

## Interview Questions

- Why is JSON alone insufficient without schema validation?
- How does a discriminated action model prevent command injection?
