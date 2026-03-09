The two documents outline a **protocol (“Tech Bro Two-Step”: `bro_read` \+ `bro_write`)** that simplifies integrations and makes systems **agent-ready**.

This doc provides something clever:  
**a sequence of prompts someone using Claude Code or Codex could run to “bro-optimize” their entire codebase.**

In other words:

Turn an arbitrary codebase into a system that automatically generates  
`bro_read` and `bro_write` infrastructure for every entity.

Below is a **prompt ladder** designed for **Claude Code / Codex workflows**.  
Each prompt progressively upgrades the system.

Think of it as **“The Bro Optimization Pipeline.”**

---

# **🐧 The Bro Optimization Prompt Series**

*(For Claude Code / Codex Users)*

These prompts assume the model has access to the repository.

---

# **1️⃣ Bro Recon Prompt**

**Goal:** Understand the system before modifying it.

```
You are performing a "Bro Optimization Audit".

Scan the repository and identify:

1. All core entities in the system
   (users, accounts, orders, policies, claims, etc.)

2. All existing read APIs or queries related to those entities.

3. All mutation endpoints or commands related to those entities.

4. Internal services that own pieces of the entity graph.

Produce a report with:

ENTITY
- entity name
- owning service
- existing read endpoints
- existing mutation endpoints
- missing data sources

Finally recommend a bro_read and bro_write page structure for each entity.
```

Output: **system map**

---

# **2️⃣ Entity Graph Mapping Prompt**

```
For each entity discovered in the repository:

Create an "Entity Graph Specification".

The spec must include:

- primary entity fields
- linked entities
- related services
- historical data sources
- audit logs
- permissions data

Output a canonical data aggregation structure for the bro_read page.

The goal is: a single request that returns the entire entity graph.
```

Output: **bro\_read data model**

---

# **3️⃣ bro\_read Generator Prompt**

Now we generate the read layer.

```
Generate a bro_read endpoint for the following entity:

ENTITY_NAME: <entity>

Requirements:

1. Endpoint path
   /<entity>/:id/bro_read

2. Endpoint returns:
   - complete entity state
   - aggregated data from all services
   - history and metadata

3. Output format:
   plain HTML
   no JavaScript
   semantic tags
   tables for lists
   sections for entity groups

4. Include:
   - timestamps
   - internal IDs
   - status flags
   - linked entity URLs

The page must be machine-readable by agents and humans.
```

---

# **4️⃣ bro\_write Generator Prompt**

```
Generate a bro_write endpoint for the entity:

ENTITY_NAME: <entity>

Requirements:

1. Endpoint path
   /<entity>/:id/bro_write

2. Page must list ALL possible actions.

3. Each action should be an HTML form containing:
   - form label
   - input fields
   - action endpoint
   - method (POST/PUT/PATCH)

4. Group forms by category:

- account management
- updates
- state transitions
- support actions
- compliance actions

The goal: an AI agent should be able to parse the page and discover every available mutation.
```

---

# **5️⃣ Auto-Discovery Prompt**

This makes the system maintain itself.

```
Modify the bro generation system so that:

1. On each build
2. The system scans all routes/controllers
3. Extracts mutation endpoints
4. Automatically adds them to bro_write

Additionally:

- automatically include new entity fields in bro_read
- generate HTML from templates

Output the pipeline architecture.
```

---

# **6️⃣ Security Hardening Prompt**

```
Implement authentication and authorization for bro endpoints.

Requirements:

- OAuth2 client credentials
- token scoped by entity ID
- audit logging of all access
- rate limiting

Add middleware that:

1. verifies tokens
2. enforces entity scope
3. logs access events

Output code examples for the chosen framework.
```

---

# **7️⃣ Performance Optimization Prompt**

```
Optimize bro_read endpoints for performance.

Requirements:

- aggregation fanout
- short-lived caching (30-120 seconds)
- async fetch of internal services
- circuit breakers for slow services

Output architecture diagrams and example code.
```

---

# **8️⃣ Partner Integration Prompt**

```
Create documentation and onboarding instructions for external partners.

Include:

- how to obtain credentials
- how to access bro_read
- how to invoke bro_write forms programmatically
- example agent workflow

Output a partner integration guide.
```

---

# **9️⃣ Agent Enablement Prompt**

This is where things get fun.

