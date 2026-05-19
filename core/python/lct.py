"""
Link-Cut Tree (LCT) implementation using splay trees with path-parent pointers.

Supports dynamic forest operations in O(log n) amortized time:
  - link(u, v, w)      : add edge (u,v) with weight w
  - cut(u, v)          : remove edge (u,v)
  - connected(u, v)    : connectivity query
  - path_query(u, v)   : total weight on u-v path
  - path_nodes(u, v)   : list of node IDs on u-v path
  - find_root(v)        : root of the represented tree
  - get_dist / set_dist: distance label storage
  - is_stale / mark_stale / mark_fresh: flush tracking
"""

from __future__ import annotations
from typing import Optional


class LCTNode:
    """
    Splay-tree node used inside the Link-Cut Tree.

    Represented-tree relationship:
      - `parent` is the splay-tree parent OR the path-parent pointer when this
        node is the root of its preferred-path splay tree.
      - `left` / `right` are splay-tree children (within the preferred path).
      - `reversed` is a lazy flag for reversing the path.

    Aggregate:
      - `edge_weight`  : weight of the edge connecting this node to its
                         represented-tree parent (only meaningful when node is
                         NOT the splay-tree root; stored here for convenience).
      - `path_weight`  : sum of all edge_weights in the splay subtree rooted
                         here (including self.edge_weight).
    """

    __slots__ = (
        "id", "left", "right", "parent",
        "reversed",
        "edge_weight", "path_weight",
        "dist", "stale", "heat",
    )

    def __init__(self, node_id: int) -> None:
        self.id: int = node_id
        self.left: Optional[LCTNode] = None
        self.right: Optional[LCTNode] = None
        self.parent: Optional[LCTNode] = None

        self.reversed: bool = False

        self.edge_weight: float = 0.0   # weight of edge to represented-tree parent
        self.path_weight: float = 0.0   # aggregate over splay subtree

        self.dist: float = float("inf")  # SSSP distance label
        self.stale: bool = False         # needs distance flush
        self.heat: int = 0               # heat score for promotion/demotion


# ---------------------------------------------------------------------------
# Helper predicates
# ---------------------------------------------------------------------------

def _is_root(x: LCTNode) -> bool:
    """True iff x is the root of its splay tree (i.e., parent is a path-parent)."""
    p = x.parent
    return p is None or (p.left is not x and p.right is not x)


def _pull_up(x: LCTNode) -> None:
    """Recompute path_weight from children."""
    s = x.edge_weight
    if x.left:
        s += x.left.path_weight
    if x.right:
        s += x.right.path_weight
    x.path_weight = s


def _push_down(x: LCTNode) -> None:
    """Push lazy reversal tag to children."""
    if x.reversed:
        x.left, x.right = x.right, x.left
        if x.left:
            x.left.reversed ^= True
        if x.right:
            x.right.reversed ^= True
        x.reversed = False


# ---------------------------------------------------------------------------
# Splay operations
# ---------------------------------------------------------------------------

def _rotate(x: LCTNode) -> None:
    """Single rotation of x with its parent."""
    p = x.parent
    g = p.parent

    # Identify which child x is
    if p.left is x:
        # x is left child → right rotation
        p.left = x.right
        if x.right:
            x.right.parent = p
        x.right = p
    else:
        # x is right child → left rotation
        p.right = x.left
        if x.left:
            x.left.parent = p
        x.left = p

    # Re-parent x
    x.parent = g
    p.parent = x

    # Fix grandparent
    if g is not None:
        if g.left is p:
            g.left = x
        elif g.right is p:
            g.right = x
        # else: g is a path-parent pointer — leave g.left / g.right alone

    _pull_up(p)
    _pull_up(x)


def _splay(x: LCTNode) -> None:
    """
    Splay x to the root of its splay tree.
    Pushes tags top-down along the splay-root path first.
    """
    # Collect ancestors up to splay-tree root to push tags top-down
    stack: list[LCTNode] = []
    cur: LCTNode = x
    while not _is_root(cur):
        stack.append(cur)
        cur = cur.parent  # type: ignore[assignment]
    stack.append(cur)  # the splay root itself

    # Push tags from root downward
    while stack:
        _push_down(stack.pop())

    # Now splay x up
    while not _is_root(x):
        p = x.parent
        g = p.parent
        if not _is_root(p):
            assert g is not None
            # Zig-zig or zig-zag
            if (g.left is p) == (p.left is x):
                _rotate(p)
            else:
                _rotate(x)
        _rotate(x)


# ---------------------------------------------------------------------------
# Access / make_root
# ---------------------------------------------------------------------------

def _access(x: LCTNode) -> LCTNode:
    """
    Makes x the rightmost node on its preferred path (the path from x to the
    root of the represented tree).  Returns the last node whose preferred child
    changed (used in make_root).
    """
    last: Optional[LCTNode] = None
    cur: LCTNode = x
    while cur is not None:
        _splay(cur)
        cur.right = last        # detach old preferred child, attach new one
        _pull_up(cur)
        last = cur
        cur = cur.parent        # follow path-parent pointer
    _splay(x)
    return last  # type: ignore[return-value]


def _make_root(x: LCTNode) -> None:
    """Make x the root of its represented tree."""
    _access(x)
    x.reversed ^= True
    _push_down(x)


