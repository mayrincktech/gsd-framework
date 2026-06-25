# Task Format — Hermes GSD Framework

Each task is a markdown file in `.planning/features/{feature-id}/tasks/{NN}-slug.md`.

## Required Metadata (frontmatter)

```yaml
---
id: "01-01"                    # FeatureID-TaskID
title: "Create tasks table"    # Short title
status: pending                # pending | in_progress | completed | failed
assignee: code-ai              # code-ai | qa-ai | orchestrator
model: deepseek-v4-flash       # Model for delegation
provider: custom:opencode-go   # Provider for delegation
dependencies: []               # List of task IDs that must complete first
files:                         # Max 5 files
  - src/db/schema.ts
  - src/db/migrations/001.sql
estimated_lines: 80            # Max 500
phase: EXECUTE                 # Which pipeline phase owns this task
created_at: 2026-06-24T12:00:00Z
---
```

## Body Structure

### Description
What to build. Be specific — reference architecture decisions, design system tokens, and wireframes.

### Acceptance Criteria
- [ ] Checklist item 1
- [ ] Checklist item 2
- [ ] Max 5 files touched
- [ ] Max 500 lines changed

### Gate Requirements
- UX Review: min 42/60 (if UI task)
- Files touched: ≤ 5
- Lines changed: ≤ 500
- Dependencies satisfied

### Context
- Architecture: `.planning/ARCHITECTURE.md`
- Design System: `.planning/DESIGN-SYSTEM.md`
- Wireframe: `.planning/features/{feature-id}/WIREFRAMES.md#task-NN`

## Rules
- One responsibility per task
- Max 5 files, max 500 lines
- If task needs more → split into multiple tasks
- Status updates must sync to the Kanban board
