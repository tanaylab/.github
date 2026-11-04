from reviewer.diff import changed_lines, filter_diff, parse_diff

MODIFY = """diff --git a/a.R b/a.R
index 1111111..2222222 100644
--- a/a.R
+++ b/a.R
@@ -10,3 +10,4 @@ f <- function(x) {
 x <- 1
-y <- 2
+y <- 3
+z <- 4
 w <- 5
"""

RENAME = """diff --git a/x.py b/y.py
similarity index 90%
rename from x.py
rename to y.py
index 1111111..2222222 100644
--- a/x.py
+++ b/y.py
@@ -1,2 +1,2 @@
-a = 1
+a = 2
 b = 2
"""

DELETE = """diff --git a/old.R b/old.R
deleted file mode 100644
index 1111111..0000000
--- a/old.R
+++ /dev/null
@@ -1,2 +0,0 @@
-a
-b
"""

BINARY = """diff --git a/img.bin b/img.bin
index 1111111..2222222 100644
Binary files a/img.bin and b/img.bin differ
"""

LOCK = """diff --git a/renv.lock b/renv.lock
index 1111111..2222222 100644
--- a/renv.lock
+++ b/renv.lock
@@ -1 +1 @@
-old
+new
diff --git a/man/foo.Rd b/man/foo.Rd
index 1111111..2222222 100644
--- a/man/foo.Rd
+++ b/man/foo.Rd
@@ -1 +1 @@
-old
+new
"""


def test_parse_added_and_context_lines():
    assert parse_diff(MODIFY) == {"a.R": {10, 11, 12, 13}}


def test_parse_rename_uses_new_path():
    assert parse_diff(RENAME) == {"y.py": {1, 2}}


def test_parse_deleted_file():
    assert not parse_diff(DELETE).get("old.R")


def test_parse_binary_omitted():
    assert "img.bin" not in parse_diff(BINARY)


def test_only_skipped_files():
    assert filter_diff(LOCK) == ""
    assert changed_lines("") == 0


def test_filter_keeps_unskipped():
    assert filter_diff(LOCK + MODIFY) == MODIFY


def test_changed_lines_ignores_headers():
    assert changed_lines(MODIFY) == 3


def _file(path, n):
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -0,0 +1,{n} @@\n" + "+x\n" * n


def test_data_files_skipped():
    for p in ["splits/fold0.bed", "res/table.tsv", "x.csv", "genome.fa"]:
        assert filter_diff(_file(p, 2)) == "", p


def test_fit_diff_keeps_all_when_small():
    from reviewer.diff import fit_diff
    d = _file("a.py", 5) + _file("b.yaml", 5)
    assert fit_diff(d, 100) == (d, [])


def test_fit_diff_code_first_then_what_fits():
    from reviewer.diff import fit_diff
    big_cfg, code, huge_code, small_cfg = _file("c.yaml", 60), _file("a.py", 50), _file("b.R", 500), _file("d.yaml", 10)
    kept, left = fit_diff(big_cfg + code + huge_code + small_cfg, 100)
    assert kept == code + small_cfg
    assert left == ["c.yaml", "b.R"]
