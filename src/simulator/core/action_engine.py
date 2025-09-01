from __future__ import annotations
from typing import Dict, List
import copy
import re
from .actions import ActionType, TransitionResult, DiffEntry
from .dsl import eval_expr
from .state import ObjectState
from .object_types import ObjectType


_ASSIGN_RE = re.compile(r"^(.+?)\s*=\s*(.+)$")
_INCDEC_RE = re.compile(r"^(?P<attr>\w+)\s+(?P<op>inc|dec)$")
_TREND_TARGET_RE = re.compile(r"^(?P<attr>\w+)\s+trend$", re.IGNORECASE)


class ActionEngine:
    def __init__(self, obj_type: ObjectType):
        self.obj_type = obj_type

    def apply(self, state: ObjectState, action: ActionType, params: Dict[str, str]) -> TransitionResult:
        if action.object_type != self.obj_type.name:
            return TransitionResult(before=state, after=None, status="rejected",
                                    reason=f"Action {action.name} not valid for {self.obj_type.name}")

        for pname, spec in action.parameters.items():
            if pname not in params:
                return TransitionResult(before=state, after=None, status="rejected",
                                        reason=f"Missing parameter: {pname}")
            if spec.space is not None and params[pname] not in spec.space:
                return TransitionResult(before=state, after=None, status="rejected",
                                        reason=f"Parameter {pname} must be in {spec.space}")

        ctx = {**state.values, **params}

        # Use effective preconditions (converts structured to DSL if needed)
        effective_preconditions = action.get_effective_preconditions()
        for cond in effective_preconditions:
            try:
                ok = bool(eval_expr(cond, ctx))
            except Exception as e:
                return TransitionResult(before=state, after=None, status="rejected",
                                        reason=f"Precondition error: {cond!r}: {e}")
            if not ok:
                return TransitionResult(before=state, after=None, status="rejected",
                                        reason=f"Precondition failed: {cond}")

        new_state = copy.deepcopy(state)
        diffs: List[DiffEntry] = []

        # Use effective effects (converts structured to DSL if needed)
        effective_effects = action.get_effective_effects()
        for eff in effective_effects:
            eff = eff.strip()
            if not eff:
                continue

            m = _INCDEC_RE.match(eff)
            if m:
                component = m.group("attr")
                op = m.group("op")
                if not self.obj_type.has_component(component):
                    return TransitionResult(before=state, after=None, status="rejected",
                                            reason=f"Unknown component in effect: {component}")
                component_type = self.obj_type.get_component(component)
                old = new_state.values[component]
                direction = "up" if op == "inc" else "down"
                new = component_type.space.step(old, direction)
                if new != old:
                    diffs.append(DiffEntry(attribute=component, before=old, after=new, kind="value"))
                    new_state.values[component] = new
                continue

            m = _ASSIGN_RE.match(eff)
            if not m:
                return TransitionResult(before=state, after=None, status="rejected",
                                        reason=f"Malformed effect (expected assignment or inc/dec): {eff}")
            lhs, rhs = m.group(1).strip(), m.group(2).strip()

            tm = _TREND_TARGET_RE.match(lhs)
            if tm:
                component = tm.group("attr")
                if not self.obj_type.has_component(component):
                    return TransitionResult(before=state, after=None, status="rejected",
                                            reason=f"Unknown component in trend target: {component}")
                try:
                    val = eval_expr(rhs, ctx)
                except Exception as e:
                    return TransitionResult(before=state, after=None, status="rejected",
                                            reason=f"Effect eval error: {eff!r}: {e}")
                if val not in ("up","down","none"):
                    return TransitionResult(before=state, after=None, status="rejected",
                                            reason=f"Invalid trend value: {val!r}")
                old = new_state.trends.get(component, "none")
                if old != val:
                    diffs.append(DiffEntry(attribute=f"{component}.trend", before=old, after=val, kind="trend"))
                    new_state.trends[component] = val
                continue

            component = lhs
            if not self.obj_type.has_component(component):
                return TransitionResult(before=state, after=None, status="rejected",
                                        reason=f"Unknown component in effect: {component}")
            try:
                val = eval_expr(rhs, ctx)
            except Exception as e:
                return TransitionResult(before=state, after=None, status="rejected",
                                        reason=f"Effect eval error: {eff!r}: {e}")
            if not isinstance(val, str):
                return TransitionResult(before=state, after=None, status="rejected",
                                        reason=f"Effect must assign string to component {component}, got {val!r}")
            component_type = self.obj_type.get_component(component)
            space = component_type.space
            if not space.has(val):
                return TransitionResult(before=state, after=None, status="rejected",
                                        reason=f"Assigned value {val!r} not in space {space.levels!r}")
            old = new_state.values[component]
            if old != val:
                diffs.append(DiffEntry(attribute=component, before=old, after=val, kind="value"))
                new_state.values[component] = val

            ctx[component] = val

        return TransitionResult(before=state, after=new_state, status="ok", diff=diffs)