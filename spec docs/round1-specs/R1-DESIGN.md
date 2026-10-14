# R1 — Phantom Stock-Out Detector
## Design Requirements

Read `SHARED-DESIGN-SYSTEM.md` first. Everything in it applies. This document covers only what is specific to R1.

**Accent:** `--action: #1B5E57` (deep teal), `--action-weak: #E3EFED`, `--focus: #2A8A7F`.
Teal rather than blue because this product is about money recovered, and because every retail dashboard in the room will be blue.

---

## 1. What this screen is

A store manager opens it at 7am with a coffee, scans it for ninety seconds, and walks the floor. It is a worklist, not a dashboard. Density over whitespace, scannability over beauty.

The entire product is one question: **which twenty shelves do I check today?** Every pixel either answers that or gets cut.

---

## 2. Status meanings

| Status | Colour | Shown as |
|---|---|---|
| Phantom (high confidence) | `--critical` | 3px bar + square + "Likely phantom" |
| Misplaced | `--warn` | bar + square + "Possibly misplaced" |
| Delisted | `--unknown` | bar + square + "Possibly delisted" |
| Confirmed after check | `--ok` | bar + square + "Confirmed" |
| Dismissed | `--muted-fail` | grey bar + "Dismissed" |

The left bars form a continuous vertical ribbon down the table. The eye reads severity in one pass without reading a word.

---

## 3. Screen 1 — Morning list

```
┌──────────┬──────────────────────────────────────────────────────────────┐
│          │ Store 14, Koramangala ▾   Thu 16 Oct   Prototype · simulated │ 48px
│ Phantom  ├──────────────────────────────────────────────────────────────┤
│          │ Morning check list                                           │
│ Checks   │                                                              │
│ Walks    │  20          6            ₹27,400         14                │
│ Method   │  checks      aisle walks  recoverable     confirmed          │
│ Impact   │                                                              │
│          │ [All][Phantom][Misplaced][Delisted]    Rank by: [₹][conf]    │
│          │ ─────────────────────────────────────────────────────────── │
│          │ ▍#  SKU           Aisle  Conf   ₹ at risk  Why               │
│          │ ▍1  TOORDAL1KG      4    0.94    ₹ 9,400   11 zero-sale …    │
└──────────┴──────────────────────────────────────────────────────────────┘
```

**Stats row:** four `Stat` blocks, figure 28px mono 600, label 11px `--ink-3` beneath. No boxes around them — whitespace separates. The rupee figure is the only one in `--action`.

**Table columns and alignment:**

| Column | Width | Align | Font |
|---|---|---|---|
| status bar | 3px | — | — |
| # | 32px | right | mono |
| SKU | 160px | left | mono 500 |
| Aisle | 56px | right | mono |
| Confidence | 80px | right | mono |
| ₹ at risk | 96px | right | mono 500 |
| Why | flex | left | sans 13 `--ink-2` |
| Status | 120px | left | StatusBar |

Numbers right, text left, status left. **Never centre a data column.**

**Rows:** 40px, `--paper`, 1px `--hairline` bottom. No zebra striping — it fights the status bars. Hover `--action-weak` at 40%. Selected: full `--action-weak` plus a 2px `--action` left border.

**The ranking toggle:** a two-segment control labelled `₹ recovered` / `Confidence`. On switch, the table re-sorts instantly and the caption below changes:

> Ranked by money recovered — the 20 checks cover ₹27,400
> Ranked by confidence — the same 20 slots cover ₹18,500

Set `--action` on the active segment. **Give this control room.** It is the argument of the whole project expressed as one click.

---

## 4. Screen 2 — Drawer

480px, slides from the right in 180ms. The table stays visible and dims 4%.

Sections, separated by hairlines rather than cards:

1. **Header** — SKU code (mono 16), product name, status bar, close
2. **Chart** — 420×180 SVG. Sales as a solid `--action` line, system stock as a dashed `--ink-3` step line, a 1px `--critical` vertical rule at the detection day with a 11px label. Y axis left, 4 ticks. X axis 5 ticks. No legend box — label the two lines inline at their right ends.
3. **Why this ranks here** — horizontal bars, four rows: `Probability it is phantom` · `Daily demand` · `Days hidden` · `Unit margin`. Bar in `--action`, value in mono at the right. Below: `= ₹9,400 at risk`.
4. **Reason** — two sentences of plain English, `--ink-2`.
5. **Actions** — sticky footer. `Verify` primary (`--action` fill), `Dismiss` secondary (outline). 32px tall.

Esc closes. Focus traps inside while open and returns to the row on close.

---

## 5. Screen 3 — Walks

Cards in a 2-column grid, 24px gap. Each card: `--paper`, 1px `--hairline`, 16px padding, **no shadow, no radius**.

```
Aisle 4 — Pulses & grains              ₹ 11,200
─────────────────────────────────────────────
☐  TOORDAL1KG      Toor Dal 1kg         ₹ 9,400
☐  CHANA500G       Chana 500g           ₹ 1,800
```

Checkbox is a 14px square outline, `--action` when checked with a white tick. Checking a row strikes it through in `--ink-3`.

`@media print`: hide the rail and top bar, stack cards single column, black on white.

---

## 6. Screen 4 — Method

Narrow column, **max-width 680px**, left-aligned. This is the one screen that is read rather than scanned, so it gets prose measure.

- The 4-step SVG diagram at the top, full column width
- The formula in a `--sunken` block, mono, 16px padding
- A worked example with real numbers from the dataset, as a small 2-column table
- The comparison table: `Fixed 7-day rule` vs `Per-SKU probability` → rows for alerts fired, true phantoms caught, false positives, precision@20
- The "what is real and what is simulated" block from the TRD, in a `--sunken` panel

---

## 7. Screen 5 — Impact

- Six sliders stacked left (max-width 420px), each: label, mono value right-aligned, then the track
- Slider track 4px `--hairline`, filled portion `--action`, thumb a 14px `--action` **square** — not a circle
- The running total on the right: 44px mono 600 in `--action`, label beneath
- The arithmetic written out underneath as a single mono line that updates live:
  `2.3 phantoms/store/day × 11 days × 8.4 units × ₹18 × 25 stores × 365 = ₹ 1.42 Cr`
- One bar chart below: total recovered at 5 / 10 / 20 / 40 checks per day, four bars, value labels above

---

## 8. Empty and edge states

- A store with fewer than 20 confident flags shows only what it has, plus a line: *"Only 11 checks are confident enough today. Padding the list to 20 would lower precision."* **Build at least one store this way** — it demonstrates the abstention rule and no other team will have it.
- All rows dismissed → `EmptyState`: "All checks cleared for today." in `--ink-2`, left-aligned, no illustration.

---

## 9. Accessibility floor

Contrast ≥ 4.5:1 throughout. 2px `--focus` outline with 1px offset on every focusable element — never `outline: none`. Full keyboard path: tab into table → arrows through rows → Enter opens drawer → Esc closes → focus restored. Every status readable without colour. Works at 200% zoom without horizontal scroll on SKU, ₹ and status columns.

---

## 10. QA checklist before recording

- [ ] 20 rows visible at 1280×800 with no scrolling
- [ ] Ranking toggle visibly reorders and the caption changes
- [ ] No rounded corners anywhere — inspect buttons, inputs, cards, drawer
- [ ] Every number in the UI is monospaced
- [ ] No gradient, no shadow except drawer and dropdown
- [ ] The abstention store is reachable in two clicks
- [ ] Prototype chip visible on every screen
