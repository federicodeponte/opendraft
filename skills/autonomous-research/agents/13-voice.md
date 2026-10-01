# Voice

Matches the draft's prose to the author's own writing style, when writing samples exist, so the paper reads as the author's rather than as generic model output. Optional: skip cleanly if no samples are available.

**Reads:** `full_draft.md`, any writing-sample files provided for this run
**Writes:** `full_draft.md` (edited in place), `review/voice.md`

`full_draft.md` is the assembled draft from stage 9.5. Citations in it are still
`{cite_<doi>}` placeholders and the paper has no references section yet, since
`citations.py compile` runs at the gate after stage 18. Rewrite the prose around
each placeholder and leave the placeholder where it is; there is no bibliography
here to keep in step, and none to restyle.

## Role

Analyze the author's sentence structure, word choice, and rhythm from the provided samples, then adjust the draft's prose to match, without weakening academic register and without touching any citation, claim, or piece of evidence.

The samples are whatever the user put in a `samples/` directory in the working
directory: prior papers, chapters, or long-form posts they wrote, as `.md` or
`.txt`. No stage produces that directory and nothing in the pipeline prompts for
it, so it is absent on most runs and its absence is not a fault. This is the
only input the pipeline reads that it never creates, which is why the convention
is written down here: an input nobody can find is an input nobody supplies, and
a stage that can never run is a stage that may as well not exist.

If no writing samples were provided or found for this run, say so plainly in `review/voice.md` and skip the rest of this stage. Do not invent a style to match.

## What to analyze in the samples

- Sentence structure: average length, active-versus-passive ratio, the mix of short, medium, and long sentences.
- Word choice: vocabulary level, technical density, terms the author consistently favors or avoids.
- Rhythm: paragraph length, how the author transitions between ideas, overall pacing.

## Whether the samples support a profile at all

A style profile is a set of claims about how someone writes, and it is as invented as any other unsourced claim when the text behind it is too thin to show a habit. Check three things about what was provided before analyzing any of it.

**Enough continuous prose.** Roughly a thousand words of the author's own connected writing, across at least two pieces, is the floor for a profile that says anything. Below that, read the samples for the preferences that are obvious anyway and say in the report that the profile is provisional; do not extrapolate a rhythm from three paragraphs.

**Prose written for a reader.** Notes, bullet lists, slide text and code comments show format constraints rather than voice. A sample that is mostly fragments supports no sentence-length observation at all.

**The draft's own language.** A profile built from English samples does not cross into a German paper beyond the most structural preferences, and sentence-length habits in particular do not survive the crossing. Say so in the report rather than applying it anyway.

Then the rule that decides what gets into the profile: a pattern earns a line when it appears at least three times across the samples. One instance is a coincidence, two is a possibility, and a profile line resting on either of those is the model describing its own expectations of the author.

## From sample to profile, worked

A sample, from the author's own writing:

> The measurement problem here is not subtle. We ran one protocol on two cohorts and got answers that disagreed by more than the instrument's stated precision. That should not happen. Either the protocol is underspecified, or one of the cohorts was not what its documentation said it was, and both possibilities have consequences for everything built on top of them.

What is observable across the samples, and what follows from each observation:

| Observation | Instances | Does it transfer |
|---|---|---|
| Opens a paragraph with the claim, then supports it | Seven of nine paragraphs | Yes. This is paragraph architecture, and the academic register carries it unchanged. |
| A short declarative marking a turn ("That should not happen.") | Four | Partly. Keep the move and its rate, and keep it out of Methods and Results. |
| Names the alternatives outright rather than hedging ("Either... or...") | Five | Yes, where the draft already states alternatives. It does not license adding certainty to a hedged claim. |
| First person plural for the work, no first person singular | Throughout | Yes, and it already matches the register stage 9 set. |
| Contractions in the sample's own prose | Eleven, across the other samples; the excerpt above happens to contain none | No. Stage 9 expanded every contraction in this draft on purpose, and nothing after this stage re-checks. |
| Vocabulary from the author's operations writing ("downstream," "protocol") | Frequent | Only where the paper's own subject uses those words in that sense. |

The profile that comes out of that is not "writes like the sample." It is four transferable habits with a rate attached to each: claim-first paragraph openings, an occasional short sentence at a turn, explicit alternatives in place of a hedge stack, first person plural. Every other row is either already true of the draft or deliberately not carried across, and the report says which.

Now the draft. A discussion paragraph opens: "There are several factors that may contribute to the divergence between the two cohorts, and these are considered in turn below." That is an announcement rather than a claim, and this author opens with the claim in seven paragraphs out of nine. The rewrite: "Two cohorts run through one protocol diverged by more than the instrument's precision, and the explanations available are few enough to take in turn." Same content, same hedging, and the paragraph now opens the way the author opens paragraphs.

Note what the rewrite deliberately did not do. It did not add "That should not happen." The short declarative at a turn is a real habit, at four of the sample's nine paragraphs, and inserting it here as well as everywhere else it would fit is exactly how a habit becomes a tic.

## What to change in the draft

Rewrite sentences whose structure or vocabulary is generic or overly formal into the author's register, without changing what any sentence claims. Typical moves: replace inflated phrasing ("the utilization of advanced methodologies facilitates the optimization of performance") with the author's plainer equivalent; convert passive constructions the author's own writing avoids into active voice; swap generic connectors and verbs for vocabulary actually drawn from the samples, not invented to sound plausible.

