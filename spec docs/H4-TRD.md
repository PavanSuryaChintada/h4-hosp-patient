# H4 — Medication Safety Second Pair of Eyes
## Technical Requirements Document (demo build)

**Goal:** a frontend-only application that demonstrates the full idea convincingly on video.
**Non-goal:** a trained model, a backend, or real clinical data. Everything is precomputed and committed.

---

## 1. Stack

Identical to R1 — Vite + React 18 + TypeScript, plain CSS with custom properties, `react-router-dom`, React state only, hand-written SVG charts, static JSON imported directly. **No backend, no database, no API calls, no auth.**

Deliberately the same stack so whichever problem gets selected, the other's components transfer.

---

## 2. Data strategy

A one-off Python script (`/tools/generate.py`) builds the fixtures once. Commit the output. The app never runs it.

### 2.1 Reference tables
- **Drugs:** 60 generics is plenty for a demo (the brief says 500; 60 covers every case you will show). Each: generic name, class, 2–4 Indian brand names, renal-adjustment flag, pregnancy category, typical dose.
- **Interactions:** ~120 curated pairs with severity `major / moderate / minor` and a one-line mechanism.
- **Duplicate-therapy rules:** two drugs of the same class flagged.

Use real, well-known interactions — warfarin + NSAID, ACE inhibitor + potassium-sparing diuretic, metformin at low eGFR, three sedatives together. A clinician in the room will recognise them, and recognisable examples carry more weight than invented ones.

### 2.2 Patients
Generate 40 patients. Each: id, age, weight, eGFR, pregnancy status, diagnoses, and a medication list of 4–12 entries written the way a real slip looks — **mixed brand and generic, with misspellings and dose suffixes**:

```
"Crocin 650", "crocine", "T. Metformin 500mg", "Glycomet-SR",
"warfarin 5 mg", "Warf 5", "PAN-D", "pantop 40"
```

Design the cohort so the demo has range:
- 1 **hero patient**: 9 drugs, 5 interactions where **4 trace back to one drug** — this is the screen you record
- 1 patient where the right answer is *no serious issue found*
- 2 patients with unresolvable name ambiguity → abstention
- 2 with renal-dose issues at low eGFR, plus a control at normal eGFR with the same drug
- The rest ordinary

### 2.3 Run the real logic offline
1. **Resolve names** — normalise (strip `T.`, `Tab`, dose, form), candidate generation by edit distance + character trigrams, rerank, abstain when the top two candidates are within a small margin. Record raw string, resolved generic, confidence, and whether it abstained.
2. **Rule checks** — interaction pairs, duplicate therapy, renal dose vs eGFR, pregnancy contraindication.
3. **Re-score severity in patient context** — a renal flag at eGFR 28 becomes `high`; the same flag at eGFR 80 drops to `low`. Age and weight modulate too. **Store both the table severity and the re-scored severity** so the UI can show the difference.
4. **Collapse the alert graph** — build a graph where drugs are nodes and serious interactions are edges. Find the minimum set of drugs whose removal clears the most serious edges (brute force; n is under 12, so every subset is checkable in milliseconds). Output the chosen set and which edges each clears.
5. **Cap the list** — rank by severity × confidence × actionability, emit at most 5 alerts per patient.

### 2.4 Seeded near-misses
Mark 30 of the generated issues as `near_miss: true` — subtle but serious cases. Compute and store **recall on those**, so the evaluation screen reports a measured number.

### 2.5 Emit
```
/src/data/drugs.json         60 generics with brands
/src/data/interactions.json  ~120 pairs
/src/data/patients.json      40 patients with raw med lists
/src/data/resolved.json      per patient: raw → resolved, confidence, abstentions
/src/data/alerts.json        per patient: alerts, graph, chosen drug set, severities
/src/data/metrics.json       alerts/patient before and after collapse, near-miss recall, resolution accuracy
```

---

## 3. Screens

### S1 `/` — Patient queue
Table: patient id (mono) · age (mono) · eGFR (mono, coloured if low) · drug count (mono) · highest severity (StatusBar) · alert count · one-line summary.
Segmented filter: `All · High · Medium · Cleared`. Row click → S2.

### S2 `/patient/:id` — Patient detail (the hero screen)
Three stacked regions, full width:

