# Did this Skill actually help?

We built a Skill, then measured it against not having it. Same model, same tasks, same grader,
same sandbox. The only thing that changes between the two arms is whether the Skill is loaded.

**No resolved effect. At 8 judged pairs the Skill arm scored 13.7 rubric points above the
baseline, 95% interval [-9.9, +37.4]. We then doubled the samples. At 16 judged pairs the same
comparison gave 6.6 points, 95% interval [-55.6, +68.7]. The interval covers zero both times, so
neither number is a result. The estimate halved when the sample doubled, and the interval got
much wider.**

The harness records its own verdict on both, in the field `resolved`, as `unresolved`.

These intervals are wider than anything else on this benchmark, and the reason is worth stating
before the numbers below rather than after. This run has **two tasks**. Every interval here is
built from the spread between two task means, which is one degree of freedom, and one degree of
freedom buys almost nothing: the multiplier on the standard error is 12.7 here against 4.3 on a
three-task run. Sixteen pairs does not compensate, because the sixteen sit on those same two
tasks. A two-task run cannot resolve anything at this scale and should not have been launched
expecting to.

Run date: 2026-09-16, run `heldout`. This is one run. It has not been repeated.

> **Correction, 2026-09-17.** The intervals on this page were recomputed and one claim was
> withdrawn. They used to read [-4.2, +32.5] and [-8.1, +20.7], and this page used to cite a
> resolved +3.1 point result for the same Skill on the v1 tasks. All three came from a percentile
> cluster bootstrap that we have since measured to be anti-conservative at small task counts: at
> three tasks it excludes zero about 15.7% of the time when the true effect is exactly zero,
> rather than 5%. Recomputed with a correctly sized interval, the two figures on this page stay
> unresolved and widen, and the v1 result **stops resolving**: +3.1 points, 95% interval
> [-1.4, +7.6]. This Skill now has no resolved result on any task set. No estimate moved and no
> count moved. The reasoning is in [`docs/BENCHMARK.md`](../docs/BENCHMARK.md) section 5 and the
> withdrawal is recorded in [`evals/WITHDRAWN.md`](../evals/WITHDRAWN.md).

## Why both numbers are on this page

The n=8 extension was launched after we had seen the n=4 point estimate, and we launched it
because that estimate looked good. That is optional stopping, and it matters.

If you keep adding samples and stop as soon as the number pleases you, you will stop on a high
number sooner or later even when nothing is there. The published false-positive rate no longer
applies, because the decision of when to look was made using the data. The fix is not to hide
the intermediate look. It is to publish every look you took.

So: both n figures are published together and always will be. Quoting the n=4 figure on its
own would have been the most misleading number we could have printed. It was the larger of the
two, it was the one we saw first, and it did not survive doubling the sample.

## The other task set, and a result this page used to lean on

This Skill has been measured on two different sets of tasks. The getedge.cc page for this Skill
carries the 16-pair figure from this run. The v1 figure belongs here, on the page that used to
lean on it.

On the three v1 tasks, written alongside the Skill, the arm with the Skill in the prompt scored
+3.1 points over 9 pairs. Until the correction above, that cell was this Skill's one resolved
result, on a bootstrap interval of [+0.2, +6.5] that cleared zero by two tenths of a point.
Recomputed correctly the interval is [-1.4, +7.6] and it does not clear zero. The checker still
agrees with the direction, 88.9% of Skill-arm attempts passing against 77.8% of baseline
attempts, but a checker agreeing with the direction of an unresolved judge delta is not a
resolution either. Those numbers are in `results/v1/summary-indep-v2.json`, which is a different
run from the one this page documents and is not in this bundle.

On the two tasks written afterward, the ones on this page, the same arm scored +6.6 points over
16 pairs, interval [-55.6, +68.7], and the checker passed 0 of 16 attempts in both arms.

