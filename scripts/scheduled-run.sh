#!/bin/sh
# One scheduled Feed Unfucker run with your coding agent, non-interactively.
#
#   scripts/scheduled-run.sh claude     # Claude Code
#   scripts/scheduled-run.sh codex      # Codex
#   FU_AGENT_CMD='my-agent run --prompt' scripts/scheduled-run.sh custom
#
# Output goes to state/logs/, which git ignores. Claude Code's JSON output
# includes token use and cost for the run.
set -eu
cd "$(dirname "$0")/.."
agent="${1:-${FU_AGENT:-claude}}"
mkdir -p state/logs
log="state/logs/$(date +%Y-%m-%d-%H%M)-$agent.log"
prompt="Follow prompts/run.md exactly. This is a scheduled run and nobody is watching, so don't ask questions."

# Lets the Playwright extension connect to Chrome without an approval click.
token=$(sed -n 's/^PLAYWRIGHT_MCP_EXTENSION_TOKEN=//p' state/config.env 2>/dev/null | tail -n 1)
if [ -n "$token" ]; then
  export PLAYWRIGHT_MCP_EXTENSION_TOKEN="$token"
fi

case "$agent" in
  claude)
    claude -p "$prompt" --output-format json \
      --allowedTools "Bash(./fu:*),Bash(rm state/inbox/*),Read,Write,Edit,mcp__playwright,mcp__claude_ai_Gmail,mcp__Gmail,mcp__claude_ai_Google_Drive,mcp__Google_Drive" \
      >"$log" 2>&1
    ;;
  codex)
    # Network is needed to download photos and send email.
    codex exec --full-auto -c sandbox_workspace_write.network_access=true "$prompt" >"$log" 2>&1
    ;;
  custom)
    : "${FU_AGENT_CMD:?set FU_AGENT_CMD to your agent's non-interactive command}"
    $FU_AGENT_CMD "$prompt" >"$log" 2>&1
    ;;
  *)
    echo "usage: $0 claude|codex|custom" >&2
    exit 64
    ;;
esac
echo "Run finished. Log: $log"
