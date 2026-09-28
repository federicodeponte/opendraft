#!/usr/bin/env python3
"""
ABOUTME: Compose phase — 7 Crafter agents writing thesis sections
ABOUTME: Introduction, Literature Review, Methodology, Results, Discussion, Conclusion, Appendices
"""

import time
import logging
import traceback

from .context import DraftContext

logger = logging.getLogger(__name__)


def run_compose_phase(ctx: DraftContext) -> None:
    """
    Execute the compose phase: 7 sequential Crafter agents.

    Mutates ctx: intro_output, lit_review_output, methodology_output,
                 results_output, discussion_output, body_output,
                 conclusion_output, appendix_output
    """
    from utils.agent_runner import run_agent, rate_limit_delay

    logger.info("=" * 80)
    logger.info("PHASE 3: COMPOSE - Writing chapters")
    logger.info("=" * 80)

    if ctx.verbose:
        print("\n\u270d\ufe0f  PHASE 3: COMPOSE")

    if ctx.tracker:
        ctx.tracker.log_activity("\u270d\ufe0f Starting chapter composition", event_type="milestone", phase="writing")
        ctx.tracker.update_phase("writing", progress_percent=35, chapters_count=0, details={"stage": "starting_composition"})
        ctx.tracker.check_cancellation()
        ctx.tracker.send_heartbeat()

    _write_introduction(ctx)
    rate_limit_delay()

    _write_literature_review(ctx)
    rate_limit_delay()

    _write_methodology(ctx)
    rate_limit_delay()

    _write_results(ctx)
    rate_limit_delay()

    _write_discussion(ctx)

    _merge_body_sections(ctx)
    rate_limit_delay()

    _write_conclusion(ctx)
    rate_limit_delay()

    _write_appendices(ctx)
    rate_limit_delay()


# ---------------------------------------------------------------------------
# Private helpers — each constructs the prompt, calls run_agent, returns output
# ---------------------------------------------------------------------------


def _write_introduction(ctx: DraftContext) -> None:
    from utils.agent_runner import run_agent

    intro_target = ctx.word_targets['introduction']
    logger.info("[CHAPTER 1/4] Starting Introduction")
    chapter_start = time.time()

    try:
        if ctx.tracker:
            ctx.tracker.log_activity("\u270d\ufe0f Writing Introduction chapter...", event_type="writing", phase="writing")

        ctx.intro_output = run_agent(
            model=ctx.model,
            name="Crafter - Introduction",
            prompt_path="prompts/03_compose/crafter.md",
            user_input=f"""Write Introduction:

Topic: {ctx.topic}

Outline:
{ctx.formatter_output[:2000]}{ctx.citation_summary}

**CRITICAL REQUIREMENTS:**
1. Write {intro_target} words minimum
2. Include at least 1-2 tables (if relevant)
3. **Table constraints**: Maximum 300 chars per cell, maximum 5 columns
4. Put table details in prose paragraphs AFTER tables, not inside cells{ctx.language_instruction}{ctx.user_material}""",
            save_to=ctx.folders['drafts'] / "01_introduction.md",
            skip_validation=ctx.skip_validation,
            verbose=ctx.verbose,
            token_tracker=ctx.token_tracker,
            token_stage="crafter_introduction",
        )

        if ctx.tracker:
            ctx.tracker.log_activity("\u2705 Introduction complete", event_type="complete", phase="writing")

        chapter_time = time.time() - chapter_start
        logger.info(f"[CHAPTER 1/4] \u2705 Complete in {chapter_time:.1f}s")

    except Exception as e:
        logger.error(f"[CHAPTER 1/4] \u274c FAILED: {e}")
        logger.error(f"[TRACEBACK] {traceback.format_exc()}")
        if ctx.tracker:
            ctx.tracker.mark_failed(f"Chapter 1 failed: {e}")
        raise

    # MILESTONE: Introduction Complete
    if ctx.streamer:
        ctx.streamer.stream_chapter_complete(
            chapter_num=1,
            chapter_name="Introduction",
            chapter_path=ctx.folders['drafts'] / "01_introduction.md",
        )

    if ctx.tracker:
        ctx.tracker.update_phase("writing", progress_percent=40, chapters_count=1, details={"stage": "introduction_complete", "milestone": "introduction_complete"})


