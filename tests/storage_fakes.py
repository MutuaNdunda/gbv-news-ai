from collections import defaultdict
from contextlib import nullcontext
from uuid import uuid4

from storage.gcs import ObjectReference


class FakeObjects:
    def __init__(self):
        self.data = {}
        self.writes = []

    def write_bytes(self, role, name, payload, content_type, create_only=False):
        key = (role, name)
        if create_only and key in self.data and self.data[key] != payload:
            raise RuntimeError("object collision")
        self.data[key] = payload
        self.writes.append(key)
        return ObjectReference(f"gs://fake-{role}/{name}", "1")

    def write_json(self, role, name, value, create_only=False):
        import json
        return self.write_bytes(role, name,
                                (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode(),
                                "application/json", create_only=create_only)

    def read_bytes(self, role, name):
        return self.data.get((role, name))

    def read_json(self, role, name):
        import json
        value = self.read_bytes(role, name)
        return json.loads(value) if value is not None else None


class FakeArticles:
    def __init__(self):
        self.items = []
        self.versions = set()
        self.fail_persist = False

    def existing_identities(self):
        urls = {item["canonical_url"] for item, _ in self.items}
        hashes = {(item["source"], item["content_hash"]) for item, _ in self.items}
        return urls, hashes

    def persist(self, article, run_id, *references):
        if self.fail_persist:
            raise RuntimeError("database unavailable")
        key = (article["source"], article["canonical_url"],
               article["content_hash"], article["parser_version"])
        if key in self.versions:
            return uuid4(), False
        self.versions.add(key)
        self.items.append((dict(article), run_id))
        return uuid4(), True

    def counts(self, sources, months, run_id=None):
        counts = defaultdict(int)
        for item, item_run in self.items:
            month = item.get("publication_month") or item.get("published_at", "")[:7]
            if item["source"] in sources and month in months and (run_id is None or item_run == run_id):
                counts[(item["source"], month)] += 1
        return {(source, month): counts[(source, month)]
                for source in sources for month in months}


class FakeRuns:
    def __init__(self):
        self.ids = {}
        self.configs = {}
        self.statuses = {}

    def resolve(self, name, config):
        if name in self.configs and self.configs[name] != config:
            raise ValueError("Resume configuration differs from saved run")
        self.configs[name] = config
        self.ids.setdefault(name, uuid4())
        self.statuses[name] = "running"
        return self.ids[name]

    def set_status(self, run_id, status):
        name = next(name for name, value in self.ids.items() if value == run_id)
        self.statuses[name] = status

    def lock(self, run_name):
        return nullcontext()


class FakeScans:
    def __init__(self):
        self.rows = {}
        self.calls = 0

    def update(self, run_id, source, capture_month, scan):
        self.calls += 1
        self.rows[(run_id, source, capture_month)] = dict(scan)