```
Design an AI agent workflow that interacts with bro pages.

Capabilities:

1. Given an entity ID
   retrieve bro_read page

2. Interpret entity state

3. Retrieve bro_write page

4. choose appropriate action

5. submit mutation

Output:

- agent loop pseudocode
- error handling
- safety constraints
```

---

# **🔟 Bro System Self-Healing Prompt**

```
Implement automated tests that ensure bro endpoints remain valid.

Tests must verify:

- every entity has bro_read
- every entity has bro_write
- every mutation endpoint appears in bro_write
- bro_read includes required entity graph fields

Output integration test suite.
```

---

# **🧠 Bonus Prompt: The Ultimate Bro Mode**

This one turns the system **fully agent-ready**.

```
Upgrade the bro system with:

1. bro_index pages listing all entities
2. machine-readable metadata blocks
3. change history diffs
4. event streaming of entity updates

Goal:
Allow AI agents to fully navigate the platform autonomously.
```

---

# **🧩 What This Achieves**

Running these prompts converts a codebase into:

**Traditional system**

```
20 APIs
10 services
3 SDKs
months of integration
```

↓

**Bro-optimized system**

```
/users/:id/bro_read
/users/:id/bro_write
```

Agents instantly understand everything.

Which is exactly the **Tech Bro Two Step** you described.

---

# **🐧 The Bro Mode Mega Prompt**

**You are a principal systems engineer performing a "Bro Optimization".**

**Your task is to upgrade this repository so that it supports the**

**Tech Bro Two Step Protocol:**

   **bro\_read**

   **bro\_write**

**The goal of this protocol is to make the system agent-ready by ensuring**

**that every entity has:**

   **1\. A single URL that exposes the full entity graph (bro\_read)**

   **2\. A single URL that exposes every possible mutation (bro\_write)**

**Agents, partner systems, and internal tools should be able to**

**fully understand and operate on an entity using only these two pages.**

**You must analyze the entire repository and produce a complete**

**implementation plan and code changes.**

**Work through the following phases sequentially.**

**\--------------------------------------------------**

**PHASE 1 — SYSTEM RECONNAISSANCE**

**\--------------------------------------------------**

**Scan the entire repository and identify:**

**1\. Core domain entities**

  **Examples:**

  **\- users**

  **\- accounts**

  **\- policies**

  **\- claims**

  **\- orders**

  **\- subscriptions**

  **\- devices**

  **\- organizations**

**2\. For each entity identify:**

  **\- database models**

  **\- ORM definitions**

  **\- API routes**

  **\- controllers**

  **\- services**

  **\- background jobs**

  **\- related entities**

**3\. Identify all existing READ operations:**

  **\- GET endpoints**

  **\- query services**

  **\- aggregation endpoints**

**4\. Identify all existing MUTATION operations:**

  **\- POST**

  **\- PUT**

  **\- PATCH**

  **\- DELETE**

  **\- command handlers**

  **\- job triggers**

**Output a structured report:**

**ENTITY MAP**

**Entity:**

**Owning service:**

**Existing read endpoints:**

**Existing mutation endpoints:**

**Linked entities:**

**Relevant databases:**

**\--------------------------------------------------**

**PHASE 2 — ENTITY GRAPH DESIGN**

**\--------------------------------------------------**

**For each entity discovered:**

**Design a canonical "Entity Graph".**

**The entity graph must include:**

**\- primary entity fields**

**\- linked entities**

**\- history or transactions**

**\- status flags**

**\- metadata**

**\- audit events**

**\- permissions**

**\- external integrations**

**Your design goal:**

**A single request must return the entire entity state.**

**Output:**

**Entity Graph Specification**

**for each entity.**

**\--------------------------------------------------**

**PHASE 3 — BRO\_READ DESIGN**

**\--------------------------------------------------**

**For each entity implement:**

   **/\<entity\>/:id/bro\_read**

**Requirements:**

**1\. The page must return the COMPLETE entity graph.**

**2\. The page must aggregate data from all internal services.**

**3\. The page must be rendered as plain HTML.**

**4\. Do NOT use frontend frameworks.**

**5\. The HTML should include:**

  **\- section headers**

  **\- tables for collections**

  **\- labeled fields**

  **\- links to related entity bro\_read pages**

**6\. Include metadata:**

  **\- entity ID**

  **\- timestamps**

  **\- status flags**

  **\- last update time**

