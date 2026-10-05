"""Explainable provisional bootstrap signals; never human/reference labels."""

from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from annotations.l2_config import WEAK_METHOD
from annotations.schemas import AnnotationResult

RESOURCE = Path(__file__).with_name("resources") / "gbv_relevance_v1.json"


def normalize(text):
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"\s+", " ", re.sub(r"[-‐‑–—]", " ", text)).strip()


@lru_cache(maxsize=1)
def resource():
    raw = RESOURCE.read_bytes()
    rules = json.loads(raw)
    return rules, hashlib.sha256(raw).hexdigest()


def weak_method_version():
    return "l2-ws-v1.0-" + resource()[1][:16]


def matches(text, languages, prefixes=()):
    hits = []
    for language, terms in languages.items():
        for term in terms:
            pattern = r"(?<!\w)" + re.escape(normalize(term)) + r"(?!\w)"
            for match in re.finditer(pattern, text):
                preceding = text[max(0, match.start() - 35):match.start()].split()
                if any(word in prefixes for word in preceding[-3:]):
                    continue
                hits.append({"term": term, "language": language})
                break
    return hits


class WeakSupervisor:
    method_name = WEAK_METHOD

    def __init__(self):
        self.rules, self.digest = resource()
        self.method_version = weak_method_version()

    def evaluate(self, article):
        title = normalize(article.get("title") or "")
        body = normalize(article.get("article_text") or "")
        text = title + ". " + body
        sentences = [item.strip() for item in re.split(r"[.!?\n]+", text) if item.strip()]
        rules = self.rules
        positive = {category: matches(text, terms, rules["negation_prefixes"])
                    for category, terms in rules["positive_terms"].items()}
        contexts = {category: matches(text, terms, rules["negation_prefixes"])
                    for category, terms in rules["context_terms"].items()}
        votes = []

        def vote(name, hits, value="GBV", strong=True):
            votes.append({"labeling_function": "LF_" + name, "vote": value if hits else "ABSTAIN",
                          "matched_terms": hits, "strength": "strong" if hits and strong else "weak"})

        explicit = positive["explicit_gbv"]
        explicit_terms = rules["positive_terms"]["explicit_gbv"]
        substantive = (bool(matches(title, explicit_terms, rules["negation_prefixes"])) or
                       sum(bool(matches(sentence, explicit_terms, rules["negation_prefixes"])) for sentence in sentences)
                       >= rules["aggregation"]["explicit_substantive_sentences"])
        vote("explicit_gbv_terms", explicit, strong=substantive)
        for category, hits in positive.items():
            if category != "explicit_gbv":
                vote(category, hits)
        # Relationship alone or a person's gender is not evidence of GBV.
        relational_hits = []
        for sentence in sentences:
            relationship = matches(sentence, rules["context_terms"]["relationship"])
            harm = matches(sentence, rules["context_terms"]["physical_harm"])
            if relationship and harm:
                relational_hits.extend(relationship + harm)
        # Co-occurrence is weak: it does not establish who harmed whom or motive.
        vote("relationship_harm_context", relational_hits, strong=False)
        vote("trafficking_or_exploitation", contexts["exploitation"] + contexts["sexual_context"]
             if contexts["exploitation"] and contexts["sexual_context"] else [], strong=False)
        has_positive = any(positive.values())
        vote("legal_reporting_context", contexts["legal"] if has_positive else [], strong=False)
        multilingual = [hit for hits in positive.values() for hit in hits if hit["language"] != "en"]
        # Corroboration only; duplicate lexical observations are not independent strong votes.
        vote("multilingual_gbv_terms", multilingual, strong=False)
        for category, terms in rules["negative_contexts"].items():
            vote(category, matches(text, terms), "NOT_GBV")
        incidental = bool(explicit and not substantive and not any(
            hits for name, hits in positive.items() if name != "explicit_gbv")
            and len(sentences) >= rules["aggregation"]["incidental_minimum_sentences"])
        vote("incidental_gbv_mention", explicit if incidental else [], "ABSTAIN", strong=False)
        gbv = sum(v["vote"] == "GBV" and v["strength"] == "strong" for v in votes)
        negative = sum(v["vote"] == "NOT_GBV" and v["strength"] == "strong" for v in votes)
        weak_positive = any(v["vote"] == "GBV" for v in votes)
        ambiguity = matches(text, rules["ambiguous_terms"])
        # No evidence is uncertainty, never a default negative label.
        if gbv >= rules["aggregation"]["minimum_strong_positive_votes"] and not negative:
            label, reason = "gbv", "consistent_strong_gbv_evidence"
        elif negative >= rules["aggregation"]["minimum_strong_negative_votes"] and not weak_positive and not ambiguity:
            label, reason = "not_gbv", "consistent_non_gbv_context"
        else:
            label = "borderline"
            reason = "conflicting_evidence" if negative and weak_positive else "weak_or_insufficient_evidence"
        evidence = {"rule_version": rules["version"], "rule_sha256": self.digest,
                    "aggregation_version": rules["aggregation_version"], "definition_status": rules["status"],
                    "votes": votes, "gbv_votes": sum(v["vote"] == "GBV" for v in votes),
                    "not_gbv_votes": sum(v["vote"] == "NOT_GBV" for v in votes),
                    "abstain_votes": sum(v["vote"] == "ABSTAIN" for v in votes),
                    "strong_gbv_votes": gbv, "strong_not_gbv_votes": negative,
                    "aggregate_label": label, "confidence_kind": "not_applicable_weak_votes"}
        return AnnotationResult("L2", label, self.method_name, self.method_version,
                                evidence=evidence, reason_codes=[reason, "provisional_weak_label_not_gold"])

    def predict_batch(self, articles):
        return [self.evaluate(article) for article in articles]
