-- Additive L2 validation workflow. Preflight target and existing names before applying.
BEGIN;

CREATE TABLE public.validation_batches (
	id UUID NOT NULL,
	name TEXT NOT NULL,
	layer TEXT NOT NULL,
	purpose TEXT NOT NULL,
	model_method_name TEXT NOT NULL,
	model_method_version TEXT NOT NULL,
	model_version TEXT NOT NULL,
	guideline_version TEXT NOT NULL,
	sampling_strategy TEXT NOT NULL,
	seed INTEGER NOT NULL,
	requested_size INTEGER NOT NULL,
	status TEXT NOT NULL,
	protect_from_training BOOLEAN NOT NULL,
	configuration JSONB NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	frozen_at TIMESTAMP WITH TIME ZONE,
	completed_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	CONSTRAINT uq_validation_batch_name UNIQUE (name),
	CONSTRAINT validation_batch_layer_check CHECK (layer = 'L2'),
	CONSTRAINT validation_batch_purpose_check CHECK (purpose IN ('development_validation','final_test','diagnostic')),
	CONSTRAINT validation_batch_status_check CHECK (status IN ('draft','frozen','in_review','completed')),
	CONSTRAINT validation_batch_strategy_check CHECK (sampling_strategy IN ('random','stratified','enriched')),
	CONSTRAINT validation_batch_size_check CHECK (requested_size > 0),
	CONSTRAINT validation_batch_final_protection_check CHECK (purpose <> 'final_test' OR protect_from_training),
	CONSTRAINT validation_batch_diagnostic_check CHECK (sampling_strategy <> 'enriched' OR purpose = 'diagnostic')
)

;
ALTER TABLE public.validation_batches ENABLE ROW LEVEL SECURITY;

CREATE TABLE public.validation_batch_members (
	id UUID NOT NULL,
	validation_batch_id UUID NOT NULL,
	article_id UUID NOT NULL,
	article_version_id UUID NOT NULL,
	automated_annotation_id UUID NOT NULL,
	content_hash TEXT NOT NULL,
	source TEXT NOT NULL,
	language TEXT,
	sampling_stratum TEXT NOT NULL,
	selection_reason TEXT NOT NULL,
	selection_order INTEGER NOT NULL,
	initial_human_validation_id UUID,
	final_human_validation_id UUID,
	status TEXT NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_validation_member_version UNIQUE (validation_batch_id, article_version_id),
	CONSTRAINT uq_validation_member_annotation UNIQUE (validation_batch_id, automated_annotation_id),
	CONSTRAINT uq_validation_member_order UNIQUE (validation_batch_id, selection_order),
	CONSTRAINT validation_member_status_check CHECK (status IN ('pending','resolved','unable_to_determine','needs_adjudication')),
	CONSTRAINT validation_member_decision_check CHECK ((status = 'pending' AND initial_human_validation_id IS NULL AND final_human_validation_id IS NULL) OR (status <> 'pending' AND initial_human_validation_id IS NOT NULL AND final_human_validation_id IS NOT NULL)),
	FOREIGN KEY(validation_batch_id) REFERENCES public.validation_batches (id),
	FOREIGN KEY(article_id) REFERENCES public.articles (id),
	FOREIGN KEY(article_version_id) REFERENCES public.article_versions (id),
	FOREIGN KEY(automated_annotation_id) REFERENCES public.automated_annotations (id),
	FOREIGN KEY(initial_human_validation_id) REFERENCES public.human_validations (id),
	FOREIGN KEY(final_human_validation_id) REFERENCES public.human_validations (id)
)

;
CREATE INDEX idx_validation_member_content ON public.validation_batch_members (content_hash);
ALTER TABLE public.validation_batch_members ENABLE ROW LEVEL SECURITY;

