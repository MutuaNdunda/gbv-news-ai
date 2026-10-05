"""Explainable Kenya relevance evidence scoring, not a calibrated classifier."""

from annotations.schemas import AnnotationResult, DEFAULT_CONFIG


# v1 remains executable for historical comparisons; its resource is unchanged.
from annotations.l1_v1 import gazetteer, normalized, mentions
from annotations.geography import geographic_matches, load_index, resource_identity


def extract_evidence(title, body, version="v2"):
    if version == "v1":
        from annotations.l1_v1 import extract_evidence as legacy
        return legacy(title, body)
    data, _, _ = load_index()
    text = normalized(f"{title or ''}\n{body or ''}")
    geography = geographic_matches(text)
    institutions = sorted(name for name in data["institutions"] if mentions(text, name))
    return {"kenya_mentions": sum(mentions(text, name) for name in data["country_terms"]),
            "kenyan_places": sorted({x["canonical_name"] for x in geography}),
            "kenyan_counties": sorted({x["canonical_name"] for x in geography if x["entity_type"] == "county"}),
            "kenyan_geographic_evidence": geography,
            "kenyan_institutions": institutions,
            "ambiguous_places": sorted({x["canonical_name"] for x in geography if x["ambiguous"]}),
            "ambiguous_institutions": sorted(set(institutions) & set(data["ambiguous_institutions"])),
            "foreign_places": sorted(name for name in data["foreign_places"] if mentions(text, name)),
            "admin_terms": sorted(name for name in data["admin_terms"] if mentions(text, name)),
            "gazetteer_version": data["metadata"]["version"], "gazetteer_sha256": resource_identity()}


def evaluate_l1(article, config=DEFAULT_CONFIG):
    evidence = extract_evidence(article.get("title"), article.get("article_text"), config.l1_gazetteer)
    places = set(evidence["kenyan_places"]) - set(evidence["ambiguous_places"])
    institutions = set(evidence["kenyan_institutions"]) - set(evidence["ambiguous_institutions"])
    country = min(evidence["kenya_mentions"], 3) * config.country_weight
    support = country + min(len(places), 3) * config.place_weight + min(len(institutions), 2) * config.institution_weight
    foreign = min(len(evidence["foreign_places"]), 3) * config.foreign_weight
    weak = bool(evidence["ambiguous_places"] or evidence["ambiguous_institutions"])
    # Acronyms and cross-border/ethnic names require corroboration; they can never
    # decide Kenya relevance alone. Generic county/ward terminology is also weak.
    admin = min(len(evidence["admin_terms"]), 2) * config.admin_weight
    if support > 0:
        support += admin
    if support >= config.decision_threshold and foreign == 0:
        label, reasons = "kenya", ["kenya_geographic_evidence"]
        confidence = support / (support + config.confidence_prior)
    elif foreign >= config.decision_threshold and support == 0 and not weak:
        label, reasons = "not_kenya", ["foreign_only_evidence"]
        confidence = foreign / (foreign + config.confidence_prior)
    else:
        label = "ambiguous"
        reasons = ["mixed_geographic_evidence" if support and foreign else
                   "ambiguous_place_or_institution" if weak else "insufficient_geographic_evidence"]
        confidence = config.confidence_prior / (abs(support - foreign) + config.confidence_prior)
    evidence.update(kenya_score=support, foreign_score=foreign, net_score=support - foreign,
                    decision_threshold=config.decision_threshold,
                    confidence_kind="normalized_evidence_support_not_probability")
    return AnnotationResult("L1", label, "kenya_relevance_hybrid", config.method_version("L1"),
                            round(confidence, 6), evidence, reasons)
