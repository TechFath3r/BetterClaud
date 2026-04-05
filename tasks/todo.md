# OpenClawdCode — Build Plan

Phase-ordered roadmap. Pick anything unclaimed, open a PR.

Legend: `[ ]` unclaimed · `[~]` in progress · `[x]` done · `[?]` needs design decision

---

## Phase 0 — Scaffolding ✅

- [x] Rename `BetterClaud` → `OpenClawdCode`
- [x] Update package name, env vars, config paths, MCP server name
- [x] Rewrite README with community-facing vision
- [x] Scaffold `CLAUDE.md` + `claude/` subdocs
- [x] Create `tasks/todo.md` + `tasks/lessons.md`
- [x] Update GitHub repo description + topics

## Phase 1 — `memory-lancedb-pro` parity

Goal: match the capabilities of CortexReach's memory plugin inside Claude Code.

**Canonical source algorithms with line refs:** [`references/source-algorithms.md`](../references/source-algorithms.md). Numbers below are pulled from there — verify against source before implementing.

### Schema changes (do this first — other tasks depend on it)
- [x] **Migrate memory schema** — add columns: `tier` (core|working|peripheral), `temporal_type` (static|dynamic), `abstract` (L0, one-line), `overview` (L1, markdown), `confidence` (float), `access_count` (int), `last_accessed_at` (float), `scope` (string). Existing `content` becomes L2. *(shipped 0.2.0)*
- [x] **Embed-dim validation** — detect on first embed call, assert against schema, fail loud if mismatch *(shipped 0.2.0)*
- [x] **Auto migration in get_or_create_table** — detects schema drift, adds missing columns via LanceDB `add_columns` with SQL defaults. Idempotent, forward-compat. *(shipped 0.2.0)*

