"""Provider-free test for rejection archive behavior."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "reject_deals.py"
SPEC = importlib.util.spec_from_file_location("reject_deals", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RejectionTests(unittest.TestCase):
    def test_rejection_moves_draft_and_records_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            pending = root / "pending"
            rejected = root / "rejected"
            pending.mkdir()
            (pending / "B012345678.md").write_text(
                '+++\ndraft = true\nreview_status = "pending"\n+++\n\nCandidate.\n',
                encoding="utf-8",
            )
            with (
                patch.object(MODULE, "PENDING_DIR", pending),
                patch.object(MODULE, "REJECTED_DIR", rejected),
                patch.object(sys, "argv", ["reject_deals.py", "--asin", "B012345678", "--reason", "Prime-only price"]),
            ):
                self.assertEqual(MODULE.main(), 0)
            self.assertFalse((pending / "B012345678.md").exists())
            metadata = tomllib.loads((rejected / "B012345678.md").read_text(encoding="utf-8").split("+++\n", 2)[1])
            self.assertEqual(metadata["review_status"], "rejected")
            self.assertEqual(metadata["rejection_reason"], "Prime-only price")
            self.assertIn("rejected_at", metadata)
