# Model card — clause presence classifier

Everything below was measured on this machine on 22 November 2026 by re-running the code in
`clientflow/workflows/clause_model.py`. Where a number could not be reproduced, it says so.

## 1. Dataset — CUAD

| Property | Value | Verified how |
|---|---|---|
| Contracts | **510** | `len(load_cuad())` |
| Clause categories | **41** | `len(categories(docs))` |
| Provenance | Contract Understanding Atticus Dataset (CUAD v1), The Atticus Project, NeurIPS 2021 | dataset README |
| Licence | CC BY 4.0 | Hugging Face dataset card |
| Source used | `CUAD_v1/CUAD_v1.json`, 40,128,638 bytes | `fetch-cuad` |
| Annotation format | SQuAD-style: `qas[].answers[].answer_start` + `text`; empty answers mean the clause is absent | inspected file |
| Domain | US commercial contracts (NDAs, licences, distribution, hosting, etc.) | titles |

**What CUAD is not:** it is not UAE law, not UAE drafting, not client data. Every contract is a public
SEC filing.

## 2. Task definition

Two separate tasks, scored separately, because they are not equally hard:

1. **Presence** — multi-label classification: contract text → 41 binary labels.
2. **Location** — which paragraph contains the clause. Reported as a *candidate passage*, see §6.

## 3. Architecture

```
contract text
   │
   ├── TfidfVectorizer(max_features=60_000, ngram_range=(1,2), sublinear_tf=True,
   │                    min_df=2, strip_accents="unicode")
   │
   └── OneVsRestClassifier(LinearSVC(class_weight="balanced"), n_jobs=-1)
          └── 41 independent linear margins → one label each
```

**Why this and not a transformer.** 510 training examples for 41 labels is small. A TF-IDF + linear model
trains in ~13 seconds, needs no GPU, no API, no network at inference, and its coefficients can be
inspected when a prediction is challenged. A fine-tuned transformer would likely score higher on some
classes but would be harder to justify, slower to iterate and impossible to run inside a firm's network
without extra approvals.

## 4. Training procedure

- `train_test_split(test_size=0.2, random_state=42, shuffle=True)` — **split by contract**, so no contract
  appears in both train and test. 408 train / 102 test.
- Labels: `class_weight="balanced"` inside LinearSVC, because categories like *Document Name* appear in
  ~100% of contracts while *Source Code Escrow* appears in 3.
- Training time: **13.4 s** (measured; 20.1 s including corpus load).

**No separate validation split.** Hyperparameters were chosen once, by judgement, and not tuned on the test
set. This is stated as a limitation, not a virtue: with a validation split the numbers would be a little
more defensible and a little lower.

## 5. Metrics — reproduced

| Metric | Value | Note |
|---|---|---|
| Micro F1 (test) | **0.802** | reproduced twice, identical |
| Macro F1 (test) | **0.561–0.562** | varies in the third decimal between runs |
| sklearn warning | `Label 9 is present in all training examples` | one category is always present; its per-class F1 is meaningless |

The macro/micro gap is the headline: frequently-occurring clauses are detected well, rare ones are not.
That is a data problem, not a tuning problem — 3 examples cannot teach a classifier.

**Strongest classes** (from the run): Document Name 1.00 · Parties 1.00 · Governing Law 0.97 ·
Agreement Date 0.95 · Expiration Date 0.92 · Anti-Assignment 0.91.

**Weakest classes**: Affiliate License-Licensee 0.22 (support 11) · Joint Ip Ownership 0.14 (support 9) ·
Volume Restriction 0.10 (support 16) · and several at 0.00 with support 2–7 (Affiliate License-Licensor,
Non-Disparagement, Price Restrictions, Source Code Escrow, Unlimited/All-You-Can-Eat-License).

Full table: `python -m clientflow.cli train` prints the strongest eight and weakest eight.

## 6. Location accuracy — a different problem, and much worse

| Configuration | Coverage | Agreement with CUAD lawyer spans |
|---|---|---|
| Vocabulary overlap, 2,500-char blocks | 99% | 28% |
| Vocabulary overlap, 600-char blocks | 99% | 21% |
| TF-IDF retrieval vs CUAD question, 2,500-char blocks | 99% | 32% |
| TF-IDF retrieval, 600-char blocks, no abstention | 99% | 22% |
| **Shipped: same, abstaining below 0.16 similarity** | **44%** | **34%** |

Abstention floor sweep, measured on the first 120 contracts (1,435 annotated findings):

| Floor | Coverage (passage returned) | Agreement among returned |
|---|---|---|
| 0.02 | 99% | 23% |
| 0.08 | 97% | 23% |
| 0.12 | 73% | 28% |
| **0.16** | **44%** | **34%** |

**Why classification succeeds where localisation fails.** Classification only answers "is there evidence of
this clause type anywhere in 15,000 characters" — a bag-of-words model with 60,000 features is well suited,
and lawyer-written clauses use characteristic vocabulary. Localisation must pick *the same* paragraph a lawyer
picked out of ~30 candidates, where the vocabulary repeats across the document ("agreement" appears in most
paragraphs, "liability" in several). It is retrieval with a near-uniform prior, and the scorer is lexical with
no notion of clause boundaries.

**Product response.** Raise the floor until the wrong pointers disappear, accept that most findings then have
no passage, and label the rest "candidate passage to verify". The UI states 44%/34% rather than a single
flattering number, and the per-row comparison with the lawyer annotation is opt-in (`?compare=1`).

**Honest verdict:** this feature is a convenience, not a citation, and a lawyer reading a contract still
searches manually. Fixing it properly needs a span model trained on CUAD's spans (the data supports it) or an
LLM with citation enforcement — evaluated on a held-out set before anything is claimed.

## 7. Known failure modes

1. **Rare categories are effectively undetected** (support < 10).
2. **Long contracts** dilute the bag-of-words signal; a 60,000-character agreement behaves differently from
   a 5,000-character one, and the vectoriser was not normalised for length beyond sublinear TF.
3. **Drafting vocabulary drift** — a UAE or DIFC agreement uses different boilerplate; nothing in the
   training set covers it.
4. **No negation or scope modelling** — "the parties shall not be entitled to unlimited liability" and
   "unlimited liability applies" share vocabulary. The risk rules, not the classifier, are where this
   matters.
5. **Headings as evidence** — a clause whose only match is a heading (e.g. "Governing Law; Jurisdiction")
   produces a weak excerpt even when the flag is right.

## 8. Appropriate use

- Triage before human review: "these clauses appear to be present; look here".
- Consistency checking across a portfolio of agreements.
- Teaching and demonstration, with the numbers above stated.

## 9. Inappropriate use

- As legal advice, or as an opinion on enforceability.
- As the sole basis for accepting or rejecting a clause.
- On UAE/DIFC/ADGM contracts without re-evaluation on regional drafting.
- Anywhere the output is presented as a clause citation rather than a pointer.

## 10. Human oversight requirements

1. A qualified lawyer reads every finding before it influences anything.
2. The disclaimer is returned **inside the result object**, so no caller can display the findings without it.
3. No contract text leaves the machine — inference is local, so there is no data-processing question at
   review time.
4. If this were put in front of clients, it would need: re-evaluation on regional drafting, a labelled UAE
   test set, and a documented review workflow with sign-off.
