"""Bounded offline synthetic XLM-R architecture smoke; no research model/metrics."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, help="New private directory under data/")
    args = parser.parse_args(argv)
    from annotations.l2 import TransformerPredictor
    from annotations.l2_config import INPUT_VERSION, LABEL_MAPPING, L2Config, format_input
    from annotations.l2_training import private_output, train_classifier
    from annotations.l2_weak_supervision import WeakSupervisor
    from tokenizers import Tokenizer
    from tokenizers.models import WordLevel
    from tokenizers.pre_tokenizers import Whitespace
    import torch
    from transformers import PreTrainedTokenizerFast, XLMRobertaConfig, XLMRobertaForSequenceClassification

    output = private_output(args.output_dir)
    output.mkdir(parents=True, exist_ok=False)
    articles = [{"title": "Synthetic news", "article_text": body} for body in
                ("Sexual assault was reported.", "Ubakaji was discussed.",
                 "A burglary was investigated.", "Police investigated car theft.")]
    weak = WeakSupervisor()
    tick = perf_counter()
    labels = weak.predict_batch(articles)
    weak_ms = (perf_counter() - tick) * 1000
    if {result.label for result in labels} != set(LABEL_MAPPING):
        raise ValueError("Synthetic smoke needs both binary weak classes")
    vocabulary = {word: index for index, word in enumerate(("<s>", "<pad>", "</s>", "<unk>", "<mask>"))}
    pretokenizer = Whitespace()
    for word in sorted({token for article in articles for token, _ in pretokenizer.pre_tokenize_str(format_input(article))}):
        if word not in vocabulary:
            vocabulary[word] = len(vocabulary)
    backend = Tokenizer(WordLevel(vocabulary, unk_token="<unk>"))
    backend.pre_tokenizer = pretokenizer
    tokenizer = PreTrainedTokenizerFast(tokenizer_object=backend, unk_token="<unk>", pad_token="<pad>",
        bos_token="<s>", eos_token="</s>", mask_token="<mask>", model_max_length=32)
    torch.manual_seed(42)
    config = XLMRobertaConfig(vocab_size=len(vocabulary), hidden_size=16, num_hidden_layers=1,
        num_attention_heads=2, intermediate_size=32, max_position_embeddings=66, num_labels=2,
        id2label={0: "not_gbv", 1: "gbv"}, label2id=LABEL_MAPPING)
    tiny = XLMRobertaForSequenceClassification(config)
    base = output / "tiny-synthetic-base"
    tiny.save_pretrained(base, safe_serialization=True)
    tokenizer.save_pretrained(base)
    dataset = output / "bootstrap"
    dataset.mkdir()
    records = []
    for index, (article, weak_label) in enumerate(zip(articles, labels)):
        ids = {key: str(uuid5(NAMESPACE_URL, f"synthetic-l2-smoke:{index}:{key}")) for key in
               ("article_id", "article_version_id", "prerequisite_l1_annotation_id", "weak_annotation_id")}
        records.append({**ids, "source": "synthetic", "language": "mixed", "label": weak_label.label,
                        "label_id": LABEL_MAPPING[weak_label.label], "input": format_input(article),
                        "weak_method_version": weak_label.method_version,
                        "weak_rule_version": weak_label.evidence["rule_version"]})
    payload = "".join(json.dumps(row, sort_keys=True) + "\n" for row in records)
    digest = hashlib.sha256(payload.encode()).hexdigest()
    (dataset / "bootstrap.jsonl").write_text(payload)
    manifest = {"dataset_version": "l2-bootstrap-synthetic-" + digest[:12], "kind": "weak_bootstrap_development",
                "labels_are_gold": False, "input_version": INPUT_VERSION, "label_mapping": LABEL_MAPPING,
                "split_status": "development_only_no_reference_or_heldout_test", "records_sha256": digest,
                "record_count": len(records), "weak_supervision_version": weak.method_version}
    (dataset / "dataset_manifest.json").write_text(json.dumps(manifest))
    tick = perf_counter()
    trained = train_classifier(dataset, output / "tiny-trained", "synthetic-smoke-not-research-v1",
        base_model=str(base), max_steps=2, epochs=1, batch_size=2, max_length=32, device="cpu", local_files_only=True)
    training_ms = (perf_counter() - tick) * 1000
    tick = perf_counter()
    predictor = TransformerPredictor(L2Config(model_path=str(output / "tiny-trained"), device="cpu", batch_size=2))
    load_ms = (perf_counter() - tick) * 1000
    tick = perf_counter()
    results = predictor.predict_batch(articles)
    inference_ms = (perf_counter() - tick) * 1000
    report = {"kind": "synthetic_engineering_smoke_not_research_evaluation", "articles": len(articles),
              "training_steps": trained["training_parameters"]["completed_steps"],
              "model_parameters": sum(parameter.numel() for parameter in tiny.parameters()),
              "device": "cpu", "weak_supervision_ms": round(weak_ms, 3), "training_ms": round(training_ms, 3),
              "model_load_ms": round(load_ms, 3), "transformer_batch_inference_ms": round(inference_ms, 3),
              "predictions": [result.label for result in results], "research_metrics": None,
              "libraries": trained["libraries"], "network_model_downloads": False}
    (output / "smoke_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
