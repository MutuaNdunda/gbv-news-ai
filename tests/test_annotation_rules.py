"""Deterministic quality/relevance rules with synthetic, non-sensitive examples."""

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import unittest

from annotations.l0 import evaluate_l0
from annotations.l1 import evaluate_l1, gazetteer
from annotations.schemas import DEFAULT_CONFIG


def valid_article():
    body = "Residents in Nairobi discussed education funding and local community services. " * 8
    return {"title": "Community services in Nairobi", "article_text": body,
            "source": "citizen", "canonical_url": "https://citizen.digital/news/test-n1",
            "published_at": "2026-08-01T10:00:00+03:00", "raw_object_uri": "gs://raw/test.html",
            "processed_object_uri": "gs://processed/test.json", "parser_version": "test-parser",
            "content_hash": hashlib.sha256(body.encode()).hexdigest()}


class L0Tests(unittest.TestCase):
    def test_valid_and_deterministic_without_fake_confidence(self):
        first = evaluate_l0(valid_article())
        self.assertEqual(first.label, "valid")
        self.assertEqual(first, evaluate_l0(valid_article()))
        self.assertIsNone(first.confidence)
        self.assertEqual(first.method_version, "l0-v1.0")

    def test_missing_critical_fields_are_hard_failures(self):
        fields = {"title": "missing_title", "article_text": "missing_body", "source": "missing_source",
                  "canonical_url": "missing_canonical_url", "raw_object_uri": "missing_raw_uri",
                  "processed_object_uri": "missing_processed_uri", "content_hash": "missing_content_hash",
                  "parser_version": "missing_parser_version"}
        for field, reason in fields.items():
            with self.subTest(field=field):
                item = valid_article()
                item.pop(field)
                result = evaluate_l0(item)
                self.assertEqual(result.label, "invalid")
                self.assertIn(reason, result.reason_codes)

    def test_wrong_domain_credentials_and_prefix_attacks_are_rejected(self):
        for url in ("https://citizen.digital.example.com/story", "https://evil.test/story",
                    "https://secret@citizen.digital/story", "file:///private/story", "https://citizen.digital:4000/story"):
            with self.subTest(url=url):
                result = evaluate_l0(dict(valid_article(), canonical_url=url))
                self.assertEqual(result.label, "invalid")
                self.assertIn("unexpected_domain", result.reason_codes)

    def test_malformed_or_non_gcs_references_are_invalid_without_raising(self):
        for uri in ("gs://[broken/object", "gs://raw:443/object", "gs://secret@raw/object",
                    "https://raw/object", "gs://raw/", "gs://raw/object?query=1"):
            with self.subTest(uri=uri):
                result = evaluate_l0(dict(valid_article(), raw_object_uri=uri))
                self.assertEqual(result.label, "invalid")
                self.assertIn("missing_raw_uri", result.reason_codes)

    def test_missing_invalid_date_and_soft_warnings_require_review(self):
        for date in (None, "not a date", "2026-02-30"):
            result = evaluate_l0(dict(valid_article(), published_at=date))
            self.assertEqual(result.label, "needs_review")
        item = valid_article()
        item["article_text"] = "Short but meaningful extracted reporting with enough readable words to inspect. " * 2
        item["content_hash"] = hashlib.sha256(item["article_text"].encode()).hexdigest()
        self.assertEqual(evaluate_l0(item).label, "needs_review")

    def test_calendar_dates_naive_dates_and_database_dates_are_accepted(self):
        for date in ("2026-08-01", "2026-08-01T10:00:00", datetime(2026, 8, 1, tzinfo=timezone.utc)):
            self.assertEqual(evaluate_l0(dict(valid_article(), published_at=date)).label, "valid")

    def test_unusable_content_hash_and_multiple_failures(self):
        result = evaluate_l0(dict(valid_article(), title="", article_text="Access denied", content_hash="wrong"))
        self.assertEqual(result.label, "invalid")
        self.assertTrue({"missing_title", "unusable_body", "invalid_content_hash", "suspected_block_page"} <= set(result.reason_codes))
        self.assertIn("content_hash_mismatch", evaluate_l0(dict(valid_article(), content_hash="a" * 64)).reason_codes)

    def test_paywall_truncation_and_boilerplate_indicators(self):
        for text, code in (("subscribe to continue reading", "suspected_paywall"),
                           ("enable javascript", "suspected_boilerplate"), ("…", "suspected_truncation")):
            body = text + valid_article()["article_text"] if code != "suspected_truncation" else valid_article()["article_text"] + text
            item = dict(valid_article(), article_text=body, content_hash=hashlib.sha256(body.encode()).hexdigest())
            self.assertIn(code, evaluate_l0(item).reason_codes)
            self.assertEqual(evaluate_l0(item).label, "needs_review")

    def test_non_reporting_trial_is_retained_for_review(self):
        result = evaluate_l0(dict(valid_article(), source="nation", content_scope="corporate_news",
                                 canonical_url="https://www.nationmedia.com/news/example"))
        self.assertEqual(result.label, "needs_review")
        self.assertIn("non_reporting_scope", result.reason_codes)

    def test_custom_configuration_is_versioned_by_layer(self):
        changed = replace(DEFAULT_CONFIG, minimum_body_chars=700)
        self.assertNotEqual(changed.method_version("L0"), DEFAULT_CONFIG.method_version("L0"))
        self.assertEqual(changed.method_version("L1"), DEFAULT_CONFIG.method_version("L1"))


