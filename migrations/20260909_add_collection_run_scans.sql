CREATE TABLE public.collection_run_scans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_run_id UUID NOT NULL REFERENCES public.collection_runs(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    capture_month DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    index_pages INTEGER NOT NULL DEFAULT 0,
    candidate_count INTEGER NOT NULL DEFAULT 0,
    fetch_attempts INTEGER NOT NULL DEFAULT 0,
    articles_saved INTEGER NOT NULL DEFAULT 0,
    duplicates_skipped INTEGER NOT NULL DEFAULT 0,
    errors_count INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NULL,
    finished_at TIMESTAMPTZ NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT collection_run_scans_run_source_month_key
        UNIQUE (collection_run_id, source, capture_month),
    CONSTRAINT collection_run_scans_source_check
        CHECK (source IN ('nation', 'citizen', 'standard', 'star')),
    CONSTRAINT collection_run_scans_status_check
        CHECK (status IN ('pending', 'running', 'index_exhausted',
                          'index_exhausted_with_gaps', 'fetch_limit',
                          'index_page_limit', 'index_failed'))
);

CREATE INDEX idx_collection_run_scans_collection_run_id
    ON public.collection_run_scans (collection_run_id);
CREATE INDEX idx_collection_run_scans_source
    ON public.collection_run_scans (source);
CREATE INDEX idx_collection_run_scans_capture_month
    ON public.collection_run_scans (capture_month);
CREATE INDEX idx_collection_run_scans_status
    ON public.collection_run_scans (status);

ALTER TABLE public.collection_run_scans ENABLE ROW LEVEL SECURITY;