1. **Header strip** — age, weight, eGFR, pregnancy status, diagnosis list. eGFR shown with a small `low` tag when under 45.
2. **Alerts** — at most 5 rows: severity bar, issue type, drugs involved, **suggested action**, confidence. The top row on the hero patient reads *"Stop Drug X — clears 4 of the 5 serious interactions."*
3. **Two panels side by side:**
   - **Alert graph** (left, ~440px): drugs as nodes, serious interactions as edges, the chosen drug filled `--critical` and its edges thickened. Caption: *"5 interactions → 1 change, not 5 alerts."*
   - **Medication list** (right): each row shows the **raw string as written** in mono `--ink-3`, an arrow, the **resolved generic** in `--ink`, and a confidence figure. Abstained rows show `could not resolve` in `--warn` with a *"verify manually"* note.

   Putting raw and resolved side by side is what makes the hardest part of the problem visible. Nobody else will show it.

4. **Limitations footer**, always present, never dismissible:
   > No issue was found in the 9 medicines listed. This list may be incomplete. A clinician decides.

**The alert-collapse toggle:** a two-segment control above the alerts — `Collapsed (3 alerts)` / `Every pair (11 alerts)`. Switching to "every pair" expands the list to the raw 11 warnings. **This is the single best demo moment in the app** — the judge sees alert fatigue and the fix in one click.

### S3 `/resolution` — Name resolution
A table of every raw string in the cohort: raw (mono) → resolved (mono) → confidence → method (`exact` / `fuzzy` / `abstained`). Filter to abstentions. One stat at the top: **resolution accuracy on misspelled inputs**, measured against the generator's ground truth.

### S4 `/method` — How it works
The 4-step SVG diagram (reuse the Round 1 deck diagram). Then, in prose with a worked example:
- Why severity is re-scored per patient, with the eGFR 28 vs 80 pair side by side using the same drug
- How the graph collapse works, with the hero patient's graph before and after
- The explicit statement that the system never claims the list is safe

### S5 `/evaluation` — The two numbers
Two large stats side by side, and the point is that they move in opposite directions:

```
Alerts per patient          Near-miss recall
11.0 → 3.2                  28 / 30
```

Below: a grouped bar chart, per severity, of alerts raised before and after collapse. Then a short paragraph: *cutting alert volume without holding recall is not a win, so both are reported together.* A small table of the 2 missed near-misses with why they were missed — **include the misses.** A perfect score reads as unmeasured; a reported miss reads as honest.

---

## 4. Build order (4–6 hours)

| # | Task | Time |
|---|---|---|
| 1 | `generate.py`: reference tables, patients, resolution, rules, graph collapse | 120 min |
| 2 | Shell: rail, top bar, tokens, fonts, Table | 45 min |
| 3 | S2 patient detail — alerts + med list with raw→resolved | 75 min |
| 4 | Alert graph SVG + collapse toggle | 60 min |
| 5 | S1 queue + S5 evaluation | 45 min |
| 6 | S3 resolution + S4 method | 40 min |
| 7 | Polish against the design doc, screenshot QA | 30 min |

**Cut in this order if short:** S3 resolution page (keep the raw→resolved column on S2) → S4 method prose → the grouped bar chart on S5. **Never cut** the collapse toggle or the alert graph.

---

## 5. What is real and what is not

On `/method`, verbatim:

- **Real:** the drug interactions and renal rules (clinically genuine, commonly cited), the fuzzy name resolution, the patient-context severity re-scoring, the graph collapse, and the near-miss recall measured against generated ground truth.
- **Simulated:** all patients and medication lists. No real patient data was used.
- **Reduced:** 60 generics and ~120 interaction pairs rather than the full reference set, sized for the demo.
- **Precomputed:** the pipeline runs offline; the app replays committed results.

---

## 6. Safety framing — do not skip this

This is a clinical-adjacent demo, so the framing is part of the work:

- Every alert carries a confidence and a limitations line.
- The app **never** renders the word "safe" about a patient. It says *no issue was found in what was seen*.
- A permanent footer states that a clinician decides.
- No dosing instruction is generated by a model — every suggested action comes from the committed rule tables.

A judge who asks "what if the list is incomplete?" should find the answer already on screen.

---

## 7. Acceptance

- `npm run dev` from clean clone works with no network.
- The hero patient's collapse toggle flips 11 alerts to 3 and back, instantly.
- Raw → resolved is visible for every medication, including abstentions.
- The evaluation page shows both numbers and names the 2 missed near-misses.
- No console errors. No rounded corners. Every figure monospaced.
