-- Extend append-only human review to L2. Existing rows, RLS, indexes and FKs remain intact.
-- Apply after 20261004_add_human_validations.sql and 20261005_add_l2_annotations.sql.
BEGIN;
ALTER TABLE public.human_validations
    DROP CONSTRAINT human_validation_layer_check,
    DROP CONSTRAINT human_validation_machine_label_check,
    DROP CONSTRAINT human_validation_label_check,
    ADD CONSTRAINT human_validation_layer_check CHECK (layer IN ('L0','L1','L2')),
    ADD CONSTRAINT human_validation_machine_label_check CHECK (
        (layer = 'L0' AND machine_label IN ('valid','needs_review','invalid')) OR
        (layer = 'L1' AND machine_label IN ('kenya','not_kenya','ambiguous')) OR
        (layer = 'L2' AND machine_label IN ('gbv','not_gbv','borderline'))),
    ADD CONSTRAINT human_validation_label_check CHECK (human_label IS NULL OR
        (layer = 'L0' AND human_label IN ('valid','needs_review','invalid')) OR
        (layer = 'L1' AND human_label IN ('kenya','not_kenya','ambiguous')) OR
        (layer = 'L2' AND human_label IN ('gbv','not_gbv','borderline')));
COMMIT;
