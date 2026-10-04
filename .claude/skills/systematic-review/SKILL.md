---
name: systematic-review
description: Run a PRISMA-style systematic literature review that searches every available research tool (Consensus, SciSpace, alphaXiv, bioRxiv/medRxiv, web search), keeps only papers published in high-ranked journals (Q1 by SJR/JCR by default), screens papers against explicit criteria, and extracts a fixed 18-field evidence table per paper (problem, objective, method, model, dataset, features, labels, threat type, evaluation, results, baseline, limitations, future work, generalization, real-world applicability, explainability, reproducibility) followed by a research-gap synthesis, delivered as an Excel workbook (.xlsx). Use when the user asks for a systematic review, literature review, survey, related-work table, state of the art, or research gaps on a topic, e.g. "systematic review of zero-shot insider threat detection", "find the gaps in self-supervised insider threat research", "build an extraction table for these papers".
---

# Systematic Review

Produce a reproducible systematic review: documented search across **all** research
tools, transparent screening, **only papers from high-ranked journals**, a per-paper
extraction table with the 18 fields below, and a gap analysis grounded in that
table, all delivered as an **Excel workbook**. Never invent papers, numbers, or links:
every value must come from a tool result or from the paper text, otherwise write
`Not reported`.

## 0. Scope the review (ask only if it is genuinely unclear)

Write down, at the top of the review, before searching:

- **Research question** (PICO-style for ML: Population = data/users/systems,
  Intervention = method family, Comparison = baselines, Outcome = detection metrics).
- **Journal ranking rule** – default: **Q1 journals only** (SCImago SJR quartile
  or Clarivate JCR quartile, in the subject category closest to the topic, e.g.
  Computer Networks and Communications, Information Systems, Artificial
  Intelligence, Computer Science Applications). Relax to Q1–Q2 only if the user
  asks or fewer than ~10 papers qualify, and ask before relaxing.
- **Inclusion criteria** – published in a journal meeting the ranking rule,
  peer-reviewed, 2015–present, English, proposes or evaluates a detection method,
  reports quantitative results.
- **Exclusion criteria** – venue below the ranking rule; preprints (arXiv, bioRxiv,
  SSRN) without a qualifying published version; conference papers, workshops,
  book chapters, theses (unless the user asks to include top conferences such as
  CORE A*/A); no evaluation; position papers; duplicates; non-English; out of
  domain; predatory or discontinued journals (Scopus coverage discontinued,
  listed on Beall's-type lists).
- **Target size** – default: screen everything found, extract the 20–40 most relevant.

Default focus when the user doesn't say otherwise (this repo's research direction):
**insider threat detection, with emphasis on zero-shot, self-supervised,
unsupervised and few-shot approaches.**

## 1. Build the search strategy

Create 6–12 query strings combining concept blocks with synonyms, e.g.:

| Block | Terms |
|---|---|
| Domain | insider threat, insider attack, malicious insider, user behavior analytics, UEBA, user and entity behavior, data exfiltration, privilege misuse |
| Method | zero-shot, self-supervised, contrastive learning, unsupervised, anomaly detection, few-shot, transfer learning, foundation model, LLM, graph neural network, autoencoder, transformer |
| Data | CERT r4.2 / r5.2 / r6.2, LANL, TWOS, audit logs, user activity logs |

Run both broad (`insider threat detection deep learning`) and narrow
(`self-supervised contrastive insider threat CERT`) queries. Record every query.

## 2. Search ALL available research tools

Load deferred tools with `ToolSearch` first (e.g. `select:mcp__Consensus__search`).
Use every tool that exists in the session; skip silently any that is not available
and note it in the methods section.