def _write_literature_review(ctx: DraftContext) -> None:
    from utils.agent_runner import run_agent

    lit_review_target = ctx.word_targets['literature_review']
    logger.info("[SECTION 2.1/4] Starting Literature Review")
    section_start = time.time()

    try:
        if ctx.tracker:
            ctx.tracker.log_activity("\u270d\ufe0f Writing Literature Review section...", event_type="writing", phase="writing")

        ctx.lit_review_output = run_agent(
            model=ctx.model,
            name="Crafter - Literature Review",
            prompt_path="prompts/03_compose/crafter.md",
            user_input=f"""Write section 2.1 Literature Review for this draft.

Topic: {ctx.topic}

Research summaries and abstracts:
{ctx.scribe_output[:3000]}

{ctx.citation_summary}

Outline context:
{ctx.formatter_output[:2000]}

**CRITICAL REQUIREMENTS:**

1. **Section numbering:** Start with ## 2.1 Literature Review
2. **Subsections:** Use ### 2.1.1, ### 2.1.2, etc. (at least 3 subsections)
3. **Word count:** {lit_review_target} words minimum
4. **Tables:** Include at least 1-2 comparison tables (e.g., Author vs. Findings)
   - **Maximum 300 characters per cell** - keep cells concise!
   - **Maximum 5 columns** per table
   - Put details in prose AFTER the table, not inside cells
5. **Citations:** Use {{cite_XXX}} format from citation database
6. **Depth:** Use 4 levels of headings (##, ###, ####, #####)

**CITATION-CLAIM VERIFICATION (V3 feature):**
- Before using a citation, verify it actually supports your claim
- Check the citation's title/abstract matches the topic you're citing it for
- Do NOT cite a paper about "X" to support a claim about "Y"
- Example: A paper about "creatine supplementation" should NOT be cited for a claim about "caffeine effects"
- If unsure whether a citation supports a claim, rephrase the claim to match what the citation actually covers

**Content to cover:**
- Theoretical framework and foundational concepts
- Review of empirical studies (with abstracts provided)
- Comparison of different approaches/methodologies
- Evolution of the field
- Research gaps that your draft will address

**Use the abstracts provided to write evidence-based literature review with specific findings, NOT generic statements.**{ctx.language_instruction}{ctx.user_material}""",
            save_to=ctx.folders['drafts'] / "02_1_literature_review.md",
            skip_validation=ctx.skip_validation,
            verbose=ctx.verbose,
            token_tracker=ctx.token_tracker,
            token_stage="crafter_literature_review",
        )

        section_time = time.time() - section_start
        logger.info(f"[SECTION 2.1/4] \u2705 Complete in {section_time:.1f}s")

        if ctx.tracker:
            ctx.tracker.log_activity("\u2705 Literature Review complete", event_type="complete", phase="writing")
            ctx.tracker.update_phase("writing", progress_percent=45, chapters_count=2, details={"stage": "literature_review_complete"})

        if ctx.streamer:
            ctx.streamer.stream_chapter_complete(
                chapter_num=2,
                chapter_name="Literature Review (Section 2.1)",
                chapter_path=ctx.folders['drafts'] / "02_1_literature_review.md",
            )

    except Exception as e:
        logger.error(f"[SECTION 2.1/4] \u274c FAILED: {e}")
        logger.error(f"[TRACEBACK] {traceback.format_exc()}")
        if ctx.tracker:
            ctx.tracker.mark_failed(f"Section 2.1 (Literature Review) failed: {e}")
        raise


