# Entropy

Real writing varies sentence length and structure. A draft where every sentence runs the same length and shape reads as monotone and mechanical, and that uniformity is a genuine prose defect on its own terms, independent of who or what wrote it.

**Reads:** `full_draft.md`
**Writes:** `full_draft.md` (edited in place), `review/entropy.md`

`full_draft.md` is the assembled draft from stage 9.5. Citations in it are still
`{cite_<doi>}` placeholders and there is no references section yet, since
`citations.py compile` runs at the gate after stage 18. A placeholder is not a
rhythm problem: when you split or join a sentence, carry the placeholder with the
clause whose claim it supports, and do not count it as a word.

## Role

Vary sentence rhythm, structure, and vocabulary so the draft reads like considered prose rather than a template repeated with different nouns. This stage does not change what the paper claims, and it does not change authorship or disclosure obligations: the paper is still AI-assisted work if it was AI-assisted, and nothing here is about scoring against or evading any AI-detection tool. Do not run one.

## What uniform prose looks like

- Every sentence sits in a narrow length band, say 12 to 15 words, instead of a natural mix of short, medium, and long.
- The same handful of transition words carries every connection: "additionally," "furthermore," "moreover," "consequently," on nearly every paragraph.
- Every sentence follows the same subject-verb-object shape: none inverted, none built around a subordinate clause, none a deliberate fragment.
- The same three or four words carry every instance of a concept: "significant," "utilize," "facilitate," repeated well past what the idea needs.

## Fixes

- Sentence length: aim for a natural mix, roughly 30 percent short (under 15 words), 50 percent medium (15 to 25) and 20 percent long (over 25), varying by section rather than applying one fixed formula to the whole draft. Those three are a distribution, so they sum to 100, and averaging them over their band midpoints is where stage 15's mean-sentence-length band comes from; landing this mix here is what makes that band reachable there, rather than a second target competing with it. The check that decides whether there is work to do is local rather than aggregate, and the next section says how to run it.
- Sentence structure: mix simple, compound ("and"/"but"/"or"), complex ("because"/"although"), and occasional compound-complex sentences; use a fragment only rarely, for emphasis, never in a methods or results section.
- Vocabulary: replace a repeated crutch word with the plainer or more precise alternative the sentence actually calls for, not a random synonym. "Utilize" to "use," "in order to" to "to," "facilitate" to "enable" or "help," "significant" to "substantial," "considerable," "meaningful," or, better, an actual number. This covers crutch words and evaluative adjectives. Terms of art are out of scope, and the anti-patterns below say why.
- Syntax: use passive voice where the actor is genuinely unimportant or unknown, roughly 10 to 20 percent of sentences is normal for academic prose, not zero and not the majority, and vary how paragraphs open so they don't all begin with the same topic-sentence template.
- Register, section-scoped: in the Discussion and Introduction only, never in Methods or Results, a sparing amount of informality reads as considered rather than sloppy. That means a colloquial verb where it is as precise as the formal one it replaces ("falls short of the threshold"), or direct address to the reader ("Consider this result"). It does not mean a contraction: stage 9 expanded every contraction in the draft as a register rule, and nothing after this stage re-checks. The move is register, not content: "The model achieved 94.7% accuracy on the validation set" becomes "The model hit 94.7% accuracy on validation data," same claim, same number, same source attached, just a less formal verb in a section where that reads as confident rather than careless. Keep it to a handful of moves per section, and do not carry it into a Methods or Results section, where the formal register is the correct one.

## How to check a section

Every threshold here is checkable by counting, and the counts belong in the report. Count one section at a time. A full-length draft averages away the local monotony this stage exists to fix.

Count words per sentence, not characters. A placeholder is not a word: skip any `{cite_<doi>}` when counting.

Bands: short is under 15 words, medium is 15 to 25, long is over 25.

**The primary check is local.** A section can land on any aggregate distribution you like and still read as a metronome, because an aggregate does not care where the sentences sit. Two paragraphs of uniformly short sentences followed by two of uniformly long ones produce a respectable histogram and a section nobody wants to read. So the check that decides where to edit is the run:

- Three consecutive sentences in the same band is a run.
- Three consecutive sentences whose lengths fall within three words of each other is also a run, even when a band edge falls between them. Fifteen, sixteen and fourteen words in a row read as uniform, and the boundary at 15 is a convenience rather than a fact about prose.

Fixing runs fixes the aggregate as a side effect. Chasing the aggregate does not fix the runs.

**The aggregate, second.** Report the sentence-type mix per section as three counts. About 65 percent simple, 30 percent compound and 5 percent complex is the shape of monotony; something closer to 40, 35 and 25 is the shape of varied academic prose. Move from the first toward the second. It is a direction, not a target, and a section that arrives at 38/37/25 by splitting sentences for no reason other than the count has been made worse rather than better.

**Type-Token Ratio, and the window it needs.** TTR is unique word forms divided by total words, and it falls as the text grows, because function words repeat no matter who is writing. A TTR quoted with no window size attached is therefore not a number anyone can reproduce, and comparing a 400-word section against a 2,000-word one compares their lengths rather than their vocabularies.

Compute it over consecutive 200-word windows inside a section and report the mean. Then act on the change rather than the level: the same windows measured before and after this stage's edits are directly comparable, and a rise is evidence that the crutch words actually got varied. As rough orientation at that window size, a mean near 0.42 reads as repetitive and near 0.58 reads as varied, but the level moves with how dense the section is in technical terms, and a methodology section repeating one instrument's name is not defective for scoring low.