| Tool | How to use it |
|---|---|
| `mcp__Consensus__search` | Peer-reviewed literature. This skill's ranking rule is an explicit request to filter, so pass the SJR quartile filter (`sjr_max: 1` for Q1, `2` for Q1–Q2) where the tool accepts it (check its schema for the exact meaning; the rank is still verified in step 3). Run each query once like that, and once with only `query` so you can count what the venue filter removed. Max 3 calls in parallel; on rate limit wait 30 s. Keep its numbered refs and paste its sign-up/usage message verbatim at the end of the answer. |
| `mcp__SciSpace__search-papers` | Second peer-reviewed index; use `mcp__SciSpace__add-column` to pull structured fields (dataset, method, limitations) when supported. |
| `mcp__alphaXiv__discover_papers` | arXiv preprints. A preprint is **not** included on its own; use it to find work, then look for the published journal version (DOI on the arXiv page, or a title search) and check that journal's rank. alphaXiv full text is still fine for extracting from the published paper's preprint copy. |
| `mcp__alphaXiv__get_paper_content` / `mcp__alphaXiv__answer_pdf_queries` | **Full-text extraction** – the main source for fields 6–18. Ask targeted questions ("What dataset and how many users?", "What limitations do the authors state?", "Is code available?"). |
| `mcp__alphaXiv__read_files_from_github_repository` | Verify reproducibility claims (does the linked repo contain code / data / configs?). |
| `mcp__bioRxiv__*` | Only if the topic touches biology/medicine; otherwise note "not applicable". |
| `WebSearch` / `WebFetch` | Publisher landing pages (IEEE, ACM, Elsevier, Springer, Wiley, MDPI), Google Scholar-style queries, author pages, code links, open-access PDFs, and **journal ranking lookups** (scimagojr.com journal page, Clarivate JCR, Scopus source details). Also search high-ranked journals directly, e.g. `site:sciencedirect.com "Computers & Security" insider threat self-supervised`. |
| `mcp__Google_Drive__search_files` / `read_file_content` | If the user has their own papers or notes in Drive, include them (ask first if unsure). |

Also do **snowballing**: for the 5–10 most central papers, look at what they cite
(backward) and what cites them (forward, via web search "cited by").

## 3. De-duplicate, check journal rank, and screen (PRISMA)

1. Merge all results; de-duplicate by DOI, arXiv ID, then normalized title.
   Prefer the peer-reviewed version over the preprint, but keep the arXiv link.
2. **Journal ranking check**, before reading any paper in depth:
   - Identify the exact journal (not just the publisher) and its ISSN.
   - Look up its quartile on SCImago (scimagojr.com) and/or JCR, for the
     **publication year** (or the latest available year, noted as such). If a journal
     sits in several categories, use the category closest to the topic and record it.
   - Record `quartile`, `sjr`, `impact_factor` (if found), and `ranking_source`
     (e.g. "SJR 2024, Computer Networks & Communications"). Never guess a quartile:
     if it cannot be verified, the paper goes to Excluded with reason
     "rank not verifiable".
   - Exclude papers below the ranking rule with reason "journal below Q1" (or the
     rule in force). They still count in PRISMA.
   - Typical Q1 venues for this topic (verify each time, ranks change): IEEE TIFS,
     IEEE TDSC, Computers & Security, Information Sciences, Expert Systems with
     Applications, Knowledge-Based Systems, IEEE TNNLS, Engineering Applications of
     AI, Journal of Network and Computer Applications, Future Generation Computer
     Systems, ACM Computing Surveys, Neural Networks, Pattern Recognition.
3. **Title/abstract screening** against the criteria; record a one-line reason for
   every exclusion.
4. **Full-text screening** of the survivors.
5. Keep counts for the PRISMA flow:
   `identified per tool → after dedup → excluded by journal rank → screened →
   excluded (reasons) → full-text assessed → included`.

## 4. Extract data – the 18 required fields

For **every included paper** fill all fields. Prefer full text (alphaXiv / PDF via
WebFetch) over abstracts; mark the source as `[abstract only]` when full text was
unavailable. Quote numbers exactly as reported, with the dataset/split they belong to.

