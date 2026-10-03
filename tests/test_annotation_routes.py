"""Read-only annotation routes and explicit bounded token/CSRF execution."""

from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from uuid import uuid4

from app import create_app


class FakeAnnotations:
    def __init__(self):
        self.called = []
        self.run_id = uuid4()
    def overview(self):
        return {"total_versions": 1, "pending_l0": 1, "pending_l1": 0,
                "counts": {"L0": {"valid": 0, "needs_review": 0, "invalid": 0},
                           "L1": {"kenya": 0, "not_kenya": 0, "ambiguous": 0}}, "recent_runs": []}
    def runs(self, page, per_page): return [], 0
    def results(self, layer, filters, page, per_page): return [], 0
    def run_detail(self, run_id):
        if run_id != self.run_id: return None
        run = SimpleNamespace(id=run_id, status="completed", trigger_type="cli", requested_layers=["L0", "L1"],
                              started_at=datetime.now(timezone.utc), completed_at=None, requested_count=1,
                              processed_count=1, success_count=1, failed_count=0, skipped_count=0,
                              method_versions={"L0": "l0-v1.0"}, summary={}, error_summary=None)
        return {"run": run, "breakdown": [("L0", "valid", 1)]}
    def run(self, layers, limit):
        self.called.append((layers, limit))
        return {"run_id": str(self.run_id)}


class AnnotationRouteTests(unittest.TestCase):
    def setUp(self):
        self.service = FakeAnnotations()
        self.app = create_app({"TESTING": True, "ANNOTATION_UI_ENABLED": True,
                               "ANNOTATION_UI_TOKEN": "t" * 40, "SECRET_KEY": "s" * 40},
                              {"annotations": self.service})
        self.client = self.app.test_client()

    def form(self):
        self.client.get("/annotations")
        with self.client.session_transaction() as stored: csrf = stored["annotation_csrf"]
        return {"layers": "l0,l1", "limit": "20", "execution_token": "t" * 40, "csrf_token": csrf}

    def test_read_only_routes_and_run_detail(self):
        for path in ("/annotations", "/annotations/runs", "/annotations/l0", "/annotations/l1",
                     f"/annotations/runs/{self.service.run_id}"):
            self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.client.get(f"/annotations/runs/{uuid4()}").status_code, 404)

    def test_disabled_trigger_rejected_and_form_hidden(self):
        self.app.config["ANNOTATION_UI_ENABLED"] = False
        self.assertNotIn("execution_token", self.client.get("/annotations").get_data(as_text=True))
        self.assertEqual(self.client.post("/annotations/run", data={}).status_code, 403)
        self.assertEqual(self.service.called, [])

    def test_csrf_and_execution_token_required(self):
        form = self.form()
        for change in ({"csrf_token": "bad"}, {"execution_token": "bad"}):
            self.assertEqual(self.client.post("/annotations/run", data={**form, **change}).status_code, 403)
        self.assertEqual(self.service.called, [])

    def test_bounded_safe_trigger_and_token_replay_rejected(self):
        form = self.form()
        response = self.client.post("/annotations/run", data=form)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.service.called, [(["l0", "l1"], 20)])
        self.assertEqual(self.client.post("/annotations/run", data=form).status_code, 403)

    def test_public_plain_http_cannot_execute_and_limit_is_enforced(self):
        form = self.form()
        self.assertEqual(self.client.post("/annotations/run", data=form,
                                         environ_overrides={"REMOTE_ADDR": "192.0.2.10"}).status_code, 403)
        for limit in ("0", "21", "not a number"):
            self.assertEqual(self.client.post("/annotations/run", data={**form, "limit": limit}).status_code, 400)
        self.assertEqual(self.service.called, [])

    def test_short_secrets_disable_execution_and_unicode_token_fails_safely(self):
        form = self.form()
        self.assertEqual(self.client.post("/annotations/run", data={**form, "execution_token": "invalid 🛑"}).status_code, 403)
        self.app.config["SECRET_KEY"] = "too-short"
        self.assertEqual(self.client.post("/annotations/run", data=form).status_code, 403)
        self.assertEqual(self.service.called, [])

    def test_secure_remote_request_can_execute_with_valid_tokens(self):
        response = self.client.post("/annotations/run", data=self.form(), base_url="https://localhost",
                                    environ_overrides={"REMOTE_ADDR": "192.0.2.10"})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.service.called, [(["l0", "l1"], 20)])


if __name__ == "__main__": unittest.main()
