"""
Action Definitions and Transition Results

This module defines the structure for actions that can be applied to objects,
and the results of applying those actions. Actions are the primary way to
modify object states in the simulator.

Key concepts:
- Actions have parameters, preconditions, and effects
- Preconditions determine if an action can be applied
- Effects specify how the action modifies the object state
- Transition results capture the complete outcome of applying an action
"""

from __future__ import annotations
from typing import Dict, List, Literal, Optional, Union, Any
from pydantic import BaseModel, field_validator
from .state import ObjectState, Trend


class ParamSpec(BaseModel):
    """
    Specification for an action parameter.
    
    Defines the name and optional value constraints for a parameter
    that must be provided when applying an action.
    
    Attributes:
        name: Parameter name (used in DSL expressions)
        space: Optional list of allowed values (None means any string)
        
    Examples:
        >>> power_param = ParamSpec(name="to", space=["off", "on"])
        >>> level_param = ParamSpec(name="level")  # No constraints
    """
    name: str
    space: Optional[List[str]] = None

    def validate_value(self, value: str) -> None:
        """
        Validate that a parameter value meets the space constraints.
        
        Args:
            value: The parameter value to validate
            
        Raises:
            ValueError: If value is not in the allowed space
        """
        if self.space is not None and value not in self.space:
            raise ValueError(
                f"Parameter '{self.name}' value {value!r} not in allowed space: {self.space}"
            )


class ParameterValidation(BaseModel):
    """
    Structured parameter validation rule.
    
    Attributes:
        parameter: Name of the parameter to validate
        must_be_in: List of allowed values for the parameter
        description: Optional human-readable description
    """
    parameter: str
    must_be_in: List[str]
    description: Optional[str] = None


class LogicConstraint(BaseModel):
    """
    Structured logic constraint with readable if-then format.
    
    Attributes:
        if_condition: The condition that triggers this constraint
        then_constraint: The constraint that must hold if condition is true
        description: Human-readable description of the constraint
    """
    if_condition: str = ""  # Empty means always applies
    then_constraint: str
    description: Optional[str] = None


class StructuredPreconditions(BaseModel):
    """
    Structured preconditions with clear organization.
    
    Attributes:
        parameter_validation: List of parameter validation rules
        logic_constraints: List of logical constraints
        raw_expressions: Fallback to raw DSL expressions for complex cases
    """
    parameter_validation: List[ParameterValidation] = []
    logic_constraints: List[LogicConstraint] = []
    raw_expressions: List[str] = []


class AssignmentEffect(BaseModel):
    """
    Structured assignment effect.
    
    Attributes:
        component: Name of the component to modify
        value: Expression for the new value
        description: Human-readable description
    """
    component: str
    value: str
    description: Optional[str] = None


class TrendEffect(BaseModel):
    """
    Structured trend effect.
    
    Attributes:
        component: Name of the component whose trend to modify
        trend: New trend direction ("up", "down", "none")
        condition: Optional condition for when this trend applies
        description: Human-readable description
    """
    component: str
    trend: Literal["up", "down", "none"]
    condition: Optional[str] = None
    description: Optional[str] = None


class StepEffect(BaseModel):
    """
    Structured stepping effect (inc/dec in quantity space).
    
    Attributes:
        component: Name of the component to step
        direction: Direction to step ("up" for inc, "down" for dec)
        condition: Optional condition for when this step applies
        description: Human-readable description
    """
    component: str
    direction: Literal["up", "down"]
    condition: Optional[str] = None
    description: Optional[str] = None


class StructuredEffects(BaseModel):
    """
    Structured effects with clear organization.
    
    Attributes:
        assignments: List of assignment effects
        trends: List of trend effects
        steps: List of stepping effects
        raw_expressions: Fallback to raw DSL expressions for complex cases
    """
    assignments: List[AssignmentEffect] = []
    trends: List[TrendEffect] = []
    steps: List[StepEffect] = []
    raw_expressions: List[str] = []


