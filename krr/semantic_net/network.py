"""Semantic network built from the frames.

Nodes are concepts (classes), value concepts (SpaceType, ZoneType, ...) and
individuals. Edges are labelled links:

    is-a          subclass link (Student is-a Person)
    instance-of   individual to class (ali instance-of Student)
    has-a         possession / composition (Person has-a ParkingPermit)
    part-of       physical containment (ParkingSpace part-of ParkingZone)
    owns, made-by, for-space, has-type, has-class, grants, fits
                  domain relations

The network is generated from the frame definitions instead of being drawn
by hand, so the diagram always uses the same names as the frames, rules
and DL axioms. Inheritance works the same way as in frames: a node
inherits the outgoing relation edges of every concept above it on is-a.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from ..frames.frames import FrameSystem
from ..frames.ontology import build_frames
from ..knowledge_base.facts import POLICY_FACTS

STRUCTURAL = ("is-a", "instance-of")

# Value concepts: a symbolic slot becomes a node of its own.
VALUE_CONCEPTS = {"vehicleType": "VehicleType", "spaceType": "SpaceType",
                  "zoneType": "ZoneType", "permitClass": "PermitClass"}


@dataclass(frozen=True)
class Edge:
    source: str
    label: str
    target: str


class SemanticNetwork:
    def __init__(self) -> None:
        self.nodes: dict[str, str] = {}      # name -> kind (class, value, instance, literal)
        self.edges: list[Edge] = []

    def add_node(self, name: str, kind: str) -> None:
        self.nodes.setdefault(name, kind)

    def add_edge(self, source: str, label: str, target: str) -> None:
        edge = Edge(source, label, target)
        if edge not in self.edges:
            self.edges.append(edge)

    # ----- queries -------------------------------------------------------
    def out_edges(self, node: str) -> list[Edge]:
        return [e for e in self.edges if e.source == node]

    def in_edges(self, node: str) -> list[Edge]:
        return [e for e in self.edges if e.target == node]

    def superconcepts(self, node: str) -> list[str]:
        """Everything reachable upward along instance-of and is-a."""
        result, frontier = [], [node]
        while frontier:
            current = frontier.pop(0)
            for e in self.out_edges(current):
                if e.label in STRUCTURAL and e.target not in result:
                    result.append(e.target)
                    frontier.append(e.target)
        return result

    def inherited_relations(self, node: str) -> list[tuple[str, str, str]]:
        """(label, target, from_concept) for relations a node inherits along is-a."""
        out = []
        for concept in self.superconcepts(node):
            for e in self.out_edges(concept):
                if e.label not in STRUCTURAL:
                    out.append((e.label, e.target, concept))
        return out

    def path(self, start: str, goal: str) -> list[Edge] | None:
        """Shortest chain of links between two nodes, ignoring direction."""
        if start not in self.nodes or goal not in self.nodes:
            return None
        previous: dict[str, tuple[str, Edge] | None] = {start: None}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            if current == goal:
                break
            for e in self.edges:
                for a, b in ((e.source, e.target), (e.target, e.source)):
                    if a == current and b not in previous:
                        previous[b] = (current, e)
                        queue.append(b)
        if goal not in previous:
            return None
        chain, node = [], goal
        while previous[node] is not None:
            node, edge = previous[node]
            chain.append(edge)
        return list(reversed(chain))

    # ----- export --------------------------------------------------------
    def to_mermaid(self, direction: str = "LR") -> str:
        ids = {n: f"n{i}" for i, n in enumerate(self.nodes)}
        lines = [f"flowchart {direction}"]
        shape = {"class": ("[", "]"), "value": ("([", "])"), "instance": ("(", ")"),
                 "literal": ("[/", "/]")}
        for name, kind in self.nodes.items():
            left, right = shape.get(kind, ("[", "]"))
            lines.append(f'    {ids[name]}{left}"{name}"{right}')
        for e in self.edges:
            arrow = "-.->" if e.label in ("instance-of",) else "-->"
            lines.append(f'    {ids[e.source]} {arrow}|"{e.label}"| {ids[e.target]}')
        css = {"class": ("conceptNode", "fill:#dbeafe,stroke:#1e40af,color:#0f172a"),
               "value": ("valueNode", "fill:#fef3c7,stroke:#b45309,color:#0f172a"),
               "instance": ("individualNode", "fill:#dcfce7,stroke:#15803d,color:#0f172a")}
        for kind, (name, rule) in css.items():
            members = [ids[n] for n, k in self.nodes.items() if k == kind]
            if members:
                lines.append(f"    classDef {name} {rule}")
                lines.append(f"    class {','.join(members)} {name}")
        return "\n".join(lines)

    def to_dot(self, rankdir: str = "LR") -> str:
        style = {"class": 'shape=box, style="rounded,filled", fillcolor="#dbeafe", color="#1e40af"',
                 "value": 'shape=ellipse, style=filled, fillcolor="#fef3c7", color="#b45309"',
                 "instance": 'shape=box, style=filled, fillcolor="#dcfce7", color="#15803d"',
                 "literal": 'shape=note'}
        edge_style = {"is-a": 'color="#1e40af", penwidth=2',
                      "instance-of": 'style=dashed, color="#15803d"',
                      "part-of": 'color="#7c3aed"', "has-a": 'color="#b91c1c"'}
        lines = ["digraph SemanticNetwork {", f"  rankdir={rankdir};",
                 '  node [fontname="Helvetica", fontsize=11];',
                 '  edge [fontname="Helvetica", fontsize=9];']
        for name, kind in self.nodes.items():
            lines.append(f'  "{name}" [{style.get(kind, "")}];')
        for e in self.edges:
            extra = edge_style.get(e.label, 'color="#475569"')
            lines.append(f'  "{e.source}" -> "{e.target}" [label="{e.label}", {extra}];')
        lines.append("}")
        return "\n".join(lines)


def build_class_network(fs: FrameSystem | None = None, with_policy: bool = True) -> SemanticNetwork:
    """Concept-level network: every class frame, its is-a links and its relations."""
    fs = fs or build_frames()
    net = SemanticNetwork()
    for frame in fs.classes():
        net.add_node(frame.name, "class")
    for frame in fs.classes():
        if frame.isa:
            net.add_edge(frame.name, "is-a", frame.isa)
        for slot in frame.slots.values():
            spec = fs.slot_specs(frame.name)[slot.name]
            if spec.type.startswith("frame:"):
                net.add_edge(frame.name, spec.relation or slot.name, spec.type.split(":", 1)[1])
            elif slot.name in VALUE_CONCEPTS and spec.relation and slot.range:
                value_node = VALUE_CONCEPTS[slot.name]
                net.add_node(value_node, "value")
                net.add_edge(frame.name, spec.relation, value_node)
    if with_policy:
        net.add_edge("PermitClass", "grants", "ZoneType")
        net.add_edge("VehicleType", "fits", "SpaceType")
    return net


def build_instance_network(individuals: list[str], fs: FrameSystem | None = None,
                           include_policy_values: bool = True) -> SemanticNetwork:
    """Individuals, the classes they belong to and the links between them.

    Starting from the given individuals, linked individuals one step away
    (ali -> car_ali, p_ali) are pulled in as well.
    """
    fs = fs or build_frames()
    net = SemanticNetwork()
    todo, done = list(individuals), set()
    while todo:
        name = todo.pop(0)
        if name in done or name not in fs.frames:
            continue
        done.add(name)
        frame = fs.frames[name]
        net.add_node(name, "instance")
        net.add_node(frame.isa, "class")
        net.add_edge(name, "instance-of", frame.isa)
        for slot_name, spec in fs.slot_specs(name).items():
            value = fs.value(name, slot_name) if spec.if_needed is None else None
            if value is None:
                continue
            values = value if isinstance(value, list) else [value]
            if spec.type.startswith("frame:"):
                for v in values:
                    net.add_node(v, "instance")
                    net.add_edge(name, spec.relation or slot_name, v)
                    if len(done) + len(todo) < 12:
                        todo.append(v)
            elif slot_name in VALUE_CONCEPTS and include_policy_values:
                for v in values:
                    net.add_node(v, "value")
                    net.add_edge(name, spec.relation or slot_name, v)
    # Add the class hierarchy above every class that appeared.
    for cls in [n for n, k in list(net.nodes.items()) if k == "class"]:
        for parent in fs.ancestors(cls)[1:]:
            net.add_node(parent, "class")
        chain = fs.ancestors(cls)
        for child, parent in zip(chain, chain[1:]):
            net.add_edge(child, "is-a", parent)
    if include_policy_values:
        for fact in POLICY_FACTS:
            if fact[0] in ("grants", "fits") and fact[1] in net.nodes and fact[2] in net.nodes:
                net.add_edge(fact[1], fact[0], fact[2])
    return net


def build_full_network() -> SemanticNetwork:
    """Class level plus one worked example (Ali and Zara's reservation)."""
    fs = build_frames()
    net = build_class_network(fs)
    inst = build_instance_network(["ali", "r1"], fs, include_policy_values=False)
    for name, kind in inst.nodes.items():
        net.add_node(name, kind)
    for e in inst.edges:
        net.add_edge(e.source, e.label, e.target)
    return net
