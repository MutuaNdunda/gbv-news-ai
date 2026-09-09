"""Read-only infrastructure health checks."""

from sqlalchemy import text


class StorageService:
    def __init__(self, sessions, objects):
        self.sessions = sessions
        self.objects = objects

    def health(self):
        tables = ["public.collection_runs", "public.collection_run_scans", "public.articles", "public.article_versions"]
        result = {"database": False, "tables": False, "raw": False, "processed": False, "runs": False}
        try:
            with self.sessions() as session:
                session.execute(text("SELECT 1"))
                found = session.execute(text("SELECT name, to_regclass(name) IS NOT NULL FROM unnest(CAST(:names AS text[])) AS t(name)"), {"names": tables}).all()
                result["database"] = True
                result["tables"] = all(exists for _, exists in found)
        except Exception:
            pass
        for role in ("raw", "processed", "runs"):
            try:
                result[role] = self.objects.bucket_accessible(role)
            except Exception:
                result[role] = False
        result["ok"] = all(result.values())
        return result
