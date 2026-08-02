"""Provider-free tests for the Bright Data Search/PDP review-draft intake."""
from __future__ import annotations

import importlib.util
import json
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


def config() -> dict[str, object]:
    return {"marketplace": "amazon.com", "currency": "USD", "keywords": ["headphones"],
            "discovery": {"dataset_id": "gd_lwdb4vjm1ehb499uxs", "pages_to_search": 1},
            "verification": {}, "limits": {}, "policy": {"trusted_seller_terms": []}}


def verified(initial_price: object = "99.99", asin: str = "B012345678", title: str = "Product") -> dict[str, object]:
    return {"asin": asin, "title": title, "url": f"https://www.amazon.com/dp/{asin}",
            "domain": "amazon.com", "currency": "USD", "final_price": "59.99", "initial_price": initial_price,
            "is_available": True, "buybox_seller": "Brand Store", "image_url": "https://images.example.test/p.jpg"}


class BrightDataIntakeTests(unittest.TestCase):
    def test_candidate_selection_still_round_robins_by_keyword(self) -> None:
        candidates = [
            {"asin": "B000000001", "keyword": "headphones"}, {"asin": "B000000002", "keyword": "headphones"},
            {"asin": "B000000003", "keyword": "keyboards"}, {"asin": "B000000004", "keyword": "keyboards"},
        ]
        self.assertEqual([item["asin"] for item in MODULE.select_candidates(candidates, 4)], ["B000000001", "B000000003", "B000000002", "B000000004"])

    def test_category_slots_and_winners_keep_one_verified_backup_per_category(self) -> None:
        categories = MODULE.configured_categories({"categories": [{"id": "audio", "keyword": "headphones"}, {"id": "kitchen", "keyword": "air fryer"}]})
        self.assertEqual(categories, [{"id": "audio", "keyword": "headphones"}, {"id": "kitchen", "keyword": "air fryer"}])
        candidates = [
            {"asin": "B000000001", "category": "audio"},
            {"asin": "B000000002", "category": "audio"},
            {"asin": "B000000003", "category": "kitchen"},
        ]
        normalized = {
            "B000000002": {"asin": "B000000002", "title": "Audio deal"},
            "B000000003": {"asin": "B000000003", "title": "Kitchen deal"},
        }
        winners, asins = MODULE.select_category_winners(candidates, normalized)
        self.assertEqual([item["asin"] for item in winners], ["B000000002", "B000000003"])
        self.assertEqual(asins, {"B000000002", "B000000003"})

    def test_documented_search_inputs_and_dataset_default(self) -> None:
        self.assertEqual(MODULE.brightdata_search_dataset_id({"discovery": {}}), "gd_lwdb4vjm1ehb499uxs")
        self.assertEqual(MODULE.brightdata_search_inputs(["wireless headphones"], "amazon.com", {"pages_to_search": 1}),
                         [{"keyword": "wireless headphones", "url": "https://www.amazon.com", "pages_to_search": 1}])

    def test_search_record_normalizes_common_shape_and_prefers_discount(self) -> None:
        qualifying, reason = MODULE.discovery_candidate({"product_title": "Deal", "product_url": "https://www.amazon.com/dp/B012345678", "current_price": {"amount": "60"}, "list_price": "100", "currency": "USD"}, keyword="headphones", marketplace="amazon.com", minimum_discount=.20, minimum_sale_price=20)
        fallback, reason2 = MODULE.discovery_candidate({"name": "No comparison", "url": "https://www.amazon.com/dp/B012345679", "price": "60", "currency": "USD"}, keyword="headphones", marketplace="amazon.com", minimum_discount=.20, minimum_sale_price=20)
        self.assertIsNone(reason); self.assertIsNone(reason2)
        self.assertEqual([x["asin"] for x in MODULE.select_candidates([fallback, qualifying], 2)], ["B012345678", "B012345679"])

    def test_search_record_requires_an_amazon_product_url(self) -> None:
        candidate, reason = MODULE.discovery_candidate(
            {"id": "B012345678", "title": "Not a product", "url": "https://www.amazon.com/s?k=headphones", "price": "60", "currency": "USD"},
            keyword="headphones",
            marketplace="amazon.com",
            minimum_discount=.20,
            minimum_sale_price=20,
        )
        self.assertIsNone(candidate)
        self.assertEqual(reason, "Amazon URL is not a product URL")

    def test_missing_or_inconsistent_pdp_reference_is_accepted(self) -> None:
        for initial in (None, "50"):
            normalized, reason = MODULE.verified_record(verified(initial), marketplace="amazon.com", currency="USD", trusted_seller_terms=[])
            self.assertIsNone(reason); self.assertIsNone(normalized["reference_price"])
            self.assertEqual(normalized["provider_reference_price"], MODULE.parse_price(initial))

    def test_draft_without_reference_does_not_advertise_discount(self) -> None:
        normalized, _ = MODULE.verified_record(verified(None), marketplace="amazon.com", currency="USD", trusted_seller_terms=[])
        metadata = tomllib.loads(MODULE.render_review_draft(normalized, {"keyword": "headphones"}).split("+++\n", 2)[1])
        self.assertEqual(metadata["intake_source"], "brightdata-search+brightdata-pdp")
        self.assertEqual(metadata["reference_price_status"], "unavailable-requires-browser-verification")
        self.assertNotIn("list_price", metadata); self.assertNotIn("discount_pct", metadata); self.assertNotIn("affiliate_url", metadata)
        self.assertTrue(metadata["draft"]); self.assertEqual(metadata["price_access"], "unknown")

    def test_draft_with_reference_keeps_listing_fields_and_provenance(self) -> None:
        normalized, _ = MODULE.verified_record(verified(), marketplace="amazon.com", currency="USD", trusted_seller_terms=[])
        metadata = tomllib.loads(MODULE.render_review_draft(normalized, {"keyword": "headphones"}).split("+++\n", 2)[1])
        self.assertEqual(metadata["listing_source"], "brightdata")
        self.assertEqual(metadata["verification_provider"], "brightdata-pdp")
        self.assertEqual(metadata["listing_list_price"], 99.99)
        self.assertEqual(metadata["reference_price_status"], "provider-reported")

    def test_env_and_config_validation(self) -> None:
        with patch.dict(MODULE.os.environ, {}, clear=True):
            with self.assertRaisesRegex(MODULE.ProviderError, "BRIGHTDATA_API_TOKEN.*BRIGHTDATA_DATASET_ID"):
                MODULE.require_env()
        with self.assertRaisesRegex(MODULE.ProviderError, "dataset ID"):
            MODULE.brightdata_search_dataset_id({"discovery": {"dataset_id": "not-a-dataset"}})
        with self.assertRaisesRegex(MODULE.ProviderError, "positive integer"):
            MODULE.brightdata_search_inputs(["x"], "amazon.com", {"pages_to_search": 0})

    def test_prime_delivery_is_allowed_but_explicit_member_price_is_rejected(self) -> None:
        record = verified()
        record["amazon_prime"] = True
        normalized, reason = MODULE.verified_record(record, marketplace="amazon.com", currency="USD", trusted_seller_terms=[])
        self.assertIsNone(reason); self.assertIsNotNone(normalized)
        record["badge"] = "Prime member price"
        normalized, reason = MODULE.verified_record(record, marketplace="amazon.com", currency="USD", trusted_seller_terms=[])
        self.assertIsNone(normalized); self.assertEqual(reason, "Prime/member-only price")

    def test_any_marketplace_seller_is_allowed_when_policy_is_empty(self) -> None:
        normalized, reason = MODULE.verified_record(verified(), marketplace="amazon.com", currency="USD", trusted_seller_terms=[])
        self.assertIsNone(reason); self.assertEqual(normalized["buybox_seller"], "Brand Store")

    def test_existing_draft_is_not_overwritten_and_toml_controls_are_safe(self) -> None:
        normalized, _ = MODULE.verified_record(verified(), marketplace="amazon.com", currency="USD", trusted_seller_terms=[])
        normalized["title"] = "Product\\x00name".encode().decode("unicode_escape")
        with tempfile.TemporaryDirectory() as directory:
            queue = Path(directory)
            self.assertTrue(MODULE.write_review_draft(normalized, queue_dir=queue))
            draft = queue / "B012345678.md"
            original = draft.read_text()
            self.assertIn("\\u0000", original)
            self.assertEqual(tomllib.loads(original.split("+++\n", 2)[1])["title"], "Product\\x00name".encode().decode("unicode_escape"))
            normalized["title"] = "Replacement"
            self.assertFalse(MODULE.write_review_draft(normalized, queue_dir=queue))
            self.assertEqual(draft.read_text(), original)

    def test_pdp_url_asin_is_authoritative_and_zip_inputs_remain_supported(self) -> None:
        record = verified()
        record["asin"] = "B011111111"
        normalized, reason = MODULE.verified_record(record, marketplace="amazon.com", currency="USD", trusted_seller_terms=[])
        self.assertIsNone(reason); self.assertEqual(normalized["asin"], "B012345678")
        self.assertFalse(normalized["provider_asin_matches_url"])
        self.assertEqual(MODULE.build_brightdata_inputs(["https://www.amazon.com/dp/B012345678"], {"zipcode": "94107", "language": "en_US"}), [{"url": "https://www.amazon.com/dp/B012345678", "zipcode": "94107"}])

    def test_dry_run_uses_search_then_pdp_without_draft_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "report.json"
            search = {"keyword": "headphones", "title": "Product", "url": "https://www.amazon.com/dp/B012345678", "price": "60", "currency": "USD"}
            with (patch.object(MODULE, "require_env", return_value={"BRIGHTDATA_API_TOKEN": "test", "BRIGHTDATA_DATASET_ID": "test"}), patch.object(MODULE, "load_json", return_value=config()), patch.object(MODULE, "brightdata_search", return_value=[search]) as search_call, patch.object(MODULE, "brightdata_verify", return_value=[verified()]), patch.object(MODULE, "write_review_draft") as draft_write, patch("sys.argv", ["fetch_deals_serpapi.py", "--dry-run", "--report-out", str(report_path)])):
                self.assertEqual(MODULE.main(), 0)
            report = json.loads(report_path.read_text())
            search_call.assert_called_once(); draft_write.assert_not_called()
            self.assertEqual(report["providers"]["discovery"], "brightdata-amazon-products-search")
            self.assertEqual(report["verification"]["accepted"][0]["asin"], "B012345678")

    def test_category_retry_only_resubmits_the_failed_slot(self) -> None:
        category_config = {
            "marketplace": "amazon.com",
            "currency": "USD",
            "categories": [{"id": "audio", "keyword": "headphones"}, {"id": "kitchen", "keyword": "air fryer"}],
            "discovery": {"dataset_id": "gd_lwdb4vjm1ehb499uxs", "pages_to_search": 1},
            "verification": {}, "limits": {}, "policy": {"trusted_seller_terms": []},
        }
        search = [
            {"keyword": "headphones", "title": "Audio", "url": "https://www.amazon.com/dp/B000000001", "price": "60", "currency": "USD"},
            {"keyword": "air fryer", "title": "Kitchen first", "url": "https://www.amazon.com/dp/B000000002", "price": "60", "currency": "USD"},
            {"keyword": "air fryer", "title": "Kitchen backup", "url": "https://www.amazon.com/dp/B000000003", "price": "60", "currency": "USD"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "report.json"
            with (patch.object(MODULE, "require_env", return_value={"BRIGHTDATA_API_TOKEN": "test", "BRIGHTDATA_DATASET_ID": "test"}), patch.object(MODULE, "load_json", return_value=category_config), patch.object(MODULE, "brightdata_search", return_value=search), patch.object(MODULE, "brightdata_verify", side_effect=[[verified(asin="B000000001", title="Audio")], [verified(asin="B000000003", title="Kitchen backup")]]) as verify_call, patch("sys.argv", ["fetch_deals_serpapi.py", "--dry-run", "--report-out", str(report_path)])):
                self.assertEqual(MODULE.main(), 0)
            report = json.loads(report_path.read_text())
            self.assertEqual(verify_call.call_count, 2)
            self.assertEqual(report["verification"]["rounds"][0]["submitted_asins"], ["B000000001", "B000000002"])
            self.assertEqual(report["verification"]["rounds"][1]["submitted_asins"], ["B000000003"])
            self.assertEqual([winner["asin"] for winner in report["verification"]["accepted"]], ["B000000001", "B000000003"])


if __name__ == "__main__":
    unittest.main()
