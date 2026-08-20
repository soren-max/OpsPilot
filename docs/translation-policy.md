# Translation Policy

## English is canonical

English is the canonical language for OpsPilot documentation. All substantive changes should be
made to the English doc first; translations follow the English text, never the other way around.

## What should be translated

The Chinese core docs — the root `README.zh-CN.md` and the core docs under `docs/zh-CN/`
(architecture, safety model, roadmap, development, testing, and the translated design docs) —
should track major architectural changes, new milestones, and changes to user-facing behavior.
They do not need to mirror every minor edit, typo fix, or internal rewording.

## What does not require immediate translation

- ADR records (`docs/adr/`)
- Interview notes (`docs/interview/`)
- Deep design docs (e.g. `docs/design/governed-execution.md`,
  `docs/design/incident-memory-and-rag.md`)
- The learning map (`docs/learning-map.md`)

These are English only. They may be translated later if there is demand, but translation is
never a prerequisite for merging a change to them.

## Goal

Keep the documentation bilingual without forcing every small pull request to synchronize dozens
of translations. Contributors should feel free to update English docs; the Chinese tree is
synced in batches when it materially affects how readers understand or use the project.