class L1Tests(unittest.TestCase):
    def evaluate(self, text, **kwargs):
        return evaluate_l1({"title": "", "article_text": text, **kwargs})

    def test_explicit_country_place_city_institution_and_multiple_signals(self):
        for text in ("An education programme in Kenya", "Kiambu county officials meet", "Schools in Eldoret",
                     "Kenya Police issued a statement", "Nairobi and DCI discussed services in Kenya"):
            with self.subTest(text=text): self.assertEqual(self.evaluate(text).label, "kenya")

    def test_foreign_only_and_mixed_reporting(self):
        self.assertEqual(self.evaluate("Schools in London and Britain reopened").label, "not_kenya")
        result = self.evaluate("Nairobi and Kampala signed a joint programme")
        self.assertEqual(result.label, "ambiguous")
        self.assertIn("mixed_geographic_evidence", result.reason_codes)

    def test_publisher_alone_weak_admin_and_ambiguous_places_do_not_decide(self):
        for text in ("Local county officials met", "Busia officials met", "A Nandi speaker was invited", "DCI issued a statement"):
            self.assertEqual(self.evaluate(text, source="nation").label, "ambiguous")

    def test_case_boundaries_variants_and_unicode(self):
        self.assertEqual(self.evaluate("MURANG’A and tharaka-nithi reporting").label, "kenya")
        self.assertEqual(self.evaluate("Kenyan communities discussed policy").label, "kenya")
        self.assertEqual(self.evaluate("Kenyafoo and Nairobians are different words").label, "ambiguous")

    def test_gazetteer_has_all_47_distinct_counties(self):
        counties = gazetteer()["counties"]
        self.assertEqual(len(counties), 47)
        self.assertEqual(len(set(counties)), 47)
        self.assertTrue({"Nairobi", "Mombasa", "Tana River", "Uasin Gishu", "Elgeyo Marakwet", "Nyamira"} <= set(counties))

    def test_deterministic_normalized_confidence_and_structured_evidence(self):
        result = self.evaluate("Nairobi Kiambu Kenya Police")
        self.assertEqual(result, self.evaluate("Nairobi Kiambu Kenya Police"))
        self.assertTrue(0 <= result.confidence <= 1)
        self.assertEqual(result.evidence["confidence_kind"], "normalized_evidence_support_not_probability")
        self.assertIn("Kiambu", result.evidence["kenyan_counties"])
        self.assertIn("Kenya Police", result.evidence["kenyan_institutions"])


if __name__ == "__main__": unittest.main()
