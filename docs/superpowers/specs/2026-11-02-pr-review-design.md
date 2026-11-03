# Automatic Claude PR reviews for tanaylab - design

Date: 2026-11-02. Owner: aviezerl (tanaylab GitHub org admin).

## Why

The lab's Claude Team plan comes with up to $500 a month of API credit, paid into the linked Console org "Weizmann Institute of Science". Unused credit expires each month. The ready-made options are not paid from this credit. Checked 2026-11-02 against https://support.claude.com/en/articles/17154008-api-credits-for-max-and-team-plans and https://platform.claude.com/docs/en/about-claude/api-credits-for-subscribers:

- claude-code-action, even with a key from the linked org: "Runs started by the Claude Code GitHub Action, an IDE extension or the Claude desktop app count as Claude Code usage, so API credits don't cover them, even with `-p`."
- Managed Code Review: not named on either page; the docs table lists "Claude Code | No", and the Code Review docs bill it to usage credits.
- Direct API calls: "The Claude API (Messages API and Message Batches API)" is covered. "Every API key and workspace in the linked organization draws from the same balance." When it runs out, "API requests stop until your next monthly API credits arrive." So we build a small reviewer that calls the Claude API directly from GitHub Actions and posts reviews on tanaylab PRs.

## What it does

- Runs on every PR in a tanaylab repo that has opted in.
- First run on a PR: reviews the whole PR diff.
- Each later push: reviews only what changed since the commit it last reviewed.
- Looks for real problems: bugs, wrong logic, broken edge cases, resource leaks, security issues. No style or formatting comments, no praise, no summary of what the PR does.
- Claude can read and search files in the checked-out repo (read-only), so it can check callers, definitions and tests around the changed lines, not only the diff.

## What a review looks like (decided by the user)

One formal GitHub review with event `COMMENT` (never `APPROVE` or `REQUEST_CHANGES`):

- **Body:** a short bulleted list, one line per finding: `[bug|minor] file:line - problem`.
- **Inline comments:** each finding is also attached to its line in the diff, in this form: **problem** in a sentence or two, then **Suggested fix:** with a concrete change.
- **Tone:** concise, constructive, actionable. Every point says what to change. No hedging filler, no scolding.
- **Nothing found:** a one-line review saying no issues were found in the reviewed range.

## Goals

- Catch real bugs before merge in the repos that opt in.
- Stay within the $500 monthly credit with plenty of headroom.
- Each repo turns it on or off by adding or removing one small workflow file.

## Non-goals

- Style, naming or formatting feedback.
- Approving or blocking merges.
- Reviewing PRs from forks outside tanaylab.
- Replying to follow-up comments or acting on `@claude` mentions.

## Anti-goals (failure even if it technically works)

- Noise: long reviews, vague remarks, or many low-value comments that teach people to ignore it.
- Spending beyond the free credit.
- Exposing the API key, or letting PR content make the reviewer do anything other than post a review.

## Constraints

- Paid only from the linked Console org's credit, through an API key created there. Auto-reload of credit in the Console must stay off so an empty balance stops calls instead of charging.
- tanaylab is on GitHub Team; aviezerl is an org admin.
- Trigger is `pull_request` (not `pull_request_target`). Fork PRs get no secrets on `pull_request`, so they are skipped explicitly.
- Draft PRs are skipped; the review runs when a PR is marked ready.

## Decided by the user

- Review every PR in opted-in repos, automatically.
- On later pushes, review only the new changes.
- Control over which repos have it.
- Review format and tone above, including the "no issues" note.
- The linked Console org is used only by the Tanay lab. Any future lab API keys there would share the same $500.
- Everyone with push access to an opted-in repo is trusted. Accepted risk: such a person could edit the workflow in a same-repo PR and read the key; the worst case is the month's credit being used up (no auto-reload). So plain `pull_request` with an org secret is fine; no GitHub App or proxy.

## Calls made by Claude (not discussed in detail; the user can override)

- **Where it lives:** a new `tanaylab/.github` repo holds the reviewer script and a reusable workflow. Each opted-in repo has a ~10-line caller workflow. Fixes to the reviewer reach all repos at once.
- **Opting a repo in** is two steps: add the caller workflow file, and an org admin adds the repo to the secret's visibility list. Without the second step the workflow runs with no key and should exit with a clear message, not fail noisily.
- **Key handling:** API key stored as a tanaylab org secret whose visibility is limited to the selected repos. The key comes from its own workspace in the linked Console org, so its spend shows up separately. No workspace spend limit below the credit: the reviewer may use the full $500 (decided by the user; as of 2026-11-02 there is no other API usage in the org).
- **Language:** Python with the official `anthropic` SDK.
- **Model:** `claude-opus-5-5` with adaptive thinking.
- **Size limit:** if the diff to review is above a threshold, post a short "too large to review automatically" note instead.
- **Cost estimate:** 234 PRs in Aug-Oct 2026 (about 78 a month; half in misha, tgseq2f and tgskills). In a sample of 100, the median diff was 261 changed lines, the 90th percentile 2,700, the maximum 46,300. Rough guess with file reading included: under $200 a month. Not measured.

## Left to the builder

- How the reviewer finds the last commit it reviewed (for example from its own previous review's `commit_id`), and what it does after a force-push or rebase where that commit is gone (falling back to a full review is fine).
- The tools given to Claude for reading the repo, as long as they are read-only and confined to the checkout.
- Effort level, token limits per review, and the exact size threshold, tuned on a few real PRs.
- Which paths to skip (lock files, generated files, binaries, notebooks outputs).
- Mapping findings to diff lines GitHub accepts; findings on lines outside the diff go into the body only.
- Cancelling an in-progress review when a newer push arrives on the same PR.
- Prompt wording.
