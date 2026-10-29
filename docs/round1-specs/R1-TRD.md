# R1 — Phantom Stock-Out Detector
## Technical Requirements Document (demo build)

**Goal:** a frontend-only application that demonstrates the full idea convincingly on video.
**Non-goal:** a trained model, a backend, or live data. Everything is precomputed and committed.

---

## 1. Stack

| Layer | Choice | Why |
|---|---|---|
| App | Vite + React 18 + TypeScript | Fastest path to a running SPA, no config |
| Styling | Plain CSS with custom properties | Tailwind would take longer to make *not* look templated |
| Routing | `react-router-dom` | 5 routes |
| State | React state + one context | No Redux, no Zustand, nothing to learn |
| Charts | Hand-written SVG | See design doc §6. A chart library imposes its own look |
| Data | Static JSON in `/src/data`, imported directly | No fetch, no loading states to debug, works offline |
| Deploy | `npm run build` → Vercel or Netlify drop | Optional; local is fine for the video |

**No backend. No database. No API calls. No auth.** If the demo needs the network to work, it will fail on the day.

---

## 2. Data strategy — the important part

Write a **one-off Python script** (`/tools/generate.py`) that produces the fixtures **once**. Commit the output JSON. The script is never run by the app.

The script genuinely implements the method, so the numbers on screen are real outputs of real logic — just computed ahead of time.

### 2.1 Synthesise 18 months of history
- 25 stores, 800 SKUs (generate; do not hand-write)
- Per-SKU base demand drawn so the mix is realistic: ~15% fast movers (10–40/day), ~45% medium (1–10/day), ~40% slow (0.03–1/day)
- Weekday multipliers, a seasonality curve, a promo calendar with lift
- Daily sales sampled from a negative binomial around that expected demand
- System stock decremented by sales, replenished on reorder triggers

### 2.2 Inject phantoms
Pick ~3% of SKU-store series. From a chosen day: **sales become exactly 0** while **system stock stays frozen at a positive number**. Record the true start day as ground truth.

Also inject the two confusers the stretch goal asks about, so the UI can distinguish them:
- **Misplaced:** sales drop ~80% but not to zero; stock still decrements slowly
- **Delisted:** gradual decay to zero over 3–4 weeks, no inbound receipts

### 2.3 Score it
For every SKU-store on the demo date:

```
expected_rate  = base × weekday × season × promo
p_zero_run     = P(k consecutive zero days | NegBin(expected_rate))   # survival probability
p_phantom      = 1 - p_zero_run                                       # clamp [0,1]
days_lost      = expected days until it would surface otherwise (cap 30)
expected_value = p_phantom × expected_rate × unit_margin × days_lost
```

Rank by `expected_value`, **not** by `p_phantom`. That ordering is the whole differentiator and it must be visible in the UI.

### 2.4 Group into aisle walks
Each SKU has an `aisle` (1–18). Greedy selection: repeatedly take the aisle with the highest unclaimed expected value, add its flagged SKUs, until 20 checks are allocated. Output the walk grouping.

### 2.5 Emit
```
/src/data/stores.json        25 stores: id, name, city tier, format, size
/src/data/checklist.json     per store: top 20 with full score breakdown + aisle + walk id
/src/data/series.json        ~40 SKU-store series (120 days each) — only the ones a user can open
/src/data/metrics.json       precision@20, recall, per-category counts, impact arithmetic
```

Keep `series.json` under 2 MB. Only include series reachable from the checklist.

---

## 3. Screens

### S1 `/` — Morning list (the hero screen)
- Store dropdown, date fixed to the demo date
- Four stats across the top: `20 checks` · `6 aisle walks` · `₹27,400 recoverable today` · `14 confirmed phantoms` *(from ground truth, shown after "verify")*
- Table, 20 rows, ranked: `#` · SKU (mono) · Aisle · Confidence (mono) · ₹ at risk (mono) · Reason (plain English) · status
- Severity bar on the left of each row
- Row click → drawer (S2)
- Segmented filter: `All · Phantom · Misplaced · Delisted`
- A **"Rank by confidence instead"** toggle — flips the ordering and visibly reshuffles the list. **This is the single best demo moment in the app.** It shows the judge, in one click, why ranking by money is different. Add a caption under the table that updates: *"Ranked by money recovered"* / *"Ranked by confidence — ₹8,900 of value drops out of the top 20"*.

### S2 Drawer — SKU detail
- Sales vs system stock chart, 120 days, with a vertical marker at the detection day
- Score breakdown as a horizontal bar chart: the four terms of `expected_value` and what each contributed
- Plain-English reason, expanded
- `Verify` and `Dismiss` buttons — local state only, row updates to `Confirmed` or `Dismissed`
- After verify, if ground truth says phantom, show a small `Confirmed phantom` tag

### S3 `/walks` — Aisle walk plan
- The 20 checks grouped into walks, each walk a card: aisle, SKU count, total ₹ at risk, checkboxes
- Print-friendly. This is the artefact a manager actually carries.

### S4 `/method` — How it works
- The four-step flow as a static SVG diagram (reuse the Round 1 deck diagram)
- The formula, rendered plainly, with one worked example from the real data
- A short comparison table: fixed-N rule vs per-SKU probability, showing how many false positives each produces on the same day
- One paragraph on why precision@20 is the metric and why AUC-tuned models lose

### S5 `/impact` — Rupees recovered
- The arithmetic shown line by line, not just a total:
  `phantoms per store per day × days hidden × daily demand × unit margin × 25 stores × 365`
- Each input editable with a slider, total updates live
- One sensitivity bar chart: total vs number of checks per day (5 / 10 / 20 / 40), showing diminishing returns

---

## 4. Interaction rules

- Everything is instant. No spinners, no skeletons — the data is already in memory.
- Verify/dismiss state lives in React state. **No localStorage** — the demo must reset on refresh so you can re-record the video cleanly.
- The ranking toggle re-sorts with no animation. Instant swap reads as decisive.

---

## 5. Build order (4–6 hours)

| # | Task | Time |
|---|---|---|
| 1 | `generate.py`, fixtures committed, numbers sanity-checked | 90 min |
| 2 | Shell: rail, top bar, tokens, fonts, Table component | 45 min |
| 3 | S1 morning list + ranking toggle | 60 min |
| 4 | S2 drawer + the sales/stock SVG chart | 60 min |
| 5 | S4 method + S5 impact | 45 min |
| 6 | S3 walks | 20 min |
| 7 | Polish pass against the design doc, screenshot QA | 30 min |

**Cut in this order if short:** S3 walks → S5 sliders (show static arithmetic) → score-breakdown bar chart. **Never cut** the ranking toggle or the sales/stock chart; they carry the whole argument.

---

## 6. What is real and what is not

Put this on `/method` verbatim. It protects the submission and costs nothing:

- **Real:** the demand model, the probability calculation, the expected-value ranking, the aisle grouping, and the precision@20 figure measured against injected ground truth.
- **Simulated:** the sales and inventory history, generated to the brief's stated shape. No retailer data was used.
- **Precomputed:** scoring runs offline; the app replays committed results rather than computing in the browser.

---

## 7. Acceptance

- `npm run dev` from clean clone works with no network.
- Switching stores changes the list; three stores have visibly different profiles.
- The ranking toggle visibly reorders and the caption updates.
- Every row's reason is specific — never "anomaly detected".
- No console errors. 20 rows visible at 1280×800 without scrolling.
