#!/usr/bin/env python3
"""
bro_generator.py — Tech Bro Two Step Protocol Generator
========================================================
Generates bro_read and bro_write HTML pages from two sources:

  web-to-bro   Crawl a live website (as a logged-in user) and infer the
               entity data graph and available actions, then emit bro pages.

  db-to-bro    Inspect a database schema and emit bro pages wired to
               the real tables/columns/foreign-keys found there.

Usage
-----
  # Web mode
  python bro_generator.py web-to-bro \
      --url https://example.com \
      --user-id 42 \
      [--username admin --password secret] \
      [--login-url https://example.com/login] \
      [--max-pages 50] \
      [--output-dir ./bro_output]

  # DB mode — SQLite
  python bro_generator.py db-to-bro \
      --dsn sqlite:///myapp.db \
      --user-table users \
      [--user-id-column id] \
      [--output-dir ./bro_output]

  # DB mode — Postgres / MySQL / MSSQL (SQLAlchemy DSN)
  python bro_generator.py db-to-bro \
      --dsn postgresql://user:pass@host/dbname \
      --user-table users \
      [--output-dir ./bro_output]

Dependencies
------------
  pip install requests beautifulsoup4 sqlalchemy
  (playwright is optional but recommended for JS-heavy sites)
  pip install playwright && playwright install chromium
"""

import argparse
import json
import os
import sys
import re
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse
from collections import defaultdict
from typing import Optional

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

    args = parser.parse_args()

    if args.mode == "web-to-bro":
        cmd_web_to_bro(args)
    elif args.mode == "db-to-bro":
        cmd_db_to_bro(args)


if __name__ == "__main__":
    main()
