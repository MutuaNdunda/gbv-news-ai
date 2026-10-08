BEGIN;

-- Nullable: historical runs have no trustworthy worker heartbeat/attempt identity.
ALTER TABLE public.collection_runs
    ADD COLUMN IF NOT EXISTS last_heartbeat_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS stop_requested_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS stop_requested_reason TEXT,
    ADD COLUMN IF NOT EXISTS finalization_reason TEXT,
    ADD COLUMN IF NOT EXISTS worker_token UUID;

CREATE INDEX IF NOT EXISTS idx_collection_runs_running_heartbeat
    ON public.collection_runs (last_heartbeat_at) WHERE status = 'running';

COMMIT;
