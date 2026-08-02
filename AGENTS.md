# Repository instructions

## Shell execution

- Use PowerShell Core 7.x (`pwsh`) for all shell work on the local Windows host.
- Bash and `sh` are allowed on remote Linux hosts when connecting to a remote server or performing a production release. Invoke remote commands through `ssh` or related tools from `pwsh`.
- This exception does not permit invoking Bash or `sh` locally on Windows.
- Remote commands must remain within the requested task. Production deployments must still follow the runbook and safeguards below.

For every deployment to `ai.pricememo.cn` or `pricememo-prod`:

1. Read and follow `docs/QUICK_DEPLOY.md` as the required deployment runbook.
2. Do not deploy from an untagged commit, a dirty worktree, or a failed CI run.
3. If a required step cannot be completed, stop before switching containers and report the blocker instead of improvising a different production procedure.
