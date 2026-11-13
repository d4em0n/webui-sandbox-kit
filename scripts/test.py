"""Run meaningful unit/security checks and save a renderer-friendly JSON report."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class Result(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.records.append({"name": test.id(), "status": "passed"})

    def addFailure(self, test, error):
        super().addFailure(test, error)
        self.records.append({"name": test.id(), "status": "failed", "message": self._exc_info_to_string(error, test)})

    def addError(self, test, error):
        super().addError(test, error)
        self.records.append({"name": test.id(), "status": "failed", "message": self._exc_info_to_string(error, test)})

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.records.append({"name": test.id(), "status": "skipped", "message": reason})


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    result = unittest.TextTestRunner(verbosity=2, resultclass=Result).run(suite)
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "reports/unit.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.records, indent=2) + "\n")
    raise SystemExit(not result.wasSuccessful())
