"""A small frame system with slots, facets, defaults and inheritance.

Vocabulary used in the report and the viva:

* Frame      a named structure describing a class (Student) or an instance (ali)
* ISA        the parent frame; slots and defaults are inherited along it
* Slot       an attribute or relation of a frame (owns, spaceType, ...)
* Facet      information about a slot:
               value       the filled-in value (instances only)
               default     value assumed when nothing more specific is known
               type        str, int, symbol, or frame:<Class> for a link
               range       allowed symbolic values
               cardinality single or multiple
               if_needed   procedure that computes the value on demand
               predicate   name of the logic predicate the slot becomes
               relation    edge label used in the semantic network

Lookup order for frame.get(slot):
  1. the instance's own value
  2. an if-needed procedure found on the frame or an ancestor
  3. the nearest default found by walking up the ISA chain

Defaults are what make frames different from logic: a subclass can
override an inherited default (AccessibleSpace says spaceType=accessible
although ParkingSpace says standard). Classical logic is monotonic and
cannot "override", so the frame layer settles defaults first and hands the
logic layer one definite value per slot.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


class FrameError(ValueError):
    pass


@dataclass
class Slot:
    name: str
    type: str = "str"
    default: Any = None
    range: Optional[tuple] = None
    cardinality: str = "single"
    if_needed: Optional[Callable[["FrameSystem", "Frame"], Any]] = None
    predicate: Optional[str] = None
    relation: Optional[str] = None
    doc: str = ""

    def facets(self) -> dict[str, Any]:
        """The facets that are actually set, in a fixed order (for display)."""
        shown = {"type": self.type}
        if self.default is not None:
            shown["default"] = self.default
        if self.range:
            shown["range"] = "{" + ", ".join(map(str, self.range)) + "}"
        if self.cardinality != "single":
            shown["cardinality"] = self.cardinality
        if self.if_needed is not None:
            shown["if-needed"] = self.if_needed.__doc__.strip() if self.if_needed.__doc__ else "procedure"
        if self.predicate:
            shown["predicate"] = self.predicate
        return shown


@dataclass
class Frame:
    name: str
    isa: Optional[str]
    kind: str                                   # "class" or "instance"
    slots: dict[str, Slot] = field(default_factory=dict)      # class frames
    values: dict[str, Any] = field(default_factory=dict)      # instance frames
    predicate: Optional[str] = None             # class membership predicate
    doc: str = ""


@dataclass
class SlotValue:
    value: Any
    source: str          # "own value", "default from X", "if-needed on X", "unknown"


class FrameSystem:
    def __init__(self) -> None:
        self.frames: dict[str, Frame] = {}

    # ----- definition --------------------------------------------------
    def define_class(self, name: str, isa: Optional[str] = None,
                     slots: tuple[Slot, ...] = (), predicate: Optional[str] = None,
                     doc: str = "") -> Frame:
        if isa is not None and isa not in self.frames:
            raise FrameError(f"class {name}: parent {isa} is not defined")
        frame = Frame(name, isa, "class", {s.name: s for s in slots}, {}, predicate, doc)
        self.frames[name] = frame
        return frame

    def define_instance(self, name: str, isa: str, doc: str = "", **values: Any) -> Frame:
        if isa not in self.frames or self.frames[isa].kind != "class":
            raise FrameError(f"instance {name}: class {isa} is not defined")
        specs = self.slot_specs(isa)
        for slot in values:
            if slot not in specs:
                raise FrameError(f"instance {name}: class {isa} has no slot '{slot}'")
        frame = Frame(name, isa, "instance", {}, dict(values), None, doc)
        self.frames[name] = frame
        return frame

    # ----- hierarchy ---------------------------------------------------
    def ancestors(self, name: str) -> list[str]:
        """The frame itself, then its parent, grandparent, ... up to the root."""
        chain, current = [], name
        while current is not None:
            chain.append(current)
            current = self.frames[current].isa
        return chain

    def is_a(self, name: str, cls: str) -> bool:
        return cls in self.ancestors(name)

    def classes(self) -> list[Frame]:
        return [f for f in self.frames.values() if f.kind == "class"]

    def instances(self, cls: Optional[str] = None) -> list[Frame]:
        return [f for f in self.frames.values()
                if f.kind == "instance" and (cls is None or self.is_a(f.name, cls))]

    def children(self, cls: str) -> list[str]:
        return [f.name for f in self.classes() if f.isa == cls]

    def slot_specs(self, name: str) -> dict[str, Slot]:
        """All slots visible from a frame. A subclass entry overrides its parent's."""
        merged: dict[str, Slot] = {}
        for frame_name in reversed(self.ancestors(name)):
            for slot_name, slot in self.frames[frame_name].slots.items():
                if slot_name in merged:
                    # Override keeps the parent's facets and changes what the child set.
                    parent = merged[slot_name]
                    merged[slot_name] = Slot(
                        slot_name,
                        type=slot.type if slot.type != "str" else parent.type,
                        default=slot.default if slot.default is not None else parent.default,
                        range=slot.range or parent.range,
                        cardinality=parent.cardinality,
                        if_needed=slot.if_needed or parent.if_needed,
                        predicate=slot.predicate or parent.predicate,
                        relation=slot.relation or parent.relation,
                        doc=slot.doc or parent.doc)
                else:
                    merged[slot_name] = slot
        return merged

    def defining_frame(self, name: str, slot: str, facet: str) -> Optional[str]:
        """Which frame in the ISA chain supplies a given facet of a slot."""
        for frame_name in self.ancestors(name):
            spec = self.frames[frame_name].slots.get(slot)
            if spec is not None and getattr(spec, facet) is not None:
                return frame_name
        return None

    # ----- lookup ------------------------------------------------------
    def get(self, name: str, slot: str) -> SlotValue:
        frame = self.frames[name]
        specs = self.slot_specs(name)
        if slot not in specs:
            raise FrameError(f"{name} has no slot '{slot}'")
        if frame.kind == "instance" and slot in frame.values:
            return SlotValue(frame.values[slot], "own value")
        spec = specs[slot]
        if spec.if_needed is not None:
            owner = self.defining_frame(name, slot, "if_needed")
            return SlotValue(spec.if_needed(self, frame), f"if-needed on {owner}")
        if spec.default is not None:
            owner = self.defining_frame(name, slot, "default")
            return SlotValue(spec.default, f"default from {owner}")
        return SlotValue(None, "unknown")

    def value(self, name: str, slot: str) -> Any:
        return self.get(name, slot).value

    def membership_predicate(self, name: str) -> Optional[str]:
        """Most specific class predicate for an instance (student, parking_space, ...)."""
        for cls in self.ancestors(self.frames[name].isa):
            if self.frames[cls].predicate:
                return self.frames[cls].predicate
        return None

    # ----- validation --------------------------------------------------
    def validate(self) -> list[str]:
        """Check every instance value against the facets of its slot."""
        errors = []
        for inst in self.instances():
            for slot_name, spec in self.slot_specs(inst.name).items():
                value = self.value(inst.name, slot_name) if spec.if_needed is None else None
                if value is None:
                    continue
                values = value if isinstance(value, (list, tuple)) else [value]
                if spec.cardinality == "single" and isinstance(value, (list, tuple)):
                    errors.append(f"{inst.name}.{slot_name}: single-valued slot holds a list")
                for v in values:
                    errors.extend(self._check_value(inst.name, slot_name, spec, v))
        return errors

    def _check_value(self, inst: str, slot: str, spec: Slot, v: Any) -> list[str]:
        where = f"{inst}.{slot}={v!r}"
        if spec.range and v not in spec.range:
            return [f"{where}: not in range {spec.range}"]
        if spec.type == "int" and not isinstance(v, int):
            return [f"{where}: expected an integer"]
        if spec.type.startswith("frame:"):
            target = spec.type.split(":", 1)[1]
            if v not in self.frames:
                return [f"{where}: no frame called {v}"]
            if not self.is_a(v, target):
                return [f"{where}: {v} is not a {target}"]
        return []

    # ----- translation to logic ----------------------------------------
    def to_facts(self) -> list[tuple]:
        """Translate instance frames into ground atoms for the logic layer.

        ali (Student) with owns=[car_ali]  ->  student(ali), owns(ali, car_ali)
        Inherited defaults are included, so s_a3 (an AccessibleSpace with no
        own spaceType) yields space_type(s_a3, accessible).
        """
        facts: list[tuple] = []
        for inst in self.instances():
            pred = self.membership_predicate(inst.name)
            if pred:
                facts.append((pred, inst.name))
            for slot_name, spec in self.slot_specs(inst.name).items():
                if not spec.predicate:
                    continue
                value = self.value(inst.name, slot_name)
                if value is None:
                    continue
                for v in (value if isinstance(value, (list, tuple)) else [value]):
                    facts.append((spec.predicate, inst.name, v))
        return facts

    def describe(self, name: str) -> str:
        """Text rendering of a frame in the FRAME / ISA / SLOTS layout."""
        frame = self.frames[name]
        lines = [f"FRAME: {name}", f"  KIND: {frame.kind}",
                 f"  ISA:  {frame.isa or '-'}"]
        if frame.doc:
            lines.append(f"  NOTE: {frame.doc}")
        lines.append("  SLOTS:")
        for slot_name, spec in self.slot_specs(name).items():
            if frame.kind == "instance":
                sv = self.get(name, slot_name)
                if sv.value is None:
                    continue
                shown = ", ".join(map(str, sv.value)) if isinstance(sv.value, list) else sv.value
                lines.append(f"    {slot_name:<20} = {shown}   [{sv.source}]")
            else:
                own = slot_name in frame.slots
                facets = "; ".join(f"{k}: {v}" for k, v in spec.facets().items())
                marker = "" if own else f"   (inherited from {self.defining_frame(name, slot_name, 'type')})"
                lines.append(f"    {slot_name:<20} {facets}{marker}")
        return "\n".join(lines)
