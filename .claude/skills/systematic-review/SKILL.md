---
name: systematic-review
description: Run a PRISMA-style systematic literature review that searches every available research tool (Consensus, SciSpace, alphaXiv, bioRxiv/medRxiv, web search), screens papers against explicit criteria, and extracts a fixed 18-field evidence table per paper (problem, objective, method, model, dataset, features, labels, threat type, evaluation, results, baseline, limitations, future work, generalization, real-world applicability, explainability, reproducibility) followed by a research-gap synthesis. Use when the user asks for a systematic review, literature review, survey, related-work table, state of the art, or research gaps on a topic, e.g. "systematic review of zero-shot insider threat detection", "find the gaps in self-supervised insider threat research", "build an extraction table for these papers".
---

# Systematic Review

Produce a reproducible systematic review: documented search across **all** research
tools, transparent screening, a per-paper extraction table with the 18 fields below,
and a gap analysis grounded in that table. Never invent papers, numbers, or links:
every value must come from a tool result or from the paper text, otherwise write
`Not reported`.

## 0. Scope the review (ask only if it is genuinely unclear)

Write down, at the top of the review, before searching:

- **Research question** (PICO-style for ML: Population = data/users/systems,
  Intervention = method family, Comparison = baselines, Outcome = detection metrics).
- **Inclusion criteria** – e.g. peer-reviewed or arXiv, 2015–present, English,
  proposes or evaluates a detection method, reports quantitative results.
- **Exclusion criteria** – e.g. no evaluation, position papers, duplicates,
  non-English, out-of-domain.
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
| `mcp__Consensus__search` | Peer-reviewed literature. Run each query with **only** the `query` parameter (no filters unless the user asked). Max 3 calls in parallel; on rate limit wait 30 s. Keep its numbered refs and paste its sign-up/usage message verbatim at the end of the answer. |
| `mcp__SciSpace__search-papers` | Second peer-reviewed index; use `mcp__SciSpace__add-column` to pull structured fields (dataset, method, limitations) when supported. |
| `mcp__alphaXiv__discover_papers` | arXiv preprints (most ML security work appears here first). |
| `mcp__alphaXiv__get_paper_content` / `mcp__alphaXiv__answer_pdf_queries` | **Full-text extraction** – the main source for fields 6–18. Ask targeted questions ("What dataset and how many users?", "What limitations do the authors state?", "Is code available?"). |
| `mcp__alphaXiv__read_files_from_github_repository` | Verify reproducibility claims (does the linked repo contain code / data / configs?). |
| `mcp__bioRxiv__*` | Only if the topic touches biology/medicine; otherwise note "not applicable". |
| `WebSearch` / `WebFetch` | Grey literature, IEEE/ACM/Springer landing pages, Google Scholar-style queries, author pages, code links, and to fetch open-access PDFs not covered above. |
| `mcp__Google_Drive__search_files` / `read_file_content` | If the user has their own papers or notes in Drive, include them (ask first if unsure). |

Also do **snowballing**: for the 5–10 most central papers, look at what they cite
(backward) and what cites them (forward, via web search "cited by").

## 3. De-duplicate and screen (PRISMA)

1. Merge all results; de-duplicate by DOI, arXiv ID, then normalized title.
   Prefer the peer-reviewed version over the preprint, but keep the arXiv link.
2. **Title/abstract screening** against the criteria; record a one-line reason for
   every exclusion.
3. **Full-text screening** of the survivors.
4. Keep counts for the PRISMA flow:
   `identified per tool → after dedup → screened → excluded (reasons) → full-text assessed → included`.

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
| 18 | **Citation** | Authors, year, title, venue, DOI/arXiv link | Traceability |

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

## 7. Output

Return, in this order:

1. **Review protocol** – question, criteria, queries, tools used (and unavailable ones), date of search.
2. **PRISMA flow** – the counts from step 3 (text or a small table).
3. **Per-paper extraction** – one block per paper with all 18 fields
   (a wide table is unreadable in chat; use a heading per paper with a field list),
   plus a compact **summary table** (Paper | Method | Model | Dataset | Labels | Threat | Best result | Generalization | XAI | Code).
4. **Quality scores**.
5. **Synthesis and gap matrix** (step 6).
6. **References** – numbered, with exact URLs from tool results. When Consensus was
   used, cite its numbered refs inline and include its usage/sign-up message verbatim at the end.

Also save the data so it can be reused:
- `reviews/<topic-slug>/extraction.csv` – one row per paper, one column per field (UTF-8, quoted).
- `reviews/<topic-slug>/review.md` – the full written review.
If the user prefers, offer a Word document (docx skill) or a spreadsheet (xlsx skill) instead.

## Working tips

- Work in batches (e.g. 5 papers at a time) and append to the CSV as you go so
  progress survives a long session.
- For large reviews, sub-agents may each extract a batch of papers — only if the
  user agrees to spawning them.
- Re-run the 2–3 most important queries at the end to confirm nothing major was missed.
- State the search date; literature in this field moves fast.
