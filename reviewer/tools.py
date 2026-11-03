"""Read-only tools Claude uses to look around the checked-out repo."""

import os
import subprocess

from anthropic import beta_tool

MAX_READ = 400
MAX_GREP = 200


def make_tools(root: str) -> list:
    root = os.path.realpath(root)

    def resolve(path: str) -> str | None:
        p = os.path.realpath(os.path.join(root, path))
        return p if p == root or p.startswith(root + os.sep) else None

    @beta_tool
    def read_file(path: str, start_line: int = 1, end_line: int = MAX_READ) -> str:
        """Read lines of a file in the repository, numbered.

        Args:
            path: File path relative to the repository root.
            start_line: First line to return (1-based).
            end_line: Last line to return; at most 400 lines per call.
        """
        p = resolve(path)
        if p is None:
            return "error: path is outside the repository"
        if not os.path.isfile(p):
            return "error: no such file"
        with open(p, "rb") as f:
            data = f.read()
        if b"\x00" in data[:8192]:
            return "error: binary file"
        lines = data.decode("utf-8", "replace").splitlines()
        start = max(start_line, 1)
        end = min(end_line, start + MAX_READ - 1, len(lines))
        return "\n".join(f"{n}: {lines[n - 1]}" for n in range(start, end + 1))

    @beta_tool
    def grep(pattern: str, path: str = ".") -> str:
        """Search tracked files with an extended regular expression (git grep -n -E).

        Args:
            pattern: Extended regular expression.
            path: Directory or file to search, relative to the repository root.
        """
        p = resolve(path)
        if p is None:
            return "error: path is outside the repository"
        r = subprocess.run(["git", "-C", root, "grep", "-n", "-I", "-E", pattern, "--", os.path.relpath(p, root)],
                           capture_output=True, text=True)
        if r.returncode == 1:
            return "no matches"
        if r.returncode != 0:
            return f"error: {r.stderr.strip()}"
        out = r.stdout.splitlines()
        return "\n".join(out[:MAX_GREP] + (["... (truncated)"] if len(out) > MAX_GREP else []))

    @beta_tool
    def list_dir(path: str = ".") -> str:
        """List a directory in the repository; directories end with '/'.

        Args:
            path: Directory relative to the repository root.
        """
        p = resolve(path)
        if p is None:
            return "error: path is outside the repository"
        if not os.path.isdir(p):
            return "error: no such directory"
        return "\n".join(e.name + ("/" if e.is_dir() else "") for e in sorted(os.scandir(p), key=lambda e: e.name)
                         if e.name != ".git")

    return [read_file, grep, list_dir]
