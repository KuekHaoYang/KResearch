# KResearch

**Autonomous Deep Research Agent**

```
  ██╗  ██╗██████╗ ███████╗███████╗███████╗ █████╗ ██████╗  ██████╗██╗  ██╗
  ██║ ██╔╝██╔══██╗██╔════╝██╔════╝██╔════╝██╔══██╗██╔══██╗██╔════╝██║  ██║
  █████╔╝ ██████╔╝█████╗  ███████╗█████╗  ███████║██████╔╝██║     ███████║
  ██╔═██╗ ██╔══██╗██╔══╝  ╚════██║██╔══╝  ██╔══██║██╔══██╗██║     ██╔══██║
  ██║  ██╗██║  ██║███████╗███████║███████╗██║  ██║██║  ██║╚██████╗██║  ██║
  ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝
```

KResearch is an autonomous, provider-agnostic research agent that takes a plain-language question, conducts multi-source web research through an unrestricted reasoning loop, and produces a publication-quality report where **every factual claim is backed by an inline citation**. The agent is not a fixed pipeline — it freely decides what to search, what to read, when to verify, and when to stop. All tools (search, scraping, code execution) are implemented in Python and work with any LLM provider.

---

## Table of Contents

- [Key Principles](#key-principles)
- [Quick Start](#quick-start)
- [How the Agent Works](#how-the-agent-works)
- [Tools](#tools)
- [The Mind Map](#the-mind-map)
- [Provider Abstraction](#provider-abstraction)
- [Configuration Reference](#configuration-reference)
- [CLI Reference](#cli-reference)
- [Proxy Support](#proxy-support)
- [Output Format](#output-format)
- [Architecture](#architecture)
- [Dependencies](#dependencies)
- [Roadmap](#roadmap)
- [License](#license)
- [Support](#support)

---

## Key Principles

1. **No hardcoded models.** Model IDs are configuration defaults, fetched and validated against the provider API at runtime. Two defaults are configured — a complex-task model (`gemini-3-flash-preview`) and a fast model (`gemini-3.1-flash-lite-preview`) — but the user can override either via CLI flags or environment variables.

2. **No hardcoded tools.** Web search uses the `ddgs` library (DuckDuckGo), page scraping uses `trafilatura` with an `httpx`/`beautifulsoup4` fallback, and code execution uses a subprocess sandbox. None of these are tied to any provider's built-in features. The LLM calls Python functions via standard function-calling; our code executes them and returns results.

3. **No forced behaviour.** The agent's system prompt gives it a five-phase research methodology (Decompose, Search, Read, Verify, Synthesize), but it is not forced into any fixed order. It freely calls tools, revisits earlier phases, and decides when it has gathered enough evidence to write the report.

4. **Interruptible.** While the agent loop is running, a concurrent `asyncio` task monitors `stdin`. The user can type `stop` to force immediate synthesis, or type any other message (e.g., "focus more on the economic impact") which is injected into the conversation as a `[USER INTERRUPT]`.

5. **Every sentence cited.** The system prompt enforces that every factual claim in the final report carries an inline citation `[N]` linking to a numbered source at the bottom. The agent is instructed to omit any claim it cannot cite.

6. **Plain text copyable.** The Rich library is used only for the live progress panel in the terminal. The report itself is clean Markdown that can be copied, piped, or saved to a file without any formatting artifacts.

---

## Quick Start

### Prerequisites

- Python 3.10 or later
- A Google Gemini API key (get one at [ai.google.dev](https://ai.google.dev/gemini-api/docs/api-key))
- Or an OpenAI API key, or any OpenAI-compatible API endpoint

### Installation

```bash
git clone https://github.com/KuekHaoYang/KResearch.git
cd kresearch
pip install -e .

# For OpenAI / custom provider support:
pip install -e ".[openai]"
```

### Set your API key

```bash
# Gemini (default provider)
export GOOGLE_API_KEY=your-key-here

# OpenAI
export OPENAI_API_KEY=sk-...

# Custom OpenAI-compatible API (e.g. DeepSeek, Together, Ollama)
export KRESEARCH_CUSTOM_API_KEY=your-key
export KRESEARCH_CUSTOM_API_BASE=https://api.deepseek.com/v1
```

Or create a `.env` file in the project root (see `.env.example`).

### Run a research query

```bash
# With Gemini (default)
kresearch "What are the latest breakthroughs in quantum computing?"

# With OpenAI
kresearch --provider openai --model gpt-4o "What are the latest breakthroughs in quantum computing?"

# With a custom OpenAI-compatible API
kresearch --provider custom --model deepseek-chat "What are the latest breakthroughs in quantum computing?"
```

### Other common commands

```bash
# List all models available from the provider API
kresearch --list-models

# Use a specific model
kresearch --model gemini-3.1-pro-preview "your query"

# Save the report to a file
kresearch -o report.md "your query"

# Remove the iteration safety limit (agent runs until it decides to stop)
kresearch --max-iterations 0 "your query"

# Run through a proxy
kresearch --proxy http://127.0.0.1:7890 "your query"
```

---

## How the Agent Works

### The Autonomous Loop

```
User Query
     │
     ▼
┌──────────────────────────────────────────────────────────────┐
│                     AUTONOMOUS LOOP                          │
│                                                              │
│  The LLM sits in a multi-turn chat with function-calling     │
│  tools. It FREELY decides what to call and when.             │
│                                                              │
│  Loop:                                                       │
│  1. LLM receives: system prompt + current mind map state     │
│  2. LLM responds with either:                                │
│     a. Tool calls → orchestrator executes them →             │
│        all results sent back in one batch → repeat           │
│     b. Final text (after draft_report()) → this IS the       │
│        report → done                                         │
│                                                              │
│  Termination (checked in this order):                        │
│  1. Agent calls draft_report() → it decided to stop         │
│  2. User sends "stop" via stdin → forced synthesis           │
│  3. Safety limit reached (default 20 iterations,             │
│     configurable, set to 0 for unlimited)                    │
└──────────────────────────────────────────────────────────────┘
     │
     ▼
Final Report (Markdown with inline citations)
```

### The System Prompt

The system prompt (`src/kresearch/prompts.py`) is a ~7,000-character document that gives the agent a five-phase research methodology:

| Phase | What the agent does |
|---|---|
| **1. Decompose** | Break the query into 3-7 sub-questions covering What, Why, How, Who, When, debates, and implications. |
| **2. Broad Search** | For each sub-question, run `web_search` with diverse queries — literal, rephrased, academic, counterargument, data-seeking. Never repeat a query. |
| **3. Deep Reading** | Use `read_webpage` on the 5-10 most authoritative results. Prefer primary sources (papers, official reports) over secondary. Read full articles, not just snippets. |
| **4. Verify** | Cross-reference claims across 2+ independent sources. Call `log_contradiction` for disagreements. Use `execute_python` for math/data verification. Assign confidence scores honestly (0.9+ requires 3+ reliable sources agreeing). |
| **5. Synthesize** | Call `update_findings` for each topic, then `draft_report()`. Write the complete report as the next response. |

The prompt also contains strict citation rules (every factual claim must carry `[N]`), a required report structure (Executive Summary, thematic sections, Contradictions & Debates, Limitations, Sources), and quality standards (depth, specificity, balance, honesty).

### Batch Function Responses

When the LLM returns multiple tool calls in a single response, the orchestrator executes all of them concurrently, then sends **all results back in a single message**. This is the correct behaviour for the Gemini API (and is handled by `ChatSession.send_function_responses()`). Providers that do not support batch responses fall back to sending results one at a time.

### User Interrupts

While the agent loop runs, a separate `asyncio` task polls `stdin` using `select()` (non-blocking, 300ms intervals):

- **`stop` / `quit` / `done`** — The agent is told to call `draft_report()` and write the best report it can with current findings.
- **Any other text** — Injected into the conversation as `[USER INTERRUPT]: <message>`. The agent sees it and adjusts its research direction.

---

## Tools

All tools are provider-agnostic Python functions, registered via `ToolRegistry` and exposed to the LLM through standard function-calling declarations. The agent discovers tools automatically from the registry — adding a new tool requires zero changes to the agent loop.

| Tool | Implementation | Purpose |
|---|---|---|
| `web_search(query, max_results)` | `ddgs` library (DuckDuckGo Search) | Free, no-API-key web search. Returns `{title, url, snippet}` for each result. Max 20 results per call. |
| `read_webpage(url)` | `trafilatura` primary, `httpx` + `beautifulsoup4` fallback | Fetches a URL and extracts the main article content as clean Markdown. Strips navigation, scripts, ads. Truncates at 15,000 chars to protect context. |
| `execute_python(code, timeout)` | `subprocess.run()` in a restricted environment | Runs Python code in an isolated subprocess with a 30-second timeout and a restricted `PATH`. Used for math verification, data analysis, and fact-checking. |
| `update_findings(topic, content, sources, confidence)` | Writes to the `MindMap` data structure | Records a verified finding under a topic node with source URLs and a confidence score (0.0-1.0). The agent calls this frequently to build its working memory. |
| `log_contradiction(topic, claim_a, claim_b, source_a, source_b)` | Writes to the `MindMap` data structure | Records a conflict between two sources. The agent is instructed to never ignore contradictions — they must appear in the final report. |
| `spawn_subagent(query, context)` | Creates a new `ChatSession` with a focused system prompt | Launches an independent sub-agent that runs its own mini research loop (max 5 iterations, no further sub-spawning). Returns structured findings. Used for clearly independent sub-questions. |
| `draft_report()` | Sets `state.draft_requested = True`, returns mind map JSON | Signals the agent is ready to write the final report. Returns the complete mind map data so the agent can reference it while writing. The agent's next text response becomes the report. |

### Why not use provider built-in tools?

Gemini has built-in `google_search` and `code_execution`. OpenAI has `code_interpreter`. But each provider's built-in tools are different, and some providers have none. By implementing all tools in Python, KResearch's tool set is identical regardless of which LLM backend is used. Switching from Gemini to OpenAI to Anthropic requires zero changes to the tool layer.

---

## The Mind Map

The mind map (`src/kresearch/models/mind_map.py`) is the agent's **persistent epistemic state** — a hierarchical tree of everything it knows, structured by topic. Even if the LLM's conversation history gets long, the mind map retains all findings in a compact format that is included in the system prompt.

### Structure

```
MindMap
├── root: MindMapNode (topic = the original query)
│   ├── child: MindMapNode (topic = "Quantum Hardware")
│   │   ├── content: "IBM unveiled Nighthawk, a 120-qubit processor..."
│   │   ├── sources: [{url, title}, {url, title}]
│   │   ├── confidence: 0.95
│   │   └── contradictions: []
│   ├── child: MindMapNode (topic = "Error Correction")
│   │   ├── content: "Google's Willow chip operates below threshold..."
│   │   ├── sources: [{url, title}, {url, title}, {url, title}]
│   │   ├── confidence: 0.98
│   │   └── contradictions: [Contradiction(...)]
│   └── ...
└── query: "What are the latest breakthroughs in quantum computing?"
```

### Key methods

- `add_finding(topic, content, sources, confidence)` — Finds or creates a topic node and appends the finding. Content is accumulated (not replaced), sources are extended, confidence takes the max.
- `log_contradiction(topic, claim_a, claim_b, source_a, source_b)` — Attaches a `Contradiction` record to the topic node.
- `get_summary()` — Returns a compact text tree used in the system prompt so the agent knows its current state.
- `get_gaps()` — Returns topics with confidence below 0.3 (areas needing more research).
- `get_contradictions()` — Returns all unresolved contradictions across the entire tree.
- `source_count()` — Total number of sources across all nodes.

---

## Provider Abstraction

KResearch is designed to work with any LLM that supports function calling. The provider layer (`src/kresearch/providers/`) defines two abstract base classes:

### `ProviderInterface`

Every provider must implement:

| Method | Description |
|---|---|
| `generate(messages, system_instruction, tools, thinking_level)` | One-shot generation with optional tool declarations. |
| `generate_stream(messages, ...)` | Streaming generation (yields text chunks). |
| `create_chat(system_instruction, tools, thinking_level)` | Creates a multi-turn `ChatSession` — the primary interface used by the orchestrator. |
| `list_models()` | Fetches available models from the provider API. Returns `list[ModelInfo]`. |

### `ChatSession`

The multi-turn chat interface used by the agent loop:

| Method | Description |
|---|---|
| `send(message)` | Send a user message, returns `GenerateResponse` with text and/or function calls. |
| `send_function_response(name, response)` | Send a single tool result back to the model. |
| `send_function_responses(responses)` | Send multiple tool results in one batch (providers should override for correctness). |
| `get_history()` | Return the conversation history. |

### Provider-agnostic types

All types are defined in `src/kresearch/providers/types.py`:

- `Message` — role + content
- `FunctionCall` — name + args dict
- `GenerateResponse` — text, function_calls, thinking, usage, raw
- `ModelInfo` — id, name, context_window
- `ToolDeclaration` — name, description, parameters (JSON Schema)

### Current providers

| Provider | Status | Default model | Fast model |
|---|---|---|---|
| **Gemini** | Fully implemented | `gemini-3-flash-preview` | `gemini-3.1-flash-lite-preview` |
| **OpenAI** | Fully implemented | `gpt-4o` | `gpt-4o-mini` |
| **Custom API** | Fully implemented | *(user-specified)* | *(user-specified)* |
| Anthropic | Placeholder (not yet implemented) | `claude-sonnet-4-6` | `claude-haiku-4-5` |
| xAI | Placeholder (not yet implemented) | `grok-3` | `grok-3-fast` |
| Perplexity | Placeholder (not yet implemented) | `sonar-pro` | `sonar` |

Adding a new provider requires implementing `ProviderInterface` and `ChatSession`, registering it in `providers/__init__.py`, and optionally adding the SDK as an optional dependency in `pyproject.toml`. Zero changes to the orchestrator, tools, or agent logic.

---

## Configuration Reference

Configuration is handled by `KResearchConfig` (Pydantic Settings), loaded from environment variables, a `.env` file, and CLI overrides (CLI takes priority).

| Variable | CLI Flag | Default | Description |
|---|---|---|---|
| `GOOGLE_API_KEY` | — | *(required for gemini)* | Gemini API key. |
| `OPENAI_API_KEY` | — | *(required for openai)* | OpenAI API key. |
| `KRESEARCH_CUSTOM_API_KEY` | — | *(required for custom)* | API key for custom OpenAI-compatible endpoint. |
| `KRESEARCH_CUSTOM_API_BASE` | — | *(required for custom)* | Base URL for custom endpoint (e.g. `https://api.deepseek.com/v1`). |
| `KRESEARCH_PROVIDER` | `--provider` | `gemini` | LLM provider name. |
| `KRESEARCH_MODEL` | `--model` | `gemini-3-flash-preview` | Primary model for the agent loop. |
| `KRESEARCH_FAST_MODEL` | `--fast-model` | `gemini-3.1-flash-lite-preview` | Fast model for sub-agents. |
| `KRESEARCH_PROXY` | `--proxy` | — | Global HTTP proxy for all outbound requests. |
| `KRESEARCH_GEMINI_PROXY` | — | — | Proxy override for the Gemini provider only. |
| `KRESEARCH_OPENAI_PROXY` | — | — | Proxy override for the OpenAI provider only. |
| `KRESEARCH_CUSTOM_PROXY` | — | — | Proxy override for the custom provider only. |
| `KRESEARCH_MAX_ITERATIONS` | `--max-iterations` | `20` | Safety limit on agent loop iterations. Set to `0` for unlimited. |
| `KRESEARCH_MAX_CONCURRENT_SUBAGENTS` | — | `3` | Maximum number of concurrent sub-agents. |
| `KRESEARCH_THINKING_LEVEL` | — | `high` | Thinking level passed to providers that support it. |
| `KRESEARCH_VERBOSE` | `--verbose` | `false` | Enable verbose logging. |
| `KRESEARCH_OUTPUT_DIR` | — | `.` | Default directory for saved reports. |

### Priority order

CLI flags > environment variables > `.env` file > defaults.

### Proxy resolution

When multiple proxies are configured, KResearch uses the most specific one. For example, if both `KRESEARCH_PROXY` and `KRESEARCH_GEMINI_PROXY` are set, the Gemini provider uses `KRESEARCH_GEMINI_PROXY` while web scraping tools use `KRESEARCH_PROXY`.

---

## CLI Reference

```
kresearch [OPTIONS] [QUERY]

Arguments:
  QUERY                    The research question (omit for usage info).

Options:
  --model TEXT              Override the primary model.
  --fast-model TEXT         Override the fast/sub-agent model.
  --provider TEXT           LLM provider (gemini, openai, anthropic, xai, perplexity).
  --proxy TEXT              HTTP proxy URL (e.g., http://127.0.0.1:7890).
  --list-models             Fetch and display available models from the API.
  --verbose                 Enable verbose logging.
  -o, --output PATH         Save the final report to a file.
  --max-iterations INTEGER  Agent loop safety limit (0 = unlimited).
  --help                    Show usage and exit.
```

### Examples

```bash
# Basic research
kresearch "Impact of AI on healthcare diagnostics"

# Use a larger model for more complex reasoning
kresearch --model gemini-3.1-pro-preview "Compare monetary policy approaches of the Fed vs ECB"

# Use OpenAI
kresearch --provider openai --model gpt-4o "Impact of AI on healthcare diagnostics"

# Use a custom OpenAI-compatible endpoint (e.g. DeepSeek)
kresearch --provider custom --model deepseek-chat "Impact of AI on healthcare diagnostics"

# Save output and remove iteration limit
kresearch --max-iterations 0 -o deep_dive.md "History and future of nuclear fusion energy"

# List models to see what's available
kresearch --list-models
kresearch --provider openai --list-models
```

---

## Proxy Support

KResearch supports HTTP and SOCKS proxies for all outbound traffic. Proxies can be set globally or per-provider.

```bash
# Global proxy (applies to all API calls AND web scraping)
export KRESEARCH_PROXY=http://127.0.0.1:7890

# Provider-specific proxy (overrides global for that provider only)
export KRESEARCH_GEMINI_PROXY=socks5://127.0.0.1:1080
export KRESEARCH_OPENAI_PROXY=socks5://127.0.0.1:1080
export KRESEARCH_CUSTOM_PROXY=http://127.0.0.1:7890

# CLI override
kresearch --proxy http://proxy.example.com:8080 "your query"
```

The proxy is passed to:
- `google.genai.Client(http_options={"proxy": ...})` for Gemini API calls.
- `openai.AsyncOpenAI(http_client=DefaultAsyncHttpxClient(proxy=...))` for OpenAI and custom API calls.
- `httpx.AsyncClient(proxy=...)` for `read_webpage` fallback scraping.
- Future provider SDK clients.

---

## Output Format

The final report is plain Markdown with this structure:

```markdown
# Research Report: {Descriptive Title}

## Executive Summary
4-6 dense sentences: what was investigated, key findings with data,
conclusions, and caveats.

## {Thematic Section 1}
3-5 substantive paragraphs with inline citations [N] for every
factual claim. Specific data, statistics, expert opinions.

## {Thematic Section 2}
...

## Contradictions & Debates
Where sources disagree, both sides presented with citations.
Assessment of which has stronger evidence and why.

## Limitations
Gaps in available sources, unverifiable claims, areas needing
further investigation.

## Sources
[1] Source Title - https://source-url.com/path
[2] Source Title - https://source-url.com/path
...
```

The report is printed to `stdout` as plain text and can optionally be saved to a file with `-o`.

---

## Architecture

```
src/kresearch/
├── __init__.py              # Package version
├── __main__.py              # python -m kresearch entry point
├── cli.py                   # Click CLI (argument parsing, provider init, orchestrator launch)
├── config.py                # KResearchConfig (Pydantic Settings from env/.env/CLI)
├── prompts.py               # SYSTEM_TEMPLATE — the 7K-char agent system prompt
├── orchestrator.py          # Orchestrator class — the autonomous agent loop
│
├── models/
│   ├── mind_map.py          # MindMap, MindMapNode, Source, Contradiction
│   ├── task_graph.py        # TaskGraph, TaskNode, TaskStatus (sub-task tracking)
│   └── state.py             # ResearchState, ActionLog, TokenUsage (session state)
│
├── providers/
│   ├── __init__.py          # get_provider() factory + PROVIDER_REGISTRY
│   ├── base.py              # ProviderInterface (ABC), ChatSession (ABC)
│   ├── types.py             # Message, GenerateResponse, FunctionCall, ModelInfo, ToolDeclaration
│   ├── gemini/
│   │   ├── provider.py      # GeminiProvider — google-genai SDK integration
│   │   └── chat.py          # GeminiChatSession — multi-turn chat with batch function responses
│   ├── openai/
│   │   ├── provider.py      # OpenaiProvider — openai SDK integration
│   │   └── chat.py          # OpenaiChatSession — multi-turn chat with tool_call_id tracking
│   ├── custom/
│   │   └── provider.py      # CustomProvider — subclass of OpenaiProvider with custom base_url
│   ├── anthropic/__init__.py
│   ├── xai/__init__.py
│   └── perplexity/__init__.py
│
├── tools/
│   ├── registry.py          # ToolRegistry + create_default_registry()
│   ├── web_search.py        # DuckDuckGo search via ddgs
│   ├── web_reader.py        # trafilatura extraction + httpx/bs4 fallback
│   ├── code_executor.py     # Sandboxed subprocess Python execution
│   ├── research_tools.py    # update_findings, log_contradiction, draft_report
│   └── subagent_tool.py     # spawn_subagent (mini research loop)
│
└── output/
    ├── console.py           # ConsoleUI — Rich banner, live panel, model table
    └── markdown.py          # ensure_citations, format_source_list, save_report
```

### Data flow

```
CLI (cli.py)
 │  Parses args, builds KResearchConfig, creates provider via get_provider()
 ▼
Orchestrator (orchestrator.py)
 │  Builds system prompt from SYSTEM_TEMPLATE + current ResearchState
 │  Creates a ChatSession via provider.create_chat()
 │  Enters the agent loop
 ▼
Agent Loop
 │  Sends query to LLM → gets response
 │  If response has function_calls:
 │    Execute ALL calls via ToolRegistry.execute()
 │    Send ALL results back via chat.send_function_responses()
 │    Process the next response (may recurse if more calls)
 │  If response has text + draft_requested:
 │    Return text as the final report
 │  If over budget:
 │    Force synthesis via _finalize()
 ▼
Tools (tools/*.py)
 │  Each tool is an async function: (args, **ctx) -> dict
 │  ctx contains: state (ResearchState), provider, config
 │  Tools modify state.mind_map via add_finding(), log_contradiction()
 ▼
ConsoleUI (output/console.py)
 │  Rich Live panel updated after each tool call
 │  Shows: tool actions log, mind map tree, iteration/source/token stats
 ▼
Final Report → stdout and optionally → file
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `google-genai` | Gemini SDK — first provider implementation |
| `pydantic` | Data models (MindMap, ResearchState, provider types) |
| `pydantic-settings` | Configuration from environment, `.env`, CLI |
| `rich` | Terminal UI — banner, live progress panel, model table |
| `click` | CLI argument parsing |
| `ddgs` | DuckDuckGo web search — free, no API key, no rate limits |
| `trafilatura` | Article/webpage content extraction |
| `httpx` | Async HTTP client (fallback scraping) |
| `beautifulsoup4` | HTML parsing (fallback scraping) |
| `lxml` | Fast HTML/XML parser (used by trafilatura and bs4) |

### Dev dependencies

`pytest`, `pytest-asyncio`, `ruff`, `mypy`

### Optional dependencies

`openai` (for OpenAI and custom providers), `anthropic` (for future Anthropic provider)

---

## Roadmap

### Providers

- [x] **OpenAI provider** — GPT-4o / GPT-4o-mini via the OpenAI SDK with function calling
- [x] **Custom API provider** — Any OpenAI-compatible endpoint (DeepSeek, Together, Ollama, etc.)
- [ ] **Anthropic provider** — Claude Sonnet / Haiku via the Anthropic SDK with tool use
- [ ] **xAI provider** — Grok-3 / Grok-3-fast
- [ ] **Perplexity provider** — Sonar Pro / Sonar for search-native research
- [ ] **Ollama / local models** — Run research with locally hosted models via the Ollama API
- [ ] **Provider auto-fallback** — If one provider fails (rate limit, downtime), automatically retry with a configured fallback

### Tools & Capabilities

- [ ] **PDF reader tool** — Extract and analyze content from PDF URLs (research papers, reports)
- [ ] **Image/chart analysis** — Use multimodal models to interpret charts, graphs, and infographics found during research
- [ ] **Academic search** — Dedicated tool for Semantic Scholar / arXiv / Google Scholar APIs
- [ ] **Brave Search API** — Alternative search backend with an API key for higher-quality results
- [ ] **Memory across sessions** — Persist mind maps to disk so research can be resumed later
- [ ] **Concurrent sub-agents** — Run multiple sub-agents in parallel with `asyncio.gather()` instead of sequentially

### Output & Integrations

- [ ] **Telegram bot** — Run KResearch as a Telegram bot: send a query, receive the report as a message. Support for inline progress updates via message editing
- [ ] **Discord bot** — Same as Telegram, with thread-based research sessions
- [ ] **Web UI** — Simple FastAPI + WebSocket frontend: submit queries, watch research happen in real time, browse past reports
- [ ] **Export formats** — PDF export, HTML export, DOCX export via pandoc
- [ ] **Structured JSON output** — Machine-readable report format alongside Markdown for programmatic consumption

### Agent Intelligence

- [ ] **Multi-turn follow-up** — After the report is generated, allow the user to ask follow-up questions that trigger additional research with the existing mind map as context
- [ ] **Source quality scoring** — Automatic domain reputation scoring (academic > news > blog) to weight findings
- [ ] **Fact-checking mode** — Given a specific claim, verify it against multiple sources and return a confidence assessment
- [ ] **Comparative research** — "Compare X vs Y" mode that structures the report as a side-by-side analysis
- [ ] **Timeline mode** — For historical queries, build a chronological timeline with cited events

### Developer Experience

- [ ] **Plugin system** — Allow third-party tools to be loaded from entry points or a plugins directory
- [ ] **Webhook notifications** — POST the completed report to a webhook URL when research finishes
- [ ] **API server mode** — Run KResearch as a REST API (`kresearch serve`) for integration into other applications
- [ ] **Docker image** — Pre-built container for easy deployment

---

## License

MIT — see [LICENSE](LICENSE).

---

## Support

If KResearch saves you time, consider buying me a coffee:

<a href="https://www.buymeacoffee.com/kuekhaoyang">
  <img src="https://img.buymeacoffee.com/button-api/?text=Buy me a coffee&emoji=&slug=kuekhaoyang&button_colour=FFDD00&font_colour=000000&font_family=Cookie&outline_colour=000000&coffee_colour=ffffff" />
</a>