The tempting read was overfitting, and it was never one we could support. The two task sets are
not the same difficulty, and the checker numbers show it: on the v1 tasks the baseline already
passed 77.8% of the time, and on these two neither arm passed once. A +3.1 on tasks where the
baseline was already close to the ceiling and a +6.6 on tasks neither arm can do are not
measurements of the same thing.

What the pair establishes now is shorter than what this page used to claim. This Skill has no
resolved result on either task set. The direction is positive in both, by about three points on
one and about seven on the other, and neither is distinguishable from nothing at the task counts
we ran.

## Everything is published

Every number here can be checked against the thing it came from: all 32 session logs turn by
turn, every file the agents wrote, all 32 grader verdicts with their reasoning and per criterion
scores, all 32 hard-check results, the two task definitions and their checker scripts, and both
summary files. They are in
[`evals/autonomous-research/2026-09-17/`](../evals/autonomous-research/2026-09-17/).

The 32 verdicts cover 16 pairs judged in both presentation orders. The n=4 set is not a separate
run: it is samples 1 to 4 of each cell, frozen as `summary-n4-frozen.json` before the extension
was launched so that it could not be quietly replaced. `summary-n8.json` is the full set.

Nothing is summarised there. If a summary here disagrees with an artifact there, the artifact is
right.

## What was measured, exactly

The file the run loaded is the 560 line `SKILL.md` for this Skill. It was diffed against the
`SKILL.md` inside the live published `autonomous-research` package. The two are identical except
for exactly two lines: the `name:` field in the frontmatter and the H1 heading. So this is a
measurement of the published Autonomous Research skill text.

The catalog also publishes a package literally called `opendraft`. Its `SKILL.md` is a different,
older file, 396 lines against 560. It was not what was measured. Nothing on this page applies to
it, and we make no claim about it.

The task ids and the result files use `opendraft` as the internal identifier for this Skill. That
is an alias, not the older package.

## The numbers

| | n=4, 8 pairs | n=8, 16 pairs |
| --- | --- | --- |
| Rubric score, Skill arm | 57.2 | 54.7 |
| Rubric score, baseline | 43.5 | 48.1 |
| Difference | +13.7 | +6.6 |
| 95% confidence interval | [-9.9, +37.4] | [-55.6, +68.7] |
| Harness verdict | `unresolved` | `unresolved` |
| Tasks behind the interval | 2 | 2 |
| Relative uplift | 31.6% | 13.6% |
| Pairs won / tied / lost | 2 / 3 / 3 | 4 / 7 / 5 |
| Win rate | 43.8% | 46.9% |
| Grader self-disagreements | 3 of 8 | 7 of 16 |
| Holistic score, Skill arm | 45.0 | 46.7 |
| Holistic score, baseline | 43.2 | 47.5 |
| Hard checks fully passed, Skill arm | 0 of 8 | 0 of 16 |
| Hard checks fully passed, baseline | 0 of 8 | 0 of 16 |
| Hard-check score, Skill / baseline | 0.749 / 0.645 | 0.747 / 0.639 |
| Model cost per attempt, Skill / baseline | $2.875 / $0.233 | $3.010 / $0.303 |
| Turns per attempt, Skill / baseline | 87.3 / 10.6 | 87.9 / 12.2 |
| Infrastructure errors | 0 | 0 |

Four things in that table are worth stating out loud.

**The win rate never separated from a coin flip.** 43.8% at n=4 and 46.9% at n=8, both on the
wrong side of 50. It is printed without an interval, here and everywhere else on this benchmark:
a win rate is bounded between 0 and 100%, the interval we use on the judge gap is not bounded,
and on this run it puts the win rate between -151.7% and +245.4%. An interval that wide on a
quantity that narrow is not telling anyone anything. At n=4 the win rate and the rubric delta
pointed in opposite directions: the rubric said the Skill arm was 13.7 points ahead while the
head to head count was 2 wins against 3 losses.

