# H4 — Medication Safety Second Pair of Eyes
## Design Requirements

Read `SHARED-DESIGN-SYSTEM.md` first. Everything in it applies. This document covers only what is specific to H4.

**Accent:** `--action: #1C4F86` (institutional blue), `--action-weak: #E2EBF4`, `--focus: #2A79C0`.
Blue here is deliberate — clinical tools carry institutional blue, and this is the one place in the two apps where meeting the convention is right rather than lazy.

---

## 1. What this screen is

A prescriber has four minutes with a patient and will look at this for maybe twenty seconds. The product has one job: **tell them the one thing to change.**

Every design decision follows from alert fatigue being the scored enemy. Restraint is the feature. A screen with three alerts and a clear action beats a screen with eleven and a scroll bar.

---

## 2. Severity

| Level | Colour | Meaning |
|---|---|---|
| High | `--critical` | Act before this prescription leaves the room |
| Medium | `--warn` | Confirm it is intended |
| Low | `--ink-3` | Shown only on the expanded view, never in the capped list |
| Cleared | `--ok` | Checked, no issue found |

**Low-severity alerts are grey, not coloured.** If everything is coloured, nothing is urgent — that is literally the failure this product exists to fix, so the UI must not commit it.

---

## 3. Screen 2 — Patient detail (design this one first)

```
┌──────────┬──────────────────────────────────────────────────────────────┐
│          │ Patients › 2291            Prototype · simulated dataset     │ 48px
│ Medsafe  ├──────────────────────────────────────────────────────────────┤
│          │ Patient 2291                                                 │
│ Patients │ 74 y  ·  62 kg  ·  eGFR 28 low  ·  not pregnant  ·  9 meds   │
│ Resolve  │ Type 2 diabetes · Atrial fibrillation · Osteoarthritis       │
│ Method   │ ──────────────────────────────────────────────────────────── │
│ Results  │ Alerts    [Collapsed (3)] [Every pair (11)]                  │
│          │ ▍HIGH  Interaction cluster  Stop Drug X — clears 4 of 5      │
│          │ ▍HIGH  Renal dose           Halve Drug Y: eGFR 28            │
│          │ ▍MED   Duplicate therapy    Two drugs, same class            │
│          │ ──────────────────────────────────────────────────────────── │
│          │ ┌─ Alert graph ──────────┐ ┌─ Medicines as written ────────┐ │
│          │ │        (X)             │ │ "Warf 5"      → Warfarin  0.91│ │
│          │ │     ╱  ╱ ╲  ╲          │ │ "crocine"     → Paracetamol   │ │
│          │ │   (A)(C) (D)(F)        │ │ "PAN-D"       → could not …   │ │
│          │ └────────────────────────┘ └───────────────────────────────┘ │
│          │ No issue was found in the 9 medicines listed. This list may  │
│          │ be incomplete. A clinician decides.                          │
└──────────┴──────────────────────────────────────────────────────────────┘
```

**Header strip:** one line, 13px, values in mono, separated by `·`. eGFR carries a small `low` tag in `--warn-bg` with `--warn` text when under 45 — 11px, 2px 6px padding, no radius.

**Alerts table:** 48px rows (taller than R1 — these are read, not scanned). Columns: severity bar + label (80px) · issue type (160px, 500 weight) · drugs involved (mono, 180px) · **suggested action** (flex, this is the widest column and the most important) · confidence (mono, 64px, right).

**The collapse toggle:** two segments above the table — `Collapsed (3)` and `Every pair (11)`. On switch, the table expands to 11 rows including the greyed low-severity ones, and a caption appears:

> Every pair: 11 alerts, 8 of them low severity. This is what a prescriber dismisses.

Then switch back. **Rehearse this moment for the video** — it is the argument of the entire project in one click.

**Alert graph panel:** ~440×260 SVG. Nodes are 22px circles, 1.3px `--action` outline, white fill, drug abbreviation inside in 11px mono. The chosen drug is filled `--critical` with white text. Edges: serious interactions 1.5px `--critical`, others 1px `--ink-3` at 55% opacity. Caption beneath, 11px `--ink-3`: *"5 interactions → 1 change, not 5 alerts."*

