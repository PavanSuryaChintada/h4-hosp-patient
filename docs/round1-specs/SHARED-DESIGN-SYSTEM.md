# Shared Design System — both demos

Both apps use this. Identical tokens, different accent. They should look like two products from one company.

**The rule that prevents AI-slop:** the only saturated colours in either app are *status*. Everything else is paper, ink, hairlines and one accent. If a colour appears that does not mean something, delete it.

---

## 1. Hard constraints

- `border-radius: 0` everywhere. Buttons, inputs, cards, tables, modals. No exceptions.
- No gradients. No glow. No neon. No glassmorphism. No drop shadows on cards.
- No emoji in the UI.
- Light theme only.
- Sentence case for every label, button and column header. No ALL-CAPS tracked labels.
- `font-variant-numeric: tabular-nums` globally.
- Spacing only from `4 / 8 / 12 / 16 / 24 / 32 / 48`. No 10, 15, 18, 30.
- A failed or empty state renders in grey, never red. Red means danger in the data.
- No icon-only buttons without `aria-label`.

---

## 2. Tokens

```css
:root{
  /* surfaces — cool graphite paper, never cream */
  --canvas:        #F1F4F6;
  --paper:         #FFFFFF;
  --sunken:        #E6EAEE;
  --hairline:      #D2D9DF;
  --hairline-firm: #AFB9C2;

  /* ink */
  --ink:    #14202B;
  --ink-2:  #495663;
  --ink-3:  #78868F;

  /* status — the only saturated colours */
  --critical:    #A32A20;  --critical-bg:  #F7E4E2;
  --warn:        #85590A;  --warn-bg:      #F6EFE0;
  --ok:          #1C6B4A;  --ok-bg:        #E5F0EB;
  --unknown:     #514578;  --unknown-bg:   #ECE9F3;

  /* system feedback — quiet, grey not red */
  --muted-fail: #6B747C;

  --radius: 0;
  --border: 1px solid var(--hairline);
  --overlay-shadow: 0 0 0 1px var(--hairline-firm), 0 8px 24px rgba(20,32,43,.10);
}
```

**Accent — the one interactive colour, different per app:**

```css
/* R1 Phantom Stock-Out */
--action: #1B5E57;  --action-hover: #154A45;  --action-weak: #E3EFED;  --focus: #2A8A7F;

/* H4 Medication Safety */
--action: #1C4F86;  --action-hover: #163F6C;  --action-weak: #E2EBF4;  --focus: #2A79C0;
```

Shadow is used **only** on things that genuinely float: dropdown menus, drawers, toasts.

---

## 3. Typography

| Role | Family |
|---|---|
| Interface | **IBM Plex Sans** — 400 / 500 / 600 only |
| Data | **IBM Plex Mono** — 400 / 500 |

Load from Google Fonts. Fallback `ui-sans-serif, system-ui, sans-serif`.

**Mono is mandatory for:** SKU codes, store IDs, confidence scores, rupee amounts, dates, day counts, patient IDs, eGFR values, doses, drug codes, percentages, timings. Anything compared down a column.

| Token | Size / line | Weight | Use |
|---|---|---|---|
| display | 22 / 28 | 600 | Page title, one per screen |
| section | 15 / 20 | 600 | Panel headings |
| body | 13 / 18 | 400 | Default — the whole interface |
| data | 13 / 18 | 400 mono | Numeric cells |
| meta | 12 / 16 | 400 | Timestamps, secondary |
| label | 11 / 14 | 500 | Column headers, field labels |

13px base. These are operations consoles, not landing pages.

---

## 4. Layout

- Left rail **220px**, fixed, `--sunken`. App name at top, nav below.
- Top bar **48px**, fixed: breadcrumb left; context chips right.
- Content max-width **1600px**, left-aligned, 24px gutters. Never centred.
- Detail opens in a **right drawer, 480px** — not a modal. The list stays visible.
- Table row **40px**, header **32px**. Target 20+ rows visible at 1280×800.

---

## 5. Components (build once, share both apps)

`Table` · `Drawer` · `SegmentedControl` (with per-segment counts) · `StatusBar` (3px left bar + 6px square + label — **never a pill**, pills need radius) · `Dropdown` (custom, not native `<select>`; arrow keys, Enter, Esc, Home/End, type-ahead) · `Button` · `Stat` (big mono figure + small label) · `EmptyState` · `Chart` (hand-written SVG, no chart library)

**Status is always bar + square + text.** Remove the colour and it must still read. Roughly 8% of men have colour-vision deficiency, and a judge may be one.

---

## 6. Charts

Hand-written SVG. **No Recharts, no Chart.js, no D3.** Three chart types total across both apps, each under 80 lines:

1. Line + step chart (R1: sales vs stock)
2. Horizontal bar (both: contribution breakdowns)
3. Node-link graph (H4: alert graph)

Axis labels 11px `--ink-3`, 1px gridlines `--hairline`, series in `--action` and `--ink-3`. No legends unless more than one series. No 3D, no donuts, no area fills.

---

## 7. Motion

Interaction feedback 120ms. Drawer and menu 180ms. Nothing else moves. No entrance animations, no staggered fades, no hover lift. `prefers-reduced-motion` disables all of it.

---

## 8. The prototype chip

Top bar right, always visible:

```
Prototype · simulated dataset
```

11px, `--ink-3`, `--sunken` background, no border. Keep it. A judge who spots unlabelled fake data stops trusting everything else on screen; a judge who sees it labelled reads it as discipline. It costs nothing and it is the same instinct that makes the rest of the work credible.
