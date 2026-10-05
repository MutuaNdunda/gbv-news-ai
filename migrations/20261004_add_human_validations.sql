-- Separate, append-only application review history. Existing machine rows are untouched.
BEGIN;
CREATE TABLE public.human_validations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    automated_annotation_id UUID NOT NULL REFERENCES public.automated_annotations(id),
    article_id UUID NOT NULL REFERENCES public.articles(id),
    article_version_id UUID NOT NULL REFERENCES public.article_versions(id),
    layer TEXT NOT NULL CONSTRAINT human_validation_layer_check CHECK (layer IN ('L0','L1')),
    machine_label TEXT NOT NULL,
    machine_confidence DOUBLE PRECISION NULL CHECK (machine_confidence BETWEEN 0 AND 1),
    human_label TEXT NULL,
    review_decision TEXT NOT NULL CONSTRAINT human_validation_decision_check
        CHECK (review_decision IN ('confirmed','corrected','unable_to_determine','needs_adjudication')),
    review_reason TEXT NULL CHECK (length(review_reason) <= 1000),
    error_category TEXT NULL CHECK (error_category IN ('extraction_incomplete','publication_date','provenance',
        'geographic_evidence','ambiguity','rule_false_positive','rule_false_negative','other')),
    notes TEXT NULL CHECK (length(notes) <= 4000),
    reviewer_identity TEXT NOT NULL,
    guideline_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    supersedes_validation_id UUID NULL REFERENCES public.human_validations(id),
    CONSTRAINT human_validation_machine_label_check CHECK (
        (layer = 'L0' AND machine_label IN ('valid','needs_review','invalid')) OR
        (layer = 'L1' AND machine_label IN ('kenya','not_kenya','ambiguous'))),
    CONSTRAINT human_validation_label_check CHECK (human_label IS NULL OR
        (layer = 'L0' AND human_label IN ('valid','needs_review','invalid')) OR
        (layer = 'L1' AND human_label IN ('kenya','not_kenya','ambiguous'))),
    CONSTRAINT human_validation_decision_label_check CHECK (
        (review_decision = 'confirmed' AND human_label IS NOT NULL AND human_label = machine_label) OR
        (review_decision = 'corrected' AND human_label IS NOT NULL AND human_label <> machine_label) OR
        (review_decision IN ('unable_to_determine','needs_adjudication') AND human_label IS NULL)),
    CONSTRAINT human_validation_identity_check CHECK (length(trim(reviewer_identity)) > 0 AND length(trim(guideline_version)) > 0),
    CONSTRAINT human_validation_correction_reason_check CHECK (review_decision <> 'corrected' OR
        (error_category IS NOT NULL AND review_reason IS NOT NULL AND length(trim(review_reason)) > 0)),
    CONSTRAINT uq_human_validation_successor UNIQUE (supersedes_validation_id)
);
CREATE INDEX idx_human_validation_annotation_time ON public.human_validations(automated_annotation_id, created_at DESC);
CREATE INDEX idx_human_validation_article_version ON public.human_validations(article_version_id);
CREATE UNIQUE INDEX uq_human_validation_root ON public.human_validations(automated_annotation_id)
    WHERE supersedes_validation_id IS NULL;
-- No anonymous/browser grants. The configured backend role owns writes.
ALTER TABLE public.human_validations ENABLE ROW LEVEL SECURITY;
COMMIT;