Layout the nodes on a circle with fixed coordinates from the data — **do not run a force simulation.** It will jitter on every render and look unstable on video.

**Medication list panel:** each row 32px —
`raw string` in mono 12px `--ink-3` with quotes → a 10px `--ink-3` arrow → `resolved generic` in 13px `--ink` 500 → confidence in mono 12px right-aligned.
Abstained rows: resolved cell reads `could not resolve` in `--warn`, and the row gets a `--warn` 3px left bar plus a 11px note *"verify manually"*.

**Limitations footer:** full width, `--sunken` background, 12px `--ink-2`, 12px padding, 24px above it. Always visible, never dismissible, on every patient.

---

## 4. Screen 1 — Patient queue

Standard dense table, 40px rows. Columns: patient (mono) · age (mono, right) · eGFR (mono, right, `--warn` text when under 45) · meds (mono, right) · severity (StatusBar) · alerts (mono, right) · summary (flex, `--ink-2`).

Default sort: highest severity first, then alert count. Segmented filter `All · High · Medium · Cleared` with counts in each segment.

The "no serious issue found" patient must be visible in the default view — it demonstrates the system is capable of staying quiet.

---

## 5. Screen 3 — Resolution

One stat at the top: `Resolution accuracy on misspelled inputs — 94%` with the sample size beneath in 11px.

Table: raw (mono) · resolved (mono) · confidence (mono, right) · method tag.
Method tags are 11px, 2px 6px padding, no radius: `exact` in `--ok-bg`/`--ok`, `fuzzy` in `--action-weak`/`--action`, `abstained` in `--warn-bg`/`--warn`.

Segmented filter with counts, defaulting to **All** — but make `Abstained` one click away, because abstention is the interesting behaviour and a judge will want to see it.

---

## 6. Screen 4 — Method

Narrow column, max-width 680px, left-aligned.

- 4-step SVG diagram, full column width
- **The eGFR comparison, side by side in two columns:** the same drug, same dose, two patients at eGFR 28 and eGFR 80, with the severity each receives. One pair of cards does more than a paragraph here.
- The graph collapse explained with the hero patient's before/after graphs, 300px each, side by side
- The "real vs simulated vs reduced" block in a `--sunken` panel

---

## 7. Screen 5 — Evaluation

Two `Stat` blocks side by side, 44px mono figures:

```
Alerts per patient            Near-miss recall
11.0 → 3.2                    28 / 30
```

The first in `--ok` (went down, good), the second in `--ink` (held, good). Below each, an 11px label explaining direction.

Grouped bar chart: severity on the x-axis, two bars per group (before collapse, after), `--ink-3` and `--action`. Value labels above bars. No legend box — label the two bars inline on the first group only.

Then the missed near-misses table: 2 rows, with the reason each was missed. Header above it in 15px 600: `What we missed`. Do not soften that heading.

---

## 8. Tone rules for all copy

- Never the word "safe" about a patient.
- Never "AI detected" or "the model predicts". Write "flagged by the renal rule" or "matched interaction WFR-NSAID-01".
- Suggested actions are imperative and specific: *"Halve Drug Y: eGFR 28 needs renal adjustment"*, not *"Consider dose review"*.
- Confidence is a number, never a word. `0.91`, not "high confidence".

---

## 9. Accessibility floor

Contrast ≥ 4.5:1. 2px `--focus` outline, 1px offset, never `outline: none`. Full keyboard path through queue → patient → alerts. Every severity readable without colour. The alert graph needs a text alternative: an `aria-label` naming the chosen drug and the count of interactions it clears.

---

## 10. QA checklist before recording

- [ ] Collapse toggle flips 3 ↔ 11 instantly with no layout jump
- [ ] Graph nodes do not move between renders
- [ ] Raw → resolved visible for all 9 of the hero patient's medicines
- [ ] At least one abstained row on screen
- [ ] Limitations footer present on every patient
- [ ] The "no issue found" patient is reachable from the default queue
- [ ] No rounded corners, no gradients, every figure monospaced
- [ ] Prototype chip visible on every screen