## Worked example

Before: "The results demonstrate significant improvement. This improvement is important because it addresses a key challenge. Additionally, the approach shows promise for future applications. Furthermore, the methodology enables broader adoption." Four sentences of 5, 10, 8 and 6 words: every one of them in the short band, which is a run of four under the check above, and the run is what makes the passage read as a metronome. Two open with a stacked transition word, and "significant" and "improvement" are doing double duty.

After: "The results show substantial improvement over baselines. This matters: it addresses a challenge the field has struggled with for years. The approach also shows promise for clinical applications, and the methodology is straightforward enough for broader adoption." Same claims, same evidence, same citations if any were attached; the lengths now run 7, 13 and 17 words, which ends the band run and clears the three-word rule, the repeated transitions are gone, and the second sentence uses a colon instead of "this is important because" to make the same connection more directly.

Overshot, for contrast: "The results are a clear win. This matters, and it matters a lot: the field's been stuck here for years. The approach could work in clinics too, and honestly the methodology is simple enough that anyone could adopt it." The rhythm varies and the counting checks all pass. It also states a stronger result than "substantial improvement over baselines," reintroduces a contraction stage 9 removed, and turns a hedged clinical suggestion into a confident one. Two of those are claim changes, which this stage may not make at any rhythm.

## Anti-patterns

**Overcorrecting into informality.** The register moves above are narrow on purpose. A colloquial verb belongs where it is as precise as the formal one it replaces; "falls short of the clinical threshold" is fine, "the model kind of struggles here" is not, and neither is any verb that blurs a measured quantity. Keep to a handful of moves per section, Discussion and Introduction only, and drop the move rather than reaching for a second one in the same paragraph. Variety is the goal, informality is one instrument for it, and it is the least reliable one available.

**Reintroducing contractions.** Stage 9 expanded every contraction in the draft as a register rule, and nothing after this stage re-checks, so a contraction added here ships in the paper. Take the variation from sentence architecture instead.

**Splitting a sentence and dropping its hedge.** "X may improve Y because Z" split into "X improves Y. The reason is Z." reads better and claims more than the evidence carried. Every split preserves the modal and the attribution on whichever half needs them, and a split that leaves a bare assertion behind is a claim change this stage is not permitted to make.

**Varying a term of art.** The vocabulary rule reaches crutch words and evaluative adjectives. It does not reach defined terms, method and instrument names, variable names, acronyms, or any word the paper itself defined. "Statistically significant" is not an instance of "significant" to be varied; replacing it with "substantial" deletes a technical claim. Renaming "random forest" to "tree ensemble" for variety undoes the terminology consistency stage 8 just enforced, and stage 8 does not run again.

**Editing to move a number.** A sentence split, joined or added so a count lands better, carrying no content the paragraph did not already have, is padding with a metric for an excuse. The tell is that the edit has no defense other than the histogram.

**Treating a section's natural rhythm as a defect.** Methods prose repeats because procedures repeat, and a step sequence that reads as parallel is doing its job. A results section reporting five measurements in the same frame is easier to compare than one that varies the frame each time. Vary these sections least, and never at the cost of the parallelism a reader is using to read across them.

**A fragment outside its range.** A fragment in Methods or Results reads as an editing error rather than as emphasis, and a reader cannot tell the difference from the outside.

## What never changes

Citations and `{cite_<doi>}` placeholders stay exactly where they are relative to the claim they support. Do not add a claim, qualifier, or number that wasn't already in the sentence for the sake of rhythm. Do not soften or sharpen a hedge; that is the polish stage's calibration job, not this one's. If a variation would change what a sentence asserts, leave the sentence alone.

## Output: review/entropy.md

For every section that changed materially, report these before and after, as counts rather than impressions:

- Sentence count, and the three length-band counts (short, medium, long).
- The longest run of consecutive sentences in one band, and the longest run within three words of each other.
- The sentence-type counts (simple, compound, complex).
- Mean Type-Token Ratio over 200-word windows, with the window size stated.
- The most-repeated non-technical words, with how many instances of each were varied.

Then a handful of concrete before/after sentence pairs. The pairs matter more than the counts: they let a human confirm meaning was preserved, not just that style shifted. Include any pair where a sentence was split, since that is where a hedge goes missing.

## Done when

- No section still carries a run of three consecutive sentences in the same length band, or three consecutive sentences within three words of each other, except where a parallel construction in Methods or Results is doing real work for the reader.
- No single sentence-length band accounts for more than about half the sentences in any section.
- No non-technical word appears more than roughly five times per page.
- Sentence-type mix has moved toward, not necessarily onto, the roughly 40/35/25 simple/compound/complex range in sections that started closer to 65/30/5, and no sentence was split, joined or added whose only justification is that count.
- Mean Type-Token Ratio is higher after than before, measured over the same 200-word windows, in every section whose crutch words were varied. The window size is stated in the report, since the level means nothing without it.
- No term of art was varied: no defined term, method or instrument name, variable name, acronym, or term the paper itself defined.
- Every sentence split preserved the modal and the attribution of the original; no split left a bare assertion where a hedged claim stood.
- Any strategic-informality moves are confined to Discussion and Introduction, countable and few, and no contraction appears anywhere in `full_draft.md`.
- `review/entropy.md` shows concrete before/after pairs and confirms no claim, citation, or hedge changed.