def _find_root(x: LCTNode) -> LCTNode:
    """Return the root of the represented tree containing x."""
    _access(x)
    # Root is the leftmost node in the splay tree
    _push_down(x)
    while x.left:
        x = x.left
        _push_down(x)
    _splay(x)  # keep amortized balance
    return x


# ---------------------------------------------------------------------------
# Public Link-Cut Tree class
# ---------------------------------------------------------------------------

class LinkCutTree:
    """
    Link-Cut Tree for the ADAPTSKEL skeleton layer (F₁).

    Node IDs are arbitrary non-negative integers; nodes must be registered
    with add_node() before being used.
    """

    def __init__(self) -> None:
        self._nodes: dict[int, LCTNode] = {}
        self._edges: set[tuple[int, int]] = set()       # canonical (min,max) pairs
        self._edge_weights: dict[tuple[int, int], float] = {}  # canonical key -> weight

    # ------------------------------------------------------------------
    # Node management
    # ------------------------------------------------------------------

    def add_node(self, v: int) -> None:
        """Register a new isolated node."""
        if v not in self._nodes:
            self._nodes[v] = LCTNode(v)

    def _node(self, v: int) -> LCTNode:
        if v not in self._nodes:
            self.add_node(v)
        return self._nodes[v]

    # ------------------------------------------------------------------
    # Distance / stale labels
    # ------------------------------------------------------------------

    def get_dist(self, v: int) -> float:
        return self._node(v).dist

    def set_dist(self, v: int, d: float) -> None:
        self._node(v).dist = d

    def is_stale(self, v: int) -> bool:
        return self._node(v).stale

    def mark_stale(self, v: int) -> None:
        self._node(v).stale = True

    def mark_fresh(self, v: int) -> None:
        self._node(v).stale = False

    # ------------------------------------------------------------------
    # Heat
    # ------------------------------------------------------------------

    def get_heat(self, v: int) -> int:
        return self._node(v).heat

    def set_heat(self, v: int, h: int) -> None:
        self._node(v).heat = h

    # ------------------------------------------------------------------
    # Core LCT operations
    # ------------------------------------------------------------------

    def link(self, u: int, v: int, w: float) -> None:
        """
        Add edge (u,v,w) between two different trees.
        Precondition: u and v are in different trees.
        """
        nu = self._node(u)
        nv = self._node(v)
        _make_root(nu)
        # nu is now root; attach it under nv
        _access(nv)
        nu.parent = nv
        nu.edge_weight = w
        _pull_up(nu)
        # Record canonical edge
        key = (min(u, v), max(u, v))
        self._edges.add(key)
        self._edge_weights[key] = w

    def cut(self, u: int, v: int) -> None:
        """
        Remove edge (u,v).
        Precondition: (u,v) exists in the LCT.
        """
        nu = self._node(u)
        nv = self._node(v)
        _make_root(nu)
        _access(nv)
        # After make_root(u) and access(v), u should be nv.left
        assert nv.left is nu, "LCT.cut: u is not adjacent to v in splay tree"
        nv.left = None
        nu.parent = None
        nu.edge_weight = 0.0
        _pull_up(nv)
        key = (min(u, v), max(u, v))
        self._edges.discard(key)
        self._edge_weights.pop(key, None)

    def connected(self, u: int, v: int) -> bool:
        """Return True if u and v are in the same tree."""
        if u == v:
            return True
        nu = self._node(u)
        nv = self._node(v)
        return _find_root(nu) is _find_root(nv)

    def find_root(self, v: int) -> int:
        """Return the ID of the root of the tree containing v."""
        return _find_root(self._node(v)).id

    def path_query(self, u: int, v: int) -> float:
        """Return sum of edge weights on the path from u to v.

        Uses path_nodes traversal + edge weight dict to avoid the aggregation
        issue that arises from make_root reversals changing edge directions.
        O(path length) but correct for all tree shapes.
        """
        nodes = self.path_nodes(u, v)
        total = 0.0
        for i in range(len(nodes) - 1):
            key = (min(nodes[i], nodes[i + 1]), max(nodes[i], nodes[i + 1]))
            total += self._edge_weights.get(key, 0.0)
        return total

    def path_nodes(self, u: int, v: int) -> list[int]:
        """
        Return list of node IDs on the path from u to v (inclusive).
        O(path length).
        """
        nu = self._node(u)
        _make_root(nu)
        nv = self._node(v)
        _access(nv)
        # nv is now the splay root; its splay subtree = the path u..v
        result: list[int] = []
        self._collect_subtree(nv, result)
        return result

    def _collect_subtree(self, node: Optional[LCTNode], out: list[int]) -> None:
        if node is None:
            return
        _push_down(node)
        self._collect_subtree(node.left, out)
        out.append(node.id)
        self._collect_subtree(node.right, out)

    def has_edge(self, u: int, v: int) -> bool:
        """Return True if (u,v) is currently an LCT edge."""
        key = (min(u, v), max(u, v))
        return key in self._edges

    def all_edges(self) -> set[tuple[int, int]]:
        """Return the set of all canonical edge keys."""
        return set(self._edges)

    def get_edge_weight(self, u: int, v: int) -> float:
        """Return the weight of edge (u,v) in O(1) via dict lookup."""
        key = (min(u, v), max(u, v))
        if key not in self._edge_weights:
            raise KeyError(f"Edge ({u},{v}) not in LCT")
        return self._edge_weights[key]

    def __contains__(self, v: int) -> bool:
        return v in self._nodes

    def nodes(self) -> list[int]:
        return list(self._nodes.keys())
