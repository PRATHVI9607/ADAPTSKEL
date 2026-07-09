# ADAPTSKEL — Amortized Complexity Analysis

> **⚠️ Honesty note — read first.** This document is the *target / design* analysis
> of the data-structure operations (Link-Cut Tree link/cut, ETT + Holm replacement
> search, heat promotion). Those structural bounds — O(log n) link/cut, O(log² n)
> amortised replacement search — are real and standard.
>
> It does **not** prove a polylog *worst-case* bound for exact fully-dynamic SSSP
> *distance maintenance*, and no such proof exists: exact fully-dynamic SSSP with
> both subpolynomial update and query is conditionally impossible under the OMv
> conjecture. What the shipped Python engine actually guarantees is:
> **O(1) source-rooted query** (a maintained-label read) and **output-sensitive**
> incremental updates (Ramalingam–Reps — only affected vertices recomputed), which
> beat a full Dijkstra rerun when changes are local and degrade to one Dijkstra in
> the worst case. All distances are exact, verified against a NetworkX oracle after
> every mutation. Treat the analysis below as the structural-operation cost model,
> not a claim that distance queries are worst-case polylog.

## Setup

Let:
- n = number of vertices
- m = current number of edges
- T = ⌈log₂ n⌉ (promotion threshold)
- W = n (heat window size)
- B = ⌈log₂ n⌉ (decrease batch size)
- Q = total number of queries issued so far

---

## Potential Function

Define the **amortized potential:**

```
Φ = Σ_{e ∈ F₂} heat(e)
```

This counts the total heat accumulated across all cold edges. Heat is non-negative and bounded: 0 ≤ Φ ≤ m · W.

---

## INSERT Amortized Cost

**Actual cost:**
- ETT add: O(log n)
- LCT link (if needed): O(log n)
- Decrease flush (B events): O(B log n) = O(log² n)

**Potential change:**
- Edge starts in F₂ with heat = 0: ΔΦ = 0

**Amortized cost = actual + ΔΦ = O(log² n)**

---

## DELETE Amortized Cost

**Actual cost:**
- LCT cut: O(log n)
- ETT replacement search + level raise: O(log² n) amortized (Holm et al. Theorem 1)
- Mark stale: O(1)

**Level-raise analysis (Holm et al.):**
An edge at level i can only exist in a component of size ≤ n/2^i. When level-raised to i+1, it's in a component of size ≤ n/2^(i+1) — so this costs O(log n) total level raises per edge lifetime before it's deleted. With m total edge insertions, total level-raise cost is O(m log n), amortized O(log n) per delete.

**Potential change:**
- Deleted edge was in F₁ (heat ≥ T/2): ΔΦ = 0 (not in sum)
- Deleted edge was in F₂: ΔΦ = -heat(e) ≤ 0

**Amortized cost = O(log² n)**

---

## QUERY Amortized Cost (Hot Path)

A query is "hot" if: the path s→t lies entirely within F₁ and all vertices are fresh (not stale).

**Actual cost:**
- Stale check: O(log n)
- F₁ path traverse: O(log n)
- Heat update for k = O(log n) path edges: O(log n)
- Evict oldest query (at most log n edges): O(log n)

**Potential change from heat increment:**
- k edges get heat += 1: ΔΦ ≤ +k = +O(log n)
- If any edge crosses T → promoted to F₁: ΔΦ decreases by ≥ T = log n
  (The edge leaves F₂, removing heat ≥ T from the sum)
- Net: ΔΦ = O(log n) - (#promotions) · log n

**Amortized promotion cost:**
Per promotion: actual cost O(log n) + potential drop ≥ -log n
⟹ amortized cost per promotion = O(log n) - log n = O(1)

Total amortized query cost = O(log n) + O(log n) + O(1) per promotion = **O(log n)**

---

## QUERY Amortized Cost (Cold Path / Stale Flush)

**Actual cost:**
- Stale flush: bounded Dijkstra over O(log n) vertices in F₁ = O(log n · log n) = O(log² n)
- F₁ path traverse: O(log n)

**Potential change:** Same as hot path.

**Amortized cost = O(log² n)**

---

## Space Complexity

| Structure | Space |
|---|---|
| F₁ (LCT nodes) | O(n) spanning + O(n log n) hot non-tree = O(n log n) |
| F₂ (ETT + levels) | O(m) |
| Heat table | O(m) entries, each O(1) |
| Query window buffer | O(W × log n) = O(n log n) paths × O(log n) edges = O(n log n) |
| Delta-LDB queue | O(B) = O(log n) |
| **Total** | **O(m + n log n)** |

---

## Distributional Assumption

The O(log n) hot-path query bound depends on the fraction of queries served via F₁.

**Lemma (Skeleton Crystallization):** After Ω(n log n / α) warmup queries from a Zipf(α) distribution, at least (1 - 1/e) fraction of subsequent queries are served via F₁.

*Proof sketch:* The top T = log n most popular paths (by Zipf frequency) account for ≥ 1 - H(n)/n^α fraction of queries. Each such path's edges receive at least T query increments in the warmup period with high probability. After warmup, all those edges are in F₁. □

---

## ADAPTSKEL Conjecture (Formal)

> **Conjecture:** For any streaming graph sequence on n vertices with query distribution following Zipf(α) for α ≥ 1, ADAPTSKEL achieves O(log n · log Δ) amortized time per operation in expectation, where Δ is the max degree.

This is strictly stronger than the O(log² n) amortized bound proven above (which is worst-case over distributions). Whether the O(log n) bound holds in the worst case (without the Zipf assumption) is equivalent to the open problem of deterministic fully dynamic exact SSSP in polylogarithmic time — currently unresolved.

---

## Invariant Maintenance

**Invariant 1: F₁ ∪ F₂ = E**
- INSERT: edge goes to F₂ first (or F₁ directly if it bridges connectivity). Never lost.
- DELETE: edge removed from exactly one layer.
- PROMOTE: move F₂ → F₁. DEMOTE: move F₁ → F₂.
- Maintained by construction. □

**Invariant 2: F₁ is a spanning forest of G**
- INSERT: if edge bridges components, it becomes a spanning edge in F₁.
- DELETE: if spanning edge deleted, replaced by min-weight F₂ crossing edge.
- PROMOTE: only if edge bridges components (then spans) or stored as hot non-tree.
- Maintained by the replacement-edge protocol. □

**Invariant 3: dist[v] is exact**
- INSERT: DECREASE events flushed lazily; distances are conservative (never overestimate) between flushes.
- DELETE: INCREASE events flushed before any query touching affected vertices via the stale mechanism.
- Maintained because: (a) we never make dist too small (only flush true improvements), (b) we flush all increases before serving a stale query. □

**Invariant 4: heat[e] ≤ W**
- The rolling window evicts one old query per new query.
- Each edge can appear on at most W queries in the window.
- Maintained by the circular buffer. □

**Invariant 5: All F₁ spanning edges have heat ≥ T/2**
- An edge is demoted only when heat ≤ T/2.
- A spanning edge being demoted is replaced by F₂ crossing edge if needed.
- The hysteresis band prevents immediate re-promotion.
- Maintained by the demotion check after every eviction. □