| # | Category | What to extract | Why it matters for the gap |
|---|---|---|---|
| 1 | **Problem** | What problem does the paper address? | Shows what researchers are trying to solve |
| 2 | **Objective** | What exactly does the study propose? | Shows the research focus |
| 3 | **Method** | ML / DL / self-supervised / zero-shot / unsupervised / few-shot / RL / hybrid, etc. | Allows methodology comparison |
| 4 | **Model/Algorithm** | Exact models used (e.g. LSTM-AE, Isolation Forest, BERT, GCN) | Identifies dominant approaches |
| 5 | **Dataset** | Dataset name, version, size (users, days, events), type (synthetic/real, log type) | Reveals dataset limitations |
| 6 | **Features** | What information is used (logon, device, file, email, HTTP, psychometric, LDAP, sequences, graphs…) | Shows what data researchers depend on |
| 7 | **Labels** | Supervised / semi-supervised / unlabeled / weakly labeled; how many labels used in training | Very important for the zero-shot / self-supervised direction |
| 8 | **Attack/Threat Type** | Insider threat category detected (data theft/exfiltration, IP theft, sabotage, fraud, espionage, privilege abuse, masquerader, negligent insider; CERT scenarios 1–5) | Reveals coverage gaps |
| 9 | **Evaluation** | Metrics used: Accuracy, Precision, Recall, F1, AUROC, AUPRC, FPR, detection rate, time-to-detect; evaluation level (user/day/session/event); split protocol | Shows whether studies are properly evaluated |
| 10 | **Results** | Main quantitative results (best numbers with metric + dataset) | Allows meaningful comparison |
| 11 | **Baseline** | Models compared against, and whether baselines are recent/strong | Shows whether improvements are convincing |
| 12 | **Limitations** | Explicit limitations stated by the authors (quote or close paraphrase) + your critical note marked `(reviewer)` | One of the strongest sources of gaps |
| 13 | **Future Work** | What the authors recommend | Potential research opportunities |
| 14 | **Generalization** | Tested on unseen users / unseen attack types / other datasets / cross-organization? | Highly relevant to zero-shot detection |
| 15 | **Real-world applicability** | Real vs synthetic data; deployment, latency, scale, concept drift considered? | Identifies practical gaps |
| 16 | **Explainability** | Is the model interpretable / does it provide XAI (SHAP, LIME, attention, rules)? | Potential XAI gap |
| 17 | **Reproducibility** | Code available? Data available? Hyper-parameters / seeds reported? (verify links) | Identifies reproducibility issues |
| 18 | **Citation & venue rank** | Authors, year, title, journal, publisher, DOI link, quartile, SJR, impact factor, ranking source | Traceability, and proof the paper meets the ranking rule |

Rules:
- Use `Not reported` when the paper is silent – never guess. That absence is itself
  evidence for the gap analysis (e.g. "14/30 papers report no generalization test").
- Keep the author-stated limitation separate from your own critique.
- Flag class-imbalance-sensitive metrics: an Accuracy-only result on CERT is weak evidence.

## 5. Quality / risk-of-bias appraisal

Score each paper 0–2 on: clear problem statement, appropriate split (no user/time
leakage), strong recent baselines, imbalance-aware metrics, multiple datasets,
statistical reporting (seeds/variance), code/data availability. Report the total (/14).

## 6. Synthesize and identify gaps

Build the synthesis **from the extraction table**, with counts and citations:

1. **Descriptive statistics** – papers per year, per method family, per dataset,
   per label regime, per threat type, metric usage frequency.
2. **Comparison tables** – results on the same dataset/metric side by side
   (only compare like with like; note protocol differences).
3. **Gap matrix** – for each axis below state what is covered, what is missing,
   and the supporting count:
   - Method gap (e.g. few zero-shot/self-supervised works)
   - Data gap (over-reliance on synthetic CERT; few real datasets)
   - Label gap (most methods need labels for training or threshold tuning)
   - Threat-coverage gap (categories never or rarely detected)
   - Evaluation gap (accuracy only, no AUPRC, leakage-prone splits)
   - Generalization gap (no unseen-user / unseen-attack / cross-dataset tests)
   - Real-world gap (no deployment, drift, latency)
   - Explainability gap
   - Reproducibility gap
4. **Research opportunities** – 3–6 concrete, defensible research directions, each
   tied to the gaps and papers that motivate it (especially for zero-shot /
   self-supervised insider threat detection).

## 7. Output – Excel workbook

The deliverable is an **Excel workbook** `reviews/<topic-slug>/systematic_review.xlsx`.
In chat, give only a short summary (counts, top gaps, research directions) and the
file. Cite Consensus refs inline in that summary and include its usage/sign-up
message verbatim at the end, as the Consensus tool requires.

