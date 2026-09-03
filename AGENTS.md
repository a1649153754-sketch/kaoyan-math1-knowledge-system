# AGENTS.md

## Scope

This file applies to the entire repository. More specific `AGENTS.md` files, if added later, override it only within their own subtrees.

## Project purpose

Maintain a versioned, machine-checkable knowledge system for China’s Graduate Entrance Examination Mathematics I. The repository is not a loose notebook: stable IDs, source/generated boundaries, public/private data boundaries, tests, and deterministic builds are part of the product.

## Read before editing

1. `README.md`
2. `ROADMAP.md`
3. `CONTRIBUTING.md`
4. `docs/14-project-maintenance.md`
5. `docs/CODEX_HANDOFF.md`

## Non-negotiable contracts

- Preserve released formal-node IDs and the separate `F / Q / B / J` resource namespaces. Do not silently renumber published identities.
- Formal nodes, third-level checklist items, and resource IDs are different namespaces; do not treat them as interchangeable references.
- Personal scores, timing, error text, mastery state, and review dates belong only in the ignored `data/local/` layer. They must not enter Git, Pages, Releases, or pull requests.
- The exam-evidence layer may publish copyright-safe metadata and short route labels, not full question text, answers, scans, or unauthorized solution passages.
- Generated indexes, sprint material, and bundles must be regenerated from their sources. Do not hand-edit generated output when a generator exists.
- New mathematical content must state trigger conditions, conclusion, failure boundary, and a way to verify it. Prefer a minimal counterexample when correcting an overbroad claim.

## Required checks

Run these from the repository root before considering a change complete:

```bash
python -m unittest discover -s tests -p "test_*.py"
python scripts/validate_project.py
python scripts/build_released_identities.py --check
python scripts/build_exam_evidence_indexes.py --check
python scripts/build_sprint_manual.py --check
python scripts/check_bundle_deterministic.py
zensical build --clean
git diff --check
```

If a command is intentionally inapplicable to a narrow documentation-only change, explain why rather than silently skipping it.

## Editing workflow

1. Inspect `git status --short --branch` and current `VERSION`.
2. Work on a dedicated branch; keep one milestone per branch.
3. Edit canonical sources first, then run generators.
4. Add or update tests when changing schemas, ID rules, privacy boundaries, or generated outputs.
5. Review the final diff for leaked local data, broken links, ID drift, and unnecessary generated churn.
6. Update `CHANGELOG.md`, `ROADMAP.md`, or `VERSION` only when the task genuinely changes release state.

## Current direction

The next major milestone is v2.0: introduce a machine-readable knowledge graph without losing any released ID mapping. Start with a read-only architecture audit and a minimal schema; do not migrate the corpus in one unreviewable change.

## Definition of done

A change is complete only when the repository contracts still pass, generated artifacts are deterministic, public/private boundaries remain intact, and the final report lists modified files, checks run, known limitations, and the next recommended step.
