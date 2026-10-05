"""Executed Flask/SQL integration with synthetic articles only."""
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup
from sqlalchemy import select

from annotations.l2_config import MODEL_METHOD
from annotations.l2_training import bootstrap_methods
from database.models import AutomatedAnnotation, HumanValidation
from tests.test_human_review import ReviewFixture


class L2ReviewFixture(ReviewFixture):
    def setUp(self):
        super().setUp()
        original_methods = self.service.methods
        self.service.methods = lambda mode="model": (original_methods("weak") if mode == "weak" else
            {**bootstrap_methods(), "L2": "l2-ui-model", "L2_method_name": MODEL_METHOD})
        self.l2 = []
        with self.sessions.begin() as session:
            gates = self.matching("L1", "kenya") + self.matching("L1", "ambiguous")[:3]
            for index, gate in enumerate(gates):
                if gate.label != "kenya":
                    new_gate = AutomatedAnnotation(id=uuid4(), article_id=gate.article_id,
                        article_version_id=gate.article_version_id, annotation_run_id=self.run.id,
                        prerequisite_annotation_id=gate.prerequisite_annotation_id, layer="L1", label="kenya",
                        method_name=gate.method_name, method_version=gate.method_version,
                        evidence={}, reason_codes=[], created_at=self.now + timedelta(minutes=10 + index))
                    session.add(new_gate)
                    session.flush()
                    gate = new_gate
                if index == 3:
                    continue  # One eligible record stays pending.
                row = AutomatedAnnotation(id=uuid4(), article_id=gate.article_id,
                    article_version_id=gate.article_version_id, annotation_run_id=self.run.id,
                    prerequisite_annotation_id=gate.id, layer="L2", label=["gbv", "not_gbv", "borderline"][index],
                    confidence=[.9, .1, .5][index], method_name=MODEL_METHOD, method_version="l2-ui-model",
                    evidence={"gbv_probability": [.9, .1, .5][index], "model_version": "synthetic-model-v1",
                        "confidence_kind": "uncalibrated_softmax_probability", "positive_threshold": .8,
                        "negative_threshold": .2, "threshold_status": "UNVALIDATED ENGINEERING THRESHOLDS"},
                    reason_codes=["synthetic_prediction"], created_at=self.now + timedelta(minutes=20 + index))
                session.add(row)
                self.l2.append(row)
            weak = AutomatedAnnotation(id=uuid4(), article_id=self.l2[0].article_id,
                article_version_id=self.l2[0].article_version_id, annotation_run_id=self.run.id,
                prerequisite_annotation_id=self.l2[0].prerequisite_annotation_id, layer="L2", label="borderline",
                method_name=bootstrap_methods()["L2_method_name"], method_version=bootstrap_methods()["L2"],
                evidence={"votes": [{"labeling_function": "LF_synthetic", "vote": "ABSTAIN"}], "rule_version": "synthetic"},
                reason_codes=[], created_at=self.now + timedelta(minutes=40))
            session.add(weak)
            self.weak = weak


