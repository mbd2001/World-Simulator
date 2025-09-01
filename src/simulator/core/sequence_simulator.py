"""
Sequence Simulator

This module provides functionality to apply a sequence of actions to an object
and record the complete state transition history. This is useful for:
- Testing action sequences
- Analyzing state progressions
- Creating training data
- Debugging complex interactions
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import copy

from .object_types import ObjectType
from .state import ObjectState
from .actions import ActionType, TransitionResult
from .action_engine import ActionEngine


@dataclass
class ActionStep:
    """Represents a single action to be applied in a sequence."""
    action_name: str
    parameters: Dict[str, str]
    description: Optional[str] = None


@dataclass
class SimulationStep:
    """Represents one step in the simulation history."""
    step_number: int
    action_applied: ActionStep
    state_before: ObjectState
    state_after: Optional[ObjectState]
    transition_result: TransitionResult
    timestamp: str


class SequenceSimulation:
    """
    Represents a complete simulation run with full history.
    
    This class stores the complete state transition history and provides
    methods to analyze and replay the simulation.
    """
    
    def __init__(
        self,
        object_type: ObjectType,
        initial_state: ObjectState,
        steps: List[SimulationStep],
        name: Optional[str] = None,
        description: Optional[str] = None
    ):
        self.object_type = object_type
        self.initial_state = initial_state
        self.steps = steps
        self.name = name or f"{object_type.name}_simulation"
        self.description = description
        self.created_at = datetime.now().isoformat()
    
    def get_state_at_step(self, step_number: int) -> ObjectState:
        """Get the object state after applying the specified step."""
        if step_number == 0:
            return self.initial_state
        
        if step_number > len(self.steps):
            raise ValueError(f"Step {step_number} not found. Simulation has {len(self.steps)} steps.")
        
        step = self.steps[step_number - 1]
        if step.state_after is None:
            raise ValueError(f"Step {step_number} failed: {step.transition_result.reason}")
        
        return step.state_after
    
    def get_final_state(self) -> ObjectState:
        """Get the final state after all successful steps."""
        if not self.steps:
            return self.initial_state
        
        # Find the last successful step
        for step in reversed(self.steps):
            if step.state_after is not None:
                return step.state_after
        
        return self.initial_state
    
    def get_successful_steps(self) -> List[SimulationStep]:
        """Get only the steps that were successfully applied."""
        return [step for step in self.steps if step.state_after is not None]
    
    def get_failed_steps(self) -> List[SimulationStep]:
        """Get only the steps that failed."""
        return [step for step in self.steps if step.state_after is None]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert simulation to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
            "object_type": {
                "name": self.object_type.name,
                "version": self.object_type.version
            },
            "initial_state": self.initial_state.model_dump(),
            "steps": [
                {
                    "step_number": step.step_number,
                    "action": {
                        "name": step.action_applied.action_name,
                        "parameters": step.action_applied.parameters,
                        "description": step.action_applied.description
                    },
                    "state_before": step.state_before.model_dump(),
                    "state_after": step.state_after.model_dump() if step.state_after else None,
                    "result": {
                        "status": step.transition_result.status,
                        "reason": step.transition_result.reason,
                        "diff": [diff.model_dump() for diff in step.transition_result.diff]
                    },
                    "timestamp": step.timestamp
                }
                for step in self.steps
            ],
            "summary": {
                "total_steps": len(self.steps),
                "successful_steps": len(self.get_successful_steps()),
                "failed_steps": len(self.get_failed_steps()),
                "final_state": self.get_final_state().model_dump()
            }
        }


class SequenceSimulator:
    """
    Simulates sequences of actions on objects.
    
    This class can take an object type, initial state, and sequence of actions,
    then apply them step by step while recording the complete history.
    """
    
    def __init__(self, object_type: ObjectType):
        self.object_type = object_type
        self.engine = ActionEngine(object_type)
    
    def simulate(
        self,
        actions: List[ActionStep],
        available_actions: Dict[str, ActionType],
        initial_state: Optional[ObjectState] = None,
        simulation_name: Optional[str] = None,
        simulation_description: Optional[str] = None,
        stop_on_failure: bool = False
    ) -> SequenceSimulation:
        """
        Run a sequence simulation.
        
        Args:
            actions: List of actions to apply in sequence
            available_actions: Dictionary mapping action names to ActionType objects
            initial_state: Starting state (uses default if None)
            simulation_name: Name for the simulation
            simulation_description: Description of what the simulation tests
            stop_on_failure: If True, stop simulation on first failed action
            
        Returns:
            SequenceSimulation containing the complete history
        """
        if initial_state is None:
            initial_state = self.object_type.default_state()
        
        current_state = copy.deepcopy(initial_state)
        steps: List[SimulationStep] = []
        
        for i, action_step in enumerate(actions, 1):
            # Find the action type using compound key (object_type, action_name)
            action_key = (self.object_type.name, action_step.action_name)
            if action_key not in available_actions:
                # Create a failed result for unknown action
                from .actions import TransitionResult
                failed_result = TransitionResult(
                    before=current_state,
                    after=None,
                    status="rejected",
                    reason=f"Unknown action: {action_step.action_name}"
                )
                
                step = SimulationStep(
                    step_number=i,
                    action_applied=action_step,
                    state_before=copy.deepcopy(current_state),
                    state_after=None,
                    transition_result=failed_result,
                    timestamp=datetime.now().isoformat()
                )
                steps.append(step)
                
                if stop_on_failure:
                    break
                continue
            
            action_type = available_actions[action_key]
            state_before = copy.deepcopy(current_state)
            
            # Apply the action
            result = self.engine.apply(current_state, action_type, action_step.parameters)
            
            # Record the step
            step = SimulationStep(
                step_number=i,
                action_applied=action_step,
                state_before=state_before,
                state_after=result.after,
                transition_result=result,
                timestamp=datetime.now().isoformat()
            )
            steps.append(step)
            
            # Update current state if successful
            if result.was_successful() and result.after is not None:
                current_state = result.after
            elif stop_on_failure:
                break
        
        return SequenceSimulation(
            object_type=self.object_type,
            initial_state=initial_state,
            steps=steps,
            name=simulation_name,
            description=simulation_description
        )
