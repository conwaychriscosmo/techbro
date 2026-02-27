# Tech Bro — Open Source Tooling

Two Python scripts that prepare any web platform or document corpus for automation with Tech Bro. Together they handle both sides of the integration: making your platform machine-readable, and turning your documented processes into executable workflows.

```
bro_generator.py      →  generates bro_read / bro_write pages for your platform
conway_generator.py   →  generates Conway DSL workflow JSON from docs, sites, and pages
```

---

## Table of Contents

- [Background](#background)
- [The Two-Script Workflow](#the-two-script-workflow)
- [Installation](#installation)
- [bro\_generator.py — Platform Preparation](#bro_generatorpy--platform-preparation)
  - [How It Works](#how-it-works)
  - [web-to-bro](#web-to-bro)
  - [db-to-bro](#db-to-bro)
  - [Output Files](#bro-output-files)
- [conway\_generator.py — Workflow Generation](#conway_generatorpy--workflow-generation)
  - [The Conway DSL](#the-conway-dsl)
  - [doc-to-workflow](#doc-to-workflow)
  - [web-to-workflow](#web-to-workflow)
  - [webpage-to-workflow](#webpage-to-workflow)
  - [Output Files](#conway-output-files)
  - [The Manifest](#the-manifest)
- [End-to-End Example](#end-to-end-example)
- [Reference: Conway DSL Step Types](#reference-conway-dsl-step-types)
- [Contributing](#contributing)
- [License](#license)

---

## Background

Tech Bro is a Chromium-based browser automation system. It logs into platforms **as the user**, using the user's own credentials, and executes tasks on their behalf — checking claims, filing requests, managing accounts — things that currently take twenty minutes of clicking.

For Tech Bro to work optimally on a platform, two things need to exist:

1. **Structured pages** on the platform that aggregate the user's data (`bro_read`) and surface their available actions (`bro_write`) in one place, rather than spread across dozens of screens.
2. **Workflow files** that tell Tech Bro exactly what steps to take to accomplish a task — navigate here, fill this form, click that button, wait for a human when authentication is needed. You can generate them in tech bro, but it is nicer to have a script turn all your exisiting documentation into automation.

`bro_generator.py` handles #1. `conway_generator.py` handles #2.

---

## The Two-Script Workflow

```
Your Platform                          Your Docs / Help Site
      │                                        │
      ▼                                        ▼
bro_generator.py                    conway_generator.py
      │                                        │
      ▼                                        ▼
bro_read.html  ◄────── Tech Bro ──────► workflow.json
bro_write.html           executes
```

The two scripts are independent — run either or both depending on what you're building.

---

## Installation

Both scripts use standard Python 3.10+ with optional dependencies depending on mode.

**Core (required for both scripts):**
```bash
pip install requests beautifulsoup4
```

**For `bro_generator.py`:**
```bash
pip install sqlalchemy          # db-to-bro mode
pip install playwright          # web-to-bro with JS-heavy sites (optional)
playwright install chromium     # after installing playwright
```

**For `conway_generator.py`:**
```bash
pip install anthropic            # required — calls Claude API
pip install python-docx          # doc-to-workflow with .docx files
pip install pypdf                # doc-to-workflow with .pdf files
pip install pillow pytesseract   # OCR fallback for scanned PDFs (optional)
pip install pdf2image            # better OCR rendering (optional)
```

**API key** for `conway_generator.py` — set once and forget:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

---

## bro\_generator.py — Platform Preparation

### How It Works

Tech Bro navigates pages the same way a user does — but it's far more efficient when data and actions are consolidated. `bro_generator.py` analyzes your platform and generates two purpose-built HTML pages per user:

- **`bro_read`** — one page containing everything the platform knows about a user: profile, accounts, policies, claims, transaction history, linked assets, preferences. The same data that would take ten clicks to assemble, on a single page.

- **`bro_write`** — one page listing every action the user is authorized to take, as plain HTML forms with labeled fields and explicit POST targets.

Both pages are protected by the user's own session. Tech Bro accesses them as the user, with the user's credentials. No new API, no service token, no back-channel.

The pages are intentionally plain: no JavaScript framework, no pagination, no tabs. Plain HTML is instantly parseable, diffable, and self-documenting.

### web-to-bro

Crawls a live website and infers `bro_read` / `bro_write` content from the pages it finds.

The crawler can optionally log in first — it GETs the login page, extracts CSRF tokens automatically, POSTs credentials, and preserves the session cookie for the entire crawl. Use `--playwright` for sites where server-rendered HTML isn't enough.

```bash
python bro_generator.py web-to-bro \
    --url https://yourplatform.com \
    --user-id 42 \
    --output-dir ./bro_output
```

**With authentication:**
```bash
python bro_generator.py web-to-bro \
    --url https://yourplatform.com \
    --user-id 42 \
    --username alice@example.com \
    --password secret \
    --login-url https://yourplatform.com/auth/login \
    --max-pages 100 \
    --output-dir ./bro_output
```

**With Playwright for JS-heavy sites:**
```bash
python bro_generator.py web-to-bro \
    --url https://yourplatform.com \
    --user-id 42 \
    --username alice@example.com \
    --password secret \
    --playwright \
    --output-dir ./bro_output
```

| Flag | Default | Description |
|---|---|---|
| `--url` | *(required)* | Base URL to crawl |
| `--user-id` | *(required)* | User ID used in output filenames and canonical URLs |
| `--username` | — | Login username or email |
| `--password` | — | Login password |
| `--login-url` | `<base>/login` | Login form URL if non-standard |
| `--max-pages` | `50` | Maximum pages to crawl |
| `--playwright` | off | Use Playwright instead of requests (for JS-heavy sites) |
| `--output-dir` | `./bro_output` | Where to write output files |

**What the crawler extracts for `bro_read`:**
- HTML `<table>` elements with their headers and rows
- Definition lists (`<dl>/<dt>/<dd>`)
- Labeled key-value sections in `<div>` containers with semantic class names (`detail`, `profile`, `card`, `field`, etc.)

**What the crawler extracts for `bro_write`:**
- All `<form>` elements that aren't login/registration forms
- Form fields with their labels, types, and required status
- Select options, textareas, date inputs
- Submit targets and HTTP methods

---

### db-to-bro

Inspects a live database schema via SQLAlchemy reflection and generates `bro_read` / `bro_write` pages wired to the real tables, columns, and foreign key relationships.

Works with any SQLAlchemy-compatible database: SQLite, PostgreSQL, MySQL, MSSQL, Oracle.

**SQLite:**
```bash
python bro_generator.py db-to-bro \
    --dsn sqlite:///myapp.db \
    --user-table users \
    --output-dir ./bro_output
```

**PostgreSQL:**
```bash
python bro_generator.py db-to-bro \
    --dsn postgresql://user:pass@localhost/mydb \
    --user-table users \
    --user-id-column id \
    --output-dir ./bro_output
```

**MySQL:**
```bash
python bro_generator.py db-to-bro \
    --dsn mysql+pymysql://user:pass@localhost/mydb \
    --user-table customers \
    --user-id-column customer_id \
    --output-dir ./bro_output
```

| Flag | Default | Description |
|---|---|---|
| `--dsn` | *(required)* | SQLAlchemy connection string |
| `--user-table` | *(required)* | Name of the primary user/customer table |
| `--user-id-column` | `id` | Primary key column in the user table |
| `--user-id` | `schema` | Label used in output filenames |
| `--output-dir` | `./bro_output` | Where to write output files |

**What `db-to-bro` generates for `bro_read`:**
- Full schema overview (database type, table count, user-related tables)
- Per-table column detail: name, type, nullability, PK/FK flags
- Foreign key maps: outbound and inbound relationships
- `bro_index` — a linked table of every entity type with its canonical `bro_read` URL
- Complete FK relationship map across all tables

**How DB `bro_write` actions are inferred:**
- The script BFS-traverses the FK graph outward from the user table to discover all related entities
- For each related table, it generates UPDATE, CREATE (for child tables), and DELETE forms
- Column types are mapped to appropriate HTML input types: `INT/FLOAT` → `number`, `BOOL` → `select`, `TEXT` → `textarea`, `DATE` → `date`, `DATETIME` → `datetime-local`
- Audit columns (`created_at`, `updated_at`, `deleted_at`) and FK columns are excluded from forms automatically

---

### Bro Output Files

Both modes write two files to `--output-dir`:

```
bro_output/
├── user_42_bro_read.html     ← aggregated data view
└── user_42_bro_write.html    ← available actions as forms
```

The canonical URLs these files correspond to on a real platform:
```
/users/:user_id/bro_read
/users/:user_id/bro_write
```

The pattern extends to other entity types:
```
/accounts/:id/bro_read
/policies/:id/bro_read
/policies/:id/bro_write
/claims/:id/bro_read
/claims/:id/bro_write
```

---

## conway\_generator.py — Workflow Generation

Converts process descriptions from documents, help sites, and individual pages into Conway DSL JSON workflows that Tech Bro's `WorkflowOrchestrator` executes directly.

Under the hood, the script uses Claude (claude-sonnet-4-6) with a system prompt that embeds the complete Conway DSL specification — every step type, every field, the template syntax, selector priority rules, and all generation heuristics. The output is immediately executable; no hand-editing required.

### The Conway DSL

A Conway workflow is a JSON object with a flat or branching array of typed steps:

```json
{
  "id": "workflow-1234567890",
  "name": "Submit Purchase Order in SAP Ariba",
  "description": "Creates and submits a new PO through the Ariba procurement portal",
  "tags": ["procurement", "sap-ariba"],
  "steps": [
    {
      "id": "navigate_to_ariba",
      "type": "navigate",
      "description": "Open the SAP Ariba portal",
      "url": "https://s1.ariba.com",
      "waitUntil": "domcontentloaded"
    },
    {
      "id": "wait_for_dashboard",
      "type": "wait_for_load",
      "description": "Wait for the dashboard to load",
      "selector": ".dashboard-content",
      "timeout": 15000
    },
    {
      "id": "human_sso_login",
      "type": "wait_for_human",
      "description": "User completes SSO authentication",
      "prompt": {
        "title": "Login Required",
        "message": "Please complete your SSO login, then click Continue",
        "inputType": "text"
      },
      "spotlight": true,
      "screenshot": true
    },
    {
      "id": "screenshot_before_submit",
      "type": "screenshot",
      "description": "Capture order details before submission",
      "tags": ["audit", "pre-submit"],
      "fullPage": false
    },
    {
      "id": "click_submit_order",
      "type": "click",
      "description": "Submit the purchase order",
      "selector": "[data-testid='submit-order-btn']",
      "selectorAlternatives": ["button:has-text('Submit Order')", ".submit-btn"],
      "waitAfter": 3000,
      "retries": 3,
      "retryDelay": 1000
    },
    {
      "id": "check_confirmation",
      "type": "check_element",
      "description": "Verify confirmation banner appeared",
      "selector": ".confirmation-banner"
    },
    {
      "id": "branch_on_result",
      "type": "conditional",
      "description": "Handle success or error state",
      "condition": "element_exists",
      "selector": ".error-message",
      "if_true": [
        {
          "id": "human_resolve_error",
          "type": "wait_for_human",
          "prompt": {
            "title": "Error Detected",
            "message": "An error appeared. Please resolve it and click Continue."
          }
        }
      ],
      "if_false": [
        {
          "id": "screenshot_confirmation",
          "type": "screenshot",
          "description": "Capture confirmation for audit trail",
          "tags": ["confirmation", "audit"]
        }
      ]
    }
  ]
}
```

The full step type reference is in the [Reference section](#reference-conway-dsl-step-types) below.

---

### doc-to-workflow

Reads a document and extracts every distinct workflow or process described in it, emitting one JSON file per workflow found.

Supports `.docx`, `.pdf`, and `.md`/`.txt`. For `.docx`, heading styles and list formatting are preserved as structural signals. For `.pdf`, text is extracted page by page; if more than half the pages are empty (scanned document), an OCR fallback via `pytesseract` is attempted automatically.

Large documents are split into overlapping chunks (10,000 chars with 800-char overlap at paragraph boundaries) and processed in parallel — results are deduplicated before writing.

```bash
python conway_generator.py doc-to-workflow \
    --file path/to/process-guide.pdf \
    --output-dir ./workflows
```

```bash
python conway_generator.py doc-to-workflow \
    --file "SAP Ariba PO Process.docx" \
    --output-dir ./workflows
```

```bash
python conway_generator.py doc-to-workflow \
    --file onboarding-runbook.md \
    --output-dir ./workflows
```

| Flag | Default | Description |
|---|---|---|
| `--file` | *(required)* | Path to `.docx`, `.pdf`, `.md`, or `.txt` file |
| `--output-dir` | `./workflows` | Where to write workflow JSON files |
| `--api-key` | env var | Anthropic API key (or set `ANTHROPIC_API_KEY`) |

---

### web-to-workflow

Crawls an entire web domain and generates one Conway workflow JSON file per distinct process found. Built for documentation sites, help centers, and enterprise knowledge bases.

**Discovery strategy (in order):**
1. Checks `robots.txt` for `Sitemap:` directives
2. Tries `/sitemap.xml`, `/sitemap_index.xml`, `/sitemap-index.xml`, `/sitemaps/sitemap.xml`
3. Recursively follows `<sitemapindex>` → child sitemaps
4. Falls back to BFS crawl from the base URL if no sitemap is found

**Filtering:** Before calling Claude, pages are scored against 15 heuristic patterns (numbered steps, "how to", "procedure", "step-by-step", etc.) and a numbered-list density check. Only pages that score above threshold are sent for workflow generation — so running against `corp.sap.com` doesn't burn API calls on marketing pages.

**Deduplication — two layers:**
- Page content is fingerprinted (SHA-256 of normalized text) before fetching — duplicate pages (CDN mirrors, pagination variants) are skipped
- Generated workflows are fingerprinted (name + step count + first/last step type) after generation — the same "How to log in" workflow documented on 15 different pages is written once

**Concurrency:** Page fetching and workflow generation both use `ThreadPoolExecutor`. Fetch concurrency defaults to 6; generation concurrency to half that, to be respectful of the Claude API rate limit. Crawl delay from `robots.txt` is respected and distributed across workers.

```bash
python conway_generator.py web-to-workflow \
    --url https://help.yourplatform.com \
    --output-dir ./workflows
```

```bash
python conway_generator.py web-to-workflow \
    --url https://corp.sap.com \
    --max-pages 500 \
    --concurrency 8 \
    --output-dir ./workflows
```

| Flag | Default | Description |
|---|---|---|
| `--url` | *(required)* | Base URL of domain to crawl |
| `--max-pages` | `200` | Maximum pages to process |
| `--concurrency` | `6` | Parallel fetch/generate workers |
| `--output-dir` | `./workflows` | Where to write workflow JSON files |
| `--api-key` | env var | Anthropic API key |

---

### webpage-to-workflow

Processes a single URL and extracts all workflows found on that page. The lightest-weight mode — useful for targeted extraction from a specific process guide, runbook, or help article.

```bash
python conway_generator.py webpage-to-workflow \
    --url https://help.yourplatform.com/submit-a-claim \
    --output-dir ./workflows
```

If the page doesn't appear to contain step-by-step workflows, the script warns and prompts for confirmation. Use `--force` to skip the check:

```bash
python conway_generator.py webpage-to-workflow \
    --url https://yourplatform.com/api-reference \
    --force \
    --output-dir ./workflows
```

| Flag | Default | Description |
|---|---|---|
| `--url` | *(required)* | URL of page to process |
| `--force` | off | Skip workflow-page heuristic check |
| `--output-dir` | `./workflows` | Where to write workflow JSON files |
| `--api-key` | env var | Anthropic API key |

---

### Conway Output Files

Each workflow is written as a separate JSON file, named from the workflow's name slug:

```
workflows/
├── submit_purchase_order_in_sap_ariba.json
├── create_vendor_account.json
├── file_expense_report.json
├── approve_invoice.json
└── manifest.json
```

Filename collisions (two workflows with the same slugged name) are resolved automatically with a numeric suffix: `submit_purchase_order_2.json`.

---

### The Manifest

Every run writes a `manifest.json` to the output directory. It records everything generated in that run — useful for inventory, auditing, and loading workflows into Tech Bro programmatically.

```json
{
  "generator": "conway_generator.py v2",
  "mode": "web-to-workflow",
  "source": "https://corp.sap.com",
  "started_at": "2026-02-27T18:30:00Z",
  "completed_at": "2026-02-27T18:47:23Z",
  "total_workflows": 34,
  "output_dir": "./workflows",
  "workflows": [
    {
      "file": "submit_purchase_order_in_sap_ariba.json",
      "workflow_id": "workflow-1740679823000",
      "name": "Submit Purchase Order in SAP Ariba",
      "description": "Creates and submits a new PO through the Ariba portal",
      "tags": ["procurement", "sap-ariba"],
      "step_count": 12,
      "step_types": ["navigate", "wait_for_load", "wait_for_human", "fill_form", "click", "screenshot", "conditional"],
      "source_url": "https://corp.sap.com/help/ariba/purchase-orders",
      "generated_at": "2026-02-27T18:34:11Z"
    }
  ]
}
```

---

## End-to-End Example

Preparing a hypothetical insurance platform for Tech Bro automation, from scratch.

**Step 1 — Generate bro pages from the live platform (logged in):**
```bash
python bro_generator.py web-to-bro \
    --url https://portal.insureco.com \
    --user-id 99001 \
    --username test@example.com \
    --password testpass \
    --max-pages 80 \
    --output-dir ./bro_output
```
Output: `bro_output/user_99001_bro_read.html`, `bro_output/user_99001_bro_write.html`

**Step 2 — Generate bro pages from the database schema:**
```bash
python bro_generator.py db-to-bro \
    --dsn postgresql://readonly:pass@db.insureco.com/prod \
    --user-table policyholders \
    --user-id-column policyholder_id \
    --output-dir ./bro_output
```
Output: bro_read and bro_write pages with full schema, FK graph, and action surface.

**Step 3 — Generate workflows from the help center:**
```bash
python conway_generator.py web-to-workflow \
    --url https://help.insureco.com \
    --max-pages 300 \
    --concurrency 8 \
    --output-dir ./workflows
```
Output: One JSON per process found, plus `manifest.json`.

**Step 4 — Generate workflows from a specific claims guide:**
```bash
python conway_generator.py webpage-to-workflow \
    --url https://help.insureco.com/how-to-file-a-claim \
    --output-dir ./workflows
```

**Step 5 — Generate workflows from an internal runbook:**
```bash
python conway_generator.py doc-to-workflow \
    --file "Claims Processing Runbook Q1 2026.pdf" \
    --output-dir ./workflows
```

At this point `./bro_output/` contains the platform-side infrastructure and `./workflows/` contains all the task automation JSON. Tech Bro can load either directly.

---

## Reference: Conway DSL Step Types

All step types recognized by Tech Bro's `WorkflowOrchestrator`:

| Type | Description | Key Fields |
|---|---|---|
| `navigate` | Go to a URL | `url`, `waitUntil`, `timeout` |
| `wait_for_load` | Wait for page or element | `selector` (optional), `timeout` |
| `find_element` | Locate an element | `selector`, `timeout` |
| `click` | Click an element | `selector`, `waitAfter`, `retries` |
| `fill_form` | Fill and optionally submit a form | `fields` (object), `submit`, `typingDelay` |
| `extract_data` | Read text from elements | `selectors` (object of key → CSS selector) |
| `wait_for_human` | Pause for user input or action | `prompt` (title, message, inputType), `targetSelector`, `autoFill`, `spotlight` |
| `conditional` | Branch on a condition | `condition`, `selector`, `if_true`, `if_false` |
| `loop` | Repeat steps over a list | `items` (template ref), `steps` |
| `screenshot` | Capture the page | `fullPage`, `tags`, `showInUI` |
| `scroll` | Scroll the page | `direction` (down/up/to_element), `pixels`, `selector` |
| `wait` | Pause for time | `seconds` |
| `check_element` | Test element existence | `selector`, `waitFor` |
| `hover` | Hover over an element | `selector` |

**Template syntax** — reference prior step results in any field value:
```json
"fields": {
  "#order-id": "{{extract_order.extracted.order_number.text}}",
  "#vendor":   "{{human_vendor_input.human_input.payload}}"
}
```

**Step metadata** — applies to all step types:
```json
{
  "critical": false,     // if false, failure is logged but workflow continues
  "retries": 3,          // retry attempts (click, fill_form, find_element)
  "retryDelay": 1000,    // ms between retries
  "timeout": 10000       // ms before timeout (navigate, wait_for_load, find_element)
}
```

**Selector priority** — `conway_generator.py` follows this order when writing selectors:
1. `[data-testid="submit-button"]`
2. `#stable-unique-id`
3. `.descriptive-semantic-class`
4. `button:has-text("Submit Order")`
5. `[aria-label="Close dialog"]`
6. `input[type="email"]`

Every `click`, `fill_form`, and `find_element` step also gets a `selectorAlternatives` array as fallback.

---

## Contributing

Both scripts are structured for readability and extension. `bro_generator.py` is organized into a `WebCrawler` class, a `DBInspector` class, and functional page builders. `conway_generator.py` is organized into labeled sections (DSL Knowledge Base, Claude Client, Validation, Document Readers, Web Utilities, Manifest, CLI).

Areas where contributions are especially welcome:

- Additional database driver support in `db-to-bro`
- Playwright-native login flows for SSO / OAuth platforms in `web-to-bro`
- Additional document formats (`.pptx`, `.xlsx`, `.html`) in `doc-to-workflow`
- Improved workflow-page heuristics for non-English documentation sites in `web-to-workflow`
- Unit tests for the Conway DSL validator and `fix_workflow` auto-correction logic

---

## License

MIT. See `LICENSE`.

---

*Tech Bro Two Step Protocol — bro_read + bro_write + Conway DSL*
