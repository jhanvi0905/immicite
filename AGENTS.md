# AGENTS.md

## Before changing code
- Read the relevant code, tests, and documentation before editing.
- Check `docs/decisions/` when a task touches an established design decision.
- Surface assumptions that could change the behavior or scope. Ask when a wrong assumption would create material rework; otherwise make a small, reversible choice and report it.

## While changing code
- Solve the requested problem with the smallest clear, complete change.
- Prefer existing patterns and helpers. Avoid speculative abstractions, extra features, and unrelated cleanup.
- Keep the code easy for another developer to understand; shorter or cleverer is not automatically better.
- Preserve documented boundaries and accepted decisions. If a task appears to require changing one, explain the tradeoff and propose the decision update.

## Before finishing
- Check the change against the stated acceptance criteria, including relevant failure cases.
- Run the checks appropriate to the files and behavior changed.
- Report what changed, what you verified, and anything that remains uncertain.