Build it with the bundled script so the layout is the same every time:

1. Write the review data to `reviews/<topic-slug>/review.json` (append papers as you
   extract them, so progress survives a long session).
2. Run `pip install openpyxl` if needed, then
   `python <this skill's folder>/scripts/build_workbook.py reviews/<topic-slug>/review.json reviews/<topic-slug>/systematic_review.xlsx`.
3. Open the workbook (e.g. with openpyxl) to check every sheet has rows and no
   field is blank, then send it to the user. If the xlsx skill is available, follow
   its formatting checks too.

`review.json` layout (any missing value is written as `Not reported`):

```json
{
  "topic": "Zero-shot / self-supervised insider threat detection",
  "search_date": "2026-10-04",
  "protocol": {
    "question": "...", "ranking_rule": "Q1 journals (SJR or JCR)",
    "inclusion": ["..."], "exclusion": ["..."],
    "tools_used": ["Consensus", "SciSpace", "alphaXiv", "WebSearch"],
    "tools_unavailable": ["bioRxiv (not applicable)"],
    "queries": [{"tool": "Consensus", "query": "...", "hits": 20, "date": "2026-10-04"}]
  },
  "prisma": [{"stage": "Identified (all tools)", "count": 412, "note": "..."},
             {"stage": "Excluded: journal below Q1", "count": 160}],
  "papers": [{
    "title": "...", "authors": "A. Author; B. Author", "year": 2024,
    "venue": "Computers & Security", "publisher": "Elsevier",
    "quartile": "Q1", "sjr": 1.6, "impact_factor": 5.4,
    "ranking_source": "SJR 2024, Computer Science (misc.)",
    "doi_url": "https://doi.org/...",
    "problem": "...", "objective": "...", "method": "Self-supervised",
    "model": "...", "dataset": "CERT r4.2 (1000 users, 501 days, synthetic)",
    "features": "...", "labels": "...", "threat_type": "...",
    "evaluation": "...", "results": "...", "best_result": "AUROC 0.95 on CERT r4.2",
    "baseline": "...", "limitations": "...", "future_work": "...",
    "generalization": "...", "real_world": "...", "explainability": "...",
    "reproducibility": "...", "source_note": "full text",
    "quality": {"clear_problem": 2, "sound_split": 1, "strong_baselines": 2,
                "imbalance_metrics": 2, "multiple_datasets": 0,
                "statistics": 1, "code_data": 0}
  }],
  "excluded": [{"title": "...", "venue": "...", "quartile": "Q3",
                "stage": "Journal rank", "reason": "journal below Q1"}],
  "gaps": [{"axis": "Generalization", "covered": "...", "missing": "...",
            "evidence": "4/27 papers test on unseen users", "papers": "3, 8, 15, 21"}],
  "opportunities": [{"direction": "...", "gaps": "Label, Generalization",
                     "papers": "2, 9, 14"}]
}
```

Sheets the script produces:

| Sheet | Contents |
|---|---|
| Protocol | Question, ranking rule, inclusion/exclusion criteria, tools used and unavailable, search date |
| Search Log | Every query per tool with hit counts |
| PRISMA | Flow counts, including the journal-rank exclusion stage |
| Extraction | One row per included paper: journal, quartile, SJR, IF, ranking source, all 17 extraction fields, quality total |
| Summary | Compact comparison (method, model, dataset, labels, threat, best result, generalization, XAI, code) |
| Quality | Per-criterion 0–2 scores and total /14 |
| Gap Matrix | Each gap axis: covered, missing, evidence counts, supporting papers |
| Opportunities | Research directions linked to gaps and papers |
| Excluded | Every excluded paper with venue, quartile and reason, so the screening is auditable |
| References | Numbered citations with DOI links |

Only if the user asks, also produce `review.md` or a Word version (docx skill).

## Working tips

- Check the journal rank before reading a paper in full: it is the cheapest filter.
- Work in batches (e.g. 5 papers at a time) and append to `review.json` as you go.
- For large reviews, sub-agents may each extract a batch of papers — only if the
  user agrees to spawning them.
- Re-run the 2–3 most important queries at the end to confirm nothing major was missed.
- State the search date; literature in this field moves fast.
