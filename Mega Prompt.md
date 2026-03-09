# **🐧 The Bro Mode Mega Prompt**

You are a principal systems engineer performing a "Bro Optimization".

Your task is to upgrade this repository so that it supports the  
Tech Bro Two Step Protocol:

   bro\_read  
   bro\_write

The goal of this protocol is to make the system agent-ready by ensuring  
that every entity has:

   1\. A single URL that exposes the full entity graph (bro\_read)  
   2\. A single URL that exposes every possible mutation (bro\_write)

Agents, partner systems, and internal tools should be able to  
fully understand and operate on an entity using only these two pages.

You must analyze the entire repository and produce a complete  
implementation plan and code changes.

Work through the following phases sequentially.

\--------------------------------------------------  
PHASE 1 — SYSTEM RECONNAISSANCE  
\--------------------------------------------------

Scan the entire repository and identify:

1\. Core domain entities  
  Examples:  
  \- users  
  \- accounts  
  \- policies  
  \- claims  
  \- orders  
  \- subscriptions  
  \- devices  
  \- organizations

2\. For each entity identify:

  \- database models  
  \- ORM definitions  
  \- API routes  
  \- controllers  
  \- services  
  \- background jobs  
  \- related entities

3\. Identify all existing READ operations:

  \- GET endpoints  
  \- query services  
  \- aggregation endpoints

4\. Identify all existing MUTATION operations:

  \- POST  
  \- PUT  
  \- PATCH  
  \- DELETE  
  \- command handlers  
  \- job triggers

Output a structured report:

ENTITY MAP

Entity:  
Owning service:  
Existing read endpoints:  
Existing mutation endpoints:  
Linked entities:  
Relevant databases:

\--------------------------------------------------  
PHASE 2 — ENTITY GRAPH DESIGN  
\--------------------------------------------------

For each entity discovered:

Design a canonical "Entity Graph".

The entity graph must include:

\- primary entity fields  
\- linked entities  
\- history or transactions  
\- status flags  
\- metadata  
\- audit events  
\- permissions  
\- external integrations

Your design goal:

A single request must return the entire entity state.

Output:

Entity Graph Specification  
for each entity.

\--------------------------------------------------  
PHASE 3 — BRO\_READ DESIGN  
\--------------------------------------------------

For each entity implement:

   /\<entity\>/:id/bro\_read

Requirements:

1\. The page must return the COMPLETE entity graph.

2\. The page must aggregate data from all internal services.

3\. The page must be rendered as plain HTML.

4\. Do NOT use frontend frameworks.

5\. The HTML should include:

  \- section headers  
  \- tables for collections  
  \- labeled fields  
  \- links to related entity bro\_read pages

6\. Include metadata:

  \- entity ID  
  \- timestamps  
  \- status flags  
  \- last update time

7\. Ensure the page is easily parseable by both:

  \- humans  
  \- AI agents  
  \- simple HTML parsers

Provide:

\- route definition  
\- controller/service logic  
\- HTML template

\--------------------------------------------------  
PHASE 4 — BRO\_WRITE DESIGN  
\--------------------------------------------------

For each entity implement:

   /\<entity\>/:id/bro\_write

This page lists ALL possible mutations.

Requirements:

1\. Every mutation must appear as a form.

2\. Each form must contain:

  \- descriptive label  
  \- required fields  
  \- HTTP method  
  \- action endpoint

3\. Group actions into categories:

  \- updates  
  \- state transitions  
  \- administrative actions  
  \- compliance actions  
  \- support actions

4\. HTML must remain simple and framework-free.

5\. The goal is that an AI agent can:

  \- parse the page  
  \- discover actions  
  \- execute them

Provide:

\- route  
\- template  
\- mapping to existing mutation handlers

\--------------------------------------------------  
PHASE 5 — GENERATION PIPELINE  
\--------------------------------------------------

Create an automated pipeline that:

1\. Scans entity models  
2\. Scans API routes  
3\. Scans mutation handlers  
4\. Automatically regenerates:

  bro\_read templates  
  bro\_write forms

The generator should run:

   during build or deploy

so that bro pages always remain in sync with the codebase.

Provide:

\- generator architecture  
\- template system  
\- integration instructions

\--------------------------------------------------  
PHASE 6 — AUTHENTICATION  
\--------------------------------------------------

Implement authentication for bro endpoints.

Requirements:

\- OAuth2 client credentials  
\- service tokens  
\- token scoping by entity ID

Add middleware that:

\- verifies tokens  
\- checks entity authorization  
\- logs access

Output:

authentication middleware  
token validation logic  
access control rules

\--------------------------------------------------  
PHASE 7 — PERFORMANCE OPTIMIZATION  
\--------------------------------------------------

Optimize bro\_read endpoints.

Implement:

\- service fan-out aggregation  
\- async requests  
\- short TTL caching (30–120 seconds)  
\- circuit breakers for slow services

Ensure the endpoints are production-ready.

\--------------------------------------------------  
PHASE 8 — AUDIT LOGGING  
\--------------------------------------------------

Every bro endpoint access must be logged.

Log fields:

\- timestamp  
\- requesting system  
\- entity accessed  
\- action performed

Provide structured logging examples.

\--------------------------------------------------  
PHASE 9 — TESTING  
\--------------------------------------------------

Generate automated tests that verify:

1\. Every entity has bro\_read  
2\. Every entity has bro\_write  
3\. Every mutation appears in bro\_write  
4\. bro\_read returns a complete entity graph

Provide:

\- unit tests  
\- integration tests

\--------------------------------------------------  
PHASE 10 — PARTNER DOCUMENTATION  
\--------------------------------------------------

Generate a developer guide explaining:

\- the bro\_read / bro\_write protocol  
\- how partners authenticate  
\- how agents discover actions  
\- example workflows

\--------------------------------------------------  
PHASE 11 — OUTPUT FORMAT  
\--------------------------------------------------

Provide your output in the following order:

1\. System Recon Report  
2\. Entity Graph Specs  
3\. bro\_read Implementation  
4\. bro\_write Implementation  
5\. Generator Architecture  
6\. Security Implementation  
7\. Performance Strategy  
8\. Test Suite  
9\. Partner Documentation

Focus on clean, maintainable production code.

The end result should transform this repository into a  
fully agent-ready system using the bro\_read / bro\_write protocol.  
---

# **Why This Prompt Works So Well**

This prompt leverages something coding models are **exceptionally good at**:

1. **Repo comprehension**  
2. **Pattern extraction**  
3. **Code generation**  
4. **System refactoring**

Instead of asking the model for code directly, it forces a **structured principal-engineer workflow**.

That dramatically improves output quality.

