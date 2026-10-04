"""A script (Schank and Abelson) for one parking session.

A frame describes a thing. A script describes a stereotyped sequence of
events: who takes part (roles), what objects are involved (props), what
must be true before it starts (entry conditions), the ordered scenes, and
what is true afterwards (results).

The script here is executable. Each scene asks the reasoner a question
with backward chaining. If a scene's goal fails, the script stops at that
scene and the explanation module says why, which is how the gate would
answer a driver who is turned away.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..core.kb import KnowledgeBase
from ..reasoning.backward import BackwardChainer
from ..reasoning.explain import root_causes


@dataclass
class Scene:
    number: int
    name: str
    actions: str
    goal: str            # goal template; {driver}, {space}, {zone} are filled in


@dataclass
class ScriptDefinition:
    name: str
    track: str
    roles: list[str]
    props: list[str]
    entry_conditions: list[str]
    scenes: list[Scene]
    results: list[str]

    def describe(self) -> str:
        lines = [f"SCRIPT: {self.name}", f"  TRACK: {self.track}",
                 "  ROLES: " + ", ".join(self.roles),
                 "  PROPS: " + ", ".join(self.props),
                 "  ENTRY CONDITIONS:"]
        lines += [f"    - {c}" for c in self.entry_conditions]
        lines.append("  SCENES:")
        for s in self.scenes:
            lines.append(f"    {s.number}. {s.name}: {s.actions}")
            lines.append(f"       goal: {s.goal}")
        lines.append("  RESULTS:")
        lines += [f"    - {r}" for r in self.results]
        return "\n".join(lines)


PARKING_SESSION = ScriptDefinition(
    name="ParkingSession",
    track="campus parking with a permit or visitor pass",
    roles=["Driver (a Person)", "Gate system (the reasoner)", "Parking office (issues permits)"],
    props=["Vehicle", "ParkingPermit or visitor pass", "ParkingZone", "ParkingSpace",
           "Reservation (optional)"],
    entry_conditions=["The driver owns a registered vehicle",
                      "The driver has asked the gate for a specific space (requests/3)",
                      "The gate knows today's date and the current hour"],
    scenes=[
        Scene(1, "Arrive at gate", "driver stops at the barrier, gate reads the request",
              "requests({driver}, {space}, T)"),
        Scene(2, "Permit check", "gate checks that a valid permit matches the driver's role",
              "authorized_driver({driver})"),
        Scene(3, "Zone check", "gate checks that the permit opens the zone and the zone is open",
              "zone_access({driver}, {zone})"),
        Scene(4, "Bay check", "gate checks vehicle/bay fit and accessibility requirement",
              "eligible_for_space({driver}, {space})"),
        Scene(5, "Availability", "gate checks the bay is vacant or reserved for this driver",
              "can_allocate({driver}, {space})"),
        Scene(6, "Allocation", "gate resolves conflicts with other requests and allocates",
              "allocate({driver}, {space})"),
        Scene(7, "Park", "driver parks; the bay's status becomes occupied", ""),
    ],
    results=["space_status(space, occupied) replaces the old status",
             "The driver is parked in an allowed bay",
             "No other driver can be allocated that bay"],
)


@dataclass
class SceneResult:
    scene: Scene
    goal: str
    passed: bool
    detail: str = ""


@dataclass
class ScriptRun:
    driver: str
    space: str
    scenes: list[SceneResult] = field(default_factory=list)
    completed: bool = False
    kb_after: KnowledgeBase | None = None

    def text(self) -> str:
        lines = [f"Running script {PARKING_SESSION.name} for driver={self.driver}, space={self.space}"]
        for r in self.scenes:
            mark = "PASS" if r.passed else "STOP"
            lines.append(f"  Scene {r.scene.number} {r.scene.name:<16} {mark}  {r.goal}")
            if r.detail:
                lines.append(f"      {r.detail}")
        lines.append("  Script completed: the driver is parked." if self.completed
                     else "  Script stopped: the driver is turned away at the scene above.")
        return "\n".join(lines)


def run_parking_script(kb: KnowledgeBase, driver: str, space: str) -> ScriptRun:
    """Play the scenes in order, stopping at the first one whose goal fails."""
    run = ScriptRun(driver, space)
    zone = next((f[2] for f in kb.facts_for("located_in") if f[1] == space), "Z")
    bc = BackwardChainer(kb)
    for scene in PARKING_SESSION.scenes:
        if not scene.goal:                      # scene 7: change the world
            after = kb.copy()
            for f in list(after.facts_for("space_status")):
                if f[1] == space:
                    after.remove_fact(f)
            after.add_fact(("space_status", space, "occupied"))
            run.kb_after = after
            run.scenes.append(SceneResult(scene, f"space_status({space}, occupied)", True,
                                          "status updated in working memory"))
            run.completed = True
            break
        goal = scene.goal.format(driver=driver, space=space, zone=zone)
        result = bc.prove(goal, all_answers=False)
        if result.success:
            run.scenes.append(SceneResult(scene, goal, True))
            continue
        detail = ""
        if "T)" not in goal:
            causes = root_causes(kb, goal)
            detail = "reason: " + "; ".join(causes[:3]) if causes else ""
        else:
            detail = "no request recorded for this driver and space"
        run.scenes.append(SceneResult(scene, goal, False, detail))
        break
    return run
