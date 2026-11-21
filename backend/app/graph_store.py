"""The SchemeSetu knowledge graph.

Three jobs:

1. **Load** ``data/schemes.json`` into typed models, keyed by the file's mtime
   so Rule Studio edits show up instantly.
2. **Build** a graph of ``scheme <-> rule <-> document <-> field <-> source``.
   This is where explainability lives: a match is never "because the model
   said so", it is a path ``your fact -> field -> rule -> scheme``.
3. **Merge** the graphify extraction output (``graphify-out/graph.json``) when
   it exists, preserving its ``EXTRACTED | INFERRED | AMBIGUOUS`` edge tags -
   exactly how we mark how confident we are in each connection.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

import networkx as nx

from . import rule_engine as engine
from .config import settings
from .models import Profile, Scheme, SchemeBook


@dataclass
class GraphBundle:
    """Everything the API needs: the curated data plus the graph over it."""

    book: SchemeBook
    graph: nx.MultiDiGraph
    source_path: str
    loaded_at: str
    graphify: dict[str, Any] = field(default_factory=dict)

    @property
    def schemes(self) -> list[Scheme]:
        return self.book.schemes

    @property
    def categories(self) -> dict[str, str]:
        return dict(self.book.meta.get("categories", {}))

    def scheme(self, scheme_id: str) -> Optional[Scheme]:
        for s in self.book.schemes:
            if s.id == scheme_id:
                return s
        return None


_CACHE: dict[str, Any] = {"bundle": None, "mtime": None, "graphify_mtime": None}


# --------------------------------------------------------------------------- #
# 1. loading
# --------------------------------------------------------------------------- #
def load_book(path: Any | None = None) -> SchemeBook:
    """Read the curated scheme book from disk."""
    target = path or settings.schemes_path
    with open(target, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    book = SchemeBook(**raw)
    if not book.meta.get("categories"):
        book.meta["categories"] = {}
    return book


def _mtime(path: Any) -> Optional[float]:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def get_bundle(force: bool = False) -> GraphBundle:
    """Cached bundle; reloads automatically when the data files change."""
    path = settings.schemes_path
    mtime = _mtime(path)
    g_path = settings.graphify_out
    g_mtime = _mtime(g_path)
    if (
        force
        or _CACHE["bundle"] is None
        or _CACHE["mtime"] != mtime
        or _CACHE["graphify_mtime"] != g_mtime
    ):
        book = load_book(path)
        graph = build_graph(book)
        graphify = import_graphify(graph, book)
        _CACHE.update(
            {
                "bundle": GraphBundle(
                    book=book,
                    graph=graph,
                    source_path=str(path),
                    loaded_at=date.today().isoformat(),
                    graphify=graphify,
                ),
                "mtime": mtime,
                "graphify_mtime": g_mtime,
            }
        )
    return _CACHE["bundle"]


def invalidate() -> None:
    _CACHE.update({"bundle": None, "mtime": None, "graphify_mtime": None})


# --------------------------------------------------------------------------- #
# 2. building the graph
# --------------------------------------------------------------------------- #
def build_graph(book: SchemeBook) -> nx.MultiDiGraph:
    """Nodes and edges for schemes, rules, documents, fields, categories, sources."""
    g = nx.MultiDiGraph()
    labels = book.meta.get("categories", {})

    for scheme in book.schemes:
        sid = f"scheme:{scheme.id}"
        g.add_node(
            sid,
            kind="scheme",
            label=scheme.name,
            level=scheme.level,
            category=scheme.category,
            benefit_value_inr=scheme.benefit_value_inr,
            provenance=scheme.provenance,
            verified_on=scheme.verified_on,
            source_url=scheme.source_url,
            origin="curated",
        )

        cat = f"category:{scheme.category}"
        g.add_node(cat, kind="category", label=labels.get(scheme.category, scheme.category), origin="curated")
        g.add_edge(sid, cat, rel="in_category", provenance="EXTRACTED")

        src = f"source:{scheme.id}"
        g.add_node(
            src,
            kind="source",
            label=scheme.source_name or scheme.source_url,
            url=scheme.source_url,
            verified_on=scheme.verified_on,
            origin="curated",
        )
        g.add_edge(sid, src, rel="verified_from", provenance=scheme.provenance)

        for rule in scheme.rules:
            rid = f"rule:{scheme.id}::{rule.id}"
            g.add_node(
                rid,
                kind="rule",
                label=rule.text or rule.id,
                rule_id=rule.id,
                scheme_id=scheme.id,
                field=rule.field,
                op=rule.op,
                value=rule.value,
                hard=rule.hard,
                weight=rule.weight,
                source_note=rule.source_note,
                provenance=scheme.provenance,
                origin="curated",
            )
            g.add_edge(rid, sid, rel="required_by", provenance=scheme.provenance, hard=rule.hard)
            fid = f"field:{rule.field}"
            g.add_node(fid, kind="field", label=engine.field_label(rule.field), field=rule.field, origin="curated")
            g.add_edge(fid, rid, rel="tests", provenance=scheme.provenance)

        for doc in scheme.documents:
            did = f"doc:{scheme.id}::{doc.id}"
            g.add_node(
                did,
                kind="document",
                label=doc.label,
                scheme_id=scheme.id,
                mandatory=doc.mandatory,
                how_to_get=doc.how_to_get,
                origin="curated",
            )
            g.add_edge(
                sid, did, rel="needs_document", provenance=scheme.provenance, mandatory=doc.mandatory
            )

    return g


# --------------------------------------------------------------------------- #
# 3. graphify import (provenance-tagged extraction output)
# --------------------------------------------------------------------------- #
def _norm_name(text: str) -> str:
    return "".join(ch for ch in str(text).lower() if ch.isalnum())


def import_graphify(g: nx.MultiDiGraph, book: SchemeBook) -> dict[str, Any]:
    """Merge ``graphify-out/graph.json`` into the curated graph.

    Graphify gives us document-derived nodes and, crucially, one evidence tag
    per edge. We keep the tag as-is and additionally *bridge* each extracted
    node to a curated scheme or rule, so the UI can show "this rule came from
    this document".
    """
    info: dict[str, Any] = {
        "imported": False,
        "path": str(settings.graphify_out),
        "nodes": 0,
        "links": 0,
        "bridged": 0,
        "by_provenance": {"EXTRACTED": 0, "INFERRED": 0, "AMBIGUOUS": 0, "UNKNOWN": 0},
        "note": "",
    }
    if not settings.graphify_auto_import:
        info["note"] = "GRAPHIFY_AUTO_IMPORT=0 - skipped."
        return info

    path = settings.graphify_out
    if not path.exists():
        info["note"] = (
            "No graphify output yet. Run scripts/graphify_build.ps1 to extract the scheme "
            "documents into graphify-out/graph.json; the app works fully without it."
        )
        return info

    try:
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        info["note"] = f"Could not read graphify output: {exc}"
        return info

    nodes = payload.get("nodes") or payload.get("entities") or []
    links = payload.get("links") or payload.get("edges") or payload.get("relationships") or []

    by_name: dict[str, str] = {}
    for scheme in book.schemes:
        by_name[_norm_name(scheme.name)] = f"scheme:{scheme.id}"
        by_name[_norm_name(scheme.id)] = f"scheme:{scheme.id}"
    for scheme_id, rule in _all_rules(book):
        by_name[_norm_name(rule.id)] = f"rule:{scheme_id}::{rule.id}"

    id_map: dict[str, str] = {}
    for node in nodes:
        raw_id = str(node.get("id") or node.get("name") or "")
        if not raw_id:
            continue
        nid = f"gfy:{raw_id}"
        id_map[raw_id] = nid
        g.add_node(
            nid,
            kind=str(node.get("type") or node.get("kind") or "extracted"),
            label=str(node.get("name") or node.get("label") or raw_id),
            origin="graphify",
            source_file=str(node.get("source") or node.get("file") or ""),
            provenance=str(node.get("provenance") or node.get("evidence") or "EXTRACTED").upper(),
            description=str(node.get("description") or node.get("summary") or "")[:400],
        )
    info["nodes"] = len(id_map)

    bridged = 0
    for link in links:
        a = str(link.get("source") or link.get("from") or "")
        b = str(link.get("target") or link.get("to") or "")
        if a not in id_map or b not in id_map:
            continue
        tag = str(link.get("provenance") or link.get("evidence") or "EXTRACTED").upper()
        tag = tag if tag in info["by_provenance"] else "UNKNOWN"
        info["by_provenance"][tag] += 1
        g.add_edge(
            id_map[a],
            id_map[b],
            rel=str(link.get("rel") or link.get("relation") or link.get("type") or "related"),
            provenance=tag,
            origin="graphify",
            evidence=str(link.get("evidence_text") or link.get("context") or "")[:300],
        )
        info["links"] += 1
        for raw in (a, b):
            target = by_name.get(_norm_name(raw))
            if target:
                g.add_edge(id_map[raw], target, rel="graphify_evidence", provenance=tag, origin="graphify")
                bridged += 1

    info["bridged"] = bridged
    info["imported"] = True
    info["note"] = (
        f"Merged {info['nodes']} extracted nodes and {info['links']} tagged edges; "
        f"{bridged} evidence links bridge into the curated schemes and rules."
    )
    return info


def _all_rules(book: SchemeBook) -> list[tuple[str, Any]]:
    pairs: list[tuple[str, Any]] = []
    for scheme in book.schemes:
        for rule in scheme.rules:
            pairs.append((scheme.id, rule))
    return pairs


# --------------------------------------------------------------------------- #
# 4. reasoning paths + payloads for the interactive graph view
# --------------------------------------------------------------------------- #
_STATUS_REL = {"pass": "satisfies", "fail": "violates", "unknown": "undetermined"}


def node_payload(g: nx.MultiDiGraph, node_id: str) -> dict[str, Any]:
    data = dict(g.nodes[node_id])
    data["id"] = node_id
    return data


def edge_payload(u: str, v: str, key: Any, data: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {"id": f"{u}->{v}::{key}", "source": u, "target": v}
    payload.update(data)
    return payload


def reasoning_paths(bundle: GraphBundle, profile: Profile, limit: int = 600) -> list[dict[str, Any]]:
    """Every ``fact -> field -> rule -> scheme`` path with its live status.

    This is the raw material for PS5's "show which rule each match is based on".
    """
    out: list[dict[str, Any]] = []
    known = profile.known()
    for scheme in bundle.schemes:
        for rule in scheme.rules:
            result = engine.evaluate_rule(rule, profile, scheme.provenance)
            answered = rule.field in known
            out.append(
                {
                    "scheme_id": scheme.id,
                    "scheme_name": scheme.name,
                    "rule_id": rule.id,
                    "rule_node": f"rule:{scheme.id}::{rule.id}",
                    "field": rule.field,
                    "field_label": engine.field_label(rule.field),
                    "fact_node": f"fact:{rule.field}" if answered else f"missing:{rule.field}",
                    "fact_value": known.get(rule.field),
                    "status": result.status,
                    "hard": rule.hard,
                    "weight": rule.weight,
                    "rule_text": rule.text,
                    "reason": result.reason,
                    "source_note": rule.source_note,
                    "provenance": scheme.provenance,
                    "answered": answered,
                    "path": [
                        f"fact:{rule.field}" if answered else f"missing:{rule.field}",
                        f"rule:{scheme.id}::{rule.id}",
                        f"scheme:{scheme.id}",
                    ],
                }
            )
            if len(out) >= limit:
                return out
    return out


def subgraph_for_profile(
    bundle: GraphBundle,
    profile: Profile,
    matches: list[Any] | None = None,
    include_not_eligible: bool = True,
    max_edges: int = 2000,
) -> dict[str, Any]:
    """Nodes + edges for the live reasoning graph, coloured by rule status."""
    g = bundle.graph
    matches = matches or []
    verdict_of = {m.scheme_id: m for m in matches}
    known = profile.known()

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    def add(node_id: str, **attrs: Any) -> None:
        base = node_payload(g, node_id) if node_id in g else {"id": node_id}
        base.update(attrs)
        nodes[node_id] = base

    truncated = False
    for scheme in bundle.schemes:
        if truncated:
            break
        match = verdict_of.get(scheme.id)
        if match is not None and match.verdict == "not_eligible" and not include_not_eligible:
            continue
        sid = f"scheme:{scheme.id}"
        add(
            sid,
            kind="scheme",
            label=scheme.name,
            verdict=getattr(match, "verdict", None),
            confidence=getattr(match, "confidence", None),
            benefit_value_inr=scheme.benefit_value_inr,
        )
        for rule in scheme.rules:
            rid = f"rule:{scheme.id}::{rule.id}"
            result = engine.evaluate_rule(rule, profile, scheme.provenance)
            add(
                rid,
                kind="rule",
                label=rule.text or rule.id,
                status=result.status,
                hard=rule.hard,
                weight=rule.weight,
                field=rule.field,
                reason=result.reason,
                expected=rule.value,
                provenance=scheme.provenance,
                source_note=rule.source_note,
                scheme_id=scheme.id,
            )
            edges.append(
                {
                    "id": f"{rid}->{sid}",
                    "source": rid,
                    "target": sid,
                    "rel": "required_by",
                    "status": result.status,
                    "provenance": scheme.provenance,
                    "origin": "curated",
                    "hard": rule.hard,
                }
            )
            if result.status == "unknown":
                fid = f"missing:{rule.field}"
                add(
                    fid,
                    kind="missing",
                    label=engine.field_label(rule.field),
                    field=rule.field,
                    question=engine.field_question(rule.field),
                    status="unknown",
                )
                edges.append(
                    {
                        "id": f"{fid}->{rid}",
                        "source": fid,
                        "target": rid,
                        "rel": "undetermined",
                        "status": "unknown",
                        "provenance": "EXTRACTED",
                        "origin": "curated",
                    }
                )
            else:
                fact = f"fact:{rule.field}"
                add(
                    fact,
                    kind="fact",
                    label=engine.field_label(rule.field),
                    field=rule.field,
                    value=known.get(rule.field),
                    display_value=engine.format_value(known.get(rule.field)),
                )
                edges.append(
                    {
                        "id": f"{fact}->{rid}",
                        "source": fact,
                        "target": rid,
                        "rel": _STATUS_REL[result.status],
                        "status": result.status,
                        "provenance": "EXTRACTED",
                        "origin": "curated",
                    }
                )
            if len(edges) >= max_edges:
                truncated = True
                break

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "truncated": truncated,
        "graphify": bundle.graphify,
    }


def neighbourhood(bundle: GraphBundle, node_id: str, depth: int = 1) -> dict[str, Any]:
    """Click-to-explore: everything within ``depth`` hops of a node."""
    g = bundle.graph
    if node_id not in g:
        return {"nodes": [], "edges": [], "centre": node_id, "found": False}
    undirected = g.to_undirected(as_view=True)
    seen = {node_id}
    frontier = {node_id}
    for _ in range(max(1, min(depth, 3))):
        nxt: set[str] = set()
        for n in frontier:
            nxt.update(undirected.neighbors(n))
        nxt -= seen
        seen |= nxt
        frontier = nxt
    nodes = [node_payload(g, n) for n in seen]
    edges = [
        edge_payload(u, v, key, data)
        for u, v, key, data in g.edges(keys=True, data=True)
        if u in seen and v in seen
    ]
    return {"nodes": nodes, "edges": edges, "centre": node_id, "found": True}


def graph_stats(bundle: GraphBundle) -> dict[str, Any]:
    """Counts for the graph-health panel."""
    g = bundle.graph
    by_kind: dict[str, int] = {}
    for _, data in g.nodes(data=True):
        kind = str(data.get("kind", "unknown"))
        by_kind[kind] = by_kind.get(kind, 0) + 1
    by_rel: dict[str, int] = {}
    by_prov: dict[str, int] = {}
    for _, _, data in g.edges(data=True):
        rel = str(data.get("rel", "related"))
        by_rel[rel] = by_rel.get(rel, 0) + 1
        prov = str(data.get("provenance", "EXTRACTED")).upper()
        by_prov[prov] = by_prov.get(prov, 0) + 1
    return {
        "nodes": g.number_of_nodes(),
        "edges": g.number_of_edges(),
        "nodes_by_kind": by_kind,
        "edges_by_rel": by_rel,
        "edges_by_provenance": by_prov,
        "schemes": len(bundle.schemes),
        "rules": sum(len(s.rules) for s in bundle.schemes),
        "documents": sum(len(s.documents) for s in bundle.schemes),
        "fields_used": by_kind.get("field", 0),
        "graphify": bundle.graphify,
        "loaded_at": bundle.loaded_at,
        "source_path": bundle.source_path,
    }


def search(bundle: GraphBundle, query: str, limit: int = 25) -> list[dict[str, Any]]:
    """Substring search over node labels (graph explorer + spotlight search)."""
    needle = query.strip().lower()
    if not needle:
        return []
    g = bundle.graph
    hits: list[dict[str, Any]] = []
    for node_id, data in g.nodes(data=True):
        label = str(data.get("label", ""))
        if needle in label.lower() or needle in node_id.lower():
            hits.append(node_payload(g, node_id))
    hits.sort(key=lambda d: (str(d.get("kind", "")) != "scheme", len(str(d.get("label", "")))))
    return hits[:limit]
