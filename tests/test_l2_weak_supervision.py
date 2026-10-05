"""Synthetic weak-label coverage and explicit uncertainty; no real articles."""
from dataclasses import asdict
import unittest

from annotations.l2_weak_supervision import WeakSupervisor, weak_method_version


class WeakSupervisionTests(unittest.TestCase):
    def setUp(self):
        self.engine = WeakSupervisor()

    def classify(self, body, title="Synthetic news", **extras):
        return self.engine.evaluate(dict(title=title, article_text=body, **extras))

    def test_strong_categories(self):
        for text in ("Sexual assault was reported.", "Police charged a suspect with defilement.",
                     "The report discusses intimate partner violence.", "An initiative addresses FGM.",
                     "Campaigners discuss forced marriage.", "The report discusses femicide."):
            with self.subTest(text=text):
                self.assertEqual(self.classify(text).label, "gbv")

    def test_explicit_title_and_substantive_discussion(self):
        self.assertEqual(self.classify("A policy was debated.", "Gender-based violence prevention").label, "gbv")
        self.assertEqual(self.classify("Gender based violence affects access. Funding for gender based violence services was discussed.").label, "gbv")

    def test_strong_non_gbv_crime_and_general_violence(self):
        for text in ("Police investigated car theft.", "The military offensive continued.", "Mahakama inachunguza ufisadi."):
            self.assertEqual(self.classify(text).label, "not_gbv")

    def test_conflict_is_borderline(self):
        result = self.classify("A robbery and sexual assault were reported.")
        self.assertEqual(result.label, "borderline")
        self.assertIn("conflicting_evidence", result.reason_codes)

    def test_insufficient_and_ambiguous_evidence(self):
        for text in ("A school opened.", "Violence was reported.", "A wife was killed.", "Trafficking was investigated.",
                     "Sexual exploitation was discussed."):
            self.assertEqual(self.classify(text).label, "borderline")

    def test_multilingual_and_code_switching(self):
        for text in ("Mahakama inachunguza ubakaji.", "Ukeketaji was discussed by campaigners.", "Police said alibakwa."):
            result = self.classify(text)
            self.assertEqual(result.label, "gbv")
            vote = next(item for item in result.evidence["votes"] if item["labeling_function"] == "LF_multilingual_gbv_terms")
            self.assertEqual(vote["vote"], "GBV")

    def test_unicode_case_boundaries(self):
        self.assertEqual(self.classify("ＳＥＸＵＡＬ ASSAULT").label, "gbv")
        self.assertEqual(self.classify("Gender—based violence", title="Gender—based violence").label, "gbv")
        for text in ("Grapefruit is sold.", "An assaultive word appears.", "fgmarkets opened."):
            self.assertEqual(self.classify(text).label, "borderline")

    def test_negated_signal_is_uncertain(self):
        self.assertEqual(self.classify("Police said it was not sexual assault.").label, "borderline")

    def test_incidental_mention_abstains(self):
        result = self.classify("Roads were opened. Farmers spoke. A budget passed. Gender based violence was mentioned. Schools reopened.")
        self.assertEqual(result.label, "borderline")
        vote = next(v for v in result.evidence["votes"] if v["labeling_function"] == "LF_incidental_gbv_mention")
        self.assertEqual(vote["vote"], "ABSTAIN")
        self.assertTrue(vote["matched_terms"])

    def test_explainability_determinism_privacy_and_version(self):
        article = {"title": "Synthetic", "article_text": "Synthetic private name reported sexual assault."}
        first = self.engine.evaluate(article)
        self.assertEqual(asdict(first), asdict(self.engine.evaluate(article)))
        self.assertEqual(first.method_version, weak_method_version())
        self.assertEqual(first.confidence, None)
        self.assertNotIn("Synthetic private name", str(first.evidence))
        self.assertEqual(sum(first.evidence[key] for key in ("gbv_votes", "not_gbv_votes", "abstain_votes")), len(first.evidence["votes"]))
        self.assertEqual(first.evidence["rule_version"], "gbv-relevance-rules-v1.0")

    def test_publisher_and_language_identity_do_not_decide(self):
        for publisher in ("nation", "foreign", "taifaleo"):
            self.assertEqual(self.classify("A school opened.", source=publisher, language="sw").label, "borderline")
