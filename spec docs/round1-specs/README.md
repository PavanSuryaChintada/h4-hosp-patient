# Round 1 demo specs — two problem statements

Four documents plus a shared design system. Both apps are **frontend only, hardcoded data, built for a demo video**.

| File | What it is |
|---|---|
| `SHARED-DESIGN-SYSTEM.md` | Read first. Tokens, typography, components, the anti-slop rules. Both apps use it. |
| `R1-TRD.md` | Phantom Stock-Out — stack, data generation, screens, build order |
| `R1-DESIGN.md` | Phantom Stock-Out — layout, components, screen-by-screen design |
| `H4-TRD.md` | Medication Safety — stack, data generation, screens, build order |
| `H4-DESIGN.md` | Medication Safety — layout, components, screen-by-screen design |

## How to use with Claude Code

One app per session. Paste this first:

```
Build the demo app in R1-TRD.md (or H4-TRD.md), following SHARED-DESIGN-SYSTEM.md and
R1-DESIGN.md (or H4-DESIGN.md) literally.

HARD RULES
- Frontend only. No backend, no API calls, no network at runtime.
- All data is static JSON committed under /src/data, generated once by /tools/generate.py.
- border-radius 0 everywhere. No gradients, no glows, no shadows except drawer and dropdown.
- The only saturated colours are status colours.
- Hand-written SVG charts. No chart library.
- IBM Plex Sans + IBM Plex Mono. tabular-nums globally. Sentence case labels.
- Spacing only from 4/8/12/16/24/32/48.

Start with tools/generate.py and the fixtures. Show me the generated numbers before
building any UI — if the data is not convincing, the app cannot be.
```

## The single demo moment in each

- **R1:** the ranking toggle. `₹ recovered` vs `Confidence` reorders the list in front of the judge and the caption shows the value that drops out.
- **H4:** the collapse toggle. `3 alerts` vs `11 alerts` shows alert fatigue and the fix in one click.

Build and rehearse those two first. Everything else supports them.

## Honest scoping

Both are specified at 4–6 hours each with Claude Code, not 4. The data generator is the long pole in both — about a third of the total. If you are short, build the generator properly and cut UI screens from the bottom of each TRD's cut list. A thin app on convincing data beats a rich app on obviously fake numbers.
