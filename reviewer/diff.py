"""Unified diff helpers and choosing which commits to review."""

import os
import re
import subprocess
from fnmatch import fnmatch

# Matched against both the full path and the file name.
SKIP_PATTERNS = [
    "*.lock", "package-lock.json", "renv.lock", "Manifest.toml", "*.min.js",
    "*.svg", "*.png", "*.jpg", "*.pdf", "*.ipynb", "*.rds", "*.RData",
    "*.parquet", "*.h5ad", "*/vendor/*", "vendor/*", "man/*.Rd", "NAMESPACE",
    "docs/reference/*",
]

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def _sections(text: str) -> list[str]:
    return [s for s in re.split(r"(?m)^(?=diff --git )", text) if s.startswith("diff --git ")]


def _new_path(section: str) -> str | None:
    """New-side path, or None for a deleted file. Binary/mode-only sections fall back to the header."""
    m = re.search(r"(?m)^\+\+\+ (.+)$", section)
    if m:
        p = m.group(1)
        return None if p == "/dev/null" else p.removeprefix("b/")
    m = re.match(r"diff --git a/.* b/(.+)$", section.splitlines()[0])
    return m.group(1) if m else None


def _skipped(path: str) -> bool:
    return any(fnmatch(path, p) or fnmatch(os.path.basename(path), p) for p in SKIP_PATTERNS)


def parse_diff(text: str) -> dict[str, set[int]]:
    """New-side path -> new-side line numbers that appear in hunks (added and context)."""
    out: dict[str, set[int]] = {}
    for sec in _sections(text):
        if "\nBinary files " in sec or "\nGIT binary patch" in sec:
            continue
        path = _new_path(sec)
        if path is None:
            continue
        lines = out.setdefault(path, set())
        n = None
        for line in sec.splitlines():
            m = HUNK.match(line)
            if m:
                n = int(m.group(1))
            elif n is not None and line[:1] in (" ", "+"):
                lines.add(n)
                n += 1
    return out


def filter_diff(text: str) -> str:
    """The diff with sections for SKIP_PATTERNS files removed."""
    keep = []
    for sec in _sections(text):
        path = _new_path(sec) or re.match(r"diff --git a/(\S+)", sec).group(1)
        if not _skipped(path):
            keep.append(sec)
    return "".join(keep)


def changed_lines(text: str) -> int:
    return sum(
        1 for line in text.splitlines()
        if line[:1] in ("+", "-") and not line.startswith(("+++ ", "--- "))
    )


def _git(repo: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)


def git_diff(repo: str, args: str) -> str:
    r = _git(repo, "diff", "--no-color", args)
    r.check_returncode()
    return r.stdout


def merge_base(repo: str, ref: str, head_sha: str) -> str | None:
    r = _git(repo, "merge-base", ref, head_sha)
    return r.stdout.strip() if r.returncode == 0 else None


def review_range(repo: str, base_sha: str, head_sha: str, last_reviewed: str | None) -> tuple[str, str]:
    """(git diff range, label). Only what changed since last_reviewed when that is safe, else the whole PR."""
    full = (f"{base_sha}...{head_sha}", "this PR")
    if not last_reviewed or last_reviewed == head_sha:
        return full
    if _git(repo, "cat-file", "-e", f"{last_reviewed}^{{commit}}").returncode != 0:
        return full
    if _git(repo, "merge-base", "--is-ancestor", last_reviewed, head_sha).returncode != 0:
        return full
    merges = _git(repo, "rev-list", "--min-parents=2", f"{last_reviewed}..{head_sha}")
    if merges.returncode != 0 or merges.stdout.strip():
        return full
    return (f"{last_reviewed}..{head_sha}", f"{last_reviewed[:7]}..{head_sha[:7]}")