CREATE FUNCTION public.guard_l2_validation_batch() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='UPDATE' AND OLD.status='completed' THEN
  RAISE EXCEPTION 'Completed batches are immutable';
 END IF;
 IF TG_OP='UPDATE' AND OLD.status='draft' AND NEW.status NOT IN ('draft','frozen') THEN
  RAISE EXCEPTION 'Draft batches must be frozen before review';
 END IF;
 IF TG_OP='UPDATE' AND OLD.status='draft' AND NEW.status='frozen' THEN
  IF (SELECT count(*) FROM public.validation_batch_members WHERE validation_batch_id=NEW.id) <> NEW.requested_size THEN
   RAISE EXCEPTION 'Frozen membership size mismatch';
  END IF;
 END IF;
 IF TG_OP='UPDATE' AND NEW.status='completed' AND EXISTS (
  SELECT 1 FROM public.validation_batch_members WHERE validation_batch_id=NEW.id AND initial_human_validation_id IS NULL) THEN
  RAISE EXCEPTION 'Every member needs an initial review before completion';
 END IF;
 IF TG_OP = 'DELETE' AND OLD.status <> 'draft' THEN RAISE EXCEPTION 'Frozen validation batches cannot be deleted'; END IF;
 IF TG_OP = 'UPDATE' AND OLD.status <> 'draft' THEN
  IF (to_jsonb(NEW) - ARRAY['status','completed_at']) IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['status','completed_at']) THEN
   RAISE EXCEPTION 'Frozen batch configuration is immutable';
  END IF;
  IF NOT (NEW.status = OLD.status OR (OLD.status='frozen' AND NEW.status='in_review') OR (OLD.status='in_review' AND NEW.status='completed')) THEN
   RAISE EXCEPTION 'Invalid frozen batch transition';
  END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER guard_l2_validation_batch BEFORE UPDATE OR DELETE ON public.validation_batches
 FOR EACH ROW EXECUTE FUNCTION public.guard_l2_validation_batch();
CREATE FUNCTION public.guard_l2_validation_member() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE state TEXT; a public.automated_annotations; v public.article_versions;
BEGIN
 SELECT status INTO state FROM public.validation_batches WHERE id=CASE WHEN TG_OP='DELETE' THEN OLD.validation_batch_id ELSE NEW.validation_batch_id END FOR UPDATE;
 IF TG_OP='DELETE' THEN
  IF state <> 'draft' THEN RAISE EXCEPTION 'Frozen membership cannot be deleted'; END IF;
  RETURN OLD;
 END IF;
 IF TG_OP='INSERT' AND state <> 'draft' THEN RAISE EXCEPTION 'Frozen membership cannot be extended'; END IF;
 IF TG_OP='UPDATE' THEN
  IF state='completed' THEN RAISE EXCEPTION 'Completed reference decisions are immutable'; END IF;
  IF OLD.validation_batch_id <> NEW.validation_batch_id THEN RAISE EXCEPTION 'Member cannot move batches'; END IF;
  IF state <> 'draft' AND (to_jsonb(NEW) - ARRAY['status','initial_human_validation_id','final_human_validation_id']) IS DISTINCT FROM
                         (to_jsonb(OLD) - ARRAY['status','initial_human_validation_id','final_human_validation_id']) THEN
   RAISE EXCEPTION 'Frozen membership is immutable';
  END IF;
  IF OLD.initial_human_validation_id IS NOT NULL AND OLD.initial_human_validation_id IS DISTINCT FROM NEW.initial_human_validation_id THEN
   RAISE EXCEPTION 'Initial blinded decision is immutable';
  END IF;
 END IF;
 SELECT * INTO a FROM public.automated_annotations WHERE id=NEW.automated_annotation_id;
 SELECT * INTO v FROM public.article_versions WHERE id=NEW.article_version_id;
 IF a.layer <> 'L2' OR a.article_id <> NEW.article_id OR a.article_version_id <> NEW.article_version_id OR
    v.article_id <> NEW.article_id OR v.content_hash <> NEW.content_hash OR NOT EXISTS (
       SELECT 1 FROM public.validation_batches b WHERE b.id=NEW.validation_batch_id AND b.model_method_name=a.method_name AND
       b.model_method_version=a.method_version AND b.model_version=(a.evidence->>'model_version')) THEN
  RAISE EXCEPTION 'Invalid pinned member lineage';
 END IF;
 IF NEW.initial_human_validation_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.human_validations h WHERE
    h.id=NEW.initial_human_validation_id AND h.automated_annotation_id=NEW.automated_annotation_id AND h.article_version_id=NEW.article_version_id
    AND h.article_id=NEW.article_id AND h.guideline_version=(SELECT guideline_version FROM public.validation_batches WHERE id=NEW.validation_batch_id)) THEN
  RAISE EXCEPTION 'Invalid initial review lineage';
 END IF;
 IF NEW.final_human_validation_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.human_validations h WHERE
    h.id=NEW.final_human_validation_id AND h.automated_annotation_id=NEW.automated_annotation_id AND h.article_version_id=NEW.article_version_id
    AND h.article_id=NEW.article_id AND h.guideline_version=(SELECT guideline_version FROM public.validation_batches WHERE id=NEW.validation_batch_id)) THEN
  RAISE EXCEPTION 'Invalid final review lineage';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER guard_l2_validation_member BEFORE INSERT OR UPDATE OR DELETE ON public.validation_batch_members
 FOR EACH ROW EXECUTE FUNCTION public.guard_l2_validation_member();
COMMIT;
