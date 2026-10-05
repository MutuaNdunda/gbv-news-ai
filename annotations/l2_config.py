"""L2 engineering settings; independent of the unchanged L0/L1 configuration."""

from dataclasses import dataclass
import math
import os

MODEL_METHOD = "afroxlmr_gbv_relevance"
WEAK_METHOD = "gbv_relevance_weak_supervision"
L1_METHOD = "kenya_relevance_hybrid"  # Existing L1 family; version comes from AnnotationConfig.
LABEL_MAPPING = {"not_gbv": 0, "gbv": 1}
BASE_MODEL = "Davlan/afro-xlmr-base"  # Verified model card; not a GBV classifier.
INPUT_VERSION = "title-body-v1"


@dataclass(frozen=True)
class L2Config:
    model_path: str | None = None
    model_version: str | None = None
    positive_threshold: float = 0.8
    negative_threshold: float = 0.2
    batch_size: int = 8
    device: str = "auto"

    def __post_init__(self):
        if any(not isinstance(value, (float, int)) or isinstance(value, bool) for value in
               (self.positive_threshold, self.negative_threshold)):
            raise ValueError("L2 thresholds must be numeric")
        if not (math.isfinite(self.positive_threshold) and math.isfinite(self.negative_threshold)
                and 0 <= self.negative_threshold < self.positive_threshold <= 1):
            raise ValueError("L2 thresholds require 0 <= negative < positive <= 1")
        if (not isinstance(self.batch_size, int) or isinstance(self.batch_size, bool)
                or self.batch_size < 1 or self.device not in ("auto", "cpu", "mps", "cuda")):
            raise ValueError("Invalid L2 batch size or device")

    @classmethod
    def from_env(cls):
        return cls(model_path=os.getenv("L2_MODEL_PATH"), model_version=os.getenv("L2_MODEL_VERSION"),
                   positive_threshold=float(os.getenv("L2_POSITIVE_THRESHOLD", "0.8")),
                   negative_threshold=float(os.getenv("L2_NEGATIVE_THRESHOLD", "0.2")),
                   batch_size=int(os.getenv("L2_BATCH_SIZE", "8")), device=os.getenv("L2_DEVICE", "auto"))


def probability_label(probability, config):
    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("Invalid GBV probability")
    return ("gbv" if probability >= config.positive_threshold else
            "not_gbv" if probability <= config.negative_threshold else "borderline")


def format_input(article):
    title, body = article.get("title"), article.get("article_text")
    if not isinstance(title, str) or not isinstance(body, str):
        raise ValueError("L2 requires stored title and article body")
    return f"TITLE:\n{title.strip()}\n\nARTICLE:\n{body.strip()}"
