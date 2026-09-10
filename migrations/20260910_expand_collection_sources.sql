ALTER TABLE public.articles
    DROP CONSTRAINT IF EXISTS articles_source_check;

ALTER TABLE public.articles
    ADD CONSTRAINT articles_source_check
    CHECK (source IN ('nation', 'citizen', 'standard', 'star', 'tuko', 'kenyans'));

ALTER TABLE public.collection_run_scans
    DROP CONSTRAINT IF EXISTS collection_run_scans_source_check;

ALTER TABLE public.collection_run_scans
    ADD CONSTRAINT collection_run_scans_source_check
    CHECK (source IN ('nation', 'citizen', 'standard', 'star', 'tuko', 'kenyans'));
