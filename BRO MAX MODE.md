**One prompt → repository becomes agent-ready → pull request generated automatically.**

This prompt is designed for **Claude Code, Codex, or any repo-aware coding agent** with permissions to:

* read the repo  
* write files  
* run tests  
* open PRs

---

# **🐧 BRO MAX MODE**

## **Autonomous Bro Optimization Prompt**

You are an autonomous principal engineer tasked with upgrading this repository  
to support the **Tech Bro Two Step Protocol**:

```
bro_read
bro_write
```

Your mission is to transform this repository into an **agent-ready system**  
that exposes full entity state and full action surfaces for every domain entity.

The upgrade must be implemented as a clean, production-ready pull request.

Follow the phases below.

---

## **BRO MAX MODE — PHASE 0**

## **MISSION OBJECTIVE**

Convert this repository into a **Bro-Optimized System** where:

Every entity exposes:

```
/<entity>/:id/bro_read
/<entity>/:id/bro_write
```

These endpoints must allow any authorized system or AI agent to:

1. Fully understand an entity in a single request  
2. Discover every possible mutation  
3. Execute actions without API discovery

The implementation must:

* preserve existing behavior  
* require minimal manual configuration  
* automatically stay in sync with the codebase

---

## **PHASE 1 — FULL REPOSITORY RECON**

Analyze the entire repository and produce a structured report.

Detect:

1. All domain entities  
2. Database schemas  
3. ORM models  
4. API routes  
5. controllers/services  
6. command handlers  
7. mutation endpoints  
8. internal service boundaries

Generate an **Entity Inventory**.

For each entity record:

Entity Name:  
Owning Module/Service:  
Primary Data Source:  
Existing Read APIs:  
Existing Mutation APIs:  
Linked Entities:  
Event Streams or Logs:

Save the report as:

```
docs/bro/entity_inventory.md
```

---

## **PHASE 2 — ENTITY GRAPH SPECIFICATION**

For each entity construct a canonical **Entity Graph**.

The graph must include:

• core attributes  
• linked entities  
• historical records  
• state flags  
• metadata  
• audit logs  
• external integrations

The goal is that:

bro\_read returns the **complete graph of an entity**.

Save specifications as:

```
docs/bro/entity_graphs/<entity>.md
```

---

## **PHASE 3 — BRO INFRASTRUCTURE PACKAGE**

Create a reusable infrastructure module:

```
/internal/bro/
```

This module must include:

bro\_router  
bro\_read\_renderer  
bro\_write\_renderer  
entity\_graph\_aggregator  
mutation\_discovery  
auth\_middleware  
audit\_logger

The module must be framework-native for the current repository.

---

## **PHASE 4 — BRO\_READ ENDPOINTS**

For each entity generate:

```
/<entity>/:id/bro_read
```

Requirements:

• aggregate full entity graph  
• query all relevant services  
• return plain HTML  
• avoid frontend frameworks

HTML must contain:

* semantic sections  
* labeled fields  
* tables for collections  
* links to related entity bro\_read pages

Design goal:

Both humans and AI agents can parse it easily.

---

## **PHASE 5 — BRO\_WRITE ENDPOINTS**

For each entity generate:

```
/<entity>/:id/bro_write
```

This page lists every mutation action available.

Automatically discover actions by scanning:

* POST routes  
* PUT routes  
* PATCH routes  
* command handlers  
* job triggers

Each mutation must appear as an HTML form with:

• action endpoint  
• HTTP method  
• required fields  
• descriptive label

Group actions by category:

• updates  
• lifecycle transitions  
• administrative actions  
• compliance actions  
• support actions

---

## **PHASE 6 — AUTO-GENERATOR**

Create a build-time generator:

```
bro_generate
```

This tool must:

1. scan entity models  
2. scan route definitions  
3. discover mutations  
4. regenerate bro templates

The generator must run automatically during:

```
build
deploy
```

This ensures bro pages never fall out of sync.

---

## **PHASE 7 — SECURITY MODEL**

Implement authentication.

Requirements:

OAuth2 Client Credentials

Tokens must include:

• partner system ID  
• entity scope  
• expiration

Middleware must enforce:

token validation  
entity authorization  
access logging

Unauthorized access must return HTTP 401\.

---

## **PHASE 8 — PERFORMANCE**

Optimize bro\_read aggregation.

Implement:

• async service fan-out  
• short TTL cache (30-120 seconds)  
• graceful degradation if services fail  
• circuit breakers

The endpoints must scale to production workloads.

---

## **PHASE 9 — AUDIT TRAIL**

Every bro endpoint request must generate an audit event.

Log fields:

timestamp  
requesting system  
entity ID  
endpoint accessed  
action executed

Write logs to the repository's existing logging system.

---

## **PHASE 10 — TEST SUITE**

Create automated tests verifying:

1. Every entity has bro\_read  
2. Every entity has bro\_write  
3. Every mutation appears in bro\_write  
4. bro\_read returns a complete entity graph

Add tests under:

```
tests/bro/
```

---

## **PHASE 11 — PARTNER DEVELOPER GUIDE**

Generate documentation:

```
docs/bro/partner_integration.md
```

Include:

• protocol overview  
• authentication steps  
• example agent workflows  
• example requests  
• security practices

---

## **PHASE 12 — PULL REQUEST**

Create a pull request titled:

```
"BRO Optimization: Implement Tech Bro Two Step Protocol"
```

The PR must include:

• bro infrastructure module  
• bro\_read endpoints  
• bro\_write endpoints  
• generator tool  
• tests  
• documentation

Write a PR summary explaining:

• architecture  
• security model  
• performance considerations  
• future extensions

---

## **PHASE 13 — FUTURE EXTENSIONS**

Document optional future features:

bro\_index pages  
entity change diffs  
event streams  
agent SDKs  
cross-organization bro federation

---

Your final output must include:

1. generated code  
2. infrastructure modules  
3. tests  
4. documentation  
5. pull request summary

Do not remove or break existing functionality.

Focus on maintainability, security, and clarity.

This repository should emerge from this process as a  
**fully Bro-Optimized Agent-Ready Platform.**

---

# **What BRO MAX MODE Actually Does**

If a coding agent executes that prompt with repo access, it will:

1. **Scan the repo**  
2. **Identify domain entities**  
3. **Generate bro endpoints**  
4. **Create a reusable bro framework**  
5. **Add security**  
6. **Write tests**  
7. **Write docs**  
8. **Open a PR**

In practice it turns this:

```
random microservice repo
```

into:

```
agent-ready platform
with full entity introspection
```

---

