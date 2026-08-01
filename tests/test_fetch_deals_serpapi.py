"""Provider-free tests for the manual SerpApi/Bright Data draft writer."""
from __future__ import annotations

import importlib.util
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fetch_deals_serpapi.py"
SPEC = importlib.util.spec_from_file_location("fetch_deals_serpapi", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def sample_verified() -> dict[str, object]:
    return {
        "asin": "B012345678",
        "title": 'A "quoted" product\nname',
        "url": "https://www.amazon.com/dp/B012345678",
        "price": 59.99,
        "reference_price": 99.99,
        "discount_pct": 40.0,
        "currency": "USD",
        "source_currency": "GPB",
        "buybox_seller": "Amazon.com",
        "image_url": "https://images.example.test/product.jpg",
        "verified_at": "2026-07-31T12:00:00Z",
    }


class ReviewDraftTests(unittest.TestCase):
    def test_candidate_selection_round_robins_across_keywords(self) -> None:
        candidates = [
            {"asin": "B000000001", "keyword": "headphones"},
            {"asin": "B000000002", "keyword": "headphones"},
            {"asin": "B000000003", "keyword": "headphones"},
            {"asin": "B000000004", "keyword": "keyboards"},
            {"asin": "B000000005", "keyword": "keyboards"},
            {"asin": "B000000006", "keyword": "keyboards"},
        ]

        selected = MODULE.select_candidates(candidates, 4)

        self.assertEqual(
            [item["asin"] for item in selected],
            ["B000000001", "B000000004", "B000000002", "B000000005"],
        )

    def test_any_amazon_marketplace_seller_is_allowed_when_policy_is_empty(self) -> None:
        record = {
            "asin": "B012345678",
            "title": "Marketplace product",
            "url": "https://www.amazon.com/dp/B012345678",
            "domain": "amazon.com",
            "currency": "USD",
            "final_price": "59.99",
            "initial_price": "99.99",
            "is_available": True,
            "buybox_seller": "Brand Store",
            "image_url": "https://images.example.test/product.jpg",
        }

        normalized, reason = MODULE.verified_record(
            record,
            marketplace="amazon.com",
            currency="USD",
            trusted_seller_terms=[],
        )

        self.assertIsNone(reason)
        self.assertEqual(normalized["buybox_seller"], "Brand Store")

    def test_explicit_prime_member_price_is_rejected_but_prime_shipping_is_not(self) -> None:
        record = {
            "asin": "B012345678",
            "title": "Marketplace product",
            "url": "https://www.amazon.com/dp/B012345678",
            "domain": "amazon.com",
            "currency": "USD",
            "final_price": "59.99",
            "initial_price": "99.99",
            "is_available": True,
            "buybox_seller": "Brand Store",
            "image_url": "https://images.example.test/product.jpg",
            "amazon_prime": True,
        }

        normalized, reason = MODULE.verified_record(
            record,
            marketplace="amazon.com",
            currency="USD",
            trusted_seller_terms=[],
        )
        self.assertIsNone(reason)
        self.assertIsNotNone(normalized)

        record["badge"] = "Prime member price"
        normalized, reason = MODULE.verified_record(
            record,
            marketplace="amazon.com",
            currency="USD",
            trusted_seller_terms=[],
        )
        self.assertIsNone(normalized)
        self.assertEqual(reason, "Prime/member-only price")

    def test_rendered_draft_has_safe_toml_and_provider_provenance(self) -> None:
        rendered = MODULE.render_review_draft(
            sample_verified(),
            {
                "keyword": "headphones",
                "url": "https://www.amazon.com/Belkin-SoundForm-Isolate-Noise-Cancelling/dp/B012345678",
                "serpapi_sale_price": 59.99,
                "serpapi_reference_price": 99.99,
                "serpapi_discount_pct": 40.0,
            },
        )

        front_matter = rendered.split("+++\n", 2)[1]
        metadata = tomllib.loads(front_matter)
        self.assertTrue(metadata["draft"])
        self.assertEqual(metadata["review_status"], "pending")
        self.assertEqual(metadata["asin"], "B012345678")
        self.assertEqual(metadata["intake_source"], "serpapi+brightdata")
        self.assertEqual(metadata["verification_provider"], "brightdata")
        self.assertEqual(metadata["serpapi_keyword"], "headphones")
        self.assertFalse(metadata["affiliate_ready"])
        self.assertEqual(metadata["tags"], ["amazon", "amazon-us", "headphones"])
        self.assertEqual(metadata["categories"], ["deals"])
        self.assertEqual(metadata["title"], 'A "quoted" product\nname')
        self.assertNotIn("affiliate_url", metadata)

    def test_existing_queue_draft_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            queue_dir = Path(temporary_directory)
            self.assertTrue(MODULE.write_review_draft(sample_verified(), queue_dir=queue_dir))
            destination = queue_dir / "B012345678.md"
            original = destination.read_text(encoding="utf-8")

            changed = sample_verified()
            changed["title"] = "Replacement must not be written"
            self.assertFalse(MODULE.write_review_draft(changed, queue_dir=queue_dir))
            self.assertEqual(destination.read_text(encoding="utf-8"), original)

    def test_control_characters_are_escaped_and_validated_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            queue_dir = Path(temporary_directory)
            verified = sample_verified()
            verified["title"] = "Product\x00name"

            self.assertTrue(MODULE.write_review_draft(verified, queue_dir=queue_dir))
            draft_text = (queue_dir / "B012345678.md").read_text(encoding="utf-8")
            metadata = tomllib.loads(draft_text.split("+++\n", 2)[1])
            self.assertIn("\\u0000", draft_text)
            self.assertEqual(metadata["title"], "Product\x00name")

    def test_dry_run_never_calls_the_draft_writer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            report_path = Path(temporary_directory) / "report.json"
            serpapi_result = {
                "asin": "B012345678",
                "title": "Verified product",
                "link": "https://www.amazon.com/dp/B012345678",
                "extracted_price": "£59.99",
            }
            brightdata_result = {
                "asin": "B012345678",
                "title": "Verified product",
                "url": "https://www.amazon.com/Belkin-SoundForm-Isolate-Noise-Cancelling/dp/B012345678",
                "domain": "amazon.com",
                "currency": "USD",
                "final_price": "59.99",
                "initial_price": "99.99",
                "is_available": True,
                "buybox_seller": "Amazon.com",
            }
            config = {
                "marketplace": "amazon.com",
                "currency": "USD",
                "keywords": ["headphones"],
                "limits": {},
                "policy": {"trusted_seller_terms": ["amazon"]},
            }
            with (
                patch.object(MODULE, "require_env", return_value={
                    "SERPAPI_API_KEY": "test", "BRIGHTDATA_API_TOKEN": "test", "BRIGHTDATA_DATASET_ID": "test",
                }),
                patch.object(MODULE, "load_json", return_value=config),
                patch.object(MODULE, "serpapi_products", return_value=[serpapi_result]),
                patch.object(MODULE, "brightdata_verify", return_value=[brightdata_result]),
                patch.object(MODULE, "write_review_draft") as write_draft,
                patch("sys.argv", ["fetch_deals_serpapi.py", "--dry-run", "--report-out", str(report_path)]),
            ):
                self.assertEqual(MODULE.main(), 0)

            report = MODULE.json.loads(report_path.read_text(encoding="utf-8"))
            write_draft.assert_not_called()
            self.assertEqual(report["mode"], "dry-run")
            self.assertEqual(report["drafts"], {"created": [], "skipped_existing": [], "skipped_known": []})

    def test_parent_asin_is_diagnostic_but_submitted_url_asin_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            report_path = Path(temporary_directory) / "report.json"
            serpapi_result = {
                "asin": "B012345678",
                "title": "Submitted product",
                "link": "https://www.amazon.com/dp/B012345678",
                "extracted_price": "£59.99",
            }
            parent_asin_record = {
                "asin": "B011111111",
                "title": "Submitted product variant",
                "url": "https://www.amazon.com/dp/B012345678",
                "domain": "amazon.com",
                "currency": "USD",
                "final_price": "59.99",
                "initial_price": "99.99",
                "is_available": True,
                "buybox_seller": "Amazon.com",
                "image_url": "https://images.example.test/product.jpg",
            }
            unsubmitted_record = {
                **parent_asin_record,
                "asin": "B098765432",
                "url": "https://www.amazon.com/dp/B098765432",
            }
            config = {
                "marketplace": "amazon.com",
                "currency": "USD",
                "keywords": ["headphones"],
                "limits": {},
                "policy": {"trusted_seller_terms": ["amazon"]},
            }
            with (
                patch.object(MODULE, "require_env", return_value={
                    "SERPAPI_API_KEY": "test", "BRIGHTDATA_API_TOKEN": "test", "BRIGHTDATA_DATASET_ID": "test",
                }),
                patch.object(MODULE, "load_json", return_value=config),
                patch.object(MODULE, "serpapi_products", return_value=[serpapi_result]),
                patch.object(MODULE, "brightdata_verify", return_value=[parent_asin_record, unsubmitted_record]),
                patch("sys.argv", ["fetch_deals_serpapi.py", "--dry-run", "--report-out", str(report_path)]),
            ):
                self.assertEqual(MODULE.main(), 0)

            report = MODULE.json.loads(report_path.read_text(encoding="utf-8"))
            accepted = report["verification"]["accepted"]
            self.assertEqual(len(accepted), 1)
            self.assertEqual(accepted[0]["asin"], "B012345678")
            self.assertEqual(accepted[0]["provider_asin"], "B011111111")
            self.assertFalse(accepted[0]["provider_asin_matches_url"])
            reasons = [item["reason"] for item in report["verification"]["rejected"]]
            self.assertIn("Bright Data ASIN was not among submitted candidates", reasons)

    def test_rendered_draft_contains_provider_listing_fields_and_price_gate(self) -> None:
        rendered = MODULE.render_review_draft(sample_verified())
        metadata = tomllib.loads(rendered.split("+++\n", 2)[1])
        self.assertEqual(metadata["listing_source"], "brightdata")
        self.assertEqual(metadata["listing_url"], "https://www.amazon.com/dp/B012345678")
        self.assertEqual(metadata["listing_image"], "https://images.example.test/product.jpg")
        self.assertEqual(metadata["price_access"], "unknown")
        self.assertTrue(metadata["price_review_required"])

    def test_brightdata_inputs_include_configured_delivery_zip(self) -> None:
        inputs = MODULE.build_brightdata_inputs(
            ["https://www.amazon.com/dp/B012345678"],
            {"zipcode": "94107", "language": "en_US"},
        )
        self.assertEqual(inputs, [{"url": "https://www.amazon.com/dp/B012345678", "zipcode": "94107"}])


if __name__ == "__main__":
    unittest.main()
