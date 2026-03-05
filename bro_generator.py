#!/usr/bin/env python3
"""
bro_generator.py — Tech Bro Two Step Protocol Generator
========================================================
Generates bro_read and bro_write HTML pages from five sources:

  web-to-bro        Crawl a live website (as a logged-in user) and infer the
                    entity data graph and available actions, then emit bro pages.

  db-to-bro         Inspect a database schema and emit bro pages wired to
                    the real tables/columns/foreign-keys found there.

  openapi-to-bro    Read an OpenAPI 3.x / Swagger 2.x spec (URL or local file)
                    and emit bro pages from its paths, schemas, and operations.

  odata-to-bro      Consume an OData $metadata document (SAP, Salesforce,
                    Dynamics, SharePoint, etc.) and emit bro pages from its
                    EntityTypes, NavigationProperties, and FunctionImports.

  graphql-to-bro    Introspect a GraphQL endpoint and emit bro pages from its
                    types, queries, mutations, and field descriptions.

Usage
-----
  # Web mode
  python bro_generator.py web-to-bro \\
      --url https://example.com \\
      --user-id 42 \\
      [--username admin --password secret] \\
      [--login-url https://example.com/login] \\
      [--max-pages 50] \\
      [--output-dir ./bro_output]

  # DB mode — SQLite
  python bro_generator.py db-to-bro \\
      --dsn sqlite:///myapp.db \\
      --user-table users \\
      [--user-id-column id] \\
      [--output-dir ./bro_output]

  # DB mode — Postgres / MySQL / MSSQL (SQLAlchemy DSN)
  python bro_generator.py db-to-bro \\
      --dsn postgresql://user:pass@host/dbname \\
      --user-table users \\
      [--output-dir ./bro_output]

  # OpenAPI mode — from URL
  python bro_generator.py openapi-to-bro \\
      --spec https://api.example.com/openapi.json \\
      --user-entity User \\
      [--base-url https://api.example.com] \\
      [--bearer-token sk-...] \\
      [--output-dir ./bro_output]

  # OpenAPI mode — from local file
  python bro_generator.py openapi-to-bro \\
      --spec ./openapi.yaml \\
      --user-entity Customer \\
      [--output-dir ./bro_output]

  # OData mode — SAP, Salesforce, Dynamics, SharePoint
  python bro_generator.py odata-to-bro \\
      --metadata-url https://services.odata.org/V4/Northwind/$metadata \\
      --user-entity Customers \\
      [--service-url https://services.odata.org/V4/Northwind/] \\
      [--bearer-token eyJ...] \\
      [--output-dir ./bro_output]

  # OData mode — local $metadata XML file
  python bro_generator.py odata-to-bro \\
      --metadata-url ./metadata.xml \\
      --user-entity Customer \\
      [--output-dir ./bro_output]

  # GraphQL mode — introspect live endpoint
  python bro_generator.py graphql-to-bro \\
      --endpoint https://api.example.com/graphql \\
      --user-type User \\
      [--bearer-token eyJ...] \\
      [--output-dir ./bro_output]

Dependencies
------------
  pip install requests beautifulsoup4 sqlalchemy pyyaml
  (playwright is optional but recommended for JS-heavy sites)
  pip install playwright && playwright install chromium
"""

import argparse
import json
import os
import sys
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse, urlencode
from collections import defaultdict
from typing import Optional, Any

# ---------------------------------------------------------------------------
# HTML rendering helpers
# ---------------------------------------------------------------------------

PAGE_CSS = """
body { font-family: monospace; font-size: 13px; max-width: 1100px;
       margin: 0 auto; padding: 20px; background: #f8f8f8; color: #222; }
h1   { font-size: 1.3em; border-bottom: 2px solid #333; padding-bottom: 6px; }
h2   { font-size: 1.1em; margin-top: 24px; border-bottom: 1px solid #aaa; }
h3   { font-size: 1em; margin: 14px 0 4px; }
.section { background: white; border: 1px solid #ddd; padding: 12px 16px;
           margin-bottom: 12px; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; padding: 4px 8px; border: 1px solid #ddd; font-size: 12px; }
th { background: #eee; }
form  { background: white; border: 1px solid #bbb; padding: 12px 16px;
        margin-bottom: 10px; }
label { display: inline-block; width: 200px; font-weight: bold; }
input, select, textarea { font-family: monospace; font-size: 12px;
                           padding: 3px 6px; border: 1px solid #ccc;
                           width: 320px; margin: 3px 0; }
button[type=submit] { margin-top: 8px; padding: 5px 14px;
                      background: #333; color: white; border: none;
                      cursor: pointer; font-family: monospace; }
.meta  { color: #777; font-size: 11px; margin-bottom: 16px; }
.badge { display: inline-block; background: #333; color: white;
         font-size: 10px; padding: 1px 6px; margin-left: 6px; }
"""