def _write_methodology(ctx: DraftContext) -> None:
    from utils.agent_runner import run_agent

    methodology_target = ctx.word_targets['methodology']
    logger.info("[SECTION 2.2/4] Starting Methodology")
    section_start = time.time()

    try:
        if ctx.tracker:
            ctx.tracker.log_activity("\u270d\ufe0f Writing Methodology section...", event_type="writing", phase="writing")

        ctx.methodology_output = run_agent(
            model=ctx.model,
            name="Crafter - Methodology",
            prompt_path="prompts/03_compose/crafter.md",
            user_input=f"""Write section 2.2 Methodology for this draft.

Topic: {ctx.topic}

Literature Review context (what was identified):
{ctx.lit_review_output[-2000:]}

Research gaps from Signal phase:
{ctx.signal_output[:1500]}

Outline:
{ctx.formatter_output[:2000]}

{ctx.citation_summary}

**CRITICAL REQUIREMENTS:**

1. **Section numbering:** Start with ## 2.2 Methodology
2. **Subsections:** Use ### 2.2.1, ### 2.2.2, etc. (at least 2-3 subsections)
3. **Word count:** {methodology_target} words minimum
4. **Tables:** Include at least 1 methodology summary table
   - **Maximum 300 characters per cell** - keep cells concise!
   - **Maximum 5 columns** per table
   - Put details in prose AFTER the table, not inside cells
5. **Build on Literature Review:** Reference gaps identified in section 2.1
6. **Citations:** ONLY use citations from the CITATION DATABASE above with {{cite_XXX}} format

**CITATION-CLAIM VERIFICATION:**
- Before using a citation, verify it actually supports your claim
- Check the citation's title/abstract matches the methodology you're describing
- Do NOT cite a paper about "X methodology" to describe "Y methodology"
- If unsure, rephrase to match what the citation actually covers

**\U0001f6a8 CRITICAL ANTI-HALLUCINATION RULES:**
- **NEVER claim "we conducted studies"** - This is a literature review draft, not an empirical study
- **NEVER invent datasets** (e.g., "Dataset X-500", "we analyzed 10,000 samples")
- **NEVER fabricate experimental procedures** (e.g., "we ran experiments on...")
- **ONLY describe methodologies from cited literature** - Use "Previous research {{cite_XXX}} used..." not "We used..."
- **Use hypothetical/theoretical language** for proposed approaches: "A potential methodology might involve..." not "We implemented..."
- **Focus on synthesizing existing research methods**, not claiming to have conducted new research

**Content to cover:**
- Research design and approach (qualitative/quantitative/mixed) - from literature
- Data collection methods - as described in cited sources
- Analysis framework/techniques - from existing research
- Rationale for chosen methods (connect to gaps from 2.1) - theoretical justification
- Tools and technologies used - from literature, not "we used"
- Study limitations and considerations - theoretical discussion

**Connect to Literature Review:** "To address the gap identified in section 2.1 regarding X, a potential methodology could follow approaches described in {{cite_XXX}}..."**{ctx.language_instruction}{ctx.user_material}""",
            save_to=ctx.folders['drafts'] / "02_2_methodology.md",
            skip_validation=ctx.skip_validation,
            verbose=ctx.verbose,
            token_tracker=ctx.token_tracker,
            token_stage="crafter_methodology",
        )

        section_time = time.time() - section_start
        logger.info(f"[SECTION 2.2/4] \u2705 Complete in {section_time:.1f}s")

        if ctx.tracker:
            ctx.tracker.log_activity("\u2705 Methodology complete", event_type="complete", phase="writing")
            ctx.tracker.update_phase("writing", progress_percent=50, chapters_count=2, details={"stage": "methodology_complete"})

        if ctx.streamer:
            ctx.streamer.stream_chapter_complete(
                chapter_num=2,
                chapter_name="Methodology (Section 2.2)",
                chapter_path=ctx.folders['drafts'] / "02_2_methodology.md",
            )

    except Exception as e:
        logger.error(f"[SECTION 2.2/4] \u274c FAILED: {e}")
        logger.error(f"[TRACEBACK] {traceback.format_exc()}")
        if ctx.tracker:
            ctx.tracker.mark_failed(f"Section 2.2 (Methodology) failed: {e}")
        raise


