import os
import subprocess

import pytest

from reviewer.tools import make_tools


@pytest.fixture
def tools(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.R").write_text("".join(f"line{i}\n" for i in range(1, 11)))
    (tmp_path / "b.bin").write_bytes(b"\x00\x01\x02")
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    t = {f.name: f for f in make_tools(str(tmp_path))}
    return tmp_path, t


def call(tool, **kw):
    return tool.call(kw)


def test_read_file_numbered_range(tools):
    _, t = tools
    assert call(t["read_file"], path="src/a.R", start_line=3, end_line=4) == "3: line3\n4: line4"


def test_list_dir_marks_dirs(tools):
    _, t = tools
    out = call(t["list_dir"]).splitlines()
    assert "src/" in out and "b.bin" in out


def test_grep_finds_line(tools):
    _, t = tools
    assert "src/a.R:7:line7" in call(t["grep"], pattern="line7")


def test_rejects_escape(tools):
    _, t = tools
    assert call(t["read_file"], path="../../etc/passwd").startswith("error:")
    assert call(t["list_dir"], path="/etc").startswith("error:")
    assert call(t["grep"], pattern="root", path="../..").startswith("error:")


def test_rejects_symlink_escape(tools):
    root, t = tools
    os.symlink("/etc", root / "link")
    assert call(t["read_file"], path="link/passwd").startswith("error:")


def test_binary_and_missing(tools):
    _, t = tools
    assert call(t["read_file"], path="b.bin").startswith("error:")
    assert call(t["read_file"], path="nope.R").startswith("error:")


def test_tool_schemas(tools):
    _, t = tools
    assert set(t["read_file"].input_schema["properties"]) == {"path", "start_line", "end_line"}
    assert set(t["grep"].input_schema["properties"]) == {"pattern", "path"}
    assert set(t["list_dir"].input_schema["properties"]) == {"path"}


def test_grep_pattern_starting_with_dash(tools):
    root, t = tools
    out = call(t["grep"], pattern=f"-Otouch {root}/PWNED #", path=".")
    assert not (root / "PWNED").exists()
    assert "PWNED" not in out


def test_rejects_git_dir(tools):
    _, t = tools
    assert call(t["read_file"], path=".git/config").startswith("error:")
    assert call(t["read_file"], path="src/../.git/config").startswith("error:")
    assert call(t["list_dir"], path=".git").startswith("error:")