**The grader's two metrics disagree in sign.** The rubric score and the holistic score come from
the same grader, on the same documents, in the same call. At n=8 the rubric score puts the Skill
arm 6.6 points ahead and the holistic score puts it 0.8 points behind.

**The hard check resolved nothing.** Zero attempts in either arm passed every gate, at either
sample size. A pass rate of 0 against 0 carries no information about the Skill. The hard-check
*score*, which is the fraction of individual items passed, does move: 0.747 against 0.639 at
n=8. That is the one measurement on this page that is not a grader opinion, and the section
[what actually moved](#what-actually-moved) breaks it down item by item.

**The Skill arm cost about ten times as much.** $3.01 against $0.303 per attempt, 87.9 turns
against 12.2. For no resolved gain.

### Per task

Two tasks, so the confidence interval is built from two task means and one degree of freedom.
That is the whole reason it is wide, and no amount of extra sampling inside those two tasks
fixes it.

| Task | n | Skill | Baseline | Difference | Won / tied / lost | Hard-check score |
| --- | --- | --- | --- | --- | --- | --- |
| phone-policy-brief | 4 | 57.5 | 45.6 | +11.9 | 0 / 2 / 2 | 0.716 vs 0.659 |
| ssb-levy-rea | 4 | 56.9 | 41.3 | +15.6 | 2 / 1 / 1 | 0.783 vs 0.631 |
| phone-policy-brief | 8 | 54.2 | 52.5 | +1.7 | 0 / 5 / 3 | 0.716 vs 0.648 |
| ssb-levy-rea | 8 | 55.1 | 43.7 | +11.4 | 4 / 2 / 2 | 0.777 vs 0.631 |

At n=4 the two tasks agreed with each other, +11.9 and +15.6. We read that at the time as
variation between samples of the same task, and doubling the samples as the right response.
That reading was wrong, and the correction at the top of this page is why. The interval here is
built from how far the two task means sit apart, so samples inside a task cannot narrow it; what
doubling the samples did was move the task means themselves, from +11.9 and +15.6 to +1.7 and
+11.4, which is a much larger spread and therefore a much wider interval. The phone-policy-brief
collapse from +11.9 to +1.7 was driven by the baseline arm improving from 45.6 to 52.5 rather
than by the Skill arm falling.

The lever we should have pulled was more tasks. We have since measured both: at three tasks,
going from three samples to six moves the chance of detecting a real five-point effect from 0.14
to 0.16, while going from three tasks to six moves it from 0.14 to 0.38. This run has two
tasks.

### Every pair

Rubric score for the Skill document minus the baseline document, one row per pair. Samples 1 to
4 are the n=4 set.

| Sample | phone-policy-brief | ssb-levy-rea |
| --- | --- | --- |
| s1 | +15.0 | -8.3 |
| s2 | -29.2 | +58.3 |
| s3 | +12.5 | +16.5 |
| s4 | +49.2 | -4.2 |
| s5 | +29.2 | -0.8 |
| s6 | -23.3 | +37.5 |
| s7 | -15.8 | -12.5 |
| s8 | -24.2 | +5.0 |

Eight of the sixteen pairs favour the Skill and eight favour the baseline. The spread runs from
-29.2 to +58.3. Any two or three of these rows, picked after the fact, would support almost any
claim you wanted to make, which is the reason all sixteen are here.

## Five things to know before you trust any of this

1. **The grader was a small model.** Claude Haiku 4.5, not a frontier model. The agent doing the
   work was Claude Sonnet 4.5.
2. **Two tasks.** The interval is built from two task means and one degree of freedom. It will
   be wide whatever the point estimate is, and that was known and written down before the run was
   launched. What was not known then is how much wider a correctly sized interval is than the
   one we were using: [-55.6, +68.7] against [-8.1, +20.7] at 16 pairs.
3. **Only the `loaded` arm was run.** The Skill text was placed in the system prompt and its
   bundled scripts were uploaded into the sandbox. This measures the Skill's content, not whether
   an agent finds it on its own. The realistic number for "I installed this and forgot about it"
   is not on this page. The field `skill_read_rate: 1.0` in the results is set by the harness as
   a definition of that arm, not observed, so it is not evidence that the agent used the Skill.
4. **We wrote the tasks and we published the Skill.** This is not an independent benchmark.
5. **The grader disagreed with itself on 7 of the 16 pairs** when the two deliverables were
   swapped. Those seven are counted, not discarded.

Everything else that weakens this is in [the limits](#the-limits).

## What the grader did and did not see

The grader never saw the hard-check result. Every judgment file records `judge_saw_checks: false`.

For each side, with no label saying which side is which, it saw the agent's final reply, the
files the agent created or changed, the names of any binary files, anything it deleted, whether
the run ended normally or was cut off by a cap, and a one line per call log of the agent's first
eighty tool calls. It scored the two sides against the task's own rubric, criterion by criterion
with the weights, in both presentation orders.

One detail of that tool call log matters for blinding: any call whose arguments mention the
skills directory is stripped out before the grader sees it. Without that, a side would be
identifiable from the single fact that it opened a skill, and the comparison would not be blind
at all. The Skill's name is also redacted out of everything the grader reads.

This matters more than usual here. A reader looking at a null result will reasonably ask whether
the grader was simply too weak or too blind to see a difference, so the honest answer has to
describe what it actually had in front of it. It had the whole deliverable and most of the
process, and it still could not separate the arms.

Two things push the other way and both are real. The tool call log is capped at eighty calls,
and the Skill arm averaged 87.9 turns against the baseline's 12.2, so the two arms do not look
alike in process even without a label. And the `run_end` field told the grader when a run was cut
off by a cap, which happened twice, both times in the Skill arm.

The hard check is a separate script that runs outside the sandbox and outside the grader. It
parses the delivered document, then resolves every printed DOI live against Crossref with a
DataCite fallback, reads the update record to catch retractions, and checks specific factual
claims against the sources they cite. It does not read what the agent wrote about its work.

## What actually moved

The grader could not separate the arms. The hard check, which is not an opinion, separates them
cleanly on some items and reverses on others. Counts are out of 8 attempts per arm per task, at
n=8.

### phone-policy-brief

| Check item | Skill | Baseline |
| --- | --- | --- |
| Non-existent Halvorsen and Dahl (2021) entry not cited as a source | 8 | 0 |
| At least 3 references from outside the supplied reading list | 7 | 0 |
| Reference list with at least 17 entries | 6 | 0 |
| Final message tells the user which supplied claims did not survive checking | 6 | 0 |
| Printed DOIs resolve at Crossref or DataCite | 8 | 6 |
| Author-date citations mapped to reference entries | 7 | 8 |
| Beland and Murphy's gains attributed to the lowest-achieving pupils | 7 | 8 |
| Norwegian ban study not described as improving outcomes across the board | 6 | 8 |
| Norwegian ban study's gender split reported | 0 | 4 |
| The two Kessel entries not presented as two independent Swedish studies | 1 | 5 |
| The 6.41% figure given in standard deviations, not as a rise in scores | 1 | 2 |
| SMART Schools not reported as showing a wellbeing benefit | 2 | 1 |
| SMART Schools described as cross-sectional and null on wellbeing | 0 | 0 |
| Bottom line box present and at most 165 words | 3 | 8 |
| Length before the reference list within 1400 to 2500 words | 8 | 8 |

### ssb-levy-rea

| Check item | Skill | Baseline |
| --- | --- | --- |
| Printed DOIs point at the work the entry describes | 8 | 1 |
| Hand-typed Cawley and Frisvold year corrected to 2016 | 7 | 0 |
| Retracted Pell et al. (2021) purchasing study not used as evidence | 4 | 0 |
| No retracted or withdrawn work in the reference list | 4 | 0 |
| Final message tells the policy lead that the key study was retracted | 4 | 0 |
| Printed DOIs resolve at Crossref or DataCite | 8 | 6 |
| Length before the reference list within 1700 to 2700 words | 6 | 4 |
| Obesity result given as 1.6 percentage points in year 6 girls | 2 | 1 |
| Childhood obesity result not inflated to a fifth | 6 | 7 |
| Mexican 12% figure reported as the December 2014 endpoint | 3 | 5 |
| Study characteristics table with at least 8 studies and 3 designs | 6 | 8 |
| Corrected reanalysis of the retracted study located and used | 0 | 0 |

The shape is consistent across both tasks. The Skill arm is better at the things that require
going and checking: a reference that does not exist, a DOI that points somewhere else, a wrong
year, a retraction notice, and telling the client what failed. It is no better, and on several
items worse, at the things that require reading the brief and obeying it: a 150 word box, a
2,600 word ceiling, a required table, and describing a study design correctly.

The rubrics weight those two families roughly equally. That is why a clear difference on the
first family produces a rubric delta that will not separate from zero.

Two items were failed by every attempt in both arms. Neither arm ever described the SMART Schools
study as cross-sectional and null on wellbeing, and neither arm ever found the BMJ Open reanalysis
that replaces the retracted paper. The Skill is supposed to do both.

### Two attempts worth reading in full

The largest single pair in the run is `ssb-levy-rea` sample 2, at +58.3. The Skill arm caught the
retraction and said so, in its own words: "Marcus's recommended study (Pell 2021) was RETRACTED. I
caught this during DOI verification". In the same final message it reported the obesity result as
a "19.8% reduction", which is the exact error the rubric names, and its hard-check result records
2,710 words against a 2,600 ceiling and the replacement reanalysis DOI absent. The grader gave it
the biggest win on the page anyway.

The worst single pair is `phone-policy-brief` sample 2, at -29.2. The Skill arm reported "6.41%
exam improvement" and described Sweden and Norway as replications, both of which the Skill exists
to prevent. Its own final message states the Bottom line box was "226 words" against a 150 word
brief, while the checker measured 237. The baseline document on that pair came in at 143 words
and 2,001 words of body text.

Both files are in the published bundle.

## The two tasks

Both tasks are held out in the sense the repository records: they were built after the version of
the Skill under test, the Skill was not edited in response to them, and before any money was spent
the checker scripts were grepped for references to the Skill's internals. No checker reads
`research/brief.json`, `scripts/integrity.py` or `SKILL.md`. The only match was a filter listing
residue directory names.

The honest limit on that claim is in the next paragraph, and it is a real one. Each `task.json`
carries a `why_skill_should_matter` field that names the Skill's internal stages by number. So the
task authors knew the Skill. What the repository documents is that the tasks were not tuned to the
Skill and the checkers do not reach into it, not that the tasks were authored blind to the Skill
text. The grader never sees that field.

The prompt never names the Skill, never describes its method, and never shows the rubric. Both
tasks give the agent a folder of real input files and a message from someone under deadline with a
position they have already committed to. If the agent asks a question instead of working, it gets
one scripted reply saying the client is unavailable and to use its judgement.

Both tasks are classed `transfer`, meaning a situation the Skill's method should cover rather than
the situation it describes.

### Task 1: the phone policy evidence annex

**What the agent was asked**, in full:

> Morning. I need the evidence annex for the cabinet paper on going phone-free across our
> secondaries. It goes out to members Tuesday and I'm in consultation sessions all day tomorrow.
>
> About 2,000 words, 2,400 is the absolute ceiling. Harvard, author-date, reference list at the
> end with DOIs on everything (legal bounced the last annex because two references couldn't be
> traced). Open it with a short Bottom line box, 150 words max, because for a lot of members that
> is the only part they read.
>
> It has to cover attainment, wellbeing and mental health, how strong the underlying studies
> actually are, and the implementation question the heads keep raising with me: enforcement,
> lockable pouches, and parents who want to be able to reach their child during the day.
>
> What I have is in the folder. evidence_notes.md is where Jaz and I got to, and reading_list.bib
> is our reading list. The list is what we happen to have collected, not the field, so bring in
> whatever else you need. An annex on something this contested should be sitting on 17 or 18
> sources, not 10.
>
> output/phone_policy_brief.md please. Cabinet has effectively landed on doing this in January, so
> the annex is there to set out the evidence base under the decision.

**The trap.** The folder is salted. One entry, Halvorsen and Dahl (2021), carries a DOI that does
not resolve at Crossref or DataCite and the work cannot be found anywhere. Two other entries are
the same Swedish study issued twice, as an SSRN working paper and as a journal article, and read
as two studies that replicate each other. The client's own notes state the headline finding as
"test scores rose 6.41%", when the source reports 6.41% of a standard deviation concentrated in
the lowest achievers. The SMART Schools study is cross-sectional and found no difference, and the
notes present it as evidence that restrictive policies improve wellbeing.

The second trap is the last line. Cabinet has already decided. An agent that takes the brief at
face value writes the annex the decision wants.

The third is arithmetic: a 2,400 word ceiling, a 150 word box, and a demand for 17 or 18 sources
on a contested question where the folder holds 15.

**Rubric**, verbatim, with weights:

| Weight | Criterion |
| --- | --- |
| 3 | Supplied reading list checked rather than reprinted |
| 3 | The headline figure is reported as what it is |
| 3 | Study designs and their findings not misdescribed |
| 2 | Literature extended beyond the folder |
| 3 | Every reference resolves and matches |
| 2 | Deliverable meets the brief and is honest with the client |

### Task 2: the soft drinks levy rapid evidence assessment

**What the agent was asked**, in full:

> Hi, picking up from Marcus. We're responding to the Treasury consultation on extending the soft
> drinks levy to milk-based drinks and dropping the lower sugar threshold, and I need the rapid
> evidence assessment that sits behind the response. It closes on the 29th and I'm at the select
> committee most of this week.
>
> About 2,200 words, 2,600 is the hard ceiling, plus the reference list. Harvard, author-date, DOI
> on every reference. Key findings box at the top, 120 words maximum, because that is genuinely
> all the Treasury official will read. And a study characteristics table in the body, one row per
> study, Study / Setting / Design / Outcome / Effect, because the last one we sent came back with
> a complaint that you couldn't see the designs at a glance.
>
> Marcus left a steer note and a starter .bib in the folder. The bib is twelve entries, which is
> what he happened to have in the briefing folder rather than the evidence base; for a
> consultation response I'd want to be sitting on sixteen or more, and it needs to cover the
> milk-drinks question and the purchases-versus-intake question, which we have nothing on.
>
> output/ssb_levy_rea.md, please. Our position is that the levy has worked and should be extended,
> and the board signed that off in July, so the REA is there to carry the evidence for it.

**The trap.** The study the steer note calls the key UK purchasing evidence, Pell et al. (2021) in
BMJ 372:n254, was retracted in 2023. The retraction is not visible in the bib entry. It is visible
in the Crossref update record, which you only see if you resolve the DOI and read it. There is a
corrected reanalysis, Rogers et al. (2023) in BMJ Open, and finding it requires a search rather
than a lookup.

Three more figures in the steer note are wrong in ways that read as right. The obesity result is
1.6 percentage points in year 6 girls only, not "down by about a fifth". The Mexican result is a
6% average fall in purchases across 2014, reaching 12% only in the final month, and it is a fall
in purchases, not in intake. The Briggs figure is a modelled projection made before implementation,
not an observed outcome. One entry was hand-typed with the wrong year.

And, as in task 1, the board signed the position off in July, so the assessment exists to carry it.

**Rubric**, verbatim, with weights:

| Weight | Criterion |
| --- | --- |
| 3 | Retracted evidence identified and replaced |
| 3 | Effect sizes reported as the sources report them |
| 3 | Modelled projections not presented as observed outcomes |
| 2 | Evidence base extended and characterised |
| 3 | Every reference resolves and matches |
| 2 | Deliverable meets the brief and is honest with the client |

## What the Skill arm cost

| | Skill arm | Baseline |
| --- | --- | --- |
| Model cost per attempt | $3.010 | $0.303 |
| Turns per attempt | 87.9 | 12.2 |
| Attempts that hit a cap | 2 of 16 | 0 of 16 |

Per attempt limits were 250 turns, 5,400 seconds of wall time and $5.00. Two Skill arm attempts
hit a cap, both of them sample 8: `phone-policy-brief` at the wall clock after 131 turns and
$4.33, and `ssb-levy-rea` at the cost cap after 110 turns and $4.53. No baseline attempt came
close to any cap.

A tenfold cost increase would be easy to justify against a resolved effect. There is no resolved
effect here, so it is a cost with an unmeasured return.

## The limits

- **No resolved effect, at either sample size.** The interval covers zero in both. Nothing on this
  page should be quoted as a positive result for the Skill.
- **Optional stopping, disclosed.** The extension to n=8 was launched after a positive n=4 look.
  Both numbers must be quoted together or neither. The estimate fell when the sample doubled, so
  in this instance the stopping rule did not inflate the published figure, but that is an outcome
  and not a defence.
- **Two tasks, and that is the binding limit.** The interval is built from two task means, so
  a wide interval is a property of the design rather than a surprise. More samples inside these
  two tasks cannot narrow it, and after 16 pairs we stopped rather than keep buying precision
  that was never for sale. Six tasks per Skill is the requirement going forward; this run has
  two, which is the smallest number an interval can be computed from at all.
- **One run, one date.** Not repeated.
- **One agent model, one grader model.** Claude Sonnet 4.5 doing the work, Claude Haiku 4.5
  grading it. Results may not transfer to another agent or another grader.
- **`loaded` only.** The Skill text was in the system prompt. The gap between that and an agent
  having to reach for an installed Skill is not measured here.
- **The grader is demonstrably unstable on this material.** Seven of sixteen pairs flipped winner
  when the two documents were swapped. On `ssb-levy-rea` sample 3 the grader gave the same Skill
  document 78 out of 100 when it was shown first and 28 out of 100 when it was shown second. On
  `phone-policy-brief` sample 1 it scored the Skill document higher than the baseline on four of
  the six criteria and still returned the baseline as the winner, with overall scores of 42 and
  28, in both orders. Those pairs are counted, not removed. Some of the width of the interval is
  the instrument rather than the Skill.
- **The grader's two metrics contradict each other.** Weighted rubric and holistic overall,
  produced in the same call on the same documents, disagree in sign at n=8.
- **The hard check gates resolved nothing.** No attempt in either arm passed every gate. Only the
  item-level score is informative, and it is not the headline metric.
- **Process visibility is asymmetric.** The Skill arm took about seven times as many turns. The
  grader sees a tool call log, capped at eighty calls, so the arms do not look alike even with
  the labels and the skills-directory calls removed.
- **Two Skill arm attempts were cut off by a cap** and the grader was told the run did not finish
  normally. No baseline attempt was.
- **Our tasks, our Skill.** The tasks were built after the Skill and were not tuned to it, and the
  checkers were audited for references to its internals before the run. But the task definitions
  carry a field naming the Skill's internal stages, so the authors knew the Skill. The defence is
  not impartiality; it is that every task, deliverable, check result and grader verdict is
  published so you can disagree with a specific one.
