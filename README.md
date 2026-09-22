# Claude Skills

A collection of Claude Code commands and skills to enhance your development workflow, packaged as the `joel-workflow` plugin.

## Marketplace Overview

This repository is a Claude Code plugin marketplace containing one plugin, `joel-workflow`: workflow slash commands plus skills that automate common development tasks.

## Available Commands

| Command | Description |
|---------|-------------|
| `/ship` | End-to-end ship workflow: format, commit, verify with evidence (always), push, PR, CI watch, review consolidation |
| `/review-pr` | Moved to Beam's private `beam-claude-skills` plugin — its CI reads that copy as instructions |
| `/verify` | Evidence-based verification of any change — routes UI to /verify-ui; telemetry, APIs and jobs get real invocations and read-backs |
| `/verify-ui` | UI arm of /verify — prove a UI flow in a real browser via agent-browser (localhost or staging) |
| `/pick-up-linear-ticket` | Claim a Linear ticket and set up a branch to start implementation |
| `/brag-doc` | Generate weekly brag doc entries from GitHub activity |
| `/skill-reviewer` | Review a Claude Code skill for structural and domain quality |
| `/newspaper` | Rewrite a draft into the newspaper model: headline, impact, detail-on-request |

## Available Skills

### 📋 [Guideline Refresher](skills/guideline-refresher/)

Auto-refresh coding guidelines based on codebase patterns, PR reviews, and approved code.

**What it does:** Analyzes your git history, merged PRs, and review comments to generate evidence-based coding guidelines that reflect your actual practices—not outdated documentation.

**Perfect for:**
- Keeping guidelines current after migrations or refactorings
- Documenting actual team patterns from approved code
- Generating area-specific rules (frontend, backend, utils, etc.)

**Links:**
- 📖 [Full Documentation](skills/guideline-refresher/README.md)
- 🚀 [Usage Examples](EXAMPLES.md)

### 🚢 [E2E](skills/e2e/)

Full delivery pipeline: Claude/Fable plans with one approval gate, codex/Sol implements each task headlessly with graded reasoning effort, dual review with fix loops, then ship to PR with CI watch.

### 🔍 [Investigate](skills/investigate/)

Findings, not code: claims the Linear ticket, ranks hypotheses before hunting evidence, posts a ≤300-word comment where every claim carries a link or record id and every unreachable source is flagged up top, then hands the ticket to In Review. The `agent:investigate` fleet watch runs it as `/investigate <ticket>`.

### 👀 [Codex Collab](skills/codex-collab/)

Pulls codex/Sol in as a read-only second pair of eyes on whatever workflow is running: cross-model review, corroboration of a conclusion, or a blind second opinion on a design — with graded reasoning effort and honest disagreement reporting.

### 🔁 [Dev Workflow Iterate](skills/dev-workflow-iterate/)

Periodic review of the workflow itself: instruments-first evidence, an adversarial panel that attacks the draft, a blind Sol opinion, and deletion-first output. Light mode (~30 min pulse) or deep mode (quarterly, expensive). Iron laws: prior art before proposals, live-verify tool claims, no new surfaces.

### ✍️ [Writing PR Descriptions](skills/writing-pr-descriptions/)

PR bodies a reviewer absorbs in 30 seconds: What / Why with 3-bullet section caps, one idea per sentence, outcome-not-inventory, stack etiquette. Ships with [VOICE.md](skills/writing-pr-descriptions/VOICE.md) — Joel's mined tone-of-voice guide (guidelines; SKILL.md rules always win). Owns the body format for `/ship` and works standalone to draft or tighten any PR description.

## Installation

### From Marketplace (Recommended)

```bash
# Add marketplace
/plugin marketplace add jjholmes927/jjholmes927-claude-skills

# Install plugin
/plugin install joel-workflow@jjholmes927-claude-skills
```

### Manual Installation

```bash
# Clone and install all skills
git clone https://github.com/jjholmes927/jjholmes927-claude-skills.git
cd jjholmes927-claude-skills
./install.sh
```

## Quick Start

Once installed, skills work automatically:

```
You: "Refresh guidelines for frontend/components"
Claude: [Uses guideline-refresher skill automatically]
```

Or run directly from command line:
```bash
~/.claude/skills/guideline-refresher/refresh.sh --area frontend/components
```

## Contributing

Contributions welcome! To add a new skill:

1. Create a directory under `skills/{skill-name}/`
2. Add `SKILL.md` with skill definition
3. Add implementation files (Python, shell scripts, etc.)
4. Add `README.md` with documentation
5. Update this README with the new skill
6. Update `plugin.json` with the skill metadata

## Workflow evaluations

`evals/` contains ten starter cases: seven stage decisions using snapshots of the
current workflow documents, paired defective/correct code reviews, and a small
implementation checked by independent behavioural assertions. Python 3 and Git
are the only dependencies for preparation and grading.

```bash
python3 -B -m unittest discover -s evals -p 'test_*.py'
python3 -B evals/run.py list
python3 -B evals/run.py run --model gpt-6-astra --case stale-verification
```

`run` invokes authenticated Codex with an explicit model, fresh sessions, a
120-second timeout per case, native read-only/workspace-write permissions and
network-disabled workspace tools. It ignores user config and execution rules;
this is a controlled baseline, not a test of your installed plugins or Kandev
profile. No production workflow commands are executed. Model calls consume the
CLI account's normal usage. Omit `--case` to run the suite; repeat it before
using results to choose a default model. `--source-root` selects another source
checkout with the same workflow paths.

Results go to a new temporary directory by default. Each case preserves its
prompt, source hashes, initial file hashes, response, logs, duration, requested
model and grade. Resolved model identity remains unknown unless independently
confirmed; the requested name alone does not establish it. CLI failures,
timeouts and incomplete responses are separate from failed quality checks.

For another harness, use `prepare --output /absolute/new-directory`, run each
`prompt.txt` in its adjacent `workspace` with appropriate native permissions,
and save the final JSON as the adjacent `response.json`. Then use
`grade --output /absolute/new-directory`. The preparation and grading protocol
does not depend on Codex; automatic launch currently supports Codex only.
Keep graders and expected answers outside the agent's workspace.

Decision cases assess instruction interpretation, not tool enforcement. Code
cases check actual file changes and outcomes. Review explanations still need
human spot-checks. Live watcher deduplication, approval/cancellation transitions,
publication, deployment and cross-harness resume remain integration work. Add
cases from observed failures without teaching their expected answers in prompts.

## License

MIT - See LICENSE file for details

## Contributing

Every change under `skills/` or `commands/` needs a version bump in `plugin.json` and both version fields in `.claude-plugin/marketplace.json`, otherwise installed copies never pick it up. CI enforces this on `master` and a local pre-push hook catches it earlier:

```bash
git config core.hooksPath .githooks
```

`master` only accepts pull requests with the version check green.
