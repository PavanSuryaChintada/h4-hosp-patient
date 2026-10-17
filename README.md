# Medsafe

**Medication safety, a second pair of eyes.**

A prescriber has about twenty seconds for a medication check. Medsafe reads the medicine list the way it is written on the slip, resolves messy brand and generic names, checks the list against interaction, renal, duplicate-therapy and pregnancy rules, re-scores every flag for the patient in front of you, and collapses clusters of alerts into the one change that clears them.

Alert fatigue is the problem it targets. A screen with three alerts and a clear action beats a screen with eleven and a scroll bar.

## The idea in one click

Patient `2291`: 74 years, eGFR 28, nine medicines, eleven raw warnings.

| View | Alerts | Top line |
|---|---|---|
| Every pair | 11 | Five separate warnings about diclofenac, three low-severity notes |
| Collapsed | 3 | *Stop diclofenac — clears 4 of the 5 serious interactions* |

Use the `Collapsed / Every pair` toggle on any patient to switch between the two views.

## Live demo

**https://pavansuryachintada.github.io/h4-hosp-patient/**

Sign in with any demo account below; clicking an account on the sign-in page signs you in directly. A guided walkthrough starts after the first sign-in and can be restarted from the top bar.

| Role | Email | Password |
|---|---|---|
| Consultant physician | `prescriber@medsafe.demo` | `Medsafe@2026` |
| Clinical pharmacist | `pharmacist@medsafe.demo` | `Pharma@2026` |
| Reviewer | `reviewer@medsafe.demo` | `Review@2026` |

These are hardcoded demo accounts. There is no real authentication; the session is kept in the browser.

## Screens

| Route | What it shows |
|---|---|
| `/` | Overview: live collapse demo, architecture, a worked end-to-end example, comparison with a typical checker, tech stack |
| `/login` | Sign-in with the demo accounts listed underneath |
| `/app` | Patient queue, ranked by severity, with filter counts |
| `/app/patient/:id` | Context strip, capped alert list with collapse toggle, alert graph, medicines as written → resolved, limitations footer |
| `/app/resolution` | Every raw medicine string in the cohort, what it resolved to, confidence, method, and a ground-truth check |
| `/app/method` | The four-step pipeline, the same renal flag on two patients, the graph before and after the collapse |
| `/app/evaluation` | Alerts per patient against near-miss recall, alerts by severity, and the cases that were missed |

`/app/patient/2291?view=all` opens straight into the every-pair view.

## Guided walkthrough

Thirteen steps that move through the app on their own and highlight one thing at a time: the queue, patient 2291's context, the three collapsed alerts, the every-pair view, the alert graph, the slip as written, the limitations footer, name resolution, the method and the evaluation. Arrow keys move between steps; Esc closes it.

## How it works

1. **Resolve names.** Raw slip text such as `"Warf 5"`, `"crocine"` or `"PAN-D"` maps to a generic with a confidence. When the top two candidates are too close, the system abstains and asks for a manual check instead of guessing.
2. **Check rules.** Interaction pairs (class-level rules such as NSAID + ACE inhibitor), duplicate therapy (including the same drug under two brands), renal dose against eGFR, and pregnancy contraindications.
3. **Re-score in context.** Each rule carries a modifier. A moderate NSAID + spironolactone flag becomes high at eGFR 28. The same metformin renal flag is high at eGFR 28 and low at eGFR 80. Both the table severity and the re-scored severity are stored and shown.
4. **Collapse and cap.** Drugs are nodes and serious interactions are edges. The system finds the drug whose removal clears the most serious edges, among the drugs the rule table allows stopping. Warfarin, lithium and insulin are never suggested for stopping. What remains is ranked by severity and confidence and capped at five.

Every suggested action comes from the rule tables, not from a model.

## Running it

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # type-check and production build
```

There is no backend, no API and no network access at runtime.

## Deploying

**GitHub Pages (live now).** `.github/workflows/pages.yml` builds on every push to `main` with `BASE_PATH=/h4-hosp-patient/` and copies `index.html` to `404.html`, so deep links work on Pages.

**Vercel.** Import the repo, keep the detected settings, deploy. `vercel.json` pins the build (`npm ci`, `npm run build`, output `dist`) and rewrites every path to `index.html`, so deep links such as `/app/patient/2291` survive a refresh. Vercel serves from the root, so no base path is needed.

```bash
npx vercel          # preview
npx vercel --prod   # production
```

## Project layout

```
src/
  data/
    drugs.ts        generics, Indian brand names, interaction / renal / pregnancy rules
    patients.ts     simulated cohort, medicine lists as written
    engine.ts       rule pass: re-scoring, duplicates, renal, pregnancy, collapse, cap, metrics
    evaluation.ts   near-miss labels and the reported misses
  components/       shell, status primitives, alert graph, SVG charts, guided walkthrough
  screens/          landing, sign-in, queue, patient detail, resolution, method, evaluation
  auth.tsx          hardcoded demo accounts and the protected-route guard
spec docs/          technical requirements and design specifications
```

## What is real and what is not

- **Real:** the drug interactions and renal rules (clinically genuine, commonly cited). The patient-context re-scoring, the graph collapse and the five-alert cap, which run over the data in the app.
- **Simulated:** all patients and medicine lists. The name-resolution outputs with their ground-truth labels, and the near-miss labels, are fixtures. No real patient data was used.
- **Reduced:** 68 generics and 89 interaction rules, expanding to 195 drug pairs, rather than a full reference set.

## Safety framing

- The app never describes a patient as safe. When nothing is flagged it says no issue was found in what was seen.
- A medicine name it cannot resolve is shown as unresolved and marked as not checked.
- A permanent footer on every patient states that the list may be incomplete and that a clinician decides.

## Design

IBM Plex Sans and Plex Mono, tabular numerals, zero border radius, no gradients or shadows on cards. The only saturated colours are status colours, and every status is a bar, a square and a word, so it still reads without colour. Charts are hand-written SVG, with no chart library.
