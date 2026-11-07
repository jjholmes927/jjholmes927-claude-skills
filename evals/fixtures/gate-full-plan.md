# Plan: Normalise contact handles (r1)

## Routes and identities
- Execution: direct, claude-opus-5-5 in the Kandev task worktree.
- Review: codex, gpt-6-luna, read-only audit.
- Ship: joel-workflow ship, base master, two stacked PRs.

## Runtime assumptions
- Rails app with Sidekiq workers and one Postgres primary; one writer per profile row.
- The sweep runs as a rake task from one production console and restarts by id range.

## Audit dispositions
- gpt-6-luna, 1 round: REVISE.
- Accepted: sweep in 1,000-row batches.
- Accepted: log and skip rows that fail to parse instead of raising.
- Rejected: move the parser into a gem (out of scope).

## Acceptance criteria
- New and edited profiles store `contact_handle` as a lowercase `@name`.
- After PR 1 deploys, a sweep rewrites the existing production profiles (about 41,000 rows) to the same format.

## Tasks
| # | Task | Files | Tests | Effort |
|---|---|---|---|---|
| 1 | Normalise handles on save | `app/models/profile.rb` | `spec/models/profile_spec.rb` | low |
| 2 | Add the sweep rake task | `lib/tasks/handles.rake` | `spec/tasks/handles_spec.rb` | low |

## Post-deploy actions
- Run `rake handles:normalise` against production profiles once PR 1 is live.

## Dependencies and choices
- PR 2 (sweep) stacks on PR 1; running the sweep before PR 1 is live lets new saves bring old formats back.
- Open, one-way: the sweep overwrites `contact_handle` in place. Option A (recommended): copy old values into `contact_handle_before` first, so the sweep can be reverted. Option B: overwrite with no copy; old values are lost.
- Open, two-way: also read the legacy Twitter field when `contact_handle` is blank. Recommended: yes; removing it later is a one-line change.
