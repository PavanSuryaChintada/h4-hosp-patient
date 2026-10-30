# Mini fixtures

A hand-written miniature of the H4 data pack, in the pack's exact file layout and column names, for tests that must run without the pack: a fresh clone, or the grader's machine.

Six training patients and two test patients exercise the shapes that matter:

- a medication list split by line breaks
- `NA` pregnancy, and a blank eGFR and weight
- medicines marked stopped, and a non-medicine line
- combination brands at two strengths, a misspelt brand, an abbreviation, a synonym, a `+` combination and a hyphenated `-LC` combination
- the same line written twice, differing only in spacing

`train_resolution.csv` and `train_labels.csv` were worked out by hand from these tables and the pack README's rules. The drug facts are simplified test data, not a clinical reference. Brand and generic names are real, as in the pack.
