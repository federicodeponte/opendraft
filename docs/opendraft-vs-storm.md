# OpenDraft vs STORM / Co-STORM

OpenDraft and Stanford's STORM / Co-STORM are both open-source systems that research a topic and write a long, cited document. They aim at different outputs: OpenDraft drafts academic papers from scholarly databases, STORM writes Wikipedia-style articles from web search, and Co-STORM adds a human in the loop.

This page uses only two kinds of sources: the peer-reviewed NIH paper that compares both systems, and the public STORM documentation. OpenDraft facts come from this repository's [README](../README.md).

## What the NIH paper says

Talukder, Combs, Schmitt, Reif and Auerbach (NIH / NIEHS), *Discourse2Draft: an AI-powered structured document writing tool*, Frontiers in Artificial Intelligence, 27 October 2026, [doi:10.3389/frai.2026.1945655](https://doi.org/10.3389/frai.2026.1945655).

The authors pick four open-source systems that, in their words, "collectively cover the major design directions" in current scholarly writing tools: Literature Review Agent, OpenDraft, STORM / Co-STORM and Thoth. They describe the two covered here as follows:

- **OpenDraft** "targets autonomous long-form academic drafting with multi-agent research, structured writing, citation filtering, and PDF/DOCX/LaTeX export."
- **STORM and Co-STORM** "focus on topic exploration, outline synthesis, retrieval-grounded article generation, collaborative discourse, and mind-map-supported knowledge curation", supporting "knowledge-curation-based article generation through both autonomous and interactive workflows."

The paper's detailed feature comparison is in its Supplementary Section 1.1.

## Side by side

| | OpenDraft | STORM | Co-STORM |
|:---|:---|:---|:---|
| **Output** | Research papers, literature reviews, thesis chapters (10k to 20k+ words) | Wikipedia-like articles written from scratch | Article plus a shared mind map, built with the user |
| **Who drives** | Autonomous: one topic in, full draft out | Autonomous | Collaborative: the user observes or steers the discussion |
| **How it researches** | 19 specialized agents: research, structure, writing, citation, polish, export | Perspective-guided question asking and a simulated writer/expert conversation, then outline, then article | LLM experts and a moderator agent take turns with the user |
| **Where sources come from** | CrossRef, OpenAlex, Semantic Scholar | Web search retrievers (You.com, Bing, Serper, Brave, SearXNG, DuckDuckGo, Tavily, Google, Azure) or your own documents via VectorRM | Same retrievers as STORM |
| **Citation check** | A source is kept only when its DOI is held by at least two of CrossRef, OpenAlex and Semantic Scholar; each citation records which databases confirmed it ([details](../README.md#citation-verification)) | Citations point to the retrieved web sources | Citations point to the retrieved web sources |
| **Export** | PDF, Word (.docx), LaTeX | Article text | Article text |
| **Models** | Gemini, OpenAI or Claude with your own key | Any model supported by LiteLLM | Any model supported by LiteLLM |
| **Install** | `pip install opendraft`, `npx opendraft`, or the agent skill `npx skills add federicodeponte/opendraft --skill autonomous-research` | `pip install knowledge-storm` | `pip install knowledge-storm` |
| **Papers** | Cited in the NIH paper above and the NUS survey [arXiv:2605.18661](https://arxiv.org/abs/2605.18661) | [arXiv:2402.14207](https://arxiv.org/abs/2402.14207) (NAACL 2024) | [arXiv:2408.15232](https://arxiv.org/abs/2408.15232) (EMNLP 2024) |
| **License** | MIT | MIT | MIT |

STORM / Co-STORM facts are from the [stanford-oval/storm README](https://github.com/stanford-oval/storm).

## Which one to use

- **You need a paper, literature review or thesis draft with scholarly citations:** OpenDraft. Its sources come from scholarly databases with DOIs, and it exports PDF, Word and LaTeX.
- **You want a broad, encyclopedia-style overview of a topic from the web:** STORM. Its own README says the output is not publication-ready and that Wikipedia editors found it helpful in their pre-writing stage.
- **You want to explore a topic interactively and steer the research yourself:** Co-STORM, with its turn-based discussion and mind map.

Found an error in this comparison? [Open an issue](https://github.com/federicodeponte/opendraft/issues).
