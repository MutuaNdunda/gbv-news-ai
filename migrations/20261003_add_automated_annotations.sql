-- Additive annotation lineage; does not modify article content or collection rows.
BEGIN;
CREATE TABLE public.annotation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_run_id UUID NULL REFERENCES public.collection_runs(id),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ NULL,
    status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running','completed','completed_with_errors','failed','interrupted')),
    requested_layers JSONB NOT NULL,
    trigger_type TEXT NOT NULL CHECK (trigger_type IN ('cli','manual_ui','post_collection','scheduled')),
    requested_count INTEGER NOT NULL DEFAULT 0 CHECK (requested_count >= 0),
    processed_count INTEGER NOT NULL DEFAULT 0 CHECK (processed_count >= 0),
    success_count INTEGER NOT NULL DEFAULT 0 CHECK (success_count >= 0),
    failed_count INTEGER NOT NULL DEFAULT 0 CHECK (failed_count >= 0),
    skipped_count INTEGER NOT NULL DEFAULT 0 CHECK (skipped_count >= 0),
    method_versions JSONB NOT NULL,
    configuration JSONB NOT NULL,
    error_summary JSONB NULL,
    summary JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE public.automated_annotations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id UUID NOT NULL REFERENCES public.articles(id),
    article_version_id UUID NOT NULL REFERENCES public.article_versions(id),
    annotation_run_id UUID NOT NULL REFERENCES public.annotation_runs(id),
    prerequisite_annotation_id UUID NULL REFERENCES public.automated_annotations(id),
    layer TEXT NOT NULL CHECK (layer IN ('L0','L1','L2','L3','L4','L5')),
    label TEXT NOT NULL,
    confidence DOUBLE PRECISION NULL CHECK (confidence BETWEEN 0 AND 1),
    evidence JSONB NULL,
    reason_codes JSONB NULL,
    method_name TEXT NOT NULL,
    method_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (layer <> 'L0' OR label IN ('valid','needs_review','invalid')),
    CHECK (layer <> 'L1' OR label IN ('kenya','not_kenya','ambiguous')),
    CHECK (layer <> 'L1' OR prerequisite_annotation_id IS NOT NULL)
);
CREATE INDEX idx_annotation_runs_started_at ON public.annotation_runs(started_at DESC);
CREATE INDEX idx_auto_annotations_version_layer_method
    ON public.automated_annotations(article_version_id, layer, method_version, created_at DESC);
CREATE INDEX idx_auto_annotations_article_id ON public.automated_annotations(article_id);
CREATE INDEX idx_auto_annotations_run_id ON public.automated_annotations(annotation_run_id);
CREATE INDEX idx_auto_annotations_layer_label ON public.automated_annotations(layer, label);
CREATE INDEX idx_auto_annotations_method_version ON public.automated_annotations(method_version);
-- Existing backend PostgreSQL role performs writes; no anonymous browser API grants.
ALTER TABLE public.annotation_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.automated_annotations ENABLE ROW LEVEL SECURITY;
COMMIT;
