"""A 组扩展测试：归一化后的路径必须严格落在项目根目录内。

对应 fullcheck.project_path()。两类路径不过滤就会被误记为实际依赖，进而制造假 MD/RD：
上级目录逃逸（../outside.h）、前缀相同的兄弟目录（/course/project-old/）。
第三个用例是正向对照：项目内子目录里的文件必须仍然被计入，否则说明过滤过头。
"""
import tempfile
import unittest
from pathlib import Path

from buildchecker.fullcheck import execution_graph


class TestPathNormalizationBoundaries(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.root = "/course/project"

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, text):
        path = self.folder / name
        path.write_text(text, encoding="utf-8")
        return path

    def traces(self, reader_extra=""):
        """Make(10) -> cc1(11) job：写 unit.o，读 unit.c 和 reader_extra 里的路径。"""
        self.write("t.10", 'execve("/usr/bin/make", ["make", "app"], []) = 0\n'
                           'clone(child_stack=NULL, flags=SIGCHLD) = 11\n')
        self.write("t.11", 'execve("/usr/bin/cc1", ["cc1", "unit.c"], []) = 0\n'
                           'openat(AT_FDCWD, "unit.c", O_RDONLY) = 3\n'
                           + reader_extra +
                           'openat(AT_FDCWD, "unit.o", O_RDWR|O_CREAT|O_TRUNC, 0666) = 7\n')

    def dependencies(self, reader_extra=""):
        self.traces(reader_extra)
        targets, _ = execution_graph(self.folder, self.root)
        return set(targets["unit.o"]["dependencies"])

    def test_parent_directory_escape_is_not_a_dependency(self):
        deps = self.dependencies('openat(AT_FDCWD, "../outside.h", O_RDONLY) = 4\n'
                                 'openat(AT_FDCWD, "/course/project/../../etc/passwd", O_RDONLY) = 5\n')
        self.assertEqual(deps, {"unit.c"})

    def test_sibling_directory_with_shared_prefix_is_not_a_dependency(self):
        # 前缀比较必须带结尾的 "/"：否则 /course/project-old 会被当成 /course/project 的子目录
        deps = self.dependencies('openat(AT_FDCWD, "/course/project-old/legacy.h", O_RDONLY) = 6\n')
        self.assertEqual(deps, {"unit.c"})

    def test_file_inside_project_subdirectory_is_still_a_dependency(self):
        # 正向对照：过滤不能过头，项目内子目录的读取必须保留
        deps = self.dependencies('openat(AT_FDCWD, "src/needed.h", O_RDONLY) = 8\n')
        self.assertEqual(deps, {"unit.c", "src/needed.h"})


if __name__ == "__main__":
    unittest.main()
