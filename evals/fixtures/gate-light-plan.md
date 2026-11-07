# Plan: Name the delivery fee bands (r1)

## Routes and identities
- Execution: direct, current coordinator.
- Review: codex, gpt-6-luna, read-only.

## Acceptance criteria
- `pricing.py` reads its weight limit and both fees from named module constants.
- Fees for every weight stay exactly as they are today.

## Tasks
| # | Task | Files | Tests | Effort |
|---|---|---|---|---|
| 1 | Move the limit and fees into constants | `pricing.py` | existing `test_pricing.py` | low |
| 2 | Pin the constants with a test | `test_pricing.py` | `test_fee_constants` | low |

## Runtime assumptions
Pure function, no state, no persistence.

## Permitted effects
Commits on the task branch and one PR. Nothing else.

## Audit dispositions
gpt-6-luna, 1 round: READY. 0 accepted, 0 rejected.