### Retrieval pipeline
- [ ] **Hybrid retrieval (weighted sum, NOT RRF)** — `fused = 0.7 * vector + 0.3 * bm25`, with exact-match floor: if `bm25 ≥ 0.75`, take `max(fused, bm25 * 0.92)`. Clamp to `[0.1, 1.0]`. LanceDB native FTS for BM25.
- [ ] **Candidate pool** — fetch top `max(20, limit*2)` from each of vector and BM25, union, sort by fused score
- [ ] **Cross-encoder rerank** — default `bge-reranker-v2-m3` via Ollama (not jina, we're local-only). Rerank `limit*2` candidates. Blend: `0.6*rerank + 0.4*fused`. Hard cutoff at `0.35`.
- [ ] **Post-process pipeline order** — `minScore(0.3) → rerank → recency_boost → importance_weight → length_norm → hard_min(0.35) → MMR_diversity → limit`
- [ ] **Composite decay score** — `0.4*recency + 0.3*frequency + 0.3*intrinsic`, applied as multiplier on search score with tier floor. See formulas below.

### Decay engine (composite, not pure Weibull)
- [ ] **Recency (Weibull stretched-exponential):**
  - `effectiveHL = baseHL * exp(1.5 * importance)` where `baseHL = 30 days` (or `30/3` if `temporal_type == "dynamic"`)
  - `λ = ln(2) / effectiveHL`; `β` per-tier: `core=0.8, working=1.0, peripheral=1.3`
  - `recency = exp(-λ * days_since_last_active^β)` — where `last_active = lastAccessedAt if accessCount > 0 else createdAt`
- [ ] **Frequency:** `base = 1 - exp(-accessCount/5)`; `recentnessBonus = exp(-avgGapDays/30)`; `frequency = base * (0.5 + 0.5*recentnessBonus)`
- [ ] **Intrinsic:** `importance * confidence`
- [ ] **Search boost application:** `multiplier = boostMin + (1-boostMin) * max(tierFloor, composite)`, clamped `[boostMin=0.3, 1.0]`. Tier floors: `core=0.9, working=0.7, peripheral=0.5`.

### Auto-capture
- [ ] **`Stop` hook → memory extractor** — LLM call (default Haiku 4.5, configurable to Ollama). Max **5 memories per extraction**. Output schema: `{memories: [{category, abstract, overview, content}]}`
- [ ] **6 categories** — `profile, preferences, entities, events, cases, patterns`. Category rules:
  - `ALWAYS_MERGE`: `profile` (skip dedup, always merge)
  - `MERGE_SUPPORTED`: `preferences, entities, patterns`
  - `TEMPORAL_VERSIONED`: `preferences, entities` (facts replaced over time)
  - `APPEND_ONLY`: `events, cases` (create or skip only)
- [ ] **Batch-internal dedup** — pairwise cosine on L0 abstracts, threshold `0.85`
- [ ] **Pre-store dedup** — vector search against existing memories, threshold `0.7`, top-3 similar sent to LLM dedup prompt which returns `{decision: create|merge|skip|support|contextualize|contradict|supersede, match_index, reason}`
- [ ] **Admission control (opt-in)** — AMAC-v1 scoring: `utility + confidence + novelty + recency + typePrior`. Defaults (balanced preset): `admit ≥ 0.60`, `reject < 0.45`. Type priors: `profile=0.95, preferences=0.9, patterns=0.85, cases=0.8, entities=0.75, events=0.45`

### Context injection
- [ ] **`UserPromptSubmit` hook** — fetch top-K memories for current prompt (hybrid retrieval + decay), inject as markdown block before the prompt
- [ ] **Token budget** — cap injection at configurable N tokens (default ~2000), rank by rerank score
- [ ] **`SessionStart` hook** — preload top memories scoped to current cwd / project
- [ ] **`PostCompact` hook** — flag that next UserPromptSubmit should re-inject project summaries

### Isolation / scoping
- [ ] **Scope schema** — scope string formatted as `global | agent:<id> | project:<id> | user:<id> | custom:<name>`
- [ ] **Scope derivation** — from cwd + git root + env vars; fallback to `global`
- [ ] **Default accessible scopes per query** — `["global", "project:<current>", "agent:openclawd"]`

### Migration & CLI
- [ ] **`openclawd` CLI** — `doctor`, `list`, `delete`, `export`, `import`, `stats`, `migrate`
- [ ] **`openclawd doctor`** — check Ollama reachable, embedding dim matches, LanceDB opens, hook wiring present in settings.json
- [ ] **Migration script from memory-lancedb-pro** — read their SQLite + LanceDB, map categories/tiers, import
- [ ] **Fix hook paths** — hardcoded to `SCRIPT_DIR` in setup.sh, should point at installed venv

### Tests
- [ ] **Decay-engine tests** — verify recency, frequency, composite formulas against reference values from source
- [ ] **Hybrid-fusion tests** — verify weighted-sum + bm25 floor edge cases
- [ ] **End-to-end integration test** — start MCP server via stdio, call tools, verify responses

## Phase 2 — `lossless-claw` parity (LCM-lite)

Goal: nothing from the conversation is ever truly lost. **Canonical source:** [`references/source-algorithms.md`](../references/source-algorithms.md).

### SQLite schema
- [ ] **Port schema** from `lossless-claw/src/db/migration.ts`: `conversations`, `messages`, `summaries (kind leaf|condensed, depth 0..N)`, `summary_messages` (leaf→msgs), `summary_parents` (condensed→summaries), `context_items` (flat ordered). See research doc for full DDL.
- [ ] **FTS5 virtual tables** — `messages_fts`, `summaries_fts` (porter+unicode61 tokenizer)
- [ ] **DB location default** — `~/.local/share/openclawd/lcm.db`

### Message capture
- [ ] **`UserPromptSubmit` + `PostToolUse` hooks** — append each turn to `messages` table; track `conversation_id` keyed on Claude Code session
- [ ] **Token estimator** — `ceil(text.length / 4)` (match lossless-claw's simple heuristic)

### Summarization
- [ ] **Triggers** — (a) `currentTokens > 0.75 * tokenBudget` full-sweep; (b) `rawTokensOutsideTail >= 20000` incremental leaf
- [ ] **Targets** — `leafTargetTokens = 2400`, `condensedTargetTokens = 2000`, compression floor 35%
- [ ] **Hierarchy** — `depth` field on summaries; `D1 prompt` for leaf→session, `D2` for session→phase, `D3+` for phase→durable
- [ ] **Fanout** — leaf needs ≥8 items, condensed needs ≥4 (hard floor 2)
- [ ] **Summary provider** — configurable; default to Haiku 4.5 via API, fallback to local Ollama
- [ ] **Timeout** — 60s per summary call; reject if output > 3x target tokens

### Context assembly
- [ ] **Assembler algorithm** (match lossless-claw `assemble`):
  1. Fetch `context_items` by ordinal
  2. Split into `evictable` + `freshTail` (last 64 items default)
  3. Protect tool-use/tool-result pairs in fresh tail
  4. Always include fresh tail even if over budget
  5. Fill remaining budget from evictable — BM25-lite relevance if query provided, else newest-first chronological
  6. Assemble + normalize content blocks

### Recall tools (MCP)
- [ ] **`lcm_grep`** — regex OR full_text search across messages, summaries, or both. Params: `pattern, mode, scope, since, before, limit` (default 50, max 200). Returns `[msg#<id>]` / `[sum_xxx]` citations + 200-char snippets, capped at ~10k tokens output.
- [ ] **`lcm_describe`** — return summary content + lineage + token counts for a given `sum_xxx` ID
- [ ] **`lcm_expand`** — traverse summary DAG for one or more `summaryIds`. For condensed: walks `summary_parents` (default maxDepth=3). For leaf with `includeMessages=true`: fetches `summary_messages` → raw messages. `tokenCap` enforced during recursion.

### Integration with Claude Code
- [ ] **`PostCompact` hook** — on native compaction, surface relevant summaries on next `UserPromptSubmit`
- [ ] **Session reconciliation** — when Claude Code drops old messages, ensure our SQLite archive stays complete

## Phase 3 — Community polish

- [ ] **PyPI package**
- [ ] **Homebrew formula** (maybe)
- [ ] **Export/import** for moving memories between machines
- [ ] **Backup/restore** with timestamped snapshots
- [ ] **Docs site** (probably just GitHub Pages off `/docs`)
- [ ] **Example context profiles** (dev, repair, sysadmin, casual — mirror Dan's existing set)

## Open design questions

- [?] **Which extractor/summarizer model?** Haiku 4.5 is smart/cheap/paid; local Ollama is free/dumber. Config-driven — `OPENCLAWD_EXTRACTOR=haiku|ollama|...`. Default to Haiku if `ANTHROPIC_API_KEY` present, else Ollama.
- [?] **Which reranker?** Jina API is what memory-lancedb-pro uses — but we're local-only. `bge-reranker-v2-m3` via Ollama is the closest local equivalent. Confirm Ollama can run it.
- [?] **LanceDB FTS vs SQLite FTS5 for BM25?** LanceDB native FTS is simpler for memories (co-located with vectors). SQLite FTS5 is mandatory for the LCM layer anyway. Don't duplicate — memories use LanceDB FTS, LCM uses SQLite FTS5.
- [?] **Should admission control be on by default?** memory-lancedb-pro keeps it opt-in (`enabled: false`). We could enable balanced preset by default to reduce noise — but might frustrate new users who don't see their memories stored. Start opt-in, document the knob.
- [?] **Remote Ollama support?** `OPENCLAWD_OLLAMA_URL` already allows it — just document.
- [?] **Conversation identity** — Claude Code doesn't expose a stable conversation ID to hooks. How do we key LCM conversations? Probably cwd + session start timestamp. Needs spike.