class ActionType(BaseModel):
    """
    Definition of an action that can be applied to objects.
    
    ActionType defines a parameterized operation that can modify object states.
    It supports both legacy format (raw DSL) and new structured format for
    better human readability.
    
    Attributes:
        name: Unique action name within the object type
        object_type: Name of the object type this action applies to
        version: Action version (increment for breaking changes)
        parameters: Dictionary of parameter specifications
        
        # Legacy format (backward compatibility)
        preconditions: List of DSL expressions that must evaluate to True
        effects: List of DSL statements that modify the object state
        
        # New structured format (preferred)
        structured_preconditions: Structured precondition rules
        structured_effects: Structured effect definitions
        
    Examples:
        >>> # Legacy format
        >>> flip_action = ActionType(
        ...     name="flip_switch",
        ...     object_type="flashlight",
        ...     parameters={"to": ParamSpec(name="to", space=["off", "on"])},
        ...     preconditions=['to in ["off","on"]', 'to == "on" -> battery_level != "empty"'],
        ...     effects=['switch = to', 'bulb = "on" if switch == "on" else "off"']
        ... )
        >>> 
        >>> # New structured format
        >>> flip_action_new = ActionType(
        ...     name="flip_switch",
        ...     object_type="flashlight",
        ...     structured_preconditions=StructuredPreconditions(...),
        ...     structured_effects=StructuredEffects(...)
        ... )
    """
    name: str
    object_type: str
    version: int = 1
    parameters: Dict[str, ParamSpec] = {}
    
    # Legacy format (backward compatibility)
    preconditions: List[str] = []
    effects: List[str] = []
    
    # New structured format (preferred)
    structured_preconditions: Optional[StructuredPreconditions] = None
    structured_effects: Optional[StructuredEffects] = None

    @field_validator("name")
    @classmethod
    def _validate_non_empty_name(cls, v: str) -> str:
        """Ensure action name is not empty."""
        if not v:
            raise ValueError("ActionType.name cannot be empty")
        return v

    def get_identifier(self) -> str:
        """
        Get a unique identifier for this action.
        
        Returns:
            String in format "object_type/action_name@vN"
        """
        return f"{self.object_type}/{self.name}@v{self.version}"

    def has_parameter(self, param_name: str) -> bool:
        """
        Check if this action has a specific parameter.
        
        Args:
            param_name: Name of the parameter to check
            
        Returns:
            True if the parameter exists, False otherwise
        """
        return param_name in self.parameters

    def validate_parameters(self, params: Dict[str, str]) -> None:
        """
        Validate a set of parameter values against this action's specification.
        
        Args:
            params: Dictionary of parameter values to validate
            
        Raises:
            ValueError: If required parameters are missing or values are invalid
        """
        # Check for missing required parameters
        missing_params = set(self.parameters.keys()) - set(params.keys())
        if missing_params:
            raise ValueError(f"Missing required parameters: {sorted(missing_params)}")
        
        # Check for unknown parameters
        unknown_params = set(params.keys()) - set(self.parameters.keys())
        if unknown_params:
            raise ValueError(f"Unknown parameters: {sorted(unknown_params)}")
        
        # Validate each parameter value
        for param_name, value in params.items():
            self.parameters[param_name].validate_value(value)

    def get_effective_preconditions(self) -> List[str]:
        """
        Get the effective preconditions as DSL expressions.
        
        If structured preconditions are available, convert them to DSL.
        Otherwise, use the legacy preconditions list.
        
        Returns:
            List of DSL precondition expressions
        """
        if self.structured_preconditions:
            return self._convert_structured_preconditions_to_dsl()
        return self.preconditions

    def get_effective_effects(self) -> List[str]:
        """
        Get the effective effects as DSL expressions.
        
        If structured effects are available, convert them to DSL.
        Otherwise, use the legacy effects list.
        
        Returns:
            List of DSL effect expressions
        """
        if self.structured_effects:
            return self._convert_structured_effects_to_dsl()
        return self.effects

    def _convert_structured_preconditions_to_dsl(self) -> List[str]:
        """Convert structured preconditions to DSL expressions."""
        dsl_expressions = []
        
        if self.structured_preconditions:
            # Convert parameter validations
            for param_val in self.structured_preconditions.parameter_validation:
                space_str = '", "'.join(param_val.must_be_in)
                dsl_expressions.append(f'{param_val.parameter} in ["{space_str}"]')
            
            # Convert logic constraints
            for constraint in self.structured_preconditions.logic_constraints:
                if constraint.if_condition:
                    # If-then constraint: convert to implication
                    dsl_expressions.append(f'{constraint.if_condition} -> {constraint.then_constraint}')
                else:
                    # Always constraint
                    dsl_expressions.append(constraint.then_constraint)
            
            # Add raw expressions
            dsl_expressions.extend(self.structured_preconditions.raw_expressions)
        
        return dsl_expressions

    def _convert_structured_effects_to_dsl(self) -> List[str]:
        """Convert structured effects to DSL expressions."""
        dsl_expressions = []
        
        if self.structured_effects:
            # Convert assignments
            for assignment in self.structured_effects.assignments:
                dsl_expressions.append(f'{assignment.component} = {assignment.value}')
            
            # Convert trends
            for trend in self.structured_effects.trends:
                if trend.condition:
                    trend_expr = f'{trend.component} trend = "{trend.trend}" if {trend.condition} else "none"'
                else:
                    trend_expr = f'{trend.component} trend = "{trend.trend}"'
                dsl_expressions.append(trend_expr)
            
            # Convert steps
            for step in self.structured_effects.steps:
                if step.condition:
                    # For conditional steps, we need to use conditional assignment
                    # This is a bit complex, so for now we'll use raw expressions
                    direction_word = "inc" if step.direction == "up" else "dec"
                    dsl_expressions.append(f'# Conditional step: {step.component} {direction_word} if {step.condition}')
                else:
                    direction_word = "inc" if step.direction == "up" else "dec"
                    dsl_expressions.append(f'{step.component} {direction_word}')
            
            # Add raw expressions
            dsl_expressions.extend(self.structured_effects.raw_expressions)
        
        return dsl_expressions

    def __str__(self) -> str:
        """Human-readable string representation."""
        param_count = len(self.parameters)
        precond_count = len(self.preconditions)
        effect_count = len(self.effects)
        return (
            f"ActionType({self.get_identifier()}: "
            f"{param_count} params, {precond_count} preconditions, {effect_count} effects)"
        )

    def __repr__(self) -> str:
        """Detailed string representation for debugging."""
        return (
            f"ActionType(name='{self.name}', object_type='{self.object_type}', "
            f"version={self.version}, parameters={list(self.parameters.keys())})"
        )


