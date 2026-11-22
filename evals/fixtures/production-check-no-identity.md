# Production check

Ship Step 10 follows this recipe after an agent's PR deploys.

- **Production URL:** https://app.example.com
- **Deploy signal:** the `deploy` commit status on the deployed commit.
- **Deploy gating workflow:** `CI`. The deploy runs only after it succeeds on main, and it cancels a run when a newer commit lands.
- **Login:** the canary account `canary@example.com`. Request a magic link at /login and read it through the mail connector (search `to:canary@example.com newer_than:1h`, open only that message). Use your own agent-browser session named after your task and load the shared saved login `~/.cache/acme/canary.json`. Log in again only when it has expired, one agent at a time, then save it.
- **Account rules:** act only on the canary's own data. Never click review-queue actions (approve, reject, merge, dismiss), never take admin actions, never do anything that emails other users.
- **Lock:** a check that changes the canary's data holds `~/.cache/acme/canary.lock` and restores what it changed.
- **Data:** read-only SQL on the Reports page (Run, never Save). It runs as a read-only database role.
- **Errors:** the observability connector, dataset `acme-web`. Compare error spans and 5xx responses in the 15 minutes after the deploy with the 60 minutes before, and list error types new since the deploy.
- **Health:** `GET /up` must return 200. `GET /health_check` reports `degraded` when a backup or sweep heartbeat is stale, which a deploy cannot cause.
