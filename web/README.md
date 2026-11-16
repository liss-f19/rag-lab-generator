# web — SOP Lab Assistant UI

React + TypeScript client for the `rag-lab-generator` backend. It makes the RAG internals
visible: retrieved chunks with scores, graph paths, strategy comparison and streamed agent tool
calls — not only a chat box.

## Run it

Two processes. Backend first:

```bash
# repository root
uv run rag-lab serve                 # http://127.0.0.1:8000, add --reload while developing
```

Then the client:

```bash
cd web
npm install
npm run dev                          # http://localhost:5173
```

The dev server proxies `/api` to `http://127.0.0.1:8000`, so no CORS setup is needed. Change the
target in `vite.config.ts` if the backend runs elsewhere.

## Scripts

| command | what it does |
| --- | --- |
| `npm run dev` | Vite dev server with hot reload on :5173 |
| `npm run build` | type-checks with `tsc -b` and emits `dist/` |
| `npm run preview` | serves the production build |
| `npm run lint` | oxlint over `src/` |

## Pages

- **Chat** — threads (kept in `localStorage`), streamed answers over SSE, markdown with
  highlighted code, mermaid diagrams rendered as SVG with a source toggle, tool-call cards
  showing the arguments and the retrieved sources; clicking a source opens the chunk inspector.
  A compact toolbar selects course, lab, rag strategy and llm provider; quick actions prefill
  prompts.
- **Corpus** — courses from `data/raw`, one card per lab; the lab page has tabs for Tutorial
  (sections from `lab.xml`, code references open the file), Tasks (statement and stages), Files
  (`src/`, `slides/`, `extra/` with preview and download, pdf in an iframe) and Summary.
- **Retrieval Lab** — one query, up to four `rag`/`searcher` configurations side by side with
  per-column latency, trace badges, score bars, kind badges, section breadcrumbs, graph paths,
  and a highlight on every chunk that appears in more than one column.
- **Graph** — label search over the knowledge graph, a force-directed neighbourhood (d3-force +
  plain SVG, wheel to zoom, drag to pan), node kind colors with a legend, and the chunks
  attached to the selected node.
- **Eval** — the runs of `results/*.csv` and of the `eval_runs` table, sortable, with a bar
  chart comparing configurations on one metric.
- **Status** — the resolved backend configuration and the registry contents.

## Layout

```
src/
  api/        client.ts (typed fetch), chat.ts (SSE), hooks.ts (TanStack Query), types.ts
  components/ Layout, HealthBadge, Markdown, Mermaid, ChunkCard, ChunkPanel, GraphView, ui
  pages/      ChatPage, CorpusPage, LabPage, RetrievalPage, GraphPage, EvalPage, StatusPage
```

Every file starts with a `Role / Input / Output / Flow` header, strict TypeScript is on and
`any` is not used. Dark and light themes follow `prefers-color-scheme`.