class L2UITests(L2ReviewFixture):
    def test_dashboard_live_counts_clickable_labels_pending_and_no_body_reads(self):
        data = self.service.overview()
        self.assertEqual(data["counts"]["L2"], {"gbv": 1, "not_gbv": 1, "borderline": 1})
        self.assertEqual((data["eligible_l2"], data["pending_l2"]), (4, 1))
        html = self.client.get("/annotations").get_data(as_text=True)
        self.assertIn("L2 · 3 annotated", html)
        self.assertIn("4 eligible", html)
        for label in ("gbv", "not_gbv", "borderline"):
            self.assertIn("/annotations/l2?label=" + label, html)
        self.assertIn("/annotations/l2?pending=1", html)
        self.objects.read_json.assert_not_called()

    def test_filtered_paginated_model_results_and_prerequisite(self):
        response = self.client.get("/annotations/l2?label=gbv&source=citizen&model_version=synthetic-model-v1")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("0.9", html)
        self.assertIn("l2-ui-model", html)
        self.assertIn(str(self.l2[0].prerequisite_annotation_id), html)
        self.assertIn(str(self.l2[0].id), html)
        self.assertNotIn(str(self.l2[1].id), html)
        html = self.client.get("/annotations/l2?page=1").get_data(as_text=True)
        self.assertIn("Next page", html)
        self.assertIn("Page 1 · 3 results", html)
        self.assertIn("Page 2 · 3 results", self.client.get("/annotations/l2?page=2").get_data(as_text=True))
        self.assertIn("0 results", self.client.get("/annotations/l2?method_version=wrong").get_data(as_text=True))
        self.assertIn("1 results", self.client.get("/annotations/l2?pending=1").get_data(as_text=True))
        self.objects.read_json.assert_not_called()

    def test_weak_inspection_links_to_protected_human_review(self):
        html = self.client.get("/annotations/l2?mode=weak").get_data(as_text=True)
        self.assertIn("weak bootstrap", html)
        self.assertIn(str(self.weak.id), html)
        path = f"/annotations/l2/{self.weak.id}"
        response = self.client.get(path, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("LF_synthetic", response.get_data(as_text=True))
        self.assertNotIn("Save Review", response.get_data(as_text=True))
        self.assertEqual(self.client.post(path, data={}).status_code, 405)
        self.assertEqual(self.client.get(f"/annotations/review/{self.weak.id}").status_code, 200)
        self.assertIn("Unlock review", response.get_data(as_text=True))
        with self.sessions() as session:
            self.assertEqual(len(session.scalars(select(HumanValidation)).all()), 0)

    def test_detail_l1_model_threshold_metadata_protected_body_and_history(self):
        annotation = self.l2[0]
        path = f"/annotations/l2/{annotation.id}"
        html = self.client.get(path, follow_redirects=True).get_data(as_text=True)
        self.assertIn("Exact L1 prerequisite", html)
        self.assertIn("uncalibrated_softmax_probability", html)
        self.assertIn("Positive threshold", html)
        self.assertIn("synthetic-model-v1", html)
        self.assertIn("l1-v2.0", html)
        self.objects.read_json.assert_not_called()
        self.unlock(self.matching("L1", "kenya")[0])
        response = self.client.get(path, follow_redirects=True)
        self.assertIn("Synthetic article 0: community", response.get_data(as_text=True))
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")
        html = self.client.get(f"/articles/{annotation.article_id}").get_data(as_text=True)
        self.assertIn(path, html)
        self.assertIn("GBV probability: 0.9", html)
        self.assertIn("L1 prerequisite", html)

    def test_new_l1_makes_old_l2_historical_but_inspectable(self):
        with self.sessions.begin() as session:
            old = session.get(AutomatedAnnotation, self.l2[0].prerequisite_annotation_id)
            session.add(AutomatedAnnotation(id=uuid4(), article_id=old.article_id, article_version_id=old.article_version_id,
                annotation_run_id=old.annotation_run_id, prerequisite_annotation_id=old.prerequisite_annotation_id,
                layer="L1", label="kenya", method_name=old.method_name, method_version=old.method_version,
                evidence={}, reason_codes=[], created_at=self.now + timedelta(days=1)))
        data = self.service.overview()
        self.assertEqual((sum(data["counts"]["L2"].values()), data["pending_l2"]), (2, 2))
        self.assertEqual(self.client.get(f"/annotations/l2/{self.l2[0].id}", follow_redirects=True).status_code, 200)

    def test_invalid_filters_and_previous_l0_l1_routes(self):
        for query in ("label=kenya", "source=invalid", "mode=bad", "review_status=bad", "pending=1&label=gbv", "pending=1&review_status=confirmed"):
            self.assertEqual(self.client.get("/annotations/l2?" + query).status_code, 400)
        for path in ("/annotations/l0", "/annotations/l1"):
            self.assertEqual(self.client.get(path).status_code, 200)

    def test_weak_label_tiles_count_current_cohort_and_preserve_filters(self):
        methods = bootstrap_methods()
        with self.sessions.begin() as session:
            for index, model in enumerate(self.l2):
                label = ["gbv", "gbv", "not_gbv"][index]
                row = AutomatedAnnotation(id=uuid4(), article_id=model.article_id,
                    article_version_id=model.article_version_id, annotation_run_id=self.run.id,
                    prerequisite_annotation_id=model.prerequisite_annotation_id, layer="L2", label=label,
                    method_name=methods["L2_method_name"], method_version=methods["L2"], evidence={},
                    reason_codes=[], created_at=self.now + timedelta(minutes=30 + index))
                session.add(row)
            # Newer incompatible history must not inflate any tile.
            session.add(AutomatedAnnotation(id=uuid4(), article_id=self.weak.article_id,
                article_version_id=self.weak.article_version_id, annotation_run_id=self.run.id,
                prerequisite_annotation_id=self.weak.prerequisite_annotation_id, layer="L2", label="not_gbv",
                method_name=methods["L2_method_name"], method_version="old-weak-rules", evidence={},
                reason_codes=[], created_at=self.now + timedelta(minutes=50)))
        filters = {"mode": "weak", "source": "citizen", "method_version": methods["L2"], "label": "gbv"}
        self.assertEqual(self.service.l2_label_counts(filters), {"gbv": 1, "not_gbv": 1, "borderline": 1})
        response = self.client.get("/annotations/l2", query_string={**filters, "page": 2})
        self.assertEqual(response.status_code, 200)
        soup = BeautifulSoup(response.data, "html.parser")
        tiles = soup.find(attrs={"aria-label": "Weak bootstrap label counts"}).find_all("a")
        self.assertEqual(len(tiles), 3)
        for tile, label in zip(tiles, ("gbv", "not_gbv", "borderline")):
            self.assertEqual(tile.find("span").text, label)
            self.assertEqual(tile.find("strong").text, "1")
            query = parse_qs(urlsplit(tile["href"]).query)
            self.assertEqual(query["mode"], ["weak"])
            self.assertEqual(query["source"], ["citizen"])
            self.assertEqual(query["method_version"], [methods["L2"]])
            self.assertEqual(query["label"], [label])
            self.assertEqual(query["page"], ["1"])
            self.assertEqual(self.client.get(tile["href"]).status_code, 200)
        self.assertEqual(tiles[0].get("aria-current"), "true")
        self.objects.read_json.assert_not_called()

    def test_weak_tiles_show_zero_counts_for_empty_source_scope(self):
        response = self.client.get("/annotations/l2?mode=weak&source=star")
        soup = BeautifulSoup(response.data, "html.parser")
        tiles = soup.find(attrs={"aria-label": "Weak bootstrap label counts"}).find_all("a")
        self.assertEqual([tile.find("strong").text for tile in tiles], ["0", "0", "0"])
        self.assertNotIn("Weak bootstrap label counts", self.client.get("/annotations/l2").get_data(as_text=True))
