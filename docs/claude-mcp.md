# Local MCP setup (Jira) — not committed

Project commands such as `/hello` can call Jira MCP. **Credentials stay on your machine**; the repo only ships templates and this guide.

## Two different “login” problems

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Not logged in · Please run /login` in **Claude Code terminal** | Claude Code CLI is not authenticated to Anthropic | Run `claude login` (or `/login`) in the terminal |
| Jira MCP **401 Unauthorized** | MCP server missing or wrong Jira credentials | Follow setup below |

These are independent: you need both Claude login **and** Jira MCP configured.

## What gets committed vs gitignored

| File | Committed? | Purpose |
|------|------------|---------|
| `.mcp.json.example` | Yes | Template for **Claude Code CLI** |
| `.cursor/mcp.json.example` | Yes | Template for **Cursor IDE** |
| `.env.mcp.local.example` | Yes | Template for secrets (env vars) |
| `docs/claude-mcp.md` | Yes | This guide |
| `.mcp.json` | **No** (gitignored) | Your local Claude Code MCP config |
| `.cursor/mcp.json` | **No** (gitignored) | Your local Cursor MCP config |
| `.env.mcp.local` | **No** (gitignored) | Your Jira email + API token |

## One-time setup

### 1. Create an Atlassian Cloud API token

1. Open https://id.atlassian.com/manage-profile/security/api-tokens
2. Create a token
3. Use your Red Hat email as `JIRA_EMAIL`

### 2. Create the local secrets file

```bash
cp .env.mcp.local.example .env.mcp.local
# Edit .env.mcp.local — set JIRA_EMAIL and JIRA_API_TOKEN
```

### 3. Claude Code CLI (terminal `/hello`, `claude` in repo root)

```bash
cp .mcp.json.example .mcp.json
# .mcp.json reads JIRA_EMAIL and JIRA_API_TOKEN from your shell env.
# Either export them in ~/.zshrc or: source .env.mcp.local before starting Claude Code

export $(grep -v '^#' .env.mcp.local | xargs)   # optional: load into current shell
claude login                                     # Anthropic auth — required once
claude                                           # start session in repo root
```

Claude Code reads **`.mcp.json` at the repo root** (not under `.claude/`).

On first run it may prompt to approve project-scoped MCP servers from `.mcp.json`.

### 4. Cursor IDE (Agent chat in this repo)

```bash
cp .cursor/mcp.json.example .cursor/mcp.json
cp .env.mcp.local.example .env.mcp.local   # if not done already
```

Reload Cursor (or restart). Cursor loads `.cursor/mcp.json` and can pull extra vars from `.env.mcp.local` via `envFile`.

Check **Settings → MCP** — `jira-mcp` should appear under project-managed servers.

## Jira URL and auth (notebooks team)

This repo uses **Atlassian Cloud**:

- **Site**: `https://redhat.atlassian.net` (see `.cursor/rules/jira-conventions.mdc`)
- **Auth**: `JIRA_EMAIL` + `JIRA_API_TOKEN` (not `issues.redhat.com` / `JIRA_PERSONAL_TOKEN`)

If MCP was copied from a legacy `issues.redhat.com` global config, update the URL and switch to API token auth.

## Verify

In Claude Code or Cursor Agent, run `/hello`. Expected:

```
Hello <your Jira display name>!
```

If Jira fails but Claude is logged in, you still get `Hello there!` with an error note (see `.claude/commands/hello.md`).

## Troubleshooting

- **`uvx` not found**: install `uv` (`brew install uv` on macOS)
- **MCP not listed**: config must be at repo root (`.mcp.json`) or `.cursor/mcp.json`, not `~/.claude/mcp.json`
- **401 on Jira**: check token, email, and `JIRA_URL=https://redhat.atlassian.net`
- **Global vs project config**: `~/.cursor/mcp.json` is user-wide; project `.cursor/mcp.json` applies only in this repo

## Related

- `/hello` command: `.claude/commands/hello.md`
- Jira field conventions: `.cursor/rules/jira-conventions.mdc`
- CVE scripts auth (keychain): `scripts/cve/jira_auth.spec.md`
