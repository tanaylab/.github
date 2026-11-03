import subprocess

import pytest

from reviewer.diff import git_diff, review_range


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def commit(repo, name, text):
    (repo / name).write_text(text)
    git(repo, "add", name)
    git(repo, "commit", "-qm", name)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "t@t")
    git(tmp_path, "config", "user.name", "t")
    base = commit(tmp_path, "a.txt", "1\n")
    git(tmp_path, "checkout", "-qb", "pr")
    c1 = commit(tmp_path, "b.txt", "1\n")
    c2 = commit(tmp_path, "c.txt", "1\n")
    return tmp_path, base, c1, c2


def test_first_review_is_full(repo):
    r, base, c1, c2 = repo
    assert review_range(str(r), base, c2, None) == (f"{base}...{c2}", "this PR")


def test_incremental_after_push(repo):
    r, base, c1, c2 = repo
    assert review_range(str(r), base, c2, c1) == (f"{c1}..{c2}", f"{c1[:7]}..{c2[:7]}")
    assert "c.txt" in git_diff(str(r), f"{c1}..{c2}")
    assert "b.txt" not in git_diff(str(r), f"{c1}..{c2}")


def test_rebased_falls_back_to_full(repo):
    r, base, c1, c2 = repo
    git(r, "checkout", "-qb", "throwaway", base)
    other = commit(r, "d.txt", "1\n")
    assert review_range(str(r), base, c2, other)[1] == "this PR"


def test_unknown_sha_falls_back_to_full(repo):
    r, base, c1, c2 = repo
    assert review_range(str(r), base, c2, "0" * 40)[1] == "this PR"


def test_merge_from_base_falls_back_to_full(repo):
    r, base, c1, c2 = repo
    git(r, "checkout", "-q", "main")
    new_base = commit(r, "e.txt", "1\n")
    git(r, "checkout", "-q", "pr")
    git(r, "merge", "-q", "--no-edit", "main")
    head = git(r, "rev-parse", "HEAD")
    assert review_range(str(r), new_base, head, c2) == (f"{new_base}...{head}", "this PR")


def test_merge_base_ignores_stale_base(repo):
    from reviewer.diff import merge_base
    r, base, c1, c2 = repo
    git(r, "checkout", "-q", "main")
    commit(r, "f.txt", "1\n")
    git(r, "checkout", "-q", "pr")
    assert merge_base(str(r), "main", c2) == base
    assert merge_base(str(r), "no-such-ref", c2) is None
