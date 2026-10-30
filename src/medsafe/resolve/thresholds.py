"""Name-resolution thresholds, in one place.

MIN_CONFIDENCE and MIN_MARGIN start at the Phase 2 spec's guesses and are tuned by
``python -m eval.sweep`` on the dev split: the setting with the best resolution accuracy whose
false-resolution rate stays at or below MAX_FALSE_RESOLUTION_RATE (docs/DECISIONS.md D-016).
A wrong resolution is worse than an abstention: it can raise a confidently wrong alert.
"""

# Swept values (docs/sweep.md). The spec's starting guesses were 0.72 and 0.05: they abstained
# on 5.9% of dev lines, nearly all of them misspellings whose top candidate was right.
MIN_CONFIDENCE = 0.45        # best fuzzy score below this: abstain, "no_confident_match"
MIN_MARGIN = 0.00            # best minus second-best (different drug) below this: "ambiguous".
                             # An exact tie between two drugs always abstains, whatever this is
MAX_FALSE_RESOLUTION_RATE = 0.02

MIN_PREFIX_LENGTH = 5        # a truncated name ("rosuvastat") must keep this many characters
PREFIX_CONFIDENCE = 0.90     # confidence given to a unique prefix match
HYPHEN_PART_MIN_CONFIDENCE = 0.80   # a fuzzy piece of a hyphenated name ("monteleukast-LC")
                                    # must be this close; brand fragments ("Mftal-Spas") are not.
                                    # A fixed safety floor, not swept
FUZZY_TOP_K = 10             # candidates taken from each generator before reranking
MAX_EXTRA_HEAD_WORDS = 2     # words after the name tried for brands with numbers ("Mixtard 30")
