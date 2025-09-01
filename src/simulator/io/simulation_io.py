"""
Simulation I/O

This module handles saving and loading sequence simulations to/from YAML files.
It provides a human-readable format for storing simulation histories that can
be easily inspected, shared, and replayed.
"""

from __future__ import annotations
import yaml
from pathlib import Path
from typing import Dict, Any, List

from ..core.sequence_simulator import SequenceSimulation, ActionStep
from ..core.object_types import ObjectType
from ..core.state import ObjectState


def save_simulation(simulation: SequenceSimulation, file_path: str) -> None:
    """
    Save a sequence simulation to a YAML file.
    
    Args:
        simulation: The simulation to save
        file_path: Path where to save the simulation
    """
    data = simulation.to_dict()
    
    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, indent=2)


def load_simulation_data(file_path: str) -> Dict[str, Any]:
    """
    Load simulation data from a YAML file.
    
    Args:
        file_path: Path to the simulation file
        
    Returns:
        Dictionary containing the simulation data
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def save_action_sequence(
    actions: List[ActionStep],
    file_path: str,
    name: str = "action_sequence",
    description: str = "A sequence of actions to be applied to an object"
) -> None:
    """
    Save an action sequence definition to a YAML file.
    
    This creates a reusable action sequence that can be applied to any
    compatible object type.
    
    Args:
        actions: List of actions in the sequence
        file_path: Path where to save the sequence
        name: Name for the action sequence
        description: Description of what the sequence does
    """
    data = {
        "name": name,
        "description": description,
        "actions": [
            {
                "action_name": action.action_name,
                "parameters": action.parameters,
                "description": action.description
            }
            for action in actions
        ]
    }
    
    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, indent=2)


def load_action_sequence(file_path: str) -> List[ActionStep]:
    """
    Load an action sequence from a YAML file.
    
    Args:
        file_path: Path to the action sequence file
        
    Returns:
        List of ActionStep objects
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    actions = []
    for action_data in data.get("actions", []):
        action = ActionStep(
            action_name=action_data["action_name"],
            parameters=action_data["parameters"],
            description=action_data.get("description")
        )
        actions.append(action)
    
    return actions


def create_simulation_report(simulation: SequenceSimulation) -> str:
    """
    Create a human-readable text report of a simulation.
    
    Args:
        simulation: The simulation to report on
        
    Returns:
        Formatted text report
    """
    report = []
    
    # Header
    report.append(f"=== SIMULATION REPORT: {simulation.name} ===")
    report.append(f"Object Type: {simulation.object_type.name}@v{simulation.object_type.version}")
    report.append(f"Created: {simulation.created_at}")
    if simulation.description:
        report.append(f"Description: {simulation.description}")
    report.append("")
    
    # Summary
    successful = len(simulation.get_successful_steps())
    failed = len(simulation.get_failed_steps())
    total = len(simulation.steps)
    
    report.append(f"SUMMARY:")
    report.append(f"  Total Steps: {total}")
    report.append(f"  Successful: {successful}")
    report.append(f"  Failed: {failed}")
    report.append("")
    
    # Initial state
    report.append(f"INITIAL STATE:")
    for component, value in simulation.initial_state.values.items():
        report.append(f"  {component}: {value}")
    report.append("")
    
    # Step by step
    report.append(f"STEP-BY-STEP HISTORY:")
    
    for step in simulation.steps:
        status_icon = "✅" if step.transition_result.was_successful() else "❌"
        report.append(f"{status_icon} Step {step.step_number}: {step.action_applied.action_name}")
        
        # Parameters
        if step.action_applied.parameters:
            params = ", ".join(f"{k}={v}" for k, v in step.action_applied.parameters.items())
            report.append(f"   Parameters: {params}")
        
        # Description
        if step.action_applied.description:
            report.append(f"   Description: {step.action_applied.description}")
        
        # Result
        if step.transition_result.was_successful():
            if step.transition_result.diff:
                report.append(f"   Changes:")
                for diff in step.transition_result.diff:
                    report.append(f"     - {diff.attribute}: {diff.before} → {diff.after}")
            else:
                report.append(f"   No changes")
        else:
            report.append(f"   FAILED: {step.transition_result.reason}")
        
        report.append("")
    
    # Final state
    final_state = simulation.get_final_state()
    report.append(f"FINAL STATE:")
    for component, value in final_state.values.items():
        initial_value = simulation.initial_state.values.get(component, "N/A")
        if value != initial_value:
            report.append(f"  {component}: {initial_value} → {value}")
        else:
            report.append(f"  {component}: {value}")
    
    return "\n".join(report)