def html_page(title: str, body: str, meta: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
  <style>{PAGE_CSS}</style>
</head>
<body>
  <h1>{title}</h1>
  <div class="meta">{meta}</div>
  {body}
</body>
</html>"""

def kv_table(rows: list[tuple]) -> str:
    """Render a list of (key, value) tuples as an HTML table."""
    if not rows:
        return "<em>No data.</em>"
    cells = "\n".join(
        f"  <tr><th>{k}</th><td>{v}</td></tr>"
        for k, v in rows
    )
    return f"<table>\n{cells}\n</table>"

def data_table(headers: list[str], rows: list[list]) -> str:
    """Render a 2-D table."""
    if not rows:
        return "<em>No records.</em>"
    ths = "".join(f"<th>{h}</th>" for h in headers)
    trs = ""
    for row in rows:
        tds = "".join(f"<td>{c}</td>" for c in row)
        trs += f"<tr>{tds}</tr>\n"
    return f"<table><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table>"

def html_form(action: str, method: str, fields: list[dict], label: str) -> str:
    """
    fields: list of {"name": str, "type": str, "label": str, "required": bool}
    """
    inputs = ""
    for f in fields:
        ftype = f.get("type", "text")
        fname = f.get("name", "")
        flabel = f.get("label", fname)
        req = "required" if f.get("required") else ""
        if ftype == "textarea":
            inputs += (
                f'<div><label for="{fname}">{flabel}</label>'
                f'<textarea id="{fname}" name="{fname}" rows="3" {req}></textarea></div>\n'
            )
        elif ftype == "select" and "options" in f:
            opts = "".join(
                f'<option value="{o}">{o}</option>' for o in f["options"]
            )
            inputs += (
                f'<div><label for="{fname}">{flabel}</label>'
                f'<select id="{fname}" name="{fname}" {req}>{opts}</select></div>\n'
            )
        else:
            inputs += (
                f'<div><label for="{fname}">{flabel}</label>'
                f'<input id="{fname}" name="{fname}" type="{ftype}" {req}></div>\n'
            )
    return f"""<form action="{action}" method="{method}">
  <h3>{label}</h3>
  {inputs}
  <button type="submit">Submit</button>
</form>"""


# ---------------------------------------------------------------------------
# ██╗    ██╗███████╗██████╗      ████████╗ ██████╗      ██████╗ ██████╗  ██████╗
# ██║    ██║██╔════╝██╔══██╗        ██╔══╝██╔═══██╗     ██╔══██╗██╔══██╗██╔═══██╗
# ██║ █╗ ██║█████╗  ██████╔╝        ██║   ██║   ██║     ██████╔╝██████╔╝██║   ██║
# ██║███╗██║██╔══╝  ██╔══██╗        ██║   ██║   ██║     ██╔══██╗██╔══██╗██║   ██║
# ╚███╔███╔╝███████╗██████╔╝        ██║   ╚██████╔╝     ██████╔╝██║  ██║╚██████╔╝
#  ╚══╝╚══╝ ╚══════╝╚═════╝         ╚═╝    ╚═════╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝
# ---------------------------------------------------------------------------

class WebCrawler:
    """
    Crawls a website (optionally logging in first) and builds a structural
    model of:
      - data sections found on pages (for bro_read)
      - forms found on pages (for bro_write)
    """

    def __init__(
        self,
        base_url: str,
        user_id: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        login_url: Optional[str] = None,
        max_pages: int = 50,
        use_playwright: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.user_id = user_id
        self.username = username
        self.password = password
        self.login_url = login_url or urljoin(base_url, "/login")
        self.max_pages = max_pages
        self.use_playwright = use_playwright

        self.visited: set[str] = set()
        self.data_sections: list[dict] = []   # {page, heading, rows}
        self.forms_found: list[dict] = []      # {page, action, method, fields, label}

        self._session = None
        self._playwright_context = None

    # ------------------------------------------------------------------
    # Session setup
    # ------------------------------------------------------------------

    def _get_requests_session(self):
        try:
            import requests
            from requests import Session
        except ImportError:
            sys.exit("Install requests: pip install requests")

        session = Session()
        if self.username and self.password:
            print(f"[web] Attempting login at {self.login_url}")
            # 1. GET the login page to grab any CSRF token
            resp = session.get(self.login_url, timeout=15)
            soup = self._parse(resp.text)
            csrf = self._find_csrf(soup)
            payload = {
                "username": self.username,
                "password": self.password,
                "email": self.username,  # common alternative field name
            }
            if csrf:
                payload.update(csrf)
            # POST credentials
            session.post(self.login_url, data=payload, timeout=15)
            print("[web] Login submitted (session cookie preserved).")
        return session

    def _find_csrf(self, soup) -> dict:
        hidden = {}
        for inp in soup.find_all("input", {"type": "hidden"}):
            name = inp.get("name", "")
            if "csrf" in name.lower() or "token" in name.lower():
                hidden[name] = inp.get("value", "")
        return hidden

    def _fetch(self, url: str) -> Optional[str]:
        if self.use_playwright:
            return self._fetch_playwright(url)
        try:
            resp = self._session.get(url, timeout=15)
            if "text/html" not in resp.headers.get("content-type", ""):
                return None
            return resp.text
        except Exception as e:
            print(f"[web] Fetch error {url}: {e}")
            return None

    def _fetch_playwright(self, url: str) -> Optional[str]:
        try:
            return self._playwright_context.pages[0].goto(url) and \
                   self._playwright_context.pages[0].content()
        except Exception as e:
            print(f"[playwright] Fetch error {url}: {e}")
            return None

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse(html: str):
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            sys.exit("Install beautifulsoup4: pip install beautifulsoup4")
        return BeautifulSoup(html, "html.parser")

    def _is_same_domain(self, url: str) -> bool:
        return urlparse(url).netloc == urlparse(self.base_url).netloc

    def _normalize(self, url: str, current: str) -> Optional[str]:
        full = urljoin(current, url)
        parsed = urlparse(full)
        # Drop fragments, keep path + query
        return parsed._replace(fragment="").geturl()

    # ------------------------------------------------------------------
    # Data extraction
    # ------------------------------------------------------------------

    def _extract_data(self, url: str, soup) -> None:
        """Pull tables, definition lists, and labeled key-value sections."""
        page_label = urlparse(url).path or url

        # --- HTML tables ---
        for table in soup.find_all("table"):
            headers = [th.get_text(strip=True) for th in table.find_all("th")]
            rows = []
            for tr in table.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all("td")]
                if cells:
                    rows.append(cells)
            if rows:
                heading = self._nearest_heading(table) or "Table"
                self.data_sections.append({
                    "page": page_label,
                    "heading": heading,
                    "type": "table",
                    "headers": headers,
                    "rows": rows,
                })

        # --- Definition lists ---
        for dl in soup.find_all("dl"):
            pairs = []
            terms = dl.find_all("dt")
            defs  = dl.find_all("dd")
            for dt, dd in zip(terms, defs):
                pairs.append((dt.get_text(strip=True), dd.get_text(strip=True)))
            if pairs:
                heading = self._nearest_heading(dl) or "Details"
                self.data_sections.append({
                    "page": page_label,
                    "heading": heading,
                    "type": "kv",
                    "rows": pairs,
                })

        # --- Divs/sections with label:value patterns ---
        for section in soup.find_all(["section", "article", "div"], class_=re.compile(
            r"detail|profile|info|summary|card|field|stat", re.I
        )):
            pairs = []
            for label in section.find_all(["label", "span", "strong", "dt"]):
                text = label.get_text(strip=True).rstrip(":")
                sibling = label.find_next_sibling()
                if sibling:
                    value = sibling.get_text(strip=True)
                    if text and value and len(text) < 60:
                        pairs.append((text, value))
            if pairs:
                heading = self._nearest_heading(section) or section.get("class", ["Section"])[0]
                self.data_sections.append({
                    "page": page_label,
                    "heading": str(heading),
                    "type": "kv",
                    "rows": pairs,
                })

    def _extract_forms(self, url: str, soup) -> None:
        """Extract all non-login HTML forms as candidate write actions."""
        page_label = urlparse(url).path or url
        for form in soup.find_all("form"):
            action = form.get("action", url)
            method = (form.get("method", "POST")).upper()
            label  = (
                self._nearest_heading(form)
                or form.get("id")
                or form.get("name")
                or form.get("aria-label")
                or "Action"
            )
            # Skip obvious login forms
            if any(kw in str(label).lower() for kw in ("login", "sign in", "register", "signup")):
                continue

            fields = []
            for inp in form.find_all(["input", "select", "textarea"]):
                itype = inp.get("type", "text")
                if itype in ("hidden", "submit", "button", "reset", "image"):
                    continue
                name = inp.get("name") or inp.get("id") or ""
                flabel = self._field_label(form, inp) or name
                field = {
                    "name": name,
                    "type": inp.name if inp.name == "textarea" else (
                        "select" if inp.name == "select" else itype
                    ),
                    "label": flabel,
                    "required": inp.has_attr("required"),
                }
                if inp.name == "select":
                    field["options"] = [o.get_text(strip=True) for o in inp.find_all("option")]
                if name:
                    fields.append(field)

            if fields:
                self.forms_found.append({
                    "page": page_label,
                    "action": urljoin(url, action),
                    "method": method,
                    "label": str(label),
                    "fields": fields,
                })

    @staticmethod
    def _nearest_heading(tag) -> Optional[str]:
        """Walk backwards in siblings + ancestors to find the nearest heading."""
        for sibling in tag.previous_siblings:
            if hasattr(sibling, "name") and sibling.name in ("h1","h2","h3","h4","h5","h6"):
                return sibling.get_text(strip=True)
        for ancestor in tag.parents:
            for sibling in ancestor.previous_siblings:
                if hasattr(sibling, "name") and sibling.name in ("h1","h2","h3","h4","h5","h6"):
                    return sibling.get_text(strip=True)
            break
        return None

    @staticmethod
    def _field_label(form, inp) -> Optional[str]:
        inp_id = inp.get("id")
        if inp_id:
            lbl = form.find("label", {"for": inp_id})
            if lbl:
                return lbl.get_text(strip=True)
        placeholder = inp.get("placeholder")
        if placeholder:
            return placeholder
        aria = inp.get("aria-label")
        if aria:
            return aria
        return None

    # ------------------------------------------------------------------
    # Crawler loop
    # ------------------------------------------------------------------

    def crawl(self) -> None:
        if self.use_playwright:
            self._init_playwright()
        else:
            self._session = self._get_requests_session()

        queue = [self.base_url]
        print(f"[web] Starting crawl from {self.base_url} (max {self.max_pages} pages)")

        while queue and len(self.visited) < self.max_pages:
            url = queue.pop(0)
            if url in self.visited:
                continue
            self.visited.add(url)
            print(f"[web] Crawling ({len(self.visited)}/{self.max_pages}): {url}")

            html = self._fetch(url)
            if not html:
                continue

            soup = self._parse(html)
            self._extract_data(url, soup)
            self._extract_forms(url, soup)

            # Enqueue links
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                    continue
                full = self._normalize(href, url)
                if full and self._is_same_domain(full) and full not in self.visited:
                    queue.append(full)

        print(f"[web] Crawl complete. Pages: {len(self.visited)}, "
              f"data sections: {len(self.data_sections)}, forms: {len(self.forms_found)}")

    def _init_playwright(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            sys.exit("Install playwright: pip install playwright && playwright install chromium")
        pw = sync_playwright().__enter__()
        browser = pw.chromium.launch(headless=True)
        self._playwright_context = browser.new_context()
        if self.username and self.password:
            page = self._playwright_context.new_page()
            page.goto(self.login_url)
            try:
                page.fill('input[name="username"], input[name="email"]', self.username)
                page.fill('input[name="password"]', self.password)
                page.click('button[type="submit"], input[type="submit"]')
                page.wait_for_load_state("networkidle")
            except Exception as e:
                print(f"[playwright] Login automation failed: {e}")


# ---------------------------------------------------------------------------
# Web-to-Bro page generation
# ---------------------------------------------------------------------------

def build_bro_read_from_web(crawler: WebCrawler, user_id: str) -> str:
    body = ""

    # Group data sections by page
    by_page: dict[str, list] = defaultdict(list)
    for ds in crawler.data_sections:
        by_page[ds["page"]].append(ds)

    if not by_page:
        body += '<div class="section"><em>No structured data sections detected. '
        body += 'Try enabling --playwright for JS-heavy sites.</em></div>'
    else:
        for page_path, sections in sorted(by_page.items()):
            body += f'<div class="section"><h2>Source: <code>{page_path}</code></h2>\n'
            for sec in sections:
                body += f"<h3>{sec['heading']}</h3>\n"
                if sec["type"] == "table":
                    body += data_table(sec.get("headers", []), sec["rows"]) + "\n"
                else:
                    body += kv_table(sec["rows"]) + "\n"
            body += "</div>\n"

    # Crawl summary
    body += '<div class="section"><h2>Crawl Coverage</h2>\n'
    body += kv_table([
        ("Pages visited", len(crawler.visited)),
        ("Data sections extracted", len(crawler.data_sections)),
        ("Forms found", len(crawler.forms_found)),
        ("Source base URL", crawler.base_url),
    ])
    body += "\n<h3>Pages Crawled</h3>\n"
    body += "<ul>" + "".join(f"<li><code>{p}</code></li>" for p in sorted(crawler.visited)) + "</ul>"
    body += "</div>\n"

    return html_page(
        title=f"bro_read — User {user_id} (web)",
        body=body,
        meta=f"Generated {datetime.utcnow().isoformat()}Z | source: {crawler.base_url} | "
             f"canonical URL: /users/{user_id}/bro_read",
    )


def build_bro_write_from_web(crawler: WebCrawler, user_id: str) -> str:
    body = ""

    if not crawler.forms_found:
        body += '<div class="section"><em>No action forms detected during crawl.</em></div>'
    else:
        by_page: dict[str, list] = defaultdict(list)
        for f in crawler.forms_found:
            by_page[f["page"]].append(f)

        for page_path, forms in sorted(by_page.items()):
            body += f'<div class="section"><h2>Source: <code>{page_path}</code></h2>\n'
            for f in forms:
                body += html_form(
                    action=f["action"],
                    method=f["method"],
                    fields=f["fields"],
                    label=f['label'] + f'<span class="badge">{f["method"]}</span>',
                ) + "\n"
            body += "</div>\n"

    return html_page(
        title=f"bro_write — User {user_id} (web)",
        body=body,
        meta=f"Generated {datetime.utcnow().isoformat()}Z | source: {crawler.base_url} | "
             f"canonical URL: /users/{user_id}/bro_write",
    )


# ---------------------------------------------------------------------------
# ██████╗ ██████╗      ████████╗ ██████╗      ██████╗ ██████╗  ██████╗
# ██╔══██╗██╔══██╗        ██╔══╝██╔═══██╗     ██╔══██╗██╔══██╗██╔═══██╗
# ██║  ██║██████╔╝        ██║   ██║   ██║     ██████╔╝██████╔╝██║   ██║
# ██║  ██║██╔══██╗        ██║   ██║   ██║     ██╔══██╗██╔══██╗██║   ██║
# ██████╔╝██████╔╝        ██║   ╚██████╔╝     ██████╔╝██║  ██║╚██████╔╝
# ╚═════╝ ╚═════╝         ╚═╝    ╚═════╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝
# ---------------------------------------------------------------------------

class DBInspector:
    """
    Uses SQLAlchemy reflection to build a structural model of the DB schema,
    then generates bro pages from that model.
    """

    # Heuristic names for user / identity tables
    USER_TABLE_HINTS = {"users", "user", "accounts", "members", "customers", "person", "people"}

    # Column name patterns that suggest PII / profile data
    PROFILE_COLS = re.compile(
        r"(name|email|phone|address|birth|gender|zip|city|state|country|"
        r"locale|timezone|avatar|bio|username|handle|created|updated|verified)",
        re.I,
    )

    # Column patterns that suggest FK relationships
    FK_PATTERN = re.compile(r"_id$|^id_", re.I)

    def __init__(self, dsn: str, user_table: str, user_id_col: str = "id"):
        self.dsn = dsn
        self.user_table = user_table
        self.user_id_col = user_id_col
        self.engine = None
        self.metadata = None
        self.tables: dict = {}       # name -> Table
        self.fk_graph: dict = defaultdict(list)  # table -> [(fk_col, ref_table, ref_col)]
        self.reverse_fk: dict = defaultdict(list) # table -> [(child_table, fk_col)]

    def connect(self):
        try:
            from sqlalchemy import create_engine, MetaData
        except ImportError:
            sys.exit("Install sqlalchemy: pip install sqlalchemy")
        print(f"[db] Connecting to: {self.dsn}")
        self.engine = create_engine(self.dsn)
        self.metadata = MetaData()
        self.metadata.reflect(bind=self.engine)
        self.tables = dict(self.metadata.tables)
        print(f"[db] Reflected {len(self.tables)} tables: {', '.join(sorted(self.tables))}")
        self._build_fk_graph()

    def _build_fk_graph(self):
        for tname, table in self.tables.items():
            for fk in table.foreign_keys:
                ref_table = fk.column.table.name
                self.fk_graph[tname].append((fk.parent.name, ref_table, fk.column.name))
                self.reverse_fk[ref_table].append((tname, fk.parent.name))

    # ------------------------------------------------------------------
    # Schema model helpers
    # ------------------------------------------------------------------

    def _col_info(self, table) -> list[tuple]:
        """Return [(col_name, type_str, nullable, pk, fk_target)] for each column."""
        from sqlalchemy import inspect as sa_inspect
        rows = []
        fk_map = {fk.parent.name: f"{fk.column.table.name}.{fk.column.name}"
                  for fk in table.foreign_keys}
        for col in table.columns:
            rows.append((
                col.name,
                str(col.type),
                "NULL" if col.nullable else "NOT NULL",
                "PK" if col.primary_key else "",
                fk_map.get(col.name, ""),
            ))
        return rows

    def _find_user_related_tables(self) -> list[str]:
        """BFS from user_table through FK graph to find all related tables."""
        visited = {self.user_table}
        queue = [self.user_table]
        while queue:
            current = queue.pop(0)
            # child tables that reference current
            for child, _ in self.reverse_fk.get(current, []):
                if child not in visited:
                    visited.add(child)
                    queue.append(child)
        return sorted(visited)

    def _infer_write_actions(self) -> list[dict]:
        """
        Derive sensible CRUD actions from schema columns.
        Returns list of {label, table, action_type, fields}
        """
        actions = []

        def col_to_field(col, table_obj) -> Optional[dict]:
            # Skip PK, audit timestamps, and FK columns (they're set server-side)
            if col.primary_key:
                return None
            if col.name in ("created_at", "updated_at", "deleted_at",
                            "created", "updated", "modified"):
                return None
            fk_names = {fk.parent.name for fk in table_obj.foreign_keys}
            if col.name in fk_names:
                return None  # FK handled via URL routing, not form field
            type_str = str(col.type).upper()
            if "INT" in type_str or "NUMERIC" in type_str or "FLOAT" in type_str:
                ftype = "number"
            elif "BOOL" in type_str:
                ftype = "select"
                return {
                    "name": col.name,
                    "label": col.name.replace("_", " ").title(),
                    "type": "select",
                    "options": ["true", "false"],
                    "required": not col.nullable,
                }
            elif "TEXT" in type_str or "CLOB" in type_str:
                ftype = "textarea"
            elif "DATE" in type_str:
                ftype = "date"
            elif "TIME" in type_str:
                ftype = "datetime-local"
            else:
                ftype = "text"
            return {
                "name": col.name,
                "label": col.name.replace("_", " ").title(),
                "type": ftype,
                "required": not col.nullable,
            }

        related = self._find_user_related_tables()
        for tname in related:
            table = self.tables[tname]
            fields = [f for col in table.columns
                      if (f := col_to_field(col, table)) is not None]
            if not fields:
                continue

            id_col = next((c.name for c in table.columns if c.primary_key), "id")

            # UPDATE action
            actions.append({
                "label": f"Update {tname.replace('_', ' ').title()}",
                "table": tname,
                "action_type": "UPDATE",
                "action": f"/{tname}/{{{id_col}}}",
                "method": "POST",
                "fields": fields,
            })

            # CREATE action (for child tables owned by user)
            if tname != self.user_table:
                actions.append({
                    "label": f"Create New {tname.rstrip('s').replace('_', ' ').title()}",
                    "table": tname,
                    "action_type": "CREATE",
                    "action": f"/{tname}/new",
                    "method": "POST",
                    "fields": fields,
                })

            # DELETE action
            actions.append({
                "label": f"Delete {tname.rstrip('s').replace('_', ' ').title()}",
                "table": tname,
                "action_type": "DELETE",
                "action": f"/{tname}/{{{id_col}}}/delete",
                "method": "POST",
                "fields": [{"name": id_col, "label": id_col.upper(),
                             "type": "text", "required": True}],
            })

        return actions


# ---------------------------------------------------------------------------
# DB-to-Bro page generation
# ---------------------------------------------------------------------------

def build_bro_read_from_db(inspector: DBInspector, user_id: str) -> str:
    body = ""
    related = inspector._find_user_related_tables()

    # Section 1: Schema overview
    body += '<div class="section"><h2>Schema Overview</h2>\n'
    body += kv_table([
        ("Database", inspector.dsn.split("://")[0]),
        ("User table", inspector.user_table),
        ("User ID column", inspector.user_id_col),
        ("Total tables reflected", len(inspector.tables)),
        ("User-related tables", len(related)),
    ])
    body += "</div>\n"

    # Section 2: Each related table
    for tname in related:
        table = inspector.tables[tname]
        col_rows = inspector._col_info(table)
        fks = inspector.fk_graph.get(tname, [])
        rev_fks = inspector.reverse_fk.get(tname, [])

        body += f'<div class="section"><h2>Table: <code>{tname}</code>'
        if tname == inspector.user_table:
            body += ' <span class="badge">USER ROOT</span>'
        body += "</h2>\n"

        body += "<h3>Columns</h3>\n"
        body += data_table(
            ["Column", "Type", "Nullable", "PK", "Foreign Key"],
            col_rows,
        )

        if fks:
            body += "<h3>Foreign Keys (outbound)</h3>\n"
            body += data_table(
                ["Column", "References Table", "References Column"],
                [(f[0], f[1], f[2]) for f in fks],
            )

        if rev_fks:
            body += "<h3>Referenced By (inbound)</h3>\n"
            body += data_table(
                ["Child Table", "Via Column"],
                rev_fks,
            )

        body += f"<p>Canonical read URL: "
        body += f"<code>/{tname}/{{id}}/bro_read</code></p>\n"
        body += "</div>\n"

    # Section 3: bro_index — links to all entity bro_read pages
    body += '<div class="section"><h2>bro_index — Entity Graph Links</h2>\n'
    rows = []
    for tname in related:
        table = inspector.tables[tname]
        pk = next((c.name for c in table.columns if c.primary_key), "id")
        rows.append((tname, f"/{tname}/{{{pk}}}/bro_read"))
    body += data_table(["Entity Type", "Canonical bro_read URL"], rows)
    body += "</div>\n"

    # Section 4: Full FK relationship map
    body += '<div class="section"><h2>Full Relationship Map</h2>\n'
    all_fk_rows = []
    for tname in sorted(inspector.tables):
        for fk_col, ref_table, ref_col in inspector.fk_graph.get(tname, []):
            all_fk_rows.append((tname, fk_col, ref_table, ref_col))
    if all_fk_rows:
        body += data_table(["Table", "FK Column", "→ Table", "→ Column"], all_fk_rows)
    else:
        body += "<em>No explicit foreign keys detected.</em>"
    body += "</div>\n"

    return html_page(
        title=f"bro_read — User {user_id} (db schema)",
        body=body,
        meta=f"Generated {datetime.utcnow().isoformat()}Z | "
             f"db: {inspector.dsn.split('://')[0]} | "
             f"canonical URL: /users/{user_id}/bro_read",
    )


def build_bro_write_from_db(inspector: DBInspector, user_id: str) -> str:
    body = ""
    actions = inspector._infer_write_actions()

    if not actions:
        body += '<div class="section"><em>No writable actions inferred from schema.</em></div>'
    else:
        # Group by table
        by_table: dict[str, list] = defaultdict(list)
        for a in actions:
            by_table[a["table"]].append(a)

        for tname, tactions in sorted(by_table.items()):
            body += f'<div class="section"><h2>Entity: <code>{tname}</code></h2>\n'
            for a in tactions:
                badge_color = {"CREATE": "#2a7", "UPDATE": "#27a", "DELETE": "#a22"}.get(
                    a["action_type"], "#555"
                )
                label = (
                    f'{a["label"]}'
                    f'<span class="badge" style="background:{badge_color}">'
                    f'{a["action_type"]}</span>'
                )
                body += html_form(
                    action=a["action"],
                    method=a["method"],
                    fields=a["fields"],
                    label=label,
                ) + "\n"
            body += "</div>\n"

    # Summary
    body += '<div class="section"><h2>Action Surface Summary</h2>\n'
    type_counts = defaultdict(int)
    for a in actions:
        type_counts[a["action_type"]] += 1
    body += kv_table([(k, v) for k, v in sorted(type_counts.items())])
    body += f"<p>Total actions: {len(actions)}</p>"
    body += "</div>\n"

    return html_page(
        title=f"bro_write — User {user_id} (db schema)",
        body=body,
        meta=f"Generated {datetime.utcnow().isoformat()}Z | "
             f"db: {inspector.dsn.split('://')[0]} | "
             f"canonical URL: /users/{user_id}/bro_write",
    )


# ===========================================================================
#  ██████╗ ██████╗ ███████╗███╗   ██╗ █████╗ ██████╗ ██╗
# ██╔═══██╗██╔══██╗██╔════╝████╗  ██║██╔══██╗██╔══██╗██║
# ██║   ██║██████╔╝█████╗  ██╔██╗ ██║███████║██████╔╝██║
# ██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║██╔══██║██╔═══╝ ██║
# ╚██████╔╝██║     ███████╗██║ ╚████║██║  ██║██║     ██║
#  ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝     ╚═╝
# ===========================================================================

def _http_get(url: str, headers: Optional[dict] = None,
              timeout: int = 20) -> Optional[str]:
    """Simple authenticated GET — shared by all three API inspectors."""
    try:
        import requests
    except ImportError:
        sys.exit("pip install requests")
    try:
        resp = requests.get(url, headers=headers or {}, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"[fetch] {url}: {e}")
        return None


def _openapi_type_to_html(prop: dict) -> str:
    """Map an OpenAPI property schema to an HTML input type."""
    fmt  = prop.get("format", "")
    typ  = prop.get("type",   "string")
    if fmt in ("date",):             return "date"
    if fmt in ("date-time",):        return "datetime-local"
    if fmt in ("email",):            return "email"
    if fmt in ("uri", "url"):        return "url"
    if fmt in ("password",):         return "password"
    if typ in ("integer", "number"): return "number"
    if typ == "boolean":             return "select"
    if typ == "array":               return "textarea"  # JSON array
    if "description" in prop and len(prop.get("description", "")) > 120:
        return "textarea"
    return "text"


# ---------------------------------------------------------------------------
# OpenAPI Inspector
# ---------------------------------------------------------------------------

class OpenAPIInspector:
    """
    Parses an OpenAPI 3.x or Swagger 2.x specification (JSON or YAML,
    from a URL or local file) and builds a structural model of:
      - entity schemas relevant to the user  → bro_read
      - path operations (GET/POST/PUT/PATCH/DELETE) → bro_write
    """

    # Path segment patterns that suggest user-scoped resources
    USER_PATH_HINTS = re.compile(
        r"/(me|self|profile|account|user[s]?|member[s]?|customer[s]?)"
        r"(/|$|\{)", re.I
    )

    def __init__(self, spec_source: str, user_entity: str = "User",
                 base_url: Optional[str] = None,
                 bearer_token: Optional[str] = None):
        self.spec_source  = spec_source   # URL or file path
        self.user_entity  = user_entity   # e.g. "User", "Customer"
        self.base_url     = base_url
        self.bearer_token = bearer_token
        self.spec: dict   = {}
        self.version: str = "3"           # "2" = Swagger, "3" = OpenAPI

        # Populated by parse()
        self.entities: dict[str, dict]  = {}   # name → {description, properties}
        self.operations: list[dict]     = []   # each operation as action dict
        self.servers: list[str]         = []

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self) -> None:
        src = self.spec_source

        # Local file
        if not src.startswith("http"):
            path = Path(src)
            if not path.exists():
                sys.exit(f"Spec file not found: {src}")
            raw = path.read_text(encoding="utf-8")
            print(f"[openapi] Loaded from file: {path.name} ({len(raw):,} chars)")
        else:
            headers = {}
            if self.bearer_token:
                headers["Authorization"] = f"Bearer {self.bearer_token}"
            raw = _http_get(src, headers=headers)
            if not raw:
                sys.exit(f"Could not fetch spec from: {src}")
            print(f"[openapi] Fetched from URL: {src} ({len(raw):,} chars)")

        # Parse YAML or JSON
        if src.endswith((".yaml", ".yml")) or (
            raw.lstrip().startswith("openapi:") or raw.lstrip().startswith("swagger:")
        ):
            try:
                import yaml
                self.spec = yaml.safe_load(raw)
            except ImportError:
                sys.exit("pip install pyyaml")
        else:
            self.spec = json.loads(raw)

        self.version = "2" if "swagger" in self.spec else "3"
        print(f"[openapi] Spec version: {'OpenAPI 3.x' if self.version == '3' else 'Swagger 2.x'}")
        self._parse()

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse(self) -> None:
        self._extract_servers()
        self._extract_schemas()
        self._extract_operations()
        print(f"[openapi] Entities: {len(self.entities)}, "
              f"Operations: {len(self.operations)}, "
              f"Servers: {self.servers}")

    def _extract_servers(self) -> None:
        if self.base_url:
            self.servers = [self.base_url.rstrip("/")]
            return
        if self.version == "3":
            for s in self.spec.get("servers", []):
                url = s.get("url", "")
                if url:
                    self.servers.append(url.rstrip("/"))
        else:
            host   = self.spec.get("host", "")
            scheme = (self.spec.get("schemes") or ["https"])[0]
            base   = self.spec.get("basePath", "/")
            if host:
                self.servers.append(f"{scheme}://{host}{base}".rstrip("/"))

    def _resolve_ref(self, ref: str) -> dict:
        """Resolve a $ref pointer within the spec."""
        parts = ref.lstrip("#/").split("/")
        node = self.spec
        for p in parts:
            node = node.get(p, {})
        return node

    def _resolve_schema(self, schema: dict, depth: int = 0) -> dict:
        """Recursively resolve $ref and allOf/oneOf/anyOf."""
        if depth > 4:
            return schema
        if "$ref" in schema:
            schema = self._resolve_ref(schema["$ref"])
        merged = {}
        for combiner in ("allOf", "oneOf", "anyOf"):
            for sub in schema.get(combiner, []):
                merged.update(self._resolve_schema(sub, depth + 1))
        merged.update({k: v for k, v in schema.items()
                       if k not in ("allOf", "oneOf", "anyOf", "$ref")})
        return merged

    def _extract_schemas(self) -> None:
        """Pull all component schemas (or Swagger definitions)."""
        if self.version == "3":
            raw_schemas = self.spec.get("components", {}).get("schemas", {})
        else:
            raw_schemas = self.spec.get("definitions", {})

        for name, raw_schema in raw_schemas.items():
            schema = self._resolve_schema(raw_schema)
            props  = schema.get("properties", {})
            if not props:
                continue
            self.entities[name] = {
                "description": schema.get("description", ""),
                "properties": props,
                "required":   schema.get("required", []),
            }

    def _body_schema(self, operation: dict) -> Optional[dict]:
        """Extract the request body schema from an operation."""
        if self.version == "3":
            rb = operation.get("requestBody", {})
            content = rb.get("content", {})
            for mime in ("application/json", "application/x-www-form-urlencoded",
                         "multipart/form-data"):
                if mime in content:
                    s = content[mime].get("schema", {})
                    return self._resolve_schema(s)
            return None
        else:
            for param in operation.get("parameters", []):
                if param.get("in") == "body":
                    return self._resolve_schema(param.get("schema", {}))
            return None

    def _response_schema(self, operation: dict) -> Optional[dict]:
        """Extract the primary success response schema."""
        responses = operation.get("responses", {})
        for code in ("200", "201", "default"):
            resp = responses.get(code, {})
            if "$ref" in resp:
                resp = self._resolve_ref(resp["$ref"])
            if self.version == "3":
                content = resp.get("content", {})
                for mime in ("application/json",):
                    if mime in content:
                        s = content[mime].get("schema", {})
                        return self._resolve_schema(s)
            else:
                s = resp.get("schema", {})
                if s:
                    return self._resolve_schema(s)
        return None

    def _extract_operations(self) -> None:
        paths = self.spec.get("paths", {})
        for path, path_item in paths.items():
            if "$ref" in path_item:
                path_item = self._resolve_ref(path_item["$ref"])

            for method in ("get", "post", "put", "patch", "delete"):
                op = path_item.get(method)
                if not op:
                    continue

                op_id   = op.get("operationId", "")
                summary = op.get("summary", "") or op.get("description", "")
                tags    = op.get("tags", [])
                label   = summary or op_id or f"{method.upper()} {path}"

                # Determine action type
                action_type = {
                    "get":    "READ",
                    "post":   "CREATE",
                    "put":    "UPDATE",
                    "patch":  "UPDATE",
                    "delete": "DELETE",
                }.get(method, "ACTION")

                # Build fields from body schema or query/path params
                fields  = []
                b_schema = self._body_schema(op)
                if b_schema and b_schema.get("properties"):
                    required_fields = b_schema.get("required", [])
                    for prop_name, prop_schema in b_schema["properties"].items():
                        prop_schema = self._resolve_schema(prop_schema)
                        ftype = _openapi_type_to_html(prop_schema)
                        field: dict[str, Any] = {
                            "name":     prop_name,
                            "label":    prop_schema.get("title",
                                            prop_name.replace("_", " ").title()),
                            "type":     ftype,
                            "required": prop_name in required_fields,
                        }
                        if ftype == "select":
                            field["options"] = prop_schema.get("enum",
                                               ["true", "false"])
                        desc = prop_schema.get("description", "")
                        if desc:
                            field["description"] = desc
                        fields.append(field)
                else:
                    # Fall back to non-body parameters (query/path)
                    for param in op.get("parameters", []):
                        if param.get("in") in ("path", "query"):
                            pschema = self._resolve_schema(param.get("schema", {}))
                            field = {
                                "name":     param["name"],
                                "label":    param.get("description",
                                                param["name"].replace("_", " ").title()),
                                "type":     _openapi_type_to_html(pschema),
                                "required": param.get("required", False),
                            }
                            fields.append(field)

                # Determine entity grouping: use tag, or infer from path
                entity = tags[0] if tags else self._entity_from_path(path)

                # Determine if user-scoped
                user_scoped = bool(
                    self.USER_PATH_HINTS.search(path) or
                    entity.lower() == self.user_entity.lower() or
                    self.user_entity.lower() in path.lower()
                )

                server = self.servers[0] if self.servers else ""
                self.operations.append({
                    "label":       label,
                    "entity":      entity,
                    "path":        path,
                    "method":      method.upper(),
                    "action_type": action_type,
                    "action":      f"{server}{path}",
                    "fields":      fields,
                    "user_scoped": user_scoped,
                    "op_id":       op_id,
                    "tags":        tags,
                    "deprecated":  op.get("deprecated", False),
                    "response_schema": self._response_schema(op),
                })

    @staticmethod
    def _entity_from_path(path: str) -> str:
        """Infer entity name from URL path segment."""
        parts = [p for p in path.strip("/").split("/")
                 if p and not p.startswith("{")]
        if parts:
            return parts[-1].replace("-", "_").title()
        return "Root"

    # ------------------------------------------------------------------
    # bro_read model — entity schemas + user-scoped GET responses
    # ------------------------------------------------------------------

    def user_entity_info(self) -> dict:
        """
        Return schema info for the user entity and all related schemas
        referenced via GET operations on user-scoped paths.
        """
        result = {}

        # Direct schema match
        for name, entity in self.entities.items():
            if name.lower() == self.user_entity.lower():
                result[name] = entity

        # Entities returned by user-scoped GETs
        for op in self.operations:
            if op["action_type"] == "READ" and op["user_scoped"]:
                rs = op.get("response_schema")
                if rs:
                    # Unwrap array items
                    if rs.get("type") == "array" and "items" in rs:
                        rs = self._resolve_schema(rs["items"])
                    props = rs.get("properties", {})
                    if props:
                        entity_name = op["entity"]
                        if entity_name not in result:
                            result[entity_name] = {
                                "description": op["label"],
                                "properties": props,
                                "required": rs.get("required", []),
                                "from_path": op["path"],
                            }
        return result

    def write_operations(self) -> list[dict]:
        """Return all non-GET operations, optionally filtered to user scope."""
        return [op for op in self.operations
                if op["action_type"] != "READ" and not op["deprecated"]]

    def read_operations(self) -> list[dict]:
        return [op for op in self.operations
                if op["action_type"] == "READ" and not op["deprecated"]]


# ---------------------------------------------------------------------------
# OpenAPI bro page builders
# ---------------------------------------------------------------------------

def build_bro_read_from_openapi(inspector: OpenAPIInspector, user_id: str) -> str:
    body = ""
    spec_title  = (inspector.spec.get("info", {}).get("title")
                   or inspector.spec_source)
    spec_version = inspector.spec.get("info", {}).get("version", "")

    # Overview
    body += '<div class="section"><h2>API Overview</h2>\n'
    body += kv_table([
        ("Spec title",   spec_title),
        ("API version",  spec_version),
        ("Spec type",    "OpenAPI 3.x" if inspector.version == "3" else "Swagger 2.x"),
        ("User entity",  inspector.user_entity),
        ("Servers",      " · ".join(inspector.servers) or "(none declared)"),
        ("Total schemas",     len(inspector.entities)),
        ("Total operations",  len(inspector.operations)),
    ])
    body += "</div>\n"

    # Entity schemas relevant to user
    user_entities = inspector.user_entity_info()
    if user_entities:
        for ename, einfo in user_entities.items():
            desc = einfo.get("description", "") or einfo.get("from_path", "")
            body += f'<div class="section"><h2>Schema: <code>{ename}</code>'
            body += f' <span class="badge">USER ENTITY</span></h2>\n'
            if desc:
                body += f"<p>{desc}</p>\n"
            prop_rows = []
            required = set(einfo.get("required", []))
            for pname, pschema in einfo.get("properties", {}).items():
                pschema = inspector._resolve_schema(pschema)
                prop_rows.append([
                    pname,
                    pschema.get("type", ""),
                    pschema.get("format", ""),
                    "✓" if pname in required else "",
                    pschema.get("description", ""),
                ])
            if prop_rows:
                body += data_table(
                    ["Property", "Type", "Format", "Required", "Description"],
                    prop_rows,
                )
            body += "</div>\n"
    else:
        body += f'<div class="section"><em>No schema found for entity ' \
                f'"{inspector.user_entity}". Try --user-entity with a different name.</em></div>\n'

    # User-scoped GET endpoints
    reads = [op for op in inspector.read_operations() if op["user_scoped"]]
    if reads:
        body += '<div class="section"><h2>User-Scoped Read Endpoints</h2>\n'
        rows = []
        for op in reads:
            server = inspector.servers[0] if inspector.servers else ""
            rows.append([
                f"GET {op['path']}",
                op["label"],
                op["entity"],
                ", ".join(op["tags"]) or "—",
            ])
        body += data_table(["Endpoint", "Description", "Entity", "Tags"], rows)
        body += "</div>\n"

    # All schemas reference
    body += '<div class="section"><h2>All Schema Types</h2>\n'
    schema_rows = []
    for name, einfo in sorted(inspector.entities.items()):
        prop_count = len(einfo.get("properties", {}))
        schema_rows.append([name, str(prop_count),
                            einfo.get("description", "")[:80]])
    if schema_rows:
        body += data_table(["Schema", "Properties", "Description"], schema_rows)
    body += "</div>\n"

    return html_page(
        title=f"bro_read — {spec_title} / User {user_id}",
        body=body,
        meta=f"Generated {datetime.utcnow().isoformat()}Z | "
             f"source: {inspector.spec_source} | "
             f"canonical URL: /users/{user_id}/bro_read",
    )


def build_bro_write_from_openapi(inspector: OpenAPIInspector, user_id: str) -> str:
    body = ""
    ops  = inspector.write_operations()

    if not ops:
        body += '<div class="section"><em>No write operations found in spec.</em></div>\n'
    else:
        by_entity: dict[str, list] = defaultdict(list)
        for op in ops:
            by_entity[op["entity"]].append(op)

        for entity, entity_ops in sorted(by_entity.items()):
            body += f'<div class="section"><h2>Entity: <code>{entity}</code></h2>\n'
            for op in entity_ops:
                badge_color = {
                    "CREATE": "#2a7", "UPDATE": "#27a",
                    "DELETE": "#a22", "READ": "#555",
                }.get(op["action_type"], "#555")
                label = (
                    f'{op["label"]}'
                    f' <code style="font-size:10px;color:#555">'
                    f'{op["method"]} {op["path"]}</code>'
                    f'<span class="badge" style="background:{badge_color}">'
                    f'{op["action_type"]}</span>'
                )
                body += html_form(
                    action=op["action"],
                    method=op["method"],
                    fields=op["fields"],
                    label=label,
                ) + "\n"
            body += "</div>\n"

    # Summary
    body += '<div class="section"><h2>Action Surface Summary</h2>\n'
    type_counts: dict = defaultdict(int)
    method_counts: dict = defaultdict(int)
    for op in ops:
        type_counts[op["action_type"]] += 1
        method_counts[op["method"]] += 1
    body += "<h3>By Action Type</h3>\n"
    body += kv_table(list(type_counts.items()))
    body += "<h3>By HTTP Method</h3>\n"
    body += kv_table(list(method_counts.items()))
    body += f"<p>Total operations: {len(ops)}</p>\n"
    body += "</div>\n"

    spec_title = inspector.spec.get("info", {}).get("title", inspector.spec_source)
    return html_page(
        title=f"bro_write — {spec_title} / User {user_id}",
        body=body,
        meta=f"Generated {datetime.utcnow().isoformat()}Z | "
             f"source: {inspector.spec_source} | "
             f"canonical URL: /users/{user_id}/bro_write",
    )


# ===========================================================================
#  ██████╗ ██████╗  █████╗ ████████╗ █████╗
# ██╔═══██╗██╔══██╗██╔══██╗╚══██╔══╝██╔══██╗
# ██║   ██║██║  ██║███████║   ██║   ███████║
# ██║   ██║██║  ██║██╔══██║   ██║   ██╔══██║
# ╚██████╔╝██████╔╝██║  ██║   ██║   ██║  ██║
#  ╚═════╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝
# ===========================================================================

class ODataInspector:
    """
    Parses an OData $metadata CSDL document (XML) from a URL or local file.
    Supports OData v2, v3, and v4.

    Understands:
      - EntityType (properties, keys, navigation properties)
      - ComplexType (embedded value objects)
      - EntitySet / EntityContainer
      - FunctionImport / Action (OData v4 bound/unbound)
      - NavigationProperty relationships (bro_read entity graph)
      - Annotations (SAP-specific: sap:label, sap:visible, Core.Description)
    """

    CSDL_NS = {
        "edmx": "http://docs.oasis-open.org/odata/ns/edmx",
        "edm":  "http://docs.oasis-open.org/odata/ns/edm",
        # v2/v3 namespaces
        "edmx2": "http://schemas.microsoft.com/ado/2007/06/edmx",
        "edm2":  "http://schemas.microsoft.com/ado/2009/11/edm",
    }

    # OData primitive type → HTML input type
    TYPE_MAP = {
        "Edm.String":         "text",
        "Edm.Int16":          "number",
        "Edm.Int32":          "number",
        "Edm.Int64":          "number",
        "Edm.Decimal":        "number",
        "Edm.Double":         "number",
        "Edm.Single":         "number",
        "Edm.Boolean":        "select",
        "Edm.Date":           "date",
        "Edm.DateTime":       "datetime-local",
        "Edm.DateTimeOffset": "datetime-local",
        "Edm.TimeOfDay":      "time",
        "Edm.Duration":       "text",
        "Edm.Guid":           "text",
        "Edm.Binary":         "file",
        "Edm.Stream":         "file",
    }

    def __init__(self, metadata_source: str, user_entity: str,
                 service_url: Optional[str] = None,
                 bearer_token: Optional[str] = None):
        self.metadata_source = metadata_source
        self.user_entity     = user_entity
        self.service_url     = (service_url or "").rstrip("/")
        self.bearer_token    = bearer_token

        # Populated by parse()
        self.entity_types: dict[str, dict]   = {}  # name → {key, props, nav_props, ...}
        self.entity_sets:  dict[str, str]    = {}  # set_name → entity_type_name
        self.complex_types: dict[str, dict]  = {}  # name → {props}
        self.functions:    list[dict]        = []  # FunctionImports / Actions
        self.namespace:    str               = ""
        self.odata_version: str              = "4"
        self.raw_xml:      str               = ""

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self) -> None:
        src = self.metadata_source

        if not src.startswith("http"):
            path = Path(src)
            if not path.exists():
                sys.exit(f"Metadata file not found: {src}")
            self.raw_xml = path.read_text(encoding="utf-8")
            print(f"[odata] Loaded from file: {path.name} ({len(self.raw_xml):,} chars)")
        else:
            headers: dict = {"Accept": "application/xml"}
            if self.bearer_token:
                headers["Authorization"] = f"Bearer {self.bearer_token}"
            self.raw_xml = _http_get(src, headers=headers)
            if not self.raw_xml:
                sys.exit(f"Could not fetch $metadata from: {src}")
            print(f"[odata] Fetched $metadata: {src} ({len(self.raw_xml):,} chars)")

        self._parse()

    # ------------------------------------------------------------------
    # Parsing — namespace-agnostic via tag stripping
    # ------------------------------------------------------------------

    def _tag(self, elem) -> str:
        """Strip namespace from element tag."""
        t = elem.tag
        return t.split("}")[-1] if "}" in t else t

    def _attr(self, elem, *names: str) -> str:
        """Get first matching attribute (namespace-stripped)."""
        for name in names:
            if name in elem.attrib:
                return elem.attrib[name]
        return ""

    def _annotation_label(self, elem) -> str:
        """Extract SAP label or OData Core description from annotations."""
        for ann in elem.findall(".//{*}Annotation"):
            term = self._attr(ann, "Term")
            if term in ("SAP:label", "sap:label",
                        "Core.Description", "Org.OData.Core.V1.Description",
                        "Common.Label"):
                return self._attr(ann, "String") or ann.text or ""
        return ""

    def _parse(self) -> None:
        try:
            root = ET.fromstring(self.raw_xml)
        except ET.ParseError as e:
            sys.exit(f"[odata] XML parse error: {e}")

        # Detect version
        version_attr = self._attr(root, "Version")
        if version_attr.startswith("4"):
            self.odata_version = "4"
        elif version_attr.startswith("3"):
            self.odata_version = "3"
        else:
            self.odata_version = "2"

        # Walk all DataServices/Schema elements
        for schema in root.iter("{*}Schema"):
            ns = self._attr(schema, "Namespace")
            if ns and not self.namespace:
                self.namespace = ns

            # EntityType
            for et in schema.findall("{*}EntityType"):
                self._parse_entity_type(et, ns)

            # ComplexType
            for ct in schema.findall("{*}ComplexType"):
                self._parse_complex_type(ct, ns)

            # EntityContainer → EntitySet + FunctionImport/ActionImport
            for ec in schema.findall("{*}EntityContainer"):
                for es in ec.findall("{*}EntitySet"):
                    set_name  = self._attr(es, "Name")
                    type_name = self._attr(es, "EntityType").split(".")[-1]
                    self.entity_sets[set_name] = type_name

                for fi in ec.findall("{*}FunctionImport"):
                    self._parse_function(fi, "FunctionImport")
                for ai in ec.findall("{*}ActionImport"):
                    self._parse_function(ai, "ActionImport")

            # OData v4: unbound Actions/Functions
            for action in schema.findall("{*}Action"):
                self._parse_function(action, "Action")
            for func in schema.findall("{*}Function"):
                self._parse_function(func, "Function")

        print(f"[odata] Parsed: {len(self.entity_types)} entity types, "
              f"{len(self.entity_sets)} entity sets, "
              f"{len(self.functions)} functions/actions")

    def _parse_entity_type(self, et_elem, namespace: str) -> None:
        name = self._attr(et_elem, "Name")
        label = self._annotation_label(et_elem) or name

        # Key properties
        key_props = set()
        for kp in et_elem.findall(".//{*}PropertyRef"):
            key_props.add(self._attr(kp, "Name"))

        # Properties
        props = {}
        for prop in et_elem.findall("{*}Property"):
            pname   = self._attr(prop, "Name")
            ptype   = self._attr(prop, "Type")
            nullable = self._attr(prop, "Nullable").lower() != "false"
            plabel  = (self._annotation_label(prop)
                       or self._attr(prop, "sap:label")
                       or pname.replace("_", " ").title())
            max_len = self._attr(prop, "MaxLength")
            props[pname] = {
                "type":     ptype,
                "nullable": nullable,
                "label":    plabel,
                "is_key":   pname in key_props,
                "max_len":  max_len,
            }

        # Navigation Properties
        nav_props = {}
        for nav in et_elem.findall("{*}NavigationProperty"):
            nav_name = self._attr(nav, "Name")
            # v4: Type="Collection(Namespace.EntityType)"
            nav_type = self._attr(nav, "Type")
            # v2/v3: ToRole
            to_role = self._attr(nav, "ToRole")
            is_collection = "Collection(" in nav_type
            target_type = re.sub(r"Collection\(|\)", "", nav_type).split(".")[-1]
            nav_props[nav_name] = {
                "target_type": target_type or to_role,
                "is_collection": is_collection,
            }

        self.entity_types[name] = {
            "label":      label,
            "namespace":  namespace,
            "key_props":  key_props,
            "props":      props,
            "nav_props":  nav_props,
        }

    def _parse_complex_type(self, ct_elem, namespace: str) -> None:
        name  = self._attr(ct_elem, "Name")
        props = {}
        for prop in ct_elem.findall("{*}Property"):
            pname = self._attr(prop, "Name")
            props[pname] = {
                "type":  self._attr(prop, "Type"),
                "label": (self._annotation_label(prop)
                          or pname.replace("_", " ").title()),
            }
        self.complex_types[name] = {"props": props}

    def _parse_function(self, elem, kind: str) -> None:
        name       = self._attr(elem, "Name")
        entity_set = self._attr(elem, "EntitySet")
        http_method = self._attr(elem, "HttpMethod") or (
            "GET" if kind in ("Function", "FunctionImport") else "POST"
        )

        params = []
        for p in elem.findall("{*}Parameter"):
            pname = self._attr(p, "Name")
            ptype = self._attr(p, "Type")
            params.append({
                "name":     pname,
                "type":     ptype,
                "html_type": self.TYPE_MAP.get(ptype, "text"),
                "label":    pname.replace("_", " ").title(),
                "required": self._attr(p, "Nullable").lower() == "false",
            })

        # Build action URL
        if self.service_url:
            action_url = f"{self.service_url}/{name}"
        else:
            action_url = f"/{name}"

        self.functions.append({
            "name":        name,
            "kind":        kind,
            "entity_set":  entity_set,
            "method":      http_method,
            "action_url":  action_url,
            "params":      params,
            "label":       name.replace("_", " ").replace("Get", "Get ").title(),
        })

    # ------------------------------------------------------------------
    # Entity graph helpers
    # ------------------------------------------------------------------

    def _find_user_related(self) -> list[str]:
        """
        BFS from user_entity through navigation properties.
        Returns ordered list: user entity first, then navigable entities.
        """
        ue = self.user_entity
        # Fuzzy match: case-insensitive, also try set name → type name
        candidate = None
        for name in self.entity_types:
            if name.lower() == ue.lower():
                candidate = name
                break
        if not candidate:
            for set_name, type_name in self.entity_sets.items():
                if set_name.lower() == ue.lower():
                    candidate = type_name
                    break
        if not candidate:
            # Use closest match
            for name in self.entity_types:
                if ue.lower() in name.lower() or name.lower() in ue.lower():
                    candidate = name
                    break
        if not candidate:
            print(f"[odata] Warning: user entity '{ue}' not found. "
                  f"Available: {', '.join(list(self.entity_types)[:10])}")
            return list(self.entity_types.keys())[:5]

        visited = {candidate}
        queue   = [candidate]
        while queue:
            current = queue.pop(0)
            et = self.entity_types.get(current, {})
            for nav_name, nav_info in et.get("nav_props", {}).items():
                target = nav_info["target_type"]
                if target and target in self.entity_types and target not in visited:
                    visited.add(target)
                    queue.append(target)

        rest = sorted(visited - {candidate})
        return [candidate] + rest

    def _entity_set_for_type(self, type_name: str) -> Optional[str]:
        for set_name, tname in self.entity_sets.items():
            if tname == type_name:
                return set_name
        return None

    def _entity_read_url(self, type_name: str) -> str:
        entity_set = self._entity_set_for_type(type_name) or type_name
        if self.service_url:
            return f"{self.service_url}/{entity_set}({{key}})"
        return f"/{entity_set}({{key}})"

    def _props_to_fields(self, et_info: dict,
                          skip_key: bool = True) -> list[dict]:
        """Convert OData property definitions to bro form fields."""
        fields = []
        for pname, pinfo in et_info.get("props", {}).items():
            if skip_key and pinfo.get("is_key"):
                continue
            ptype    = pinfo["type"]
            html_type = self.TYPE_MAP.get(ptype, "text")
            field: dict[str, Any] = {
                "name":     pname,
                "label":    pinfo["label"],
                "type":     html_type,
                "required": not pinfo["nullable"],
            }
            if html_type == "select":
                field["options"] = ["true", "false"]
            fields.append(field)
        return fields


# ---------------------------------------------------------------------------
# OData bro page builders
# ---------------------------------------------------------------------------

def build_bro_read_from_odata(inspector: ODataInspector, user_id: str) -> str:
    body = ""
    related = inspector._find_user_related()

    # Overview
    src_label = (inspector.metadata_source.split("?")[0]
                 .replace("/$metadata", ""))
    body += '<div class="section"><h2>OData Service Overview</h2>\n'
    body += kv_table([
        ("Service URL",     inspector.service_url or "(not provided)"),
        ("OData version",   inspector.odata_version),
        ("Namespace",       inspector.namespace),
        ("User entity",     inspector.user_entity),
        ("Entity types",    len(inspector.entity_types)),
        ("Entity sets",     len(inspector.entity_sets)),
        ("Functions/Actions", len(inspector.functions)),
    ])
    body += "</div>\n"

    # User entity + navigable entities
    for etype_name in related:
        et = inspector.entity_types.get(etype_name)
        if not et:
            continue
        entity_set = inspector._entity_set_for_type(etype_name) or etype_name
        read_url   = inspector._entity_read_url(etype_name)

        is_root = (etype_name == related[0])
        badge   = ' <span class="badge">USER ROOT</span>' if is_root else ""
        body += f'<div class="section"><h2>EntityType: <code>{etype_name}</code>{badge}</h2>\n'
        if et["label"] != etype_name:
            body += f'<p><em>{et["label"]}</em></p>\n'

        # Key properties
        body += f'<p>Key: <code>{", ".join(et["key_props"]) or "(none)"}</code> &nbsp; '
        body += f'EntitySet: <code>{entity_set}</code> &nbsp; '
        body += f'Read URL: <code>{read_url}</code></p>\n'

        # Properties table
        prop_rows = []
        for pname, pinfo in et["props"].items():
            prop_rows.append([
                pname,
                pinfo["type"],
                pinfo["label"],
                "KEY" if pinfo["is_key"] else "",
                "" if pinfo["nullable"] else "NOT NULL",
                pinfo.get("max_len", ""),
            ])
        if prop_rows:
            body += data_table(
                ["Property", "OData Type", "Label", "Key", "Nullable", "MaxLen"],
                prop_rows,
            )

        # Navigation Properties
        if et["nav_props"]:
            body += "<h3>Navigation Properties</h3>\n"
            nav_rows = []
            for nav_name, nav_info in et["nav_props"].items():
                collection = "Collection" if nav_info["is_collection"] else "Single"
                nav_rows.append([nav_name, nav_info["target_type"], collection])
            body += data_table(["Property", "Target Entity Type", "Multiplicity"],
                               nav_rows)
        body += "</div>\n"

    # Entity Set index
    body += '<div class="section"><h2>Entity Set Index (bro_index)</h2>\n'
    set_rows = []
    for etype_name in related:
        entity_set = inspector._entity_set_for_type(etype_name) or etype_name
        read_url   = inspector._entity_read_url(etype_name)
        set_rows.append([etype_name, entity_set, read_url])
    body += data_table(["Entity Type", "EntitySet", "Read URL Pattern"], set_rows)
    body += "</div>\n"

    # Functions available (read-side)
    read_funcs = [f for f in inspector.functions
                  if f["method"] == "GET" or f["kind"] == "Function"]
    if read_funcs:
        body += '<div class="section"><h2>Functions (Read Operations)</h2>\n'
        func_rows = [[f["name"], f["kind"], f["method"],
                      f["action_url"], str(len(f["params"]))]
                     for f in read_funcs]
        body += data_table(["Name", "Kind", "HTTP Method", "URL", "Params"], func_rows)
        body += "</div>\n"

    return html_page(
        title=f"bro_read — OData / User {user_id}",
        body=body,
        meta=f"Generated {datetime.utcnow().isoformat()}Z | "
             f"OData v{inspector.odata_version} | "
             f"namespace: {inspector.namespace} | "
             f"canonical URL: /users/{user_id}/bro_read",
    )


def build_bro_write_from_odata(inspector: ODataInspector, user_id: str) -> str:
    body = ""
    related = inspector._find_user_related()
    actions = []

    # CRUD actions from entity types
    for etype_name in related:
        et = inspector.entity_types.get(etype_name)
        if not et:
            continue
        entity_set = inspector._entity_set_for_type(etype_name) or etype_name
        fields_no_key  = inspector._props_to_fields(et, skip_key=True)
        fields_key_only = [
            {"name": p, "label": p.upper(), "type": "text", "required": True}
            for p in et["key_props"]
        ]
        service = inspector.service_url or ""

        if fields_no_key:
            # CREATE
            actions.append({
                "label":       f"Create {etype_name}",
                "entity":      etype_name,
                "action_type": "CREATE",
                "action":      f"{service}/{entity_set}",
                "method":      "POST",
                "fields":      fields_no_key,
            })
            # UPDATE (PATCH is OData standard for partial updates)
            actions.append({
                "label":       f"Update {etype_name}",
                "entity":      etype_name,
                "action_type": "UPDATE",
                "action":      f"{service}/{entity_set}({{key}})",
                "method":      "PATCH",
                "fields":      fields_key_only + fields_no_key,
            })

        # DELETE
        actions.append({
            "label":       f"Delete {etype_name}",
            "entity":      etype_name,
            "action_type": "DELETE",
            "action":      f"{service}/{entity_set}({{key}})",
            "method":      "DELETE",
            "fields":      fields_key_only,
        })

    # FunctionImports / Actions (write-side)
    write_funcs = [f for f in inspector.functions
                   if f["method"] != "GET" and f["kind"] != "Function"]
    for func in write_funcs:
        fields = [
            {"name": p["name"], "label": p["label"],
             "type": p["html_type"], "required": p["required"]}
            for p in func["params"]
        ]
        actions.append({
            "label":       func["label"],
            "entity":      func.get("entity_set") or "Service Actions",
            "action_type": "ACTION",
            "action":      func["action_url"],
            "method":      func["method"],
            "fields":      fields,
        })

    if not actions:
        body += '<div class="section"><em>No write actions inferred.</em></div>\n'
    else:
        by_entity: dict[str, list] = defaultdict(list)
        for a in actions:
            by_entity[a["entity"]].append(a)

        for entity, entity_actions in sorted(by_entity.items()):
            body += f'<div class="section"><h2>Entity: <code>{entity}</code></h2>\n'
            for a in entity_actions:
                badge_color = {
                    "CREATE": "#2a7", "UPDATE": "#27a",
                    "DELETE": "#a22", "ACTION": "#555",
                }.get(a["action_type"], "#555")
                label = (
                    f'{a["label"]}'
                    f' <code style="font-size:10px;color:#555">'
                    f'{a["method"]}</code>'
                    f'<span class="badge" style="background:{badge_color}">'
                    f'{a["action_type"]}</span>'
                )
                body += html_form(
                    action=a["action"], method=a["method"],
                    fields=a["fields"], label=label,
                ) + "\n"
            body += "</div>\n"

    # Summary
    body += '<div class="section"><h2>Action Surface Summary</h2>\n'
    type_counts: dict = defaultdict(int)
    for a in actions:
        type_counts[a["action_type"]] += 1
    body += kv_table(list(type_counts.items()))
    body += f"<p>Total actions: {len(actions)}</p>\n"
    body += "</div>\n"

    return html_page(
        title=f"bro_write — OData / User {user_id}",
        body=body,
        meta=f"Generated {datetime.utcnow().isoformat()}Z | "
             f"OData v{inspector.odata_version} | "
             f"namespace: {inspector.namespace} | "
             f"canonical URL: /users/{user_id}/bro_write",
    )


# ===========================================================================
#  ██████╗ ██████╗  █████╗ ██████╗ ██╗  ██╗ ██████╗ ██╗
# ██╔════╝ ██╔══██╗██╔══██╗██╔══██╗██║  ██║██╔═══██╗██║
# ██║  ███╗██████╔╝███████║██████╔╝███████║██║   ██║██║
# ██║   ██║██╔══██╗██╔══██║██╔═══╝ ██╔══██║██║▄▄ ██║██║
# ╚██████╔╝██║  ██║██║  ██║██║     ██║  ██║╚██████╔╝███████╗
#  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝ ╚══▀▀═╝ ╚══════╝
# ===========================================================================

# Full introspection query — retrieves complete schema
INTROSPECTION_QUERY = """
query IntrospectionQuery {
  __schema {
    queryType    { name }
    mutationType { name }
    subscriptionType { name }
    types {
      ...FullType
    }
    directives {
      name
      description
      locations
    }
  }
}

fragment FullType on __Type {
  kind
  name
  description
  fields(includeDeprecated: false) {
    name
    description
    args { ...InputValue }
    type { ...TypeRef }
    isDeprecated
    deprecationReason
  }
  inputFields { ...InputValue }
  interfaces { ...TypeRef }
  enumValues(includeDeprecated: false) { name description }
  possibleTypes { ...TypeRef }
}

fragment InputValue on __InputValue {
  name
  description
  type { ...TypeRef }
  defaultValue
}

fragment TypeRef on __Type {
  kind name
  ofType { kind name ofType { kind name ofType { kind name } } }
}
"""


class GraphQLInspector:
    """
    Introspects a live GraphQL endpoint to build the full type system,
    then maps it to bro_read (Query fields) and bro_write (Mutation fields).

    Handles:
      - Query / Mutation / Subscription roots
      - Object types with nested field resolution
      - Input types with full field mapping
      - Enum types (→ HTML select options)
      - NonNull / List wrappers unwrapped recursively
      - Deprecation filtering
      - User-type identification by name heuristic
    """

    # GraphQL scalar → HTML input type
    SCALAR_MAP = {
        "String":    "text",
        "ID":        "text",
        "Int":       "number",
        "Float":     "number",
        "Boolean":   "select",
        "Date":      "date",
        "DateTime":  "datetime-local",
        "Time":      "time",
        "Email":     "email",
        "URL":       "url",
        "URI":       "url",
        "JSON":      "textarea",
        "Upload":    "file",
    }

    def __init__(self, endpoint: str, user_type: str = "User",
                 bearer_token: Optional[str] = None,
                 extra_headers: Optional[dict] = None):
        self.endpoint     = endpoint.rstrip("/")
        self.user_type    = user_type
        self.bearer_token = bearer_token
        self.headers: dict = {"Content-Type": "application/json",
                               "Accept": "application/json"}
        if bearer_token:
            self.headers["Authorization"] = f"Bearer {bearer_token}"
        if extra_headers:
            self.headers.update(extra_headers)

        # Populated by introspect()
        self.schema: dict      = {}
        self.types:  dict      = {}   # name → type dict
        self.query_type:    str = ""
        self.mutation_type: str = ""
        self.subscription_type: str = ""

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def introspect(self) -> None:
        print(f"[graphql] Introspecting: {self.endpoint}")
        try:
            import requests
        except ImportError:
            sys.exit("pip install requests")

        resp = requests.post(
            self.endpoint,
            headers=self.headers,
            json={"query": INTROSPECTION_QUERY},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        if "errors" in data:
            print(f"[graphql] Introspection errors: {data['errors']}")

        self.schema = data.get("data", {}).get("__schema", {})
        if not self.schema:
            sys.exit("[graphql] Empty schema returned — "
                     "introspection may be disabled on this endpoint.")

        # Index all types by name
        for t in self.schema.get("types", []):
            name = t.get("name", "")
            if name and not name.startswith("__"):
                self.types[name] = t

        self.query_type        = (self.schema.get("queryType")        or {}).get("name", "Query")
        self.mutation_type     = (self.schema.get("mutationType")     or {}).get("name", "")
        self.subscription_type = (self.schema.get("subscriptionType") or {}).get("name", "")

        print(f"[graphql] Schema loaded: {len(self.types)} types | "
              f"Query: {self.query_type} | "
              f"Mutation: {self.mutation_type or '(none)'}")

    # ------------------------------------------------------------------
    # Type system helpers
    # ------------------------------------------------------------------

    def _unwrap_type(self, type_ref: dict) -> tuple[str, str]:
        """
        Recursively unwrap NonNull / List wrappers.
        Returns (base_type_name, kind).
        """
        if not type_ref:
            return ("", "SCALAR")
        kind = type_ref.get("kind", "")
        name = type_ref.get("name", "")
        if kind in ("NON_NULL", "LIST"):
            return self._unwrap_type(type_ref.get("ofType", {}))
        return (name or "", kind)

    def _type_label(self, type_ref: dict) -> str:
        """Human-readable type string, e.g. '[User!]!'."""
        if not type_ref:
            return ""
        kind = type_ref.get("kind", "")
        name = type_ref.get("name", "")
        inner = type_ref.get("ofType")
        if kind == "NON_NULL":
            return f"{self._type_label(inner)}!"
        if kind == "LIST":
            return f"[{self._type_label(inner)}]"
        return name or kind

    def _html_type_for_field(self, field: dict) -> tuple[str, list[str]]:
        """
        Return (html_input_type, enum_options).
        enum_options is non-empty only for ENUM types.
        """
        base_name, kind = self._unwrap_type(field.get("type", {}))
        if kind == "ENUM":
            type_def = self.types.get(base_name, {})
            options  = [ev["name"] for ev in (type_def.get("enumValues") or [])]
            return ("select", options)
        if kind == "OBJECT":
            return ("textarea", [])  # JSON for nested objects
        html_type = self.SCALAR_MAP.get(base_name, "text")
        return (html_type, [])

    def _input_type_fields(self, input_type_name: str,
                            depth: int = 0) -> list[dict]:
        """
        Flatten an INPUT_OBJECT type into bro form fields.
        Recursively inlines nested input types up to depth 2.
        """
        if depth > 2:
            return []
        type_def = self.types.get(input_type_name, {})
        fields = []
        for f in (type_def.get("inputFields") or []):
            fname   = f["name"]
            fdesc   = f.get("description", "") or ""
            base, kind = self._unwrap_type(f.get("type", {}))
            is_required = f.get("type", {}).get("kind") == "NON_NULL"

            if kind == "INPUT_OBJECT" and depth < 2:
                # Inline nested input as prefixed fields
                sub_fields = self._input_type_fields(base, depth + 1)
                for sf in sub_fields:
                    sf["name"]  = f"{fname}.{sf['name']}"
                    sf["label"] = f"{fname.title()}: {sf['label']}"
                fields.extend(sub_fields)
            elif kind == "ENUM":
                type_def_enum = self.types.get(base, {})
                options = [ev["name"] for ev in (type_def_enum.get("enumValues") or [])]
                fields.append({
                    "name": fname, "label": fdesc or fname.replace("_", " ").title(),
                    "type": "select", "options": options, "required": is_required,
                })
            else:
                html_type = self.SCALAR_MAP.get(base, "text")
                fields.append({
                    "name": fname, "label": fdesc or fname.replace("_", " ").title(),
                    "type": html_type, "required": is_required,
                })
        return fields

    # ------------------------------------------------------------------
    # Query → bro_read model
    # ------------------------------------------------------------------

    def query_fields(self) -> list[dict]:
        """Return all fields on the Query root type."""
        qt = self.types.get(self.query_type, {})
        return qt.get("fields") or []

    def user_related_types(self) -> dict[str, dict]:
        """
        Return a dict of type_name → type_def for the user type
        and all types reachable from it via non-scalar fields.
        BFS up to depth 3 to avoid exploding on large schemas.
        """
        result = {}
        ut = self.user_type

        # Find user type (case-insensitive)
        root_name = None
        for name in self.types:
            if name.lower() == ut.lower():
                root_name = name
                break
        if not root_name:
            # Fuzzy: find type whose name contains the user_type string
            for name in self.types:
                if ut.lower() in name.lower():
                    root_name = name
                    break
        if not root_name:
            print(f"[graphql] Warning: type '{ut}' not found. "
                  f"Available: {', '.join(list(self.types)[:12])}")
            return {}

        visited: set = set()
        queue = [(root_name, 0)]
        while queue:
            tname, depth = queue.pop(0)
            if tname in visited or depth > 3:
                continue
            visited.add(tname)
            tdef = self.types.get(tname)
            if not tdef or tdef.get("kind") not in ("OBJECT", "INTERFACE"):
                continue
            result[tname] = tdef
            for field in (tdef.get("fields") or []):
                base, kind = self._unwrap_type(field.get("type", {}))
                if kind == "OBJECT" and base not in visited:
                    queue.append((base, depth + 1))

        return result

    def mutation_fields(self) -> list[dict]:
        """Return all fields on the Mutation root type."""
        if not self.mutation_type:
            return []
        mt = self.types.get(self.mutation_type, {})
        return mt.get("fields") or []

    def _mutation_to_action(self, field: dict) -> dict:
        """Convert a Mutation field to a bro write action."""
        fname = field["name"]
        fdesc = field.get("description", "") or fname
        args  = field.get("args", []) or []

        form_fields = []
        for arg in args:
            aname   = arg["name"]
            adesc   = arg.get("description", "") or aname.replace("_", " ").title()
            base, kind = self._unwrap_type(arg.get("type", {}))
            is_req  = arg.get("type", {}).get("kind") == "NON_NULL"

            if kind == "INPUT_OBJECT":
                inlined = self._input_type_fields(base)
                for f in inlined:
                    f["name"]  = f"{aname}.{f['name']}"
                form_fields.extend(inlined)
            elif kind == "ENUM":
                tdef = self.types.get(base, {})
                opts = [ev["name"] for ev in (tdef.get("enumValues") or [])]
                form_fields.append({
                    "name": aname, "label": adesc,
                    "type": "select", "options": opts, "required": is_req,
                })
            else:
                html_type = self.SCALAR_MAP.get(base, "text")
                form_fields.append({
                    "name": aname, "label": adesc,
                    "type": html_type, "required": is_req,
                })

        # Infer action type from field name convention
        fname_lower = fname.lower()
        if any(kw in fname_lower for kw in ("create", "add", "register", "signup", "insert")):
            action_type = "CREATE"
        elif any(kw in fname_lower for kw in ("update", "edit", "set", "change", "patch")):
            action_type = "UPDATE"
        elif any(kw in fname_lower for kw in ("delete", "remove", "destroy", "archive")):
            action_type = "DELETE"
        else:
            action_type = "MUTATION"

        return {
            "label":       fdesc,
            "mutation":    fname,
            "action_type": action_type,
            "action":      self.endpoint,
            "method":      "POST",
            "fields":      form_fields,
            "description": field.get("description", ""),
        }


# ---------------------------------------------------------------------------
# GraphQL bro page builders
# ---------------------------------------------------------------------------

def build_bro_read_from_graphql(inspector: GraphQLInspector, user_id: str) -> str:
    body = ""

    # Overview
    body += '<div class="section"><h2>GraphQL Schema Overview</h2>\n'
    body += kv_table([
        ("Endpoint",          inspector.endpoint),
        ("User type",         inspector.user_type),
        ("Query root",        inspector.query_type),
        ("Mutation root",     inspector.mutation_type or "(none)"),
        ("Total types",       len(inspector.types)),
        ("Query fields",      len(inspector.query_fields())),
        ("Mutation fields",   len(inspector.mutation_fields())),
    ])
    body += "</div>\n"

    # User type and related types
    related = inspector.user_related_types()
    if not related:
        body += (f'<div class="section"><em>Type "{inspector.user_type}" not found. '
                 f'Try --user-type with one of: '
                 f'{", ".join(list(inspector.types)[:10])}</em></div>\n')
    else:
        for tname, tdef in related.items():
            is_root = tname.lower() == inspector.user_type.lower()
            badge   = ' <span class="badge">USER TYPE</span>' if is_root else ""
            desc    = tdef.get("description", "") or ""
            body += f'<div class="section"><h2>Type: <code>{tname}</code>{badge}</h2>\n'
            if desc:
                body += f'<p>{desc}</p>\n'

            field_rows = []
            for f in (tdef.get("fields") or []):
                base_name, kind = inspector._unwrap_type(f.get("type", {}))
                type_label      = inspector._type_label(f.get("type", {}))
                fdesc           = f.get("description", "") or ""
                field_rows.append([
                    f["name"],
                    type_label,
                    kind,
                    fdesc[:80],
                ])
            if field_rows:
                body += data_table(
                    ["Field", "Type", "Kind", "Description"], field_rows
                )
            body += "</div>\n"

    # User-relevant Query fields
    user_queries = []
    for qf in inspector.query_fields():
        base, _ = inspector._unwrap_type(qf.get("type", {}))
        if (base in related or
                inspector.user_type.lower() in qf["name"].lower() or
                inspector.user_type.lower() in base.lower()):
            user_queries.append(qf)

    if user_queries:
        body += '<div class="section"><h2>User-Relevant Queries</h2>\n'
        q_rows = []
        for qf in user_queries:
            type_label = inspector._type_label(qf.get("type", {}))
            args_str   = ", ".join(a["name"] for a in (qf.get("args") or []))
            q_rows.append([qf["name"], type_label, args_str,
                           (qf.get("description") or "")[:80]])
        body += data_table(["Query", "Returns", "Args", "Description"], q_rows)
        body += "</div>\n"

    # Enum types reference
    enums = {name: tdef for name, tdef in inspector.types.items()
             if tdef.get("kind") == "ENUM" and not name.startswith("__")}
    if enums:
        body += '<div class="section"><h2>Enum Types</h2>\n'
        for ename, edef in sorted(enums.items()):
            values = [ev["name"] for ev in (edef.get("enumValues") or [])]
            body += f'<h3><code>{ename}</code></h3>\n'
            body += f'<p>{", ".join(f"<code>{v}</code>" for v in values)}</p>\n'
        body += "</div>\n"

    return html_page(
        title=f"bro_read — GraphQL / User {user_id}",
        body=body,
        meta=f"Generated {datetime.utcnow().isoformat()}Z | "
             f"endpoint: {inspector.endpoint} | "
             f"canonical URL: /users/{user_id}/bro_read",
    )


def build_bro_write_from_graphql(inspector: GraphQLInspector, user_id: str) -> str:
    body = ""
    mutations = inspector.mutation_fields()

    if not mutations:
        body += ('<div class="section"><em>No mutations found on this schema. '
                 'Mutations may be disabled or require auth.</em></div>\n')
    else:
        actions = [inspector._mutation_to_action(m) for m in mutations]

        # Group by inferred action type
        by_type: dict[str, list] = defaultdict(list)
        for a in actions:
            by_type[a["action_type"]].append(a)

        for atype in ("CREATE", "UPDATE", "DELETE", "MUTATION"):
            group = by_type.get(atype)
            if not group:
                continue
            badge_color = {"CREATE": "#2a7", "UPDATE": "#27a",
                           "DELETE": "#a22", "MUTATION": "#555"}.get(atype, "#555")
            body += f'<div class="section"><h2>'
            body += (f'<span class="badge" style="background:{badge_color}">'
                     f'{atype}</span> Mutations</h2>\n')

            for a in group:
                label = (
                    f'{a["label"]}'
                    f' <code style="font-size:10px;color:#777">'
                    f'mutation {a["mutation"]}(...)</code>'
                )
                # GraphQL mutations POST to the same endpoint as JSON
                # We embed the mutation name as a hidden field for Tech Bro
                fields_with_op = [
                    {"name": "__mutation", "type": "hidden",
                     "label": "Mutation", "required": True},
                ] + a["fields"]
                body += html_form(
                    action=a["action"], method="POST",
                    fields=a["fields"], label=label,
                ) + "\n"
                if a.get("description"):
                    body += f'<p style="color:#777;font-size:11px">{a["description"]}</p>\n'
            body += "</div>\n"

    # Summary
    body += '<div class="section"><h2>Mutation Surface Summary</h2>\n'
    body += kv_table([
        ("Total mutations", len(mutations)),
        ("Endpoint",        inspector.endpoint),
        ("Protocol",        "GraphQL (POST application/json)"),
    ])
    body += "</div>\n"

    return html_page(
        title=f"bro_write — GraphQL / User {user_id}",
        body=body,
        meta=f"Generated {datetime.utcnow().isoformat()}Z | "
             f"endpoint: {inspector.endpoint} | "
             f"canonical URL: /users/{user_id}/bro_write",
    )


# ===========================================================================
# CLI command handlers for the three new modes
# ===========================================================================

def cmd_openapi_to_bro(args):
    inspector = OpenAPIInspector(
        spec_source=args.spec,
        user_entity=args.user_entity,
        base_url=getattr(args, "base_url", None),
        bearer_token=getattr(args, "bearer_token", None),
    )
    inspector.load()

    out     = Path(args.output_dir)
    user_id = getattr(args, "user_id", None) or "schema"
    write_output(build_bro_read_from_openapi(inspector, user_id),
                 out / f"user_{user_id}_bro_read.html")
    write_output(build_bro_write_from_openapi(inspector, user_id),
                 out / f"user_{user_id}_bro_write.html")
    print("\n[done] bro_read and bro_write pages generated (openapi mode).")


def cmd_odata_to_bro(args):
    inspector = ODataInspector(
        metadata_source=args.metadata_url,
        user_entity=args.user_entity,
        service_url=getattr(args, "service_url", None),
        bearer_token=getattr(args, "bearer_token", None),
    )
    inspector.load()

    out     = Path(args.output_dir)
    user_id = getattr(args, "user_id", None) or "schema"
    write_output(build_bro_read_from_odata(inspector, user_id),
                 out / f"user_{user_id}_bro_read.html")
    write_output(build_bro_write_from_odata(inspector, user_id),
                 out / f"user_{user_id}_bro_write.html")
    print("\n[done] bro_read and bro_write pages generated (odata mode).")


def cmd_graphql_to_bro(args):
    inspector = GraphQLInspector(
        endpoint=args.endpoint,
        user_type=args.user_type,
        bearer_token=getattr(args, "bearer_token", None),
    )
    inspector.introspect()

    out     = Path(args.output_dir)
    user_id = getattr(args, "user_id", None) or "schema"
    write_output(build_bro_read_from_graphql(inspector, user_id),
                 out / f"user_{user_id}_bro_read.html")
    write_output(build_bro_write_from_graphql(inspector, user_id),
                 out / f"user_{user_id}_bro_write.html")
    print("\n[done] bro_read and bro_write pages generated (graphql mode).")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def write_output(content: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"[out] Written: {path}")


def cmd_web_to_bro(args):
    crawler = WebCrawler(
        base_url=args.url,
        user_id=args.user_id,
        username=args.username,
        password=args.password,
        login_url=args.login_url,
        max_pages=args.max_pages,
        use_playwright=args.playwright,
    )
    crawler.crawl()

    out = Path(args.output_dir)
    write_output(
        build_bro_read_from_web(crawler, args.user_id),
        out / f"user_{args.user_id}_bro_read.html",
    )
    write_output(
        build_bro_write_from_web(crawler, args.user_id),
        out / f"user_{args.user_id}_bro_write.html",
    )
    print("\n[done] bro_read and bro_write pages generated (web mode).")


def cmd_db_to_bro(args):
    inspector = DBInspector(
        dsn=args.dsn,
        user_table=args.user_table,
        user_id_col=args.user_id_column,
    )
    inspector.connect()

    out = Path(args.output_dir)
    user_id = args.user_id or "schema"
    write_output(
        build_bro_read_from_db(inspector, user_id),
        out / f"user_{user_id}_bro_read.html",
    )
    write_output(
        build_bro_write_from_db(inspector, user_id),
        out / f"user_{user_id}_bro_write.html",
    )
    print("\n[done] bro_read and bro_write pages generated (db mode).")


def main():
    parser = argparse.ArgumentParser(
        description="Tech Bro Two Step — bro_read / bro_write page generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    # ---- web-to-bro ----
    wp = sub.add_parser("web-to-bro", help="Crawl a website and generate bro pages")
    wp.add_argument("--url",        required=True, help="Base URL to crawl")
    wp.add_argument("--user-id",    required=True, help="User ID for canonical URLs")
    wp.add_argument("--username",   default=None,  help="Login username / email")
    wp.add_argument("--password",   default=None,  help="Login password")
    wp.add_argument("--login-url",  default=None,  help="Login form URL (default: <base>/login)")
    wp.add_argument("--max-pages",  type=int, default=50, help="Max pages to crawl (default 50)")
    wp.add_argument("--playwright", action="store_true", help="Use Playwright instead of requests")
    wp.add_argument("--output-dir", default="./bro_output", help="Output directory")

    # ---- db-to-bro ----
    dp = sub.add_parser("db-to-bro", help="Inspect a DB schema and generate bro pages")
    dp.add_argument("--dsn",            required=True,
                    help="SQLAlchemy DSN, e.g. sqlite:///app.db or postgresql://u:p@h/db")
    dp.add_argument("--user-table",     required=True, help="Name of the primary user table")
    dp.add_argument("--user-id-column", default="id",  help="PK column in user table (default: id)")
    dp.add_argument("--user-id",        default="schema", help="User ID label for output filenames")
    dp.add_argument("--output-dir",     default="./bro_output", help="Output directory")

    # ---- openapi-to-bro ----
    op = sub.add_parser("openapi-to-bro",
                        help="Read an OpenAPI/Swagger spec and generate bro pages")
    op.add_argument("--spec",         required=True,
                    help="URL or file path to OpenAPI 3.x/Swagger 2.x spec (JSON or YAML)")
    op.add_argument("--user-entity",  default="User",
                    help="Schema name representing the user (default: User)")
    op.add_argument("--base-url",     default=None,
                    help="Override server base URL from spec")
    op.add_argument("--bearer-token", default=None,
                    help="Bearer token for authenticated spec endpoints")
    op.add_argument("--user-id",      default="schema",
                    help="User ID label for output filenames")
    op.add_argument("--output-dir",   default="./bro_output",
                    help="Output directory")

    # ---- odata-to-bro ----
    od = sub.add_parser("odata-to-bro",
                        help="Consume an OData $metadata document and generate bro pages")
    od.add_argument("--metadata-url", required=True,
                    help="URL or file path to OData $metadata XML document")
    od.add_argument("--user-entity",  required=True,
                    help="EntityType or EntitySet name representing the user")
    od.add_argument("--service-url",  default=None,
                    help="OData service root URL (used in action URLs)")
    od.add_argument("--bearer-token", default=None,
                    help="Bearer token for authenticated $metadata requests")
    od.add_argument("--user-id",      default="schema",
                    help="User ID label for output filenames")
    od.add_argument("--output-dir",   default="./bro_output",
                    help="Output directory")

    # ---- graphql-to-bro ----
    gq = sub.add_parser("graphql-to-bro",
                        help="Introspect a GraphQL endpoint and generate bro pages")
    gq.add_argument("--endpoint",     required=True,
                    help="GraphQL endpoint URL (introspection will be queried)")
    gq.add_argument("--user-type",    default="User",
                    help="GraphQL type name representing the user (default: User)")
    gq.add_argument("--bearer-token", default=None,
                    help="Bearer token for Authorization header")
    gq.add_argument("--user-id",      default="schema",
                    help="User ID label for output filenames")
    gq.add_argument("--output-dir",   default="./bro_output",
                    help="Output directory")

    args = parser.parse_args()

    if args.mode == "web-to-bro":
        cmd_web_to_bro(args)
    elif args.mode == "db-to-bro":
        cmd_db_to_bro(args)
    elif args.mode == "openapi-to-bro":
        cmd_openapi_to_bro(args)
    elif args.mode == "odata-to-bro":
        cmd_odata_to_bro(args)
    elif args.mode == "graphql-to-bro":
        cmd_graphql_to_bro(args)


if __name__ == "__main__":
    main()
