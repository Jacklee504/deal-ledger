"""Provider-free tests for explicit manual promotion safeguards."""
from __future__ import annotations

import importlib.util
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "promote_deals.py"
SPEC = importlib.util.spec_from_file_location("promote_deals", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

VALIDATOR_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_live_deal_metadata.py"
VALIDATOR_SPEC = importlib.util.spec_from_file_location("validate_live_deal_metadata", VALIDATOR_SCRIPT)
assert VALIDATOR_SPEC and VALIDATOR_SPEC.loader
VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
VALIDATOR_SPEC.loader.exec_module(VALIDATOR)


def pending_draft() -> str:
    return """+++
title = "Example – Unicode-safe"
draft = true
review_status = "pending"
asin = "B012345678"
marketplace = "amazon.com"
currency = "USD"
affiliate_ready = false
price_access = "unknown"
price_review_required = true
product_url = "https://www.amazon.com/dp/B012345678"
image = "https://images.example.test/product.jpg"
listing_image = "https://images.example.test/product.jpg"
sale_price = 59.99
list_price = 99.99
+++

Pending review.
"""


class PromotionTests(unittest.TestCase):
    def test_associates_url_requires_a_tag_or_sitestripe_short_link(self) -> None:
        self.assertTrue(MODULE.is_valid_associates_url("https://www.amazon.com/dp/B012345678?tag=example-20"))
        self.assertTrue(MODULE.is_valid_associates_url("https://amzn.to/example"))
        self.assertFalse(MODULE.is_valid_associates_url("https://www.amazon.com/dp/B012345678"))
        self.assertFalse(MODULE.is_valid_associates_url("https://www.amazon.co.uk/dp/B012345678?tag=example-21"))

    def test_promotion_requires_public_price_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            pending = root / "review-queue" / "deals"
            pending.mkdir(parents=True)
            (pending / "B012345678.md").write_text(pending_draft(), encoding="utf-8")
            with patch.object(MODULE, "SOURCE_DIR", pending), patch.object(MODULE, "TARGET_DIR", root / "content" / "deals"):
                with self.assertRaises(MODULE.PromotionError):
                    MODULE.promote(
                        asin="B012345678",
                        affiliate_url="https://www.amazon.com/dp/B012345678?tag=example-20",
                        public_price=59.99,
                        public_reference_price=99.99,
                        confirm_public_price=False,
                    )

    def test_promotion_stores_manual_public_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            pending = root / "review-queue" / "deals"
            target = root / "content" / "deals"
            pending.mkdir(parents=True)
            (pending / "B012345678.md").write_text(pending_draft(), encoding="utf-8")
            with (
                patch.object(MODULE, "SOURCE_DIR", pending),
                patch.object(MODULE, "TARGET_DIR", target),
            ):
                destination = MODULE.promote(
                    asin="B012345678",
                    affiliate_url="https://www.amazon.com/dp/B012345678?tag=example-20",
                    public_price=60.00,
                    public_reference_price=100.00,
                    confirm_public_price=True,
                )
            metadata = tomllib.loads(destination.read_text(encoding="utf-8").split("+++\n", 2)[1])
            self.assertFalse(metadata["draft"])
            self.assertEqual(metadata["review_status"], "approved")
            self.assertEqual(metadata["price_access"], "public")
            self.assertEqual(metadata["listing_sale_price"], 60.0)
            self.assertEqual(metadata["listing_url"], "https://www.amazon.com/dp/B012345678")
            self.assertEqual(metadata["affiliate_url"], "https://www.amazon.com/dp/B012345678?tag=example-20")
            self.assertEqual(VALIDATOR.validate(destination), [])
            self.assertNotIn("before promoting", destination.read_text(encoding="utf-8"))