**7\. Ensure the page is easily parseable by both:**

  **\- humans**

  **\- AI agents**

  **\- simple HTML parsers**

**Provide:**

**\- route definition**

**\- controller/service logic**

**\- HTML template**

**\--------------------------------------------------**

**PHASE 4 — BRO\_WRITE DESIGN**

**\--------------------------------------------------**

**For each entity implement:**

   **/\<entity\>/:id/bro\_write**

**This page lists ALL possible mutations.**

**Requirements:**

**1\. Every mutation must appear as a form.**

**2\. Each form must contain:**

  **\- descriptive label**

  **\- required fields**

  **\- HTTP method**

  **\- action endpoint**

**3\. Group actions into categories:**

  **\- updates**

  **\- state transitions**

  **\- administrative actions**

  **\- compliance actions**

  **\- support actions**

**4\. HTML must remain simple and framework-free.**

**5\. The goal is that an AI agent can:**

  **\- parse the page**

  **\- discover actions**

  **\- execute them**

**Provide:**

**\- route**

**\- template**

**\- mapping to existing mutation handlers**

**\--------------------------------------------------**

**PHASE 5 — GENERATION PIPELINE**

**\--------------------------------------------------**

**Create an automated pipeline that:**

**1\. Scans entity models**

**2\. Scans API routes**

**3\. Scans mutation handlers**

**4\. Automatically regenerates:**

  **bro\_read templates**

  **bro\_write forms**

**The generator should run:**

   **during build or deploy**

**so that bro pages always remain in sync with the codebase.**

**Provide:**

**\- generator architecture**

**\- template system**

**\- integration instructions**

**\--------------------------------------------------**

**PHASE 6 — AUTHENTICATION**

**\--------------------------------------------------**

**Implement authentication for bro endpoints.**

**Requirements:**

**\- OAuth2 client credentials**

**\- service tokens**

**\- token scoping by entity ID**

**Add middleware that:**

**\- verifies tokens**

**\- checks entity authorization**

**\- logs access**

**Output:**

**authentication middleware**

**token validation logic**

**access control rules**

**\--------------------------------------------------**

**PHASE 7 — PERFORMANCE OPTIMIZATION**

**\--------------------------------------------------**

**Optimize bro\_read endpoints.**

**Implement:**

**\- service fan-out aggregation**

**\- async requests**

**\- short TTL caching (30–120 seconds)**

**\- circuit breakers for slow services**

**Ensure the endpoints are production-ready.**

**\--------------------------------------------------**

**PHASE 8 — AUDIT LOGGING**

**\--------------------------------------------------**

**Every bro endpoint access must be logged.**

**Log fields:**

**\- timestamp**

**\- requesting system**

**\- entity accessed**

**\- action performed**

**Provide structured logging examples.**

**\--------------------------------------------------**

**PHASE 9 — TESTING**

**\--------------------------------------------------**

**Generate automated tests that verify:**

**1\. Every entity has bro\_read**

**2\. Every entity has bro\_write**

**3\. Every mutation appears in bro\_write**

**4\. bro\_read returns a complete entity graph**

**Provide:**

**\- unit tests**

**\- integration tests**

**\--------------------------------------------------**

**PHASE 10 — PARTNER DOCUMENTATION**

**\--------------------------------------------------**

**Generate a developer guide explaining:**

**\- the bro\_read / bro\_write protocol**

**\- how partners authenticate**

**\- how agents discover actions**

**\- example workflows**

**\--------------------------------------------------**

**PHASE 11 — OUTPUT FORMAT**

**\--------------------------------------------------**

**Provide your output in the following order:**

**1\. System Recon Report**

**2\. Entity Graph Specs**

**3\. bro\_read Implementation**

**4\. bro\_write Implementation**

**5\. Generator Architecture**

**6\. Security Implementation**

**7\. Performance Strategy**

**8\. Test Suite**

**9\. Partner Documentation**

**Focus on clean, maintainable production code.**

**The end result should transform this repository into a**

**fully agent-ready system using the bro\_read / bro\_write protocol.**

---

# **Why This Prompt Works So Well**

**This prompt leverages something coding models are exceptionally good at:**

1. **Repo comprehension**  
2. **Pattern extraction**  
3. **Code generation**  
4. **System refactoring**

**Instead of asking the model for code directly, it forces a structured principal-engineer workflow.**

**That dramatically improves output quality.**

