import pytest

from reviewer import review
from reviewer.review import MARKER, build_review, last_reviewed_sha

BOT = {"login": "github-actions[bot]"}


def test_last_reviewed_sha_picks_latest_marked():
    reviews = [
        {"user": BOT, "body": f"{MARKER}\nold", "commit_id": "a1"},
        {"user": {"login": "alice"}, "body": f"{MARKER}\nfake", "commit_id": "x"},
        {"user": BOT, "body": f"{MARKER}\nnew", "commit_id": "b2"},
        {"user": BOT, "body": "some other bot review", "commit_id": "c3"},
    ]
    assert last_reviewed_sha(reviews) == "b2"


def test_last_reviewed_sha_none():
    assert last_reviewed_sha([]) is None
    assert last_reviewed_sha([{"user": {"login": "bob"}, "body": "lgtm", "commit_id": "a"}]) is None


FINDINGS = [
    {"severity": "minor", "path": "b.R", "line": 3, "problem": "NA not handled.", "fix": "Use `na.rm = TRUE`."},
    {"severity": "bug", "path": "a.R", "line": 12, "problem": "Off by one.", "fix": "Use `<=`."},
]


def test_build_review_bullets_and_inline():
    r = build_review(FINDINGS, {"a.R": {12}, "b.R": {3}}, "this PR")
    assert r["event"] == "COMMENT"
    lines = r["body"].splitlines()
    assert lines[0] == MARKER
    assert lines[1] == "- [bug] a.R:12 - Off by one."
    assert lines[2] == "- [minor] b.R:3 - NA not handled."
    assert [c["path"] for c in r["comments"]] == ["a.R", "b.R"]
    c = r["comments"][0]
    assert c["side"] == "RIGHT" and c["line"] == 12
    assert c["body"] == "**Bug:** Off by one.\n\n**Suggested fix:** Use `<=`."
    assert r["comments"][1]["body"].startswith("**Minor:** ")


def test_offdiff_finding_goes_to_body_only():
    r = build_review([dict(FINDINGS[1], line=999)], {"a.R": {12}}, "this PR")
    assert "- [bug] a.R:999 - Off by one." in r["body"]
    assert "Use `<=`." in r["body"]
    assert r["comments"] == []


def test_build_review_no_findings():
    r = build_review([], {}, "this PR")
    assert r["body"] == f"{MARKER}\nNo issues found in this PR."
    assert r["comments"] == []


@pytest.fixture
def env(monkeypatch):
    for k, v in {"GITHUB_REPOSITORY": "tanaylab/x", "PR_NUMBER": "5", "BASE_SHA": "b" * 40,
                 "HEAD_SHA": "h" * 40, "ANTHROPIC_API_KEY": "k", "REPO_DIR": "/tmp"}.items():
        monkeypatch.setenv(k, v)
    posted = []
    monkeypatch.setattr(review, "gh_reviews", lambda repo, n: [])
    monkeypatch.setattr(review, "post_review", lambda repo, n, payload: posted.append(payload))
    monkeypatch.setattr(review, "review_range", lambda *a: ("b...h", "this PR"))
    monkeypatch.setattr(review, "run_claude", lambda *a: pytest.fail("run_claude called"))
    return posted


def test_empty_after_skip_posts_no_issues(env, monkeypatch):
    lock = "diff --git a/renv.lock b/renv.lock\n--- a/renv.lock\n+++ b/renv.lock\n@@ -1 +1 @@\n-a\n+b\n"
    monkeypatch.setattr(review, "git_diff", lambda repo, args: lock)
    assert review.main() == 0
    assert env[0]["body"].endswith("No issues found in this PR.")
    assert env[0]["commit_id"] == "h" * 40


def _file(path, n):
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -0,0 +1,{n} @@\n" + "+x\n" * n


def test_nothing_fits_posts_note(env, monkeypatch):
    monkeypatch.setattr(review, "git_diff", lambda repo, args: _file("a.R", review.MAX_CHANGED + 1))
    assert review.main() == 0
    assert env[0]["body"].endswith("Not reviewed, too large to fit in one review: a.R")


