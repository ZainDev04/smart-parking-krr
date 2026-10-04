"""Mermaid diagrams generated from the knowledge base itself.

Generated diagrams cannot drift from the code: rename a slot or a class and
the next build redraws the picture. Hand-drawn diagrams (architecture,
chaining flowcharts) live in docs/diagrams/*.mmd.
"""

from __future__ import annotations

from ..frames.frames import FrameSystem
from ..frames.ontology import build_frames
from ..logic.description_logic import DLReasoner
from ..semantic_net.network import (build_class_network, build_full_network,
                                    build_instance_network)


def frame_hierarchy(fs: FrameSystem | None = None) -> str:
    """Class frames with their own slots and facets, ISA links and relation links."""
    fs = fs or build_frames()
    lines = ["classDiagram", "    direction LR"]
    for frame in fs.classes():
        lines.append(f"    class {frame.name} {{")
        for slot in frame.slots.values():
            spec = fs.slot_specs(frame.name)[slot.name]
            kind = spec.type.split(":", 1)[1] if spec.type.startswith("frame:") else spec.type
            text = f"{slot.name} : {kind}"
            if spec.cardinality == "multiple":
                text += " [many]"
            if slot.default is not None:
                text += f" default={slot.default}"
            if spec.if_needed is not None:
                text += " if-needed"
            lines.append(f"        {text}")
        lines.append("    }")
    for frame in fs.classes():
        if frame.isa:
            lines.append(f"    {frame.isa} <|-- {frame.name} : ISA")
    for frame in fs.classes():
        for slot in frame.slots.values():
            spec = fs.slot_specs(frame.name)[slot.name]
            if spec.type.startswith("frame:"):
                target = spec.type.split(":", 1)[1]
                lines.append(f"    {frame.name} --> {target} : {slot.name}")
    return "\n".join(lines)


def semantic_network_classes() -> str:
    return build_class_network().to_mermaid("LR")


def semantic_network_full() -> str:
    return build_full_network().to_mermaid("LR")


def semantic_network_instance(individuals: list[str]) -> str:
    return build_instance_network(individuals).to_mermaid("LR")


def dl_hierarchy() -> str:
    """Classified concept hierarchy (direct parents only). Dashed = inferred."""
    reasoner = DLReasoner()
    parents = reasoner.direct_parents()
    inferred = {(a, b) for a, b, inf in reasoner.classify() if inf}
    defined = set(reasoner.definitions)
    lines = ["flowchart RL"]
    names = reasoner.concept_names()
    for n in names:
        shape = f'{n}(["{n}"])' if n in defined else f'{n}["{n}"]'
        lines.append(f"    {shape}")
    for child, ps in parents.items():
        for p in ps:
            arrow = "-.->" if (child, p) in inferred else "-->"
            lines.append(f"    {child} {arrow} {p}")
    lines.append("    classDef defined fill:#fef3c7,stroke:#b45309")
    if defined:
        lines.append(f"    class {','.join(sorted(defined))} defined")
    return "\n".join(lines)


GENERATED = {
    "frame_hierarchy": frame_hierarchy,
    "semantic_network": semantic_network_classes,
    "semantic_network_example": semantic_network_full,
    "dl_hierarchy": dl_hierarchy,
}