class DiffEntry(BaseModel):
    """
    Record of a single attribute change during action application.
    
    DiffEntry captures the before and after values of an attribute change,
    allowing for complete audit trails and undo operations.
    
    Attributes:
        attribute: Name of the attribute that changed
        before: Previous value of the attribute
        after: New value of the attribute
        kind: Type of change ("value" for attribute values, "trend" for trends)
        
    Examples:
        >>> value_diff = DiffEntry(
        ...     attribute="switch",
        ...     before="off",
        ...     after="on",
        ...     kind="value"
        ... )
        >>> trend_diff = DiffEntry(
        ...     attribute="battery_level.trend",
        ...     before="none",
        ...     after="down",
        ...     kind="trend"
        ... )
    """
    attribute: str
    before: str
    after: str
    kind: Literal["value", "trend"] = "value"

    def is_value_change(self) -> bool:
        """Check if this diff represents an attribute value change."""
        return self.kind == "value"

    def is_trend_change(self) -> bool:
        """Check if this diff represents an attribute trend change."""
        return self.kind == "trend"

    def __str__(self) -> str:
        """Human-readable string representation."""
        change_type = "trend" if self.kind == "trend" else "value"
        return f"{self.attribute} {change_type}: {self.before} → {self.after}"


class TransitionResult(BaseModel):
    """
    Complete result of applying an action to an object state.
    
    TransitionResult captures everything that happens when an action is applied:
    the initial state, the final state (if successful), success/failure status,
    detailed diffs of all changes, and any constraint violations.
    
    Attributes:
        before: Object state before the action was applied
        after: Object state after successful application (None if rejected)
        status: Whether the action succeeded ("ok") or failed ("rejected")
        reason: Detailed explanation if the action was rejected
        diff: List of all attribute changes made by the action
        violations: List of constraint violations (for future use)
        
    Examples:
        >>> # Successful transition
        >>> result = TransitionResult(
        ...     before=initial_state,
        ...     after=final_state,
        ...     status="ok",
        ...     diff=[DiffEntry(attribute="switch", before="off", after="on")]
        ... )
        >>> 
        >>> # Rejected transition
        >>> result = TransitionResult(
        ...     before=initial_state,
        ...     after=None,
        ...     status="rejected",
        ...     reason="Precondition failed: battery_level != 'empty'"
        ... )
    """
    before: ObjectState
    after: Optional[ObjectState]
    status: Literal["ok", "rejected"]
    reason: Optional[str] = None
    diff: List[DiffEntry] = []
    violations: List[str] = []

    def was_successful(self) -> bool:
        """Check if the action application was successful."""
        return self.status == "ok"

    def was_rejected(self) -> bool:
        """Check if the action application was rejected."""
        return self.status == "rejected"

    def get_changed_attributes(self) -> List[str]:
        """
        Get a list of attribute names that were changed.
        
        Returns:
            List of attribute names (without .trend suffix for trend changes)
        """
        changed = set()
        for diff_entry in self.diff:
            attr_name = diff_entry.attribute
            # Remove .trend suffix for trend changes
            if diff_entry.kind == "trend" and attr_name.endswith(".trend"):
                attr_name = attr_name[:-6]
            changed.add(attr_name)
        return sorted(changed)

    def get_value_changes(self) -> List[DiffEntry]:
        """Get only the attribute value changes (not trend changes)."""
        return [diff for diff in self.diff if diff.is_value_change()]

    def get_trend_changes(self) -> List[DiffEntry]:
        """Get only the attribute trend changes (not value changes)."""
        return [diff for diff in self.diff if diff.is_trend_change()]

    def __str__(self) -> str:
        """Human-readable string representation."""
        if self.was_successful():
            change_count = len(self.diff)
            return f"TransitionResult(status=ok, {change_count} changes)"
        else:
            return f"TransitionResult(status=rejected, reason={self.reason})"