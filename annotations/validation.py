"""Human-validation contracts, distinct from automated scoring and reference labels."""

LABELS = {"L0": ("valid", "needs_review", "invalid"),
          "L1": ("kenya", "not_kenya", "ambiguous"),
          "L2": ("gbv", "not_gbv", "borderline")}
DECISIONS = {"confirmed": "Confirm machine annotation", "corrected": "Correct machine annotation",
             "unable_to_determine": "Unable to determine", "needs_adjudication": "Needs adjudication"}
ERROR_CATEGORIES = {"": "No error category", "extraction_incomplete": "Incomplete extraction",
    "publication_date": "Publication date", "provenance": "Provenance",
    "geographic_evidence": "Geographic evidence", "ambiguity": "Ambiguity",
    "rule_false_positive": "Rule false positive", "rule_false_negative": "Rule false negative",
    "other": "Other"}
STATUSES = {"not_reviewed": "Not reviewed", "confirmed": "Reviewed — confirmed",
            "corrected": "Reviewed — corrected", "unable_to_determine": "Unable to determine",
            "needs_adjudication": "Needs adjudication"}

REVIEW_FILTERS = {**STATUSES, "reviewed": "All recorded reviews"}


class ReviewConflict(ValueError):
    """Another review was saved after the displayed form was loaded."""


def validate_review(annotation, decision, human_label, error_category, reason, notes):
    """Derive confirmation labels, reject cross-layer labels and unresolved decisions."""
    if annotation.layer not in LABELS or annotation.label not in LABELS[annotation.layer]:
        raise ValueError("Only supported L0/L1/L2 machine labels can be reviewed")
    if decision not in DECISIONS:
        raise ValueError("Choose a supported review decision")
    human_label = human_label or None
    if decision == "confirmed" and human_label is None:
        human_label = annotation.label
    if human_label is not None and human_label not in LABELS[annotation.layer]:
        raise ValueError("Human label does not belong to this annotation layer")
    if decision == "confirmed" and human_label != annotation.label:
        raise ValueError("Confirmation must retain the machine label")
    if decision == "corrected" and (human_label is None or human_label == annotation.label):
        raise ValueError("Correction requires a different label")
    if decision in ("unable_to_determine", "needs_adjudication") and human_label is not None:
        raise ValueError("Unresolved decisions must leave the human label unset")
    if error_category not in ERROR_CATEGORIES:
        raise ValueError("Choose a supported reason category")
    reason, notes = (reason or "").strip(), (notes or "").strip()
    if len(reason) > 1000 or len(notes) > 4000:
        raise ValueError("Reason is limited to 1,000 characters; notes to 4,000")
    if decision == "corrected" and (not error_category or not reason):
        raise ValueError("Corrections require an error category and reason")
    return dict(review_decision=decision, human_label=human_label, error_category=error_category or None,
                review_reason=reason or None, notes=notes or None)
