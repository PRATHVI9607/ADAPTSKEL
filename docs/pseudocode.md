# ADAPTSKEL — Core Algorithm Pseudocode

---

## Data Structures Used

```
G          — the full graph (all edges, all weights)
F₁         — skeleton layer  (Link-Cut Tree, hot edges only)
F₂         — residual layer  (Euler Tour Tree, cold edges only)
dist[v]    — shortest distance from source s to vertex v
heat[e]    — heat score of edge e (how often it appears on queried paths)
window     — sliding queue of the last W query path-edge-sets
LDB.dec    — min-heap of pending DECREASE events  (from insertions)
LDB.inc    — set of pending INCREASE events        (from deletions)

Constants:
  T  = ceil(log₂ n)   — promotion threshold  (heat ≥ T → hot)
  W  = n              — rolling window size
  B  = ceil(log₂ n)   — max decrease events flushed per INSERT
```

---

## 1. INSERT(u, v, w)

```
FUNCTION INSERT(u, v, w):

  // ── Step 1: Add edge to graph ──────────────────────────────────────
  G.add_edge(u, v, w)

  // ── Step 2: Decide which layer the new edge goes to ────────────────
  IF heat[u,v] >= T  AND  NOT F₁.connected(u, v):
      F₁.link(u, v, w)          // hot edge + no cycle → goes to skeleton
  ELSE:
      F₂.add_edge(u, v, w, level=0)   // cold, or would form a cycle → residual

  // ── Step 3: Enqueue DECREASE events for both endpoints ─────────────
  FOR each endpoint x IN {u, v}:
      other = the other endpoint
      candidate_dist = dist[other] + w
      IF candidate_dist < dist[x]:
          LDB.dec.push(other, x, w, candidate_dist)

  // ── Step 4: Flush up to B decrease events (bounded relaxation) ─────
  FLUSH_DECREASES(limit = B)

  // ── Step 5: Update distance labels (Python ref: full Dijkstra) ─────
  RECOMPUTE_DISTANCES()

  RETURN stats
```

---

## 2. DELETE(u, v)

```
FUNCTION DELETE(u, v):

  w = G.get_weight(u, v)
  G.remove_edge(u, v)

  // ── Step 1: Mark distances as potentially stale ────────────────────
  LDB.inc.push(u, v)            // distances involving u,v may have grown

  // ── Step 2: Remove edge from its structural layer ──────────────────
  IF (u,v) IN F₁:
      F₁.cut(u, v)              // skeleton breaks here
      F₁_DELETION_REPAIR(u, v)  // try to heal the skeleton from F₂

  ELSE IF (u,v) IN F₂:
      F₂.remove_edge(u, v)      // cold edge removed — no structural damage

  // ── Step 3: Flush all INCREASE events (must happen before queries) ──
  stale_vertices = FLUSH_INCREASES()
  FOR v IN stale_vertices:
      F₁.mark_stale(v)

  // ── Step 4: Recompute distances ────────────────────────────────────
  RECOMPUTE_DISTANCES()

  RETURN stats
```

---

## 3. F₁_DELETION_REPAIR(u, v)

```
// Called after cutting (u,v) from F₁.
// u and v might now be in two disconnected trees in F₁.
// We search F₂ for a replacement spanning edge using Holm et al. levels.

FUNCTION F₁_DELETION_REPAIR(u, v):

  FOR level FROM F₂.max_level DOWN TO 0:

      replacement = F₂.find_min_crossing_edge(u, v, level)
      // "crossing edge" = an F₂ edge with one endpoint in
      //  component(u) and the other in component(v) at this level

      IF replacement != NULL:
          (ru, rv, rw) = replacement
          F₂.remove_edge(ru, rv)
          F₁.link(ru, rv, rw)        // move replacement into skeleton
          RETURN                      // skeleton is healed — done

      ELSE:
          // No replacement found at this level.
          // Raise all level-`level` edges in the smaller component
          // (Holm et al. amortised trick — each edge raised at most log n times)
          smaller_component = smaller_of(component(u), component(v)) in F₂ at level
          FOR each edge e IN smaller_component AT level:
              F₂.raise_level(e, level + 1)

  // If we exit the loop without finding a replacement,
  // u and v are now in genuinely disconnected components — that's correct.
```

---

## 4. QUERY(s, t)

```
FUNCTION QUERY(s, t):

  // ── Step 1: Flush urgent increases before answering ─────────────────
  IF LDB.inc is NOT empty:
      stale = FLUSH_INCREASES()
      RECOMPUTE_DISTANCES()
      FOR v IN stale:
          F₁.mark_stale(v)

  // ── Step 2: Get exact shortest-path distance and path ───────────────
  dist_val  = DIJKSTRA(G, s, t)          // ground-truth (NetworkX in Python ref)
  path_edges = SHORTEST_PATH_EDGES(G, s, t)

  // ── Step 3: Update heat scores for edges on this path ───────────────
  newly_hot  = HEAT_INCREMENT(path_edges)
  newly_cold = HEAT_EVICT_OLDEST_IF_WINDOW_FULL()

  // ── Step 4: Promote newly-hot edges from F₂ → F₁ ───────────────────
  FOR each edge e IN newly_hot:
      IF e IN F₂:
          PROMOTE(e.u, e.v, e.w)

  // ── Step 5: Demote newly-cold edges from F₁ → F₂ ───────────────────
  FOR each edge e IN newly_cold:
      IF e IN F₁:
          DEMOTE(e.u, e.v, e.w)

  RETURN dist_val
```