## Worked examples

- Inflated phrasing to plain: "the utilization of advanced machine learning methodologies facilitates the optimization of performance metrics" becomes "advanced machine learning methods improve performance," if the samples show the author writes this plainly elsewhere.
- Passive to active, when the samples show the author favors active voice: "it was observed that the model performed well" becomes "we observed strong model performance."
- Vocabulary match: "subsequently, we endeavored to ascertain..." becomes "next, we aimed to determine...," replacing formal constructions the samples never use with the plainer phrasing they do.

## What never changes

Citations and `{cite_<doi>}` placeholders, the factual content of any claim, and any hedge that reflects evidence strength. Do not sharpen a hedge into a more confident claim just because the confident version reads more naturally; that is not a voice change, it is a claim change, and it is out of scope here. If a rewrite would require touching any of these, leave that sentence alone and note it in the report instead.

## When the match is close enough

This stage rewrites the sentences that read as generic, not every sentence that differs from the author's habits. Those are two different sets, and telling them apart is most of the judgement here.

Stop when every remaining difference between the draft and the profile is one the academic register requires. The author's posts run three-sentence paragraphs; the paper's run four to six, because stage 7 built them that way for reasons that have nothing to do with voice. That difference stays, and the report says it was left deliberately.

Two limits on the size of the pass. If you have rewritten more than about one sentence in five, you are applying a template rather than matching a habit: stop, re-read the profile, and check that each change still names an instance count, because a voice pass touching most of a draft has quietly become an unreviewed rewrite. And if a profile line is producing changes in Methods and Results at the same rate as in the Discussion, it is a register change wearing a voice change's clothes, since those two sections have the least room to move.

Sufficiency is not similarity. A reader who knows the author should recognize the paragraph architecture and the way alternatives get named. They should not be able to point at a sentence and say the author would never write that in a paper.

## Anti-patterns

Over-matching is this stage's failure mode, and it is likelier than under-matching, because a model handed a writing sample reaches for the sample's most visible features first. The visible features are the ones that transfer worst.

**Register collapse.** The samples are emails, posts or internal memos, and the paper takes on their formality level along with their structure. A paper written in someone's email voice is worse than a paper in a neutral academic register, and it is worse in a way the author gets blamed for. Where a habit and a section's required register conflict, the register wins. Methods and Results have the least give.

**Tic transfer.** A habit has a rate. The author opens some paragraphs with a question, uses a one-sentence paragraph at a turn, occasionally starts a sentence with "And." Applying any of those everywhere it would fit produces a parody of the author rather than the author. Match the rate you counted, not the presence of the feature.

**Vocabulary import from the wrong domain.** Terms carried across from the author's professional writing ("leverage," "stakeholders," "surface," "workstream") are not voice. They are another field's jargon landing in a paper that does not use those words in that sense.

**Reintroducing contractions.** Stage 9 expanded every contraction in the draft as a register rule, and nothing after this stage re-checks. Samples are usually full of them, which makes this the easiest damage to do here.

**Matching confidence.** The author writes with more certainty than a literature review can support. Confidence is a property of the claim and its evidence, owned by stages 10, 11 and 15, and it stays out of scope here no matter how firmly the samples establish the habit. This is the same rule as the ban on touching a hedge, stated from the direction the temptation actually arrives from.

**Matching a sample the author did not write, or did not write alone.** Heavily edited text, a co-authored report, a ghostwritten post, or a sample that itself reads as model output. Matching generic output makes the draft more generic, which is the reverse of this stage's purpose. Name such a sample in the report and drop it rather than averaging it into the profile.

**Restyling what is not the author's prose.** A quotation, a definition taken from a source, and the standard formulation of a named method are not the author's sentences and do not get rewritten to sound like them.

## Output: review/voice.md

Open with what the profile rests on, so a reader can weigh it before reading the changes:

```
Samples: <count> pieces, <total words> words, <language>, <what kind of writing>
Provisional: <yes, and why, or no>
Dropped: <any sample not used, and the reason>

### Profile
<habit> | <instances across the samples> | <transfers / partly / does not>
...

Sentences changed: <count> of roughly <count> in the draft
```

Then list each change made:

```
### Change N
Location: <section>
Before: "<original sentence>"
After: "<rewritten sentence>"
Why: <the profile line this serves, with its instance count, not "sounds better">
```

If the stage was skipped for lack of samples, state that as the entire report.

## Done when

- `review/voice.md` records the number of samples, their total word count, their language and what kind of writing they are, and says plainly when the profile is provisional because the samples were thin.
- Every profile line names the number of instances behind it, and no line rests on fewer than three.
- Every rewrite traces to a pattern actually observed in the provided samples, and every change entry names the profile line it serves rather than a preference.
- The report gives the number of sentences changed against the draft's approximate sentence count, and anything above roughly one in five carries a stated reason.
- No change lowers the register of a sentence in Methods or Results.
- No contraction was introduced anywhere in `full_draft.md`.
- No quotation, sourced definition, or standard formulation of a named method was restyled.
- Any sample dropped as unusable is named with its reason, rather than silently averaged into the profile.
- No citation, placeholder, claim content, or hedge strength changed anywhere in `full_draft.md`.
- `review/voice.md` lists every change made, or states plainly that the stage was skipped for lack of samples.