def test_large_diff_reviews_what_fits(env, monkeypatch):
    small, big = _file("a.R", 3), _file("b.yaml", review.MAX_CHANGED)
    monkeypatch.setattr(review, "git_diff", lambda repo, args: small + big)
    seen = []
    monkeypatch.setattr(review, "run_claude", lambda diff, *a: seen.append(diff) or [])
    assert review.main() == 0
    assert seen == [small]
    assert env[0]["body"] == f"{MARKER}\nNo issues found in this PR.\n\nNot reviewed, too large to fit in one review: b.yaml"


def test_build_review_lists_left_out():
    r = build_review([FINDINGS[1]], {"a.R": {12}}, "this PR", [f"f{i}.yaml" for i in range(25)])
    last = r["body"].splitlines()[-1]
    assert last.startswith("Not reviewed, too large to fit in one review: f0.yaml, f1.yaml")
    assert last.endswith("f19.yaml and 5 more")


def test_already_reviewed_head_posts_nothing(env, monkeypatch):
    monkeypatch.setattr(review, "gh_reviews", lambda repo, n: [
        {"user": BOT, "body": f"{MARKER}\nx", "commit_id": "h" * 40}])
    assert review.main() == 0
    assert env == []


def test_missing_key_exits_zero(env, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.setattr(review, "gh_reviews", lambda *a: pytest.fail("called GitHub"))
    assert review.main() == 0
    assert env == []


def test_api_error_exits_zero(env, monkeypatch, capsys):
    import anthropic
    import httpx2 as httpx

    diff = "diff --git a/a.R b/a.R\n--- a/a.R\n+++ b/a.R\n@@ -1 +1 @@\n-a\n+b\n"
    monkeypatch.setattr(review, "git_diff", lambda repo, args: diff)

    def boom(*a):
        raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))

    monkeypatch.setattr(review, "run_claude", boom)
    assert review.main() == 0
    assert env == []
    assert "::warning::Claude review skipped" in capsys.readouterr().out


def test_rejected_inline_comment_reposts_in_body(monkeypatch):
    import subprocess

    calls = []

    def fake(repo, n, payload):
        calls.append(payload)
        if payload["comments"]:
            raise subprocess.CalledProcessError(1, "gh", stderr="HTTP 422")

    monkeypatch.setattr(review, "post_review", fake)
    payload = build_review([FINDINGS[1]], {"a.R": {12}}, "this PR")
    review._post("tanaylab/x", "5", payload)
    assert len(calls) == 2 and calls[1]["comments"] == []
    assert "**Suggested fix:** Use `<=`." in calls[1]["body"]


def _msg(stop_reason, text):
    from types import SimpleNamespace
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)])


def test_parse_findings_only_on_end_turn():
    from reviewer.review import parse_findings
    ok = '{"findings": []}'
    assert parse_findings(_msg("end_turn", ok)) == []
    assert parse_findings(_msg("max_tokens", '{"findings": [')) is None
    assert parse_findings(_msg("tool_use", "let me look")) is None
    assert parse_findings(_msg("end_turn", "not json")) is None
    assert parse_findings(_msg("refusal", "")) is None
    assert parse_findings(None) is None


def test_unfinished_reply_posts_nothing(env, monkeypatch):
    diff = "diff --git a/a.R b/a.R\n--- a/a.R\n+++ b/a.R\n@@ -1 +1 @@\n-a\n+b\n"
    monkeypatch.setattr(review, "git_diff", lambda repo, args: diff)
    monkeypatch.setattr(review, "run_claude", lambda *a: None)
    assert review.main() == 0
    assert env == []


def test_unexpected_error_exits_zero(env, monkeypatch, capsys):
    diff = "diff --git a/a.R b/a.R\n--- a/a.R\n+++ b/a.R\n@@ -1 +1 @@\n-a\n+b\n"
    monkeypatch.setattr(review, "git_diff", lambda repo, args: diff)

    def boom(*a):
        raise KeyError("findings")

    monkeypatch.setattr(review, "run_claude", boom)
    assert review.main() == 0
    assert env == []
    assert "::warning::Claude review skipped" in capsys.readouterr().out
