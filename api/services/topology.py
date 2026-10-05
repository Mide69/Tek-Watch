"""Relationships between resources in the customer's AWS inventory.

The graph uses only relationships the agent reports:
* direct — an explicit configuration relationship, such as a CloudFront
  origin or VPC placement.
* inferred — a possible association based on shared security-group membership.

Shared membership does not establish permitted traffic or actual connectivity.
We do not collect security-group rules or flow logs; connectivity is not verified.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from services.inventory_view import dim

# Services the graph is built from.
TOPOLOGY_SERVICES = ("s3", "cloudfront", "ec2", "lambda", "rds", "elb", "eks")

DIRECT = "direct"
INFERRED = "inferred"

SERVES = "serves"
RUNS_IN = "runs_in"
SHARES_SECURITY_GROUP = "shares_security_group"

# assets.s3.eu-west-2.amazonaws.com, assets.s3.amazonaws.com and the website
# form assets.s3-website-eu-west-2.amazonaws.com all name the bucket first.
_BUCKET_ORIGIN = re.compile(r"^(?P<bucket>[a-z0-9.\-]+)\.s3[.-]", re.IGNORECASE)


@dataclass(frozen=True)
class Node:
    key: str
    service: str
    resource_id: str
    name: str
    region: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {"key": self.key, "service": self.service, "resource_id": self.resource_id,
                "name": self.name, "region": self.region}


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    relationship: str
    confidence: str
    why: str

    def as_dict(self) -> Dict[str, Any]:
        return {"from": self.source, "to": self.target, "relationship": self.relationship,
                "confidence": self.confidence, "why": self.why}


@dataclass
class Graph:
    nodes: Dict[str, Node] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)

    def add_node(self, node: Node) -> None:
        self.nodes.setdefault(node.key, node)

    def add_edge(self, edge: Edge) -> None:
        if edge.source == edge.target:
            return
        if edge.source not in self.nodes or edge.target not in self.nodes:
            return
        seen = {(e.source, e.target, e.relationship) for e in self.edges}
        if (edge.source, edge.target, edge.relationship) not in seen:
            self.edges.append(edge)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [n.as_dict() for n in self.nodes.values()],
            "edges": [e.as_dict() for e in self.edges],
        }


def key_for(service: str, resource_id: str) -> str:
    return f"{service}:{resource_id}"


def _name(resource: Dict[str, Any]) -> str:
    return str(resource.get("resource_name") or resource.get("resource_id") or "unknown")


def _node(service: str, resource: Dict[str, Any]) -> Node:
    resource_id = str(resource.get("resource_id") or _name(resource))
    return Node(
        key=key_for(service, resource_id),
        service=service,
        resource_id=resource_id,
        name=_name(resource),
        region=str(resource.get("region") or ""),
    )


def _groups(resource: Dict[str, Any]) -> Set[str]:
    raw = dim(resource, "security_groups")
    return {g.strip() for g in raw.split(",") if g.strip()} if raw else set()


def bucket_from_origin(origin: str) -> Optional[str]:
    """The bucket an origin domain names, or None if it is not an S3 origin."""
    match = _BUCKET_ORIGIN.match((origin or "").strip())
    return match.group("bucket") if match else None


def build(inventory: Dict[str, List[Dict[str, Any]]]) -> Graph:
    """The graph of what the customer runs and how it is joined up."""
    graph = Graph()

    for service in TOPOLOGY_SERVICES:
        for resource in inventory.get(service, []):
            graph.add_node(_node(service, resource))

    _add_cloudfront_origins(graph, inventory)
    _add_vpc_membership(graph, inventory)
    _add_shared_security_groups(graph, inventory)
    return graph


def _add_cloudfront_origins(graph: Graph, inventory: Dict[str, List[Dict[str, Any]]]) -> None:
    """CloudFront to the bucket it serves. AWS states this, so it is direct."""
    buckets = {str(b.get("resource_name") or b.get("resource_id")): b for b in inventory.get("s3", [])}
    for distribution in inventory.get("cloudfront", []):
        origins = [o.strip() for o in dim(distribution, "origins").split(",") if o.strip()]
        for origin in origins:
            bucket = bucket_from_origin(origin)
            if not bucket or bucket not in buckets:
                continue
            graph.add_edge(Edge(
                source=_node("cloudfront", distribution).key,
                target=_node("s3", buckets[bucket]).key,
                relationship=SERVES,
                confidence=DIRECT,
                why=f"This distribution serves {bucket} as an origin.",
            ))


def _add_vpc_membership(graph: Graph, inventory: Dict[str, List[Dict[str, Any]]]) -> None:
    """Which network each resource sits in. Used to answer "what is nearby"."""
    for service in ("ec2", "lambda", "rds", "elb", "eks"):
        for resource in inventory.get(service, []):
            vpc = dim(resource, "vpc_id")
            if not vpc:
                continue
            vpc_node = Node(key=key_for("vpc", vpc), service="vpc", resource_id=vpc, name=vpc,
                            region=str(resource.get("region") or ""))
            graph.add_node(vpc_node)
            graph.add_edge(Edge(
                source=_node(service, resource).key,
                target=vpc_node.key,
                relationship=RUNS_IN,
                confidence=DIRECT,
                why=f"Runs inside {vpc}.",
            ))


def _add_shared_security_groups(graph: Graph, inventory: Dict[str, List[Dict[str, Any]]]) -> None:
    """Record shared security-group membership, without inferring connectivity.

    Membership alone does not establish that traffic is permitted. The edge
    remains an inferred association because rules and traffic are not assessed.
    """
    by_group: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
    for service in ("ec2", "lambda", "rds"):
        for resource in inventory.get(service, []):
            for group in _groups(resource):
                by_group.setdefault(group, []).append((service, resource))

    for group, members in by_group.items():
        if len(members) < 2:
            continue
        for i, (service_a, a) in enumerate(members):
            for service_b, b in members[i + 1:]:
                if service_a == service_b and a is b:
                    continue
                graph.add_edge(Edge(
                    source=_node(service_a, a).key,
                    target=_node(service_b, b).key,
                    relationship=SHARES_SECURITY_GROUP,
                    confidence=INFERRED,
                    why=f"Both share security group {group}; connectivity not verified.",
                ))


def _neighbours(graph: Graph, key: str) -> Iterable[Tuple[Edge, str, str]]:
    """(edge, other key, direction) for everything joined to this node."""
    for edge in graph.edges:
        if edge.source == key:
            yield edge, edge.target, "out"
        elif edge.target == key:
            yield edge, edge.source, "in"


def impact(graph: Graph, key: str) -> Dict[str, Any]:
    """Resources related to this resource.

    The legacy reachable_from field holds shared-group associations, not
    verified network reachability. Keep the field name for API compatibility.

    Deliberately one hop. Two hops through a shared VPC reaches everything in
    the account and tells the reader nothing.
    """
    if key not in graph.nodes:
        return {"resource": None, "serves": [], "reachable_from": [], "runs_in": [], "total": 0}

    serves: List[Dict[str, Any]] = []
    reachable: List[Dict[str, Any]] = []
    network: List[Dict[str, Any]] = []

    for edge, other_key, direction in _neighbours(graph, key):
        other = graph.nodes[other_key]
        entry = {
            **other.as_dict(),
            "relationship": edge.relationship,
            "confidence": edge.confidence,
            "why": edge.why,
        }
        if edge.relationship == SERVES:
            # Serving points from the distribution to what it serves, so the
            # interesting direction depends on which end we are standing on.
            serves.append(entry)
        elif edge.relationship == SHARES_SECURITY_GROUP:
            reachable.append(entry)
        elif edge.relationship == RUNS_IN and direction == "out":
            network.append(entry)

    return {
        "resource": graph.nodes[key].as_dict(),
        "serves": serves,
        "reachable_from": reachable,
        "runs_in": network,
        "total": len(serves) + len(reachable),
    }


def summarise(impact_result: Dict[str, Any]) -> str:
    """One plain sentence for a business owner, or "" when there is nothing to say."""
    parts: List[str] = []
    for entry in impact_result.get("serves", []):
        if entry["service"] == "cloudfront":
            parts.append(f"it is published to the internet by CloudFront distribution {entry['name']}")
        else:
            parts.append(f"it serves {entry['name']}")
    others = impact_result.get("reachable_from", [])
    if others:
        names = ", ".join(sorted({e["name"] for e in others})[:3])
        parts.append(
            f"{len(others)} other resource{'s share' if len(others) != 1 else ' shares'} "
            f"a security group with it ({names}); connectivity not verified"
        )
    if not parts:
        return ""
    return "Related resources: " + "; ".join(parts) + "."


def load_inventory(ts: Any, customer_id: str, window: str = "24h") -> Dict[str, List[Dict[str, Any]]]:
    return {svc: ts.get_service_inventory(customer_id, svc, window) for svc in TOPOLOGY_SERVICES}