---

## 5. PROMOTE(u, v, w)  —  F₂ → F₁

```
FUNCTION PROMOTE(u, v, w):
  // Move a hot edge from the residual layer up to the skeleton.

  IF (u,v) NOT IN F₂:
      RETURN    // already promoted or doesn't exist

  F₂.remove_edge(u, v)

  IF NOT F₁.connected(u, v):
      // Adding this edge to F₁ won't create a cycle — safe to link
      F₁.link(u, v, w)
      F₁_edges.add(u, v)
      stats.promotions++
  ELSE:
      // Would create a cycle in the spanning forest — edge stays in F₂
      F₂.add_edge(u, v, w, level=0)
```

---

## 6. DEMOTE(u, v, w)  —  F₁ → F₂

```
FUNCTION DEMOTE(u, v, w):
  // Move a cold edge from the skeleton down to the residual layer.

  IF (u,v) NOT IN F₁:
      RETURN

  F₁.cut(u, v)
  F₂.add_edge(u, v, w, level=0)
  F₁_edges.remove(u, v)
  stats.demotions++

  // Cutting an F₁ edge may disconnect the skeleton — repair it
  F₁_DELETION_REPAIR(u, v)
```

---

## 7. HEAT_INCREMENT(path_edges)

```
FUNCTION HEAT_INCREMENT(path_edges):
  // Slide the query window forward and update heat scores.

  window.append(path_edges)          // add this query to the window
  newly_hot = []

  FOR each edge e IN path_edges:
      heat[e] = heat[e] + 1
      IF heat[e] just crossed T (was T-1, now T):
          newly_hot.append(e)

  // Auto-evict if window overflows
  WHILE len(window) > W:
      HEAT_EVICT_ONE()

  RETURN newly_hot


FUNCTION HEAT_EVICT_ONE():
  // Remove the oldest query from the window and cool its edges.

  oldest_edges = window.pop_left()
  newly_cold = []

  FOR each edge e IN oldest_edges:
      heat[e] = heat[e] - 1
      IF heat[e] just dropped to T//2 (was T//2+1, now T//2):
          newly_cold.append(e)

  RETURN newly_cold
```

---

## 8. FLUSH_DECREASES(limit)

```
FUNCTION FLUSH_DECREASES(limit):
  // Process up to `limit` pending DECREASE events.
  // Each event is a tentative distance relaxation from an insertion.

  ops = 0
  WHILE LDB.dec is NOT empty  AND  ops < limit:

      (new_dist, u, v, w) = LDB.dec.pop_min()

      // Skip if this relaxation is stale
      IF new_dist >= dist[v]:
          CONTINUE                    // v already has an equal or better distance

      IF dist[u] + w > new_dist + ε:
          CONTINUE                    // u's label changed — this event is invalid

      // Apply relaxation
      dist[v] = new_dist
      ops++

      // Propagate: enqueue further relaxations for v's neighbours
      FOR each neighbour nb of v with edge weight edge_w:
          candidate = new_dist + edge_w
          IF candidate < dist[nb]:
              LDB.dec.push(v, nb, edge_w, candidate)

  RETURN ops
```

---

## 9. FLUSH_INCREASES()

```
FUNCTION FLUSH_INCREASES():
  // Drain all INCREASE events and return the set of stale vertices.
  // Must be called before answering any query after a deletion.

  stale = empty set

  WHILE LDB.inc is NOT empty:
      (u, v) = LDB.inc.pop()
      stale.add(u)
      stale.add(v)

  RETURN stale
  // Caller then runs RECOMPUTE_DISTANCES() to fix dist[] labels
```

---

## 10. RECOMPUTE_DISTANCES()

```
FUNCTION RECOMPUTE_DISTANCES():
  // Full single-source shortest-path from source vertex s.
  // Python reference: delegates to NetworkX Dijkstra — O(m log n).
  // C++ port: uses bounded Dijkstra scoped to stale subgraph — O(log² n).

  lengths = DIJKSTRA(G, source=s)

  FOR each vertex v IN G:
      dist[v] = lengths.get(v, INF)
      F₁.set_dist(v, dist[v])
      F₁.mark_fresh(v)
```

---

## Complexity Summary

| Operation | This Python Ref | Target (C++ port) | Why |
|---|---|---|---|
| INSERT | O(m log n) | O(log² n) | B=O(log n) relaxations × O(log n) LCT each |
| DELETE | O(m log n) | O(log² n) | Holm level-raising amortized + bounded Dijkstra |
| QUERY (hot path) | O(m log n) | O(log n) | F₁ LCT path query |
| QUERY (cold path) | O(m log n) | O(log² n) | Falls back to bounded Dijkstra |
| PROMOTE / DEMOTE | O(log n) | O(log n) | Single LCT link/cut |

> The Python reference uses NetworkX Dijkstra (O(m log n)) for all distance work — correct but slow.
> The C++ port replaces that with the LCT path queries and bounded Dijkstra to hit the theoretical bounds.

---

## Invariants (must hold after every operation)

```
INV 1:  F₁ ∪ F₂ = E                     (every edge is in exactly one layer)
INV 2:  F₁ is a valid spanning forest of G  (no cycles in skeleton)
INV 3:  dist[v] = δ(source, v) for all v    (distances are exact)
INV 4:  heat[e] ≤ W for all edges e         (heat is window-bounded)
INV 5:  ∀ e ∈ F₁ spanning edges: heat[e] ≥ T/2  (only warm edges stay in skeleton)
```