def _write_results(ctx: DraftContext) -> None:
    from utils.agent_runner import run_agent

    results_target = ctx.word_targets['results']
    logger.info("[SECTION 2.3/4] Starting Analysis and Results")
    section_start = time.time()

    try:
        if ctx.tracker:
            ctx.tracker.log_activity("\u270d\ufe0f Writing Analysis & Results section...", event_type="writing", phase="writing")

        ctx.results_output = run_agent(
            model=ctx.model,
            name="Crafter - Analysis and Results",
            prompt_path="prompts/03_compose/crafter.md",
            user_input=f"""Write section 2.3 Analysis and Results for this draft.

Topic: {ctx.topic}

Methodology used (from section 2.2):
{ctx.methodology_output[-1500:]}

Literature Review context (theoretical framework):
{ctx.lit_review_output[:1500]}

Research data:
{ctx.scribe_output[1000:2500]}

{ctx.citation_summary}

**CRITICAL REQUIREMENTS:**

1. **Section numbering:** Start with ## 2.3 Analysis and Results
2. **Subsections:** Use ### 2.3.1, ### 2.3.2, etc. (at least 3 subsections)
3. **Word count:** {results_target} words minimum
4. **Tables:** Include at least 2-3 data/results tables
   - **Maximum 300 characters per cell** - keep cells concise!
   - **Maximum 5 columns** per table
   - Put details in prose AFTER the table, not inside cells
5. **Synthesize Literature Findings:** Present results FROM CITED SOURCES, not from new research
6. **Citations:** ONLY use citations from the CITATION DATABASE above with {{cite_XXX}} format

**CITATION-CLAIM VERIFICATION:**
- Before citing a source for a finding, verify the citation actually reports that finding
- Check citation title/abstract matches the result you're attributing to it
- Do NOT cite a study about "X" to support findings about "Y"
- If unsure, rephrase to match what the citation actually found

**\U0001f6a8 CRITICAL ANTI-HALLUCINATION RULES:**
- **NEVER claim "we found", "we analyzed", "our results show"** - This is a literature review, not an empirical study
- **NEVER invent data, statistics, or results** (e.g., "we found 87% accuracy", "our analysis revealed...")
- **NEVER fabricate datasets or sample sizes** (e.g., "Dataset X-500", "we analyzed 10,000 samples")
- **ONLY present findings from cited literature** - Use "Research by {{cite_001}} found..." not "We found..."
- **ONLY use data/statistics from cited sources** - All numbers must come from {{cite_XXX}} references
- **Synthesize existing research findings**, not claim to have conducted new analysis
- **Use language like:** "Studies have shown...", "Research indicates...", "Findings suggest..." NOT "We found...", "Our analysis..."

**Content to cover:**
- Key findings FROM CITED LITERATURE (with specific data from cited abstracts/papers)
- Synthesis of data analysis and interpretation FROM EXISTING RESEARCH
- Statistical results FROM CITED STUDIES (if applicable)
- Patterns and trends observed IN THE LITERATURE
- Visual data presentation (tables summarizing findings from cited sources)
- Comparison with baseline/benchmarks FROM CITED RESEARCH

**Connect sections:** "Research applying methodologies similar to those described in section 2.2 has found..." and "These findings from the literature relate to the theoretical framework in section 2.1..."**{ctx.language_instruction}{ctx.user_material}""",
            save_to=ctx.folders['drafts'] / "02_3_analysis_results.md",
            skip_validation=ctx.skip_validation,
            verbose=ctx.verbose,
            token_tracker=ctx.token_tracker,
            token_stage="crafter_results",
        )

        section_time = time.time() - section_start
        logger.info(f"[SECTION 2.3/4] \u2705 Complete in {section_time:.1f}s")

        if ctx.tracker:
            ctx.tracker.log_activity("\u2705 Analysis & Results complete", event_type="complete", phase="writing")
            ctx.tracker.update_phase("writing", progress_percent=55, chapters_count=2, details={"stage": "results_complete"})

        if ctx.streamer:
            ctx.streamer.stream_chapter_complete(
                chapter_num=2,
                chapter_name="Analysis & Results (Section 2.3)",
                chapter_path=ctx.folders['drafts'] / "02_3_analysis_results.md",
            )

    except Exception as e:
        logger.error(f"[SECTION 2.3/4] \u274c FAILED: {e}")
        logger.error(f"[TRACEBACK] {traceback.format_exc()}")
        if ctx.tracker:
            ctx.tracker.mark_failed(f"Section 2.3 (Analysis and Results) failed: {e}")
        raise


