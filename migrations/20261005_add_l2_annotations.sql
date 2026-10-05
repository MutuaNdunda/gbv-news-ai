-- Add L2 constraints without rewriting historical L0/L1 results.
BEGIN;
ALTER TABLE public.automated_annotations
    ADD CONSTRAINT automated_annotations_l2_label_check
    CHECK (layer <> 'L2' OR label IN ('gbv','not_gbv','borderline')),
    ADD CONSTRAINT automated_annotations_l2_prerequisite_check
    CHECK (layer <> 'L2' OR prerequisite_annotation_id IS NOT NULL);
CREATE INDEX idx_auto_annotations_l2_identity
    ON public.automated_annotations(article_version_id, method_name, method_version,
                                   prerequisite_annotation_id, created_at DESC)
    WHERE layer = 'L2';
-- A stored L2 prerequisite must belong to the same extraction and be L1 Kenya.
-- Current method compatibility is resolved by the application, before ranking.
CREATE FUNCTION public.validate_l2_prerequisite() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.layer = 'L2' AND NOT EXISTS (
        SELECT 1 FROM public.automated_annotations p
        WHERE p.id = NEW.prerequisite_annotation_id AND p.layer = 'L1'
          AND p.label = 'kenya' AND p.article_id = NEW.article_id
          AND p.article_version_id = NEW.article_version_id
    ) THEN
        RAISE EXCEPTION 'L2 requires same-version L1 Kenya prerequisite';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER automated_annotations_l2_prerequisite
    BEFORE INSERT OR UPDATE ON public.automated_annotations
    FOR EACH ROW EXECUTE FUNCTION public.validate_l2_prerequisite();
COMMIT;
