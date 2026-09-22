# ReviewIQ — Git/GitHub Workflow

## Branches
- `main`
- `feature/rishi-ai-qa`
- `feature/sri-backend-api`
- `feature/alshifa-frontend`

## Workflow
Pull latest main → create/update feature branch → inspect → implement → test → inspect `git status` and `git diff` → stage → manually commit → push → open PR → team review → merge → delete branch.

## Commit Prefixes
`feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`

Avoid vague messages such as `update`, `changes`, `final`, or `done`.

## Pull Request Checklist
- What changed?
- Why was it needed?
- How was it tested?
- Known limitations?
- Screenshots where relevant.
- Contract compatibility.
- No secrets.
- No unrelated changes.
- V1 scope respected.

## Coding-Agent Rule
Agents inspect first, implement only the requested change, run tests/build, verify, and report. Agents must never automatically create Git commits.
