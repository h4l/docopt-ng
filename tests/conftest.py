import json
from pathlib import Path
import re

import docopt
import pytest


def pytest_collect_file(file_path: Path, path, parent):
    if file_path.suffix == ".docopt" and file_path.stem.startswith("test"):
        return DocoptTestFile.from_parent(path=file_path, parent=parent)


def parse_test(raw: str):
    raw = re.compile("#.*$", re.M).sub("", raw).strip()
    if raw.startswith('"""'):
        raw = raw[3:]

    for fixture in raw.split('r"""'):
        doc, _, body = fixture.partition('"""')
        cases = []
        for case in body.split("$")[1:]:
            argv, _, expect = case.strip().partition("\n")
            expect = json.loads(expect)
            prog, _, argv = argv.strip().partition(" ")
            cases.append((prog, argv, expect))
        yield doc, cases


class DocoptTestFile(pytest.File):
    def collect(self):
        raw = self.path.open().read()
        for i, (doc, cases) in enumerate(parse_test(raw), 1):
            name = f"{self.path.stem}({i})"
            for case in cases:
                yield DocoptTestItem.from_parent(
                    name=name, parent=self, doc=doc, case=case
                )


class DocoptTestItem(pytest.Item):
    def __init__(self, name, parent, doc, case):
        super(DocoptTestItem, self).__init__(name, parent)
        self.doc = doc
        self.prog, self.argv, self.expect = case

    def runtest(self):
        try:
            result = docopt.docopt(self.doc, argv=self.argv)
        except docopt.DocoptExit:
            result = "user-error"

        if self.expect != result:
            raise DocoptTestException(self, result)

    def repr_failure(self, excinfo):
        """Called when self.runtest() raises an exception."""
        if isinstance(excinfo.value, DocoptTestException):
            return "\n".join(
                (
                    "usecase execution failed:",
                    self.doc.rstrip(),
                    f"$ {self.prog} {self.argv}",
                    f"result> {json.dumps(excinfo.value.args[1])}",
                    f"expect> {json.dumps(self.expect)}",
                )
            )

    def reportinfo(self):
        return self.path, 0, f"usecase: {self.name}"


class DocoptTestException(Exception):
    pass
