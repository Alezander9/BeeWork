# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BeeWork is an autonomous multi-agent system for building and maintaining knowledge bases. Built for TreeHacks 2026. Specialized agents research topics via web browsing, write content with citations, review PRs for quality, and answer questions over the knowledge base.

## Tech Stack

- **Python 3.12** with **UV** package manager
- **Modal** for serverless sandbox execution (each agent runs in an isolated container)
- **OpenCode** as the AI coding agent framework (provides bash/edit/write tools inside sandboxes)
- **Google Gemini 3 Flash Preview** as the primary LLM (configured in each agent's `opencode.json`)
- **Laminar** (`lmnr`) for observability/tracing of LLM calls
- **Browser-Use API** for automated web research
- **Parallel.ai** for web search

## Commands

```bash
# Install dependencies
uv sync

# Run the orchestrator (creates KB repo, generates research tasks)
uv run python orchestrator/run_orchestrator_agent.py <repo_name>

# Run a researcher agent (browser research + KB editing)
uv run python researcher/run_research_agent.py --topic "..." --prompt "..." --file-path "..." --websites "..." --repo "owner/repo"

# Run the reviewer agent (PR quality gate)
uv run python reviewer/run_sandbox_agent.py --repo "owner/repo" --pr <pr_number>

# Run the chat agent (Q&A over knowledge base)
uv run python chat/run_chat_agent.py --repo "owner/repo" --question "..."
```

## Architecture

### Agent Pipeline Flow

```
Orchestrator → [Research Tasks] → Researcher(s) (parallel) → PRs → Reviewer → Merged KB
                                                                                    ↓
                                                                              Chat Agent (Q&A)
```

### Four Specialized Agents

Each agent lives in its own directory with three key files:
- `run_*.py` — Python entry point that creates a Modal sandbox and runs the agent
- `AGENTS.MD` — Natural language instructions the OpenCode agent follows
- `opencode.json` — Model selection, tool permissions, and agent configuration

| Agent | Directory | Modal App Name | Entry Point | Sandbox Timeout |
|-------|-----------|----------------|-------------|-----------------|
| Orchestrator | `orchestrator/` | `test-opencode` | `run_orchestrator_agent.py` | 10 min |
| Researcher | `researcher/` | `beework-worker` | `run_research_agent.py` | 15 min |
| Reviewer | `reviewer/` | `beework-reviewer` | `run_sandbox_agent.py` | 5 min |
| Chat | `chat/` | `chat-gbt` | `run_chat_agent.py` | 5 min |

### Execution Pattern (all agents follow this)

1. Load env vars from `.env` at project root
2. Build a Modal container image (Debian + OpenCode + gh CLI + agent code)
3. Create Modal sandbox with secrets injected
4. Clone the knowledge base GitHub repo inside the sandbox
5. Run `opencode run` with a task-specific prompt (PTY required — OpenCode hangs without it)
6. Observe/trace output via `shared/tracing.py`
7. Terminate sandbox

### Shared Module (`shared/`)

- `tracing.py` — Parses OpenCode's `--format json` JSONL output and creates Laminar spans for LLM steps, tool calls, and errors. Uses best-effort tracing (failures don't crash agents).

### Key Technical Details

- **PTY required**: All `opencode run` calls use `pty=True` — OpenCode hangs on Modal without a pseudo-terminal
- **OpenCode JSON output**: Researcher, reviewer, and chat agents use `--format json` for structured tracing; orchestrator uses plain text output
- **Git auth in sandboxes**: GitHub PAT is embedded in remote URLs for push access
- **Browser results transfer**: Researcher base64-encodes browser JSON to safely pass it into the sandbox
- **Research tasks**: Orchestrator writes JSON files to `research_tasks/` which are collected and returned for parallel researcher execution

## Environment Variables

All stored in `.env` at project root (see `.env.example`):

| Variable | Used By |
|----------|---------|
| `GEMINI_API_KEY` | All agents (primary LLM) |
| `GITHUB_PAT` | All agents (repo access, also set as `GH_TOKEN`) |
| `LMNR_PROJECT_API_KEY` | Researcher, reviewer, chat (Laminar tracing) |
| `ANTHROPIC_API_KEY` | Orchestrator (optional, for Claude models) |
| `PARALLEL_API_KEY` | Orchestrator (web search) |
| `BROWSER_USE_API_KEY` | Researcher (browser automation) |
