"""Versioned result contracts and centralized annotation configuration."""

from dataclasses import asdict, dataclass, field
import hashlib
import json


@dataclass(frozen=True)
class AnnotationConfig:
    minimum_body_chars: int = 200
    minimum_body_words: int = 35
    unusable_body_chars: int = 60
    country_weight: float = 3.0
    place_weight: float = 3.0
    institution_weight: float = 3.0
    admin_weight: float = 0.5
    foreign_weight: float = 3.0
    decision_threshold: float = 3.0
    confidence_prior: float = 2.0

    def __post_init__(self):
        if any(value <= 0 for value in asdict(self).values()):
            raise ValueError("Annotation thresholds and weights must be positive")
        if self.unusable_body_chars > self.minimum_body_chars:
            raise ValueError("Unusable-body threshold cannot exceed minimum length")

    def method_version(self, layer):
        """Non-default parameters get a distinct identity for pending/version checks."""
        fields = ("minimum_body_chars", "minimum_body_words", "unusable_body_chars") if layer == "L0" else tuple(
            name for name in asdict(self) if not name.startswith(("minimum_", "unusable_"))
        )
        values = {name: getattr(self, name) for name in fields}
        defaults = {name: getattr(AnnotationConfig(), name) for name in fields}
        base = f"{layer.lower()}-v1.0"
        if values == defaults:
            return base
        digest = hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()[:12]
        return f"{base}-{digest}"


@dataclass(frozen=True)
class AnnotationResult:
    layer: str
    label: str
    method_name: str
    method_version: str
    confidence: float | None = None
    evidence: dict = field(default_factory=dict)
    reason_codes: list[str] = field(default_factory=list)


DEFAULT_CONFIG = AnnotationConfig()