def _write_discussion(ctx: DraftContext) -> None:
    from utils.agent_runner import run_agent

    discussion_target = ctx.word_targets['discussion']
    logger.info("[SECTION 2.4/4] Starting Discussion")
    section_start = time.time()

    try:
        if ctx.tracker:
            ctx.tracker.log_activity("\u270d\ufe0f Writing Discussion section...", event_type="writing", phase="writing")

        ctx.discussion_output = run_agent(
            model=ctx.model,
            name="Crafter - Discussion",
            prompt_path="prompts/03_compose/crafter.md",
            user_input=f"""Write section 2.4 Discussion for this draft.

Topic: {ctx.topic}

Results (from section 2.3):
{ctx.results_output[-2000:]}

Literature Review context (to compare with):
{ctx.lit_review_output[:1500]}

Research gaps addressed:
{ctx.signal_output[:1000]}

{ctx.citation_summary}

**CRITICAL REQUIREMENTS:**

1. **Section numbering:** Start with ## 2.4 Discussion
2. **Subsections:** Use ### 2.4.1, ### 2.4.2, etc. (at least 2-3 subsections)
3. **Word count:** {discussion_target} words minimum
4. **Tables:** Include at least 1 summary/implications table
   - **Maximum 300 characters per cell** - keep cells concise!
   - **Maximum 5 columns** per table
   - Put details in prose AFTER the table, not inside cells
5. **Interpret Literature Findings:** Discuss findings FROM CITED SOURCES, not from new research
6. **Citations:** ONLY use citations from the CITATION DATABASE above with {{cite_XXX}} format

**\U0001f6a8 CRITICAL ANTI-HALLUCINATION RULES:**
- **NEVER claim "our results", "our findings", "we conclude"** - This is a literature review, not an empirical study
- **NEVER invent conclusions or implications** from non-existent research
- **ONLY discuss findings from cited literature** - Use "Research findings {{cite_001}} suggest..." not "Our findings suggest..."
- **Synthesize existing research**, not claim to have conducted new analysis
- **Use language like:** "The literature suggests...", "Research indicates...", "Studies have shown..." NOT "We found...", "Our analysis..."

**Content to cover:**
- Interpretation of findings FROM CITED LITERATURE (synthesized in section 2.3)
- Comparison with prior work from section 2.1
- How findings FROM LITERATURE address research gaps
- Theoretical implications FROM EXISTING RESEARCH
- Practical implications FROM CITED STUDIES
- Limitations discussed IN THE LITERATURE
- Future research directions suggested BY EXISTING RESEARCH

**CRITICAL - Explicit Section References:**

You MUST include these explicit phrases to connect back to previous sections:
1. "As discussed in section 2.1..." (refer to literature review)
2. "The findings FROM LITERATURE presented in section 2.3..." (refer to synthesized results)
3. "Compared to the theoretical framework in section 2.1..."
4. "These findings FROM CITED RESEARCH confirm/contradict [Author's] findings discussed in section 2.1..."
5. "The research gap identified in section 2.1 has been addressed by findings from {{cite_XXX}}..."

**Example opening:** "The findings FROM LITERATURE synthesized in section 2.3 reveal significant insights that both align with and extend the theoretical frameworks discussed in section 2.1. As noted in the literature review (section 2.1), previous studies by [Author] {{cite_001}} demonstrated [X]; research findings {{cite_002}}{{cite_003}} confirm this relationship while also revealing [new insight]."

**Remember:** Explicitly reference "section 2.1" at least 3-5 times throughout the Discussion to maintain strong academic coherence. ALWAYS cite sources for any findings discussed.**{ctx.language_instruction}{ctx.user_material}""",
            save_to=ctx.folders['drafts'] / "02_4_discussion.md",
            skip_validation=ctx.skip_validation,
            verbose=ctx.verbose,
            token_tracker=ctx.token_tracker,
            token_stage="crafter_discussion",
        )

        section_time = time.time() - section_start
        logger.info(f"[SECTION 2.4/4] \u2705 Complete in {section_time:.1f}s")

        if ctx.tracker:
            ctx.tracker.log_activity("\u2705 Discussion complete", event_type="complete", phase="writing")
            ctx.tracker.update_phase("writing", progress_percent=60, chapters_count=2, details={"stage": "discussion_complete"})

        if ctx.streamer:
            ctx.streamer.stream_chapter_complete(
                chapter_num=2,
                chapter_name="Discussion (Section 2.4)",
                chapter_path=ctx.folders['drafts'] / "02_4_discussion.md",
            )

    except Exception as e:
        logger.error(f"[SECTION 2.4/4] \u274c FAILED: {e}")
        logger.error(f"[TRACEBACK] {traceback.format_exc()}")
        if ctx.tracker:
            ctx.tracker.mark_failed(f"Section 2.4 (Discussion) failed: {e}")
        raise


