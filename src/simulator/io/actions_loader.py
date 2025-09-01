from __future__ import annotations
import os, glob, yaml
from typing import Dict, Any, Tuple, List, Optional
from ..core.actions import (
    ActionType, ParamSpec, StructuredPreconditions, StructuredEffects,
    ParameterValidation, LogicConstraint, AssignmentEffect, TrendEffect, StepEffect
)


def load_actions(path: str) -> Dict[Tuple[str, str], ActionType]:
    actions: Dict[Tuple[str,str], ActionType] = {}
    files = sorted(glob.glob(os.path.join(path, "**", "*.yaml"), recursive=True))
    for fp in files:
        with open(fp, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        action = _parse_action(data, source=fp)
        key = (action.object_type, action.name)
        if key in actions:
            raise ValueError(f"Duplicate action {(action.object_type, action.name)} from {fp}")
        actions[key] = action
    return actions


def _parse_action(data: Dict[str, Any], source: str) -> ActionType:
    missing = [k for k in ("action", "object_type") if k not in data]
    if missing:
        raise ValueError(f"{source}: missing keys {missing}")
    name = str(data["action"]).strip()
    object_type = str(data["object_type"]).strip()
    version = int(data.get("version", 1))

    # Parse parameters (same as before)
    params_raw = data.get("parameters", {}) or {}
    parameters: Dict[str, ParamSpec] = {}
    for p_name, spec in params_raw.items():
        space = None
        if isinstance(spec, dict) and "space" in spec:
            s = spec["space"]
            if not isinstance(s, list) or not all(isinstance(x, (str, int, float)) for x in s):
                raise ValueError(f"{source}: parameter {p_name} space must be a list of scalars")
            space = [str(x) for x in s]
        parameters[p_name] = ParamSpec(name=p_name, space=space)

    # Check if this is new structured format or legacy format
    has_structured_preconditions = "structured_preconditions" in data
    has_structured_effects = "structured_effects" in data
    
    # Parse preconditions
    preconditions = [str(x) for x in data.get("preconditions", []) or []]
    structured_preconditions = None
    if has_structured_preconditions:
        structured_preconditions = _parse_structured_preconditions(data["structured_preconditions"], source)

    # Parse effects 
    effects = [str(x) for x in data.get("effects", []) or []]
    structured_effects = None
    if has_structured_effects:
        structured_effects = _parse_structured_effects(data["structured_effects"], source)

    return ActionType(
        name=name, 
        object_type=object_type, 
        version=version,
        parameters=parameters, 
        preconditions=preconditions, 
        effects=effects,
        structured_preconditions=structured_preconditions,
        structured_effects=structured_effects
    )


def _parse_structured_preconditions(data: Dict[str, Any], source: str) -> StructuredPreconditions:
    """Parse structured preconditions from YAML data."""
    parameter_validation = []
    logic_constraints = []
    raw_expressions = []
    
    # Parse parameter validation rules
    if "parameter_validation" in data:
        for rule in data["parameter_validation"]:
            param_val = ParameterValidation(
                parameter=rule["parameter"],
                must_be_in=rule["must_be_in"],
                description=rule.get("description")
            )
            parameter_validation.append(param_val)
    
    # Parse logic constraints
    if "logic_constraints" in data:
        for constraint in data["logic_constraints"]:
            logic_constraint = LogicConstraint(
                if_condition=constraint.get("if", ""),
                then_constraint=constraint["then"],
                description=constraint.get("description")
            )
            logic_constraints.append(logic_constraint)
    
    # Parse raw expressions (fallback)
    if "raw_expressions" in data:
        raw_expressions = [str(x) for x in data["raw_expressions"]]
    
    return StructuredPreconditions(
        parameter_validation=parameter_validation,
        logic_constraints=logic_constraints,
        raw_expressions=raw_expressions
    )


def _parse_structured_effects(data: Dict[str, Any], source: str) -> StructuredEffects:
    """Parse structured effects from YAML data."""
    assignments = []
    trends = []
    steps = []
    raw_expressions = []
    
    # Parse assignments
    if "assignments" in data:
        for assignment in data["assignments"]:
            assign_effect = AssignmentEffect(
                component=assignment["component"],
                value=assignment["value"],
                description=assignment.get("description")
            )
            assignments.append(assign_effect)
    
    # Parse trends
    if "trends" in data:
        for trend in data["trends"]:
            trend_effect = TrendEffect(
                component=trend["component"],
                trend=trend["trend"],
                condition=trend.get("condition"),
                description=trend.get("description")
            )
            trends.append(trend_effect)
    
    # Parse steps
    if "steps" in data:
        for step in data["steps"]:
            step_effect = StepEffect(
                component=step["component"],
                direction=step["direction"],
                condition=step.get("condition"),
                description=step.get("description")
            )
            steps.append(step_effect)
    
    # Parse raw expressions (fallback)
    if "raw_expressions" in data:
        raw_expressions = [str(x) for x in data["raw_expressions"]]
    
    return StructuredEffects(
        assignments=assignments,
        trends=trends,
        steps=steps,
        raw_expressions=raw_expressions
    )