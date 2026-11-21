"""
clause_model.py — presence classification for the 41 CUAD clause categories.

Approach and why:

  * TF-IDF (word + character n-grams) -> One-vs-Rest linear SVM.
    Chosen because it trains in seconds on a laptop, runs offline, is
    deterministic, and — most importantly — the coefficients can be inspected, so
    "why did it say this contract has an unlimited liability clause?" has an answer
    that does not involve a language model hallucinating a justification.

  * Split is by contract, never by clause, so no contract appears on both sides of
    the evaluation.

  * Reported metrics are per class, including the classes where it is bad. A
    model reported only at macro level hides the categories that matter.

The honest limitation, stated here and in the README: 510 contracts is a small
training set for 41 labels, the contracts are US commercial agreements, and clause
drafting differs in the UAE. This is a triage aid trained on a public corpus, not
an opinion on enforceability.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.multiclass import OneVsRestClassifier
from sklearn.svm import LinearSVC

from .clause_data import ClauseDoc, categories

MODEL_PATH = Path(__file__).resolve().parent.parent / "data" / "models" / "clause_model.pkl"


def build_matrix(docs: list[ClauseDoc], cats: list[str]) -> tuple[list[str], np.ndarray]:
    X = [d.text for d in docs]
    y = np.array([[d.labels.get(c, 0) for c in cats] for d in docs], dtype=np.int8)
    return X, y


def train(docs: list[ClauseDoc], test_size: float = 0.2, seed: int = 42) -> dict:
    """Train on a contract-level split and return weights + honest metrics."""
    cats = categories(docs)
    X_text, y = build_matrix(docs, cats)

    X_train, X_test, y_train, y_test = train_test_split(
        X_text, y, test_size=test_size, random_state=seed, shuffle=True
    )

    vectorizer = TfidfVectorizer(
        lowercase=True,
        max_features=60_000,
        ngram_range=(1, 2),
        sublinear_tf=True,
        min_df=2,
        strip_accents="unicode",
    )
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    clf = OneVsRestClassifier(LinearSVC(class_weight="balanced"), n_jobs=-1)
    clf.fit(X_train_vec, y_train)
    predicted = clf.predict(X_test_vec)

    per_class = {}
    for i, cat in enumerate(cats):
        support = int(y_test[:, i].sum())
        per_class[cat] = {
            "support": support,
            "precision": round(float(precision_score(y_test[:, i], predicted[:, i], zero_division=0)), 3),
            "recall": round(float(recall_score(y_test[:, i], predicted[:, i], zero_division=0)), 3),
            "f1": round(float(f1_score(y_test[:, i], predicted[:, i], zero_division=0)), 3),
        }

    metrics = {
        "contracts_total": len(docs),
        "contracts_train": len(X_train),
        "contracts_test": len(X_test),
        "categories": len(cats),
        "micro_f1": round(float(f1_score(y_test, predicted, average="micro", zero_division=0)), 3),
        "macro_f1": round(float(f1_score(y_test, predicted, average="macro", zero_division=0)), 3),
        "per_class": per_class,
    }

    bundle = {
        "vectorizer": vectorizer,
        "classifier": clf,
        "categories": cats,
        "metrics": metrics,
    }
    return bundle


def save(bundle: dict, path: Path | str = MODEL_PATH) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        pickle.dump(bundle, fh)
    return path


def load(path: Path | str = MODEL_PATH) -> dict:
    with Path(path).open("rb") as fh:
        return pickle.load(fh)


def predict_present(bundle: dict, contract_text: str, threshold: float = 0.0) -> list[dict]:
    """Return the categories the model believes are present, with a margin score.

    LinearSVC decision values are margins, not probabilities, and they are not
    comparable across classes. We expose them as `score` and do not call them
    confidence anywhere in the UI.
    """
    vec = bundle["vectorizer"].transform([contract_text])
    scores = bundle["classifier"].decision_function(vec)[0]
    out = []
    for cat, score in zip(bundle["categories"], scores):
        if score > threshold:
            out.append({"category": cat, "score": round(float(score), 3)})
    return sorted(out, key=lambda d: -d["score"])


def metrics_table(metrics: dict, worst: int = 8) -> str:
    """Plain-text table for the CLI — strongest and weakest classes together."""
    rows = sorted(metrics["per_class"].items(), key=lambda kv: kv[1]["f1"], reverse=True)
    head = f"{'category':<52}{'support':>8}{'prec':>7}{'rec':>7}{'f1':>7}"
    lines = [head, "-" * len(head)]
    for cat, m in rows[:worst]:
        lines.append(f"{cat[:50]:<52}{m['support']:>8}{m['precision']:>7.2f}{m['recall']:>7.2f}{m['f1']:>7.2f}")
    lines.append("... weakest ...")
    for cat, m in rows[-worst:]:
        lines.append(f"{cat[:50]:<52}{m['support']:>8}{m['precision']:>7.2f}{m['recall']:>7.2f}{m['f1']:>7.2f}")
    return "\n".join(lines)