def _merge_body_sections(ctx: DraftContext) -> None:
    """Merge all body sections into a single body_output."""
    logger.info("[CHAPTER 2/4] Merging 4 sections into Main Body")

    if ctx.tracker:
        ctx.tracker.log_activity("🔗 Merging sections into Main Body...", event_type="info", phase="writing")

    try:
        merged_content = []
        for section_file in [
            ctx.folders['drafts'] / "02_1_literature_review.md",
            ctx.folders['drafts'] / "02_2_methodology.md",
            ctx.folders['drafts'] / "02_3_analysis_results.md",
            ctx.folders['drafts'] / "02_4_discussion.md",
        ]:
            if section_file.exists():
                content = section_file.read_text(encoding='utf-8')
                merged_content.append(content)
                merged_content.append("\n\n")

        ctx.body_output = "".join(merged_content)
        main_body_file = ctx.folders['drafts'] / "02_main_body.md"
        main_body_file.write_text(ctx.body_output, encoding='utf-8')

        logger.info(f"[CHAPTER 2/4] \u2705 Merged into {main_body_file}")

        if ctx.streamer:
            ctx.streamer.stream_chapter_complete(
                chapter_num=2,
                chapter_name="Main Body (Complete)",
                chapter_path=main_body_file,
            )

    except Exception as e:
        logger.error(f"[CHAPTER 2/4] \u274c Merge FAILED: {e}")
        logger.error(f"[TRACEBACK] {traceback.format_exc()}")
        if ctx.tracker:
            ctx.tracker.mark_failed(f"Chapter 2 merge failed: {e}")
        raise


def _write_conclusion(ctx: DraftContext) -> None:
    from utils.agent_runner import run_agent

    conclusion_target = ctx.word_targets['conclusion']
    logger.info("[CHAPTER 3/4] Starting Conclusion")
    chapter_start = time.time()

    try:
        if ctx.tracker:
            ctx.tracker.log_activity("\u270d\ufe0f Writing Conclusion chapter...", event_type="writing", phase="writing")

        ctx.conclusion_output = run_agent(
            model=ctx.model,
            name="Crafter - Conclusion",
            prompt_path="prompts/03_compose/crafter.md",
            user_input=f"""Write Conclusion:

Topic: {ctx.topic}

Main findings:
{ctx.body_output[:2000]}

{ctx.citation_summary}

**CRITICAL REQUIREMENTS:**
1. Write {conclusion_target} words minimum
2. Include at least 1 summary table (if relevant)
3. **Table constraints**: Maximum 300 chars per cell, maximum 5 columns
4. Put table details in prose paragraphs AFTER tables, not inside cells
5. **Citations:** ONLY use citations from the CITATION DATABASE above with {{cite_XXX}} format{ctx.language_instruction}{ctx.user_material}""",
            save_to=ctx.folders['drafts'] / "03_conclusion.md",
            skip_validation=ctx.skip_validation,
            verbose=ctx.verbose,
            token_tracker=ctx.token_tracker,
            token_stage="crafter_conclusion",
        )

        chapter_time = time.time() - chapter_start
        logger.info(f"[CHAPTER 3/4] \u2705 Complete in {chapter_time:.1f}s")

    except Exception as e:
        logger.error(f"[CHAPTER 3/4] \u274c FAILED: {e}")
        logger.error(f"[TRACEBACK] {traceback.format_exc()}")
        if ctx.tracker:
            ctx.tracker.mark_failed(f"Chapter 3 (Conclusion) failed: {e}")
        raise

    if ctx.streamer:
        ctx.streamer.stream_chapter_complete(
            chapter_num=3,
            chapter_name="Conclusion",
            chapter_path=ctx.folders['drafts'] / "03_conclusion.md",
        )

    if ctx.tracker:
        ctx.tracker.log_activity("\u2705 Conclusion complete", event_type="complete", phase="writing")
        ctx.tracker.update_phase("writing", progress_percent=70, chapters_count=3, details={"stage": "conclusion_complete", "milestone": "conclusion_complete"})


