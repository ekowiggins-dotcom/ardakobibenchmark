# Custom benchmark research pilot

Open the analyst app at `/benchmark-olustur`. Generate a brief, save it, then
start it from the research library. The page polls stored progress every five
seconds. Closing the browser does not stop the child worker process.

## Configuration

- `ANTHROPIC_API_KEY`: environment, local `.env`, or Streamlit secrets.
- `MAX_LLM_ITEMS_PER_RUN`: maximum banks per run; defaults to the existing client setting.
- `BENCHMARK_DB_PATH`: optional SQLite file location. Default:
  `data/benchmark_jobs/jobs.sqlite3` (excluded from Git).
- `BENCHMARK_DATABASE_URL`: optional shared PostgreSQL URI; takes precedence over SQLite.
- `BENCHMARK_WORKER_MODE`: `external` queues jobs for `pipeline.benchmark_worker`;
  defaults to external with PostgreSQL, local otherwise.

Each bank is limited to eight HTML pages, one extraction call, and one semantic
review call when evidence-backed candidates exist. The second pass may remove
out-of-scope findings or unsupported cells; it cannot add or rewrite values. Optional web
discovery adds one Anthropic call with at most two server-side searches per bank,
using the existing API key. Organization settings must permit web search. Only
tool-returned URLs on registered source domains are accepted, not URLs invented
in model prose. Search snippets are never used as evidence. Search errors and
queries are recorded alongside the run. Existing drafts default to no discovery;
generate a new brief with the checkbox enabled to use it.

Sources are
ranked from existing benchmark data and the official source registry. Relevant
same-host links may be followed. This cannot guarantee complete coverage.
PDFs and browser-only pages are reported as unreadable.
Custom institutions without registered sources will have explicit coverage gaps.
Only registered official domains are supported in this pilot, even when the brief
allows secondary sources. An institution-wide access block may affect every
discovered URL. A browser probe of İş Bankası also returned an access block;
automatic browser retries are therefore not enabled.

Each matrix cell requires a URL from the fetched sources and a matching quote.
This checks evidence provenance, not semantic correctness. All results require
analyst review; this workflow does not approve or publish findings.

Cancellation prevents later writes and is checked between pages/banks. An
already running request may complete and incur API usage. A new run creates a
separate record and preserves previous results. If the host stops mid-run,
cancel the interrupted job and create a new version.

## Deployment boundary

SQLite persists across browser sessions and local app restarts on the same
disk. Streamlit Cloud rebuilds can discard local files. Shared PostgreSQL storage,
an external worker entry point, a local-history migration command and GitHub Actions
configuration are implemented. See `supabase_benchmark_setup.md` to connect them.
Live hosted deployment requires the Supabase URI and API key in GitHub Actions
secrets. The queue workflow polls every 15 minutes (schedules may be delayed),
processes one job per run, and can be manually dispatched. Each run is capped
at 60 minutes; interrupted leases are detected on the next worker run.
Research records are visible to everyone with access to this analyst instance;
restrict that app to the analyst team. No result is synchronized to GitHub or
the executive app.
