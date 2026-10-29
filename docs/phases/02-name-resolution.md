# Phase 2 — Brand → Generic Resolution

**Time:** 4h. **The brief calls this "much of the real difficulty" — believe it.**

---

## Why this is the highest-leverage phase

An unresolved name is a **silent miss**. The rule engine never sees the drug, no alert fires, and recall drops with no error anywhere. Every point of resolution accuracy converts almost directly into recall.

---

## The pipeline

**Stage 1 — Normalise**
Strip, in order: dosage form prefixes (`T.`, `Tab`, `Cap`, `Inj`, `Syp`), strengths and units (`500mg`, `5 mg`, `650`), release qualifiers (`SR`, `XR`, `ER`, `CR`, `DS`), trailing punctuation. Lowercase, collapse whitespace, strip non-alphanumerics except spaces and hyphens.
Keep the original string on the record — the UI shows it and the report needs it.

**Stage 2 — Exact match**
Against generics and all brand names, on the normalised form. Most entries resolve here. Record `method="exact"`, `confidence=1.0`.

**Stage 3 — Candidate generation**
Only for what survives. Union of:
- `rapidfuzz` top-k by `WRatio` over generics and brands
- Character trigram overlap (catches transpositions that edit distance ranks poorly)
- First-letter bucket, to cut the search space

**Stage 4 — Rerank**
Score each candidate:
```
score = 0.60 × normalised_edit_similarity
      + 0.25 × trigram_overlap
      + 0.15 × length_ratio_penalty
```
Plus a small bonus if the candidate's drug class matches any of the patient's diagnoses — context genuinely disambiguates.

**Stage 5 — Abstain**
```
if top_score < 0.72                      → abstain, reason "no_confident_match"
if (top_score - second_score) < 0.05     → abstain, reason "ambiguous"
else                                     → resolve, confidence = top_score
```

**Tune those two thresholds against measured accuracy in Phase 7. Do not leave them at my guess.**

---

## Requirements

**R1 — Abstention is a first-class outcome**, not a failure. It appears in the output, in the UI, and in the report. The brief explicitly values saying "I could not resolve this" over guessing.

**R2 — Full provenance per entry:** raw string, normalised form, resolved generic or `None`, method (`exact` / `fuzzy` / `abstained`), confidence, and the top 3 candidates with their scores. The UI and the report both need this.

**R3 — An abstained drug still appears in the output** with its raw string and a `verify manually` flag. It is never silently dropped — a dropped drug is invisible, and invisible is the dangerous failure mode.

**R4 — Measured accuracy.** `tools/eval_resolution.py` runs against fixtures with known ground truth and reports: exact-match rate, fuzzy accuracy, abstention rate, and **false-resolution rate** (resolved to the wrong drug — the number that actually matters, because it produces confidently wrong alerts).

**R5 — Deterministic.** Same input, same output, every run. No randomness in tie-breaking; break ties alphabetically.

---

## Deliverables

- [ ] `src/medsafe/resolve/normalise.py`
- [ ] `src/medsafe/resolve/resolver.py` — the 5 stages, returning a `Resolution` record
- [ ] `src/medsafe/resolve/thresholds.py` — the two thresholds in one place, tunable
- [ ] `tools/eval_resolution.py` + a results table in `docs/`
- [ ] `tests/test_resolution.py` — normalisation cases, each stage, abstention triggers, determinism

## Acceptance

- Exact-match rate above 70% on fixtures (most entries are not badly mangled).
- **False-resolution rate under 2%.** This is the number to protect.
- Every abstention carries a reason.
- Running twice gives byte-identical output.

## Claude Code prompt

```
Build Phase 2 per 02-name-resolution.md, on top of Phase 1.

1. normalise.py: strip form prefixes (T., Tab, Cap, Inj, Syp), strengths and units, release
   qualifiers (SR, XR, ER, CR, DS), punctuation. Lowercase, collapse whitespace. Keep the
   original string on the record. Unit-test each rule separately.
2. resolver.py implementing the 5 stages in the spec: normalise, exact match, candidate
   generation (rapidfuzz WRatio + character trigrams + first-letter bucket), rerank with the
   weighted score given, then abstain per the two thresholds.
   Return a Resolution dataclass: raw, normalised, resolved_generic|None, method, confidence,
   top3 candidates with scores, abstain_reason|None.
3. thresholds.py holding MIN_CONFIDENCE and MIN_MARGIN as named constants with a comment
   saying they are tuned in Phase 7.
4. Abstained entries must still appear downstream with the raw string and a verify_manually
   flag. Never drop a medication.
5. tools/eval_resolution.py: run over fixtures with known ground truth, report exact-match
   rate, fuzzy accuracy, abstention rate and false-resolution rate. Write the table to
   docs/resolution-accuracy.md.
6. Determinism: ties break alphabetically, no randomness. Add a test that two runs produce
   identical output.

Docstrings on every public function.
```
