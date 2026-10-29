// Near-miss evaluation. 30 subtle-but-serious issues were seeded into the cohort;
// the two misses below both trace back to name resolution and are visible in the data.

export const NEAR_MISS = {
  seeded: 30,
  caught: 28,
  missed: [
    {
      patient: '2296',
      issue: 'Clarithromycin + colchicine',
      expected: 'High: colchicine toxicity',
      reason: '"Colcy 0.5" sat 0.04 between colchicine and Colospa, so the resolver abstained. The pair was never checked. The abstention was shown, but no interaction alert was raised.',
    },
    {
      patient: '2307',
      issue: 'Digoxin + furosemide',
      expected: 'Medium: hypokalaemia potentiates digoxin',
      reason: '"Lasx 40" resolved to losartan at 0.81 instead of furosemide. The real pair was missed, and a false dual-RAS alert was raised in its place.',
    },
  ],
};
