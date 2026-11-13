# Quote validation fix (typographic canonicalisation)

**Problem (found by replaying real Groq responses):** 27 of 68 real drafts were rejected, 25 as "quote not verbatim".
Cause: the model writes U+2011 non-breaking hyphens (19 quotes) and en dashes (5) where the PDF text has ASCII `-`,
and PDF extraction leaves line-break hyphenation ("theoret- ical"). Rejected drafts triggered expansion, then an
honest-but-wrong refusal, so answerable questions were refused ("refused_wrongly").

**Fix:** `relay.pipeline.canonical()` maps dash variants, curly quotes, NFKC ligatures, joins line-break hyphenation,
and compares case-insensitively. The quote must STILL be an exact contiguous substring: no fuzzy match.

**Replay of the same 68 real responses through the real `validate()`** (offline, zero API calls):

| | valid answer | valid refusal | quote not verbatim | quote too short |
|---|---|---|---|---|
| before | 19 | 22 | 25 | 2 |
| after | 38 | 22 | 6 | 2 |

The remaining 6 are genuine: the model "completes" a flattened fraction ("/sqrt(dk)") that the PDF text does not
contain, or splices two spans with "...". They stay rejected on purpose.

**Not yet measured:** end-to-end answer quality after the fix. It needs a new real eval (about 100K tokens; check the
daily ledger first) and HAND grading. Quote presence is still not entailment. A prompt change asking for ONE
contiguous quote, no ellipses and no equations is recommended but untested against the real model.
