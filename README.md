# tanaylab/.github

Org-wide GitHub workflows for tanaylab.

## Claude PR review

Claude reviews every non-draft PR in an opted-in repo and posts one short review: a bulleted list of real problems (bugs, broken edge cases, leaks, security), each also attached to its line with a suggested fix. After new pushes it reviews only the new commits. It never approves or blocks a PR, and skips PRs from forks.

It calls the Claude API with a key from the lab's Console org, so it is paid from the Team plan's monthly API credit. Design: [docs/superpowers/specs/2026-11-02-pr-review-design.md](docs/superpowers/specs/2026-11-02-pr-review-design.md).

### Turn it on for a repo

1. Copy [.github/workflows/review.yml](.github/workflows/review.yml) to `.github/workflows/claude-review.yml` in the repo.
2. An org admin gives the repo access to the key: Organization settings > Secrets and variables > Actions > `ANTHROPIC_API_KEY` > add the repo, or
   ```
   gh secret set ANTHROPIC_API_KEY --org tanaylab --visibility selected --repos "repo1,repo2,..."
   ```
   (this replaces the whole list, so include every repo that should keep access).

Without step 2 the workflow runs and exits with a notice, without reviewing.

### Turn it off

Delete the workflow file from the repo, and remove the repo from the secret's list.

### Cost

Each run prints its token usage in the job log. Spend shows on the `pr-review` workspace in the Claude Console.

### Development

```
uv venv -p 3.12 .venv && uv pip install -p .venv -r reviewer/requirements.txt
.venv/bin/pytest reviewer/tests -q
```