def _write_appendices(ctx: DraftContext) -> None:
    from utils.agent_runner import run_agent

    appendices_target = ctx.word_targets['appendices']
    logger.info("[CHAPTER 4/4] Starting Appendices")
    chapter_start = time.time()

    try:
        if appendices_target == '0':
            logger.info("  Skipping appendices for research paper format")
            ctx.appendix_output = ""
        else:
            ctx.appendix_output = run_agent(
                model=ctx.model,
                name="Crafter - Appendices",
                prompt_path="prompts/03_compose/crafter.md",
                user_input=f"""Write 3-4 appendices for this draft:

Topic: {ctx.topic}

Draft content summary:
- Introduction: {ctx.intro_output[:1500]}
- Main findings: {ctx.body_output[:2000]}
- Conclusion: {ctx.conclusion_output[:1000]}

{ctx.citation_summary}

**REQUIREMENTS:**
1. **Citations:** ONLY use citations from the CITATION DATABASE above with {{cite_XXX}} format
2. Generate 3-4 appendices following this structure:

## Appendix A: Conceptual Framework
A detailed framework or model relevant to the draft topic with tables/diagrams described in markdown.

## Appendix B: Supplementary Data Tables
Additional data, metrics, or case study details supporting the main analysis.

## Appendix C: Glossary of Terms
Key technical terms and definitions used throughout the draft.

## Appendix D: Additional Resources
Supplementary references, tools, and resources for further reading.

**CRITICAL REQUIREMENTS:**
1. Write {appendices_target} words total across all appendices
2. Use markdown tables where appropriate
3. **Table constraints**: Maximum 300 chars per cell, maximum 5 columns
4. Put table details in prose paragraphs AFTER tables, not inside cells
5. Each appendix should be standalone and informative{ctx.language_instruction}{ctx.user_material}""",
                save_to=ctx.folders['drafts'] / "04_appendices.md",
                skip_validation=ctx.skip_validation,
                verbose=ctx.verbose,
                token_tracker=ctx.token_tracker,
                token_stage="crafter_appendices",
            )

        chapter_time = time.time() - chapter_start
        logger.info(f"[CHAPTER 4/4] \u2705 Complete in {chapter_time:.1f}s")

        if ctx.tracker:
            ctx.tracker.update_phase("writing", progress_percent=75, chapters_count=4, details={"stage": "appendices_complete"})

        if ctx.streamer and appendices_target != '0':
            ctx.streamer.stream_chapter_complete(
                chapter_num=4,
                chapter_name="Appendices",
                chapter_path=ctx.folders['drafts'] / "04_appendices.md",
            )

        logger.info("=" * 80)
        logger.info("PHASE 3 COMPLETE - All chapters written successfully!")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"[CHAPTER 4/4] \u274c FAILED: {e}")
        logger.error(f"[TRACEBACK] {traceback.format_exc()}")
        if ctx.tracker:
            ctx.tracker.mark_failed(f"Chapter 4 (Appendices) failed: {e}")
        raise
