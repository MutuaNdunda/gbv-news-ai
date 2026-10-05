"""Explainable Kenya relevance evidence scoring, not a calibrated classifier."""

from dataclasses import replace
from functools import lru_cache
import json
from pathlib import Path
import re
import unicodedata

from annotations.schemas import AnnotationResult, DEFAULT_CONFIG


@lru_cache(maxsize=1)
def gazetteer():
    return json.loads((Path(__file__).parent / "resources/kenya_v1.json").read_text(encoding="utf-8"))


def normalized(text):
    return unicodedata.normalize("NFKC", text).casefold().replace("’", "'").replace("–", "-").replace("—", "-")


def mentions(text, term):
    parts = re.split(r"[\s-]+", normalized(term))
    pattern = r"(?<!\w)" + r"[\s-]+".join(re.escape(part) for part in parts) + r"(?!\w)"
    return len(re.findall(pattern, text))


def extract_evidence(title, body):
    data = gazetteer()
    text = normalized(f"{title or ''}\n{body or ''}")
    counties = {name for name in data["counties"] if mentions(text, name)}
    counties.update(name for alias, name in data["county_variants"].items() if mentions(text, alias))
    towns = {name for name in data["towns"] if mentions(text, name)}
    towns.update(name for alias, name in data["place_variants"].items() if mentions(text, alias))
    institutions = sorted(name for name in data["institutions"] if mentions(text, name))
    ambiguous_places = sorted((counties | towns) & set(data["ambiguous_places"]))
    ambiguous_institutions = sorted(set(institutions) & set(data["ambiguous_institutions"]))
    return {"kenya_mentions": sum(mentions(text, name) for name in data["country_terms"]),
            "kenyan_places": sorted(counties | towns), "kenyan_counties": sorted(counties),
            "kenyan_institutions": institutions, "ambiguous_places": ambiguous_places,
            "ambiguous_institutions": ambiguous_institutions,
            "foreign_places": sorted(name for name in data["foreign_places"] if mentions(text, name)),
            "admin_terms": sorted(name for name in data["admin_terms"] if mentions(text, name)),
            "gazetteer_version": data["version"]}


def evaluate_l1(article, config=DEFAULT_CONFIG):
    config = replace(config, l1_gazetteer="v1")
    evidence = extract_evidence(article.get("title"), article.get("article_text"))
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
