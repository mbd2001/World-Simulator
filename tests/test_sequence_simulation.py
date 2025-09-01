"""
Tests for Sequence Simulation

This test file validates the sequence simulation functionality, including:
- Running action sequences on objects
- Saving and loading simulation results
- Inspecting states at specific steps
- Analyzing simulation history and reports
"""

import pytest
import tempfile
import os
from pathlib import Path

from simulator.io.yaml_loader import load_object_types
from simulator.io.actions_loader import load_actions
from simulator.core.sequence_simulator import SequenceSimulator, ActionStep, SequenceSimulation
from simulator.io.simulation_io import save_simulation, load_simulation_data, create_simulation_report
from simulator.core.state import ObjectState


class TestSequenceSimulation:
    """Test the sequence simulation functionality."""
    
    @pytest.fixture
    def setup_simulation_environment(self):
        """Set up the test environment with object types and actions."""
        # Load object types and actions from the knowledge base
        kb_objects_path = "kb/objects"
        kb_actions_path = "kb/actions"
        
        registry = load_object_types(kb_objects_path)
        actions = load_actions(kb_actions_path)
        
        flashlight_type = registry.get("flashlight", 1)
        kettle_type = registry.get("kettle", 1)
        
        return {
            "registry": registry,
            "actions": actions,
            "flashlight_type": flashlight_type,
            "kettle_type": kettle_type
        }
    
    def test_flashlight_on_off_cycle(self, setup_simulation_environment):
        """Test the exact flashlight on/off/off/on sequence from the CLI example."""
        env = setup_simulation_environment
        flashlight_type = env["flashlight_type"]
        actions = env["actions"]
        
        # Create the action sequence: on -> off -> off -> on
        action_sequence = [
            ActionStep("flip_switch", {"to": "on"}, "Turn flashlight on"),
            ActionStep("flip_switch", {"to": "off"}, "Turn flashlight off"),
            ActionStep("flip_switch", {"to": "off"}, "Try to turn off again (should be no-op)"),
            ActionStep("flip_switch", {"to": "on"}, "Turn flashlight on again"),
        ]
        
        # Run simulation
        simulator = SequenceSimulator(flashlight_type)
        simulation = simulator.simulate(
            actions=action_sequence,
            available_actions=actions,
            simulation_name="test_flashlight_cycle",
            simulation_description="Test flashlight on/off/off/on sequence"
        )
        
        # Verify simulation completed successfully
        assert len(simulation.steps) == 4
        assert len(simulation.get_successful_steps()) == 4
        assert len(simulation.get_failed_steps()) == 0
        
        # Test state inspection at each step
        self._verify_flashlight_states(simulation)
        
        # Test simulation properties
        assert simulation.name == "test_flashlight_cycle"
        assert simulation.object_type.name == "flashlight"
        assert simulation.object_type.version == 1
    
    def _verify_flashlight_states(self, simulation: SequenceSimulation):
        """Verify the flashlight states at each step of the simulation."""
        
        # Initial state (step 0)
        initial_state = simulation.get_state_at_step(0)
        assert initial_state.values["switch"] == "off"
        assert initial_state.values["bulb"] == "off"
        assert initial_state.values["battery_level"] == "med"
        assert initial_state.trends.get("battery_level", "none") == "none"
        
        # After step 1: turn on
        state_1 = simulation.get_state_at_step(1)
        assert state_1.values["switch"] == "on"
        assert state_1.values["bulb"] == "on"
        assert state_1.values["battery_level"] == "med"
        assert state_1.trends["battery_level"] == "down"
        
        # After step 2: turn off
        state_2 = simulation.get_state_at_step(2)
        assert state_2.values["switch"] == "off"
        assert state_2.values["bulb"] == "off"
        assert state_2.values["battery_level"] == "med"
        assert state_2.trends.get("battery_level", "none") == "none"
        
        # After step 3: try to turn off again (no change)
        state_3 = simulation.get_state_at_step(3)
        assert state_3.values["switch"] == "off"
        assert state_3.values["bulb"] == "off"
        assert state_3.values["battery_level"] == "med"
        assert state_3.trends.get("battery_level", "none") == "none"
        
        # Verify step 3 had no changes (state same as step 2)
        assert state_3.values == state_2.values
        assert state_3.trends == state_2.trends
        
        # After step 4: turn on again
        state_4 = simulation.get_state_at_step(4)
        assert state_4.values["switch"] == "on"
        assert state_4.values["bulb"] == "on"
        assert state_4.values["battery_level"] == "med"
        assert state_4.trends["battery_level"] == "down"
        
        # Final state should be same as step 4
        final_state = simulation.get_final_state()
        assert final_state.values == state_4.values
        assert final_state.trends == state_4.trends
    
    def test_simulation_with_failure(self, setup_simulation_environment):
        """Test simulation that includes a failed action."""
        env = setup_simulation_environment
        flashlight_type = env["flashlight_type"]
        actions = env["actions"]
        
        # Create custom initial state with empty battery
        empty_battery_state = ObjectState(
            object_type=flashlight_type,
            values={"switch": "off", "bulb": "off", "battery_level": "empty"},
            trends={}
        )
        
        # Action sequence that should fail on the first step
        action_sequence = [
            ActionStep("flip_switch", {"to": "on"}, "Try to turn on with empty battery (should fail)"),
            ActionStep("flip_switch", {"to": "off"}, "This should still work"),
        ]
        
        # Run simulation without stopping on failure
        simulator = SequenceSimulator(flashlight_type)
        simulation = simulator.simulate(
            actions=action_sequence,
            available_actions=actions,
            initial_state=empty_battery_state,
            simulation_name="test_battery_failure",
            stop_on_failure=False
        )
        
        # Verify results
        assert len(simulation.steps) == 2
        assert len(simulation.get_successful_steps()) == 1  # Only step 2 should succeed
        assert len(simulation.get_failed_steps()) == 1      # Step 1 should fail
        
        # Check failed step
        failed_steps = simulation.get_failed_steps()
        assert failed_steps[0].step_number == 1
        assert "battery_level != \"empty\"" in failed_steps[0].transition_result.reason
        
        # State should remain unchanged after failed step
        with pytest.raises(ValueError, match="Step 1 failed"):
            simulation.get_state_at_step(1)
        
        # But step 2 should succeed (turning off when already off)
        state_2 = simulation.get_state_at_step(2)
        assert state_2.values["switch"] == "off"
        assert state_2.values["battery_level"] == "empty"
    
    def test_simulation_with_stop_on_failure(self, setup_simulation_environment):
        """Test simulation that stops on first failure."""
        env = setup_simulation_environment
        flashlight_type = env["flashlight_type"]
        actions = env["actions"]
        
        # Create custom initial state with empty battery
        empty_battery_state = ObjectState(
            object_type=flashlight_type,
            values={"switch": "off", "bulb": "off", "battery_level": "empty"},
            trends={}
        )
        
        # Action sequence where first action should fail
        action_sequence = [
            ActionStep("flip_switch", {"to": "on"}, "Try to turn on with empty battery (should fail)"),
            ActionStep("flip_switch", {"to": "off"}, "This should not be executed"),
        ]
        
        # Run simulation with stop on failure
        simulator = SequenceSimulator(flashlight_type)
        simulation = simulator.simulate(
            actions=action_sequence,
            available_actions=actions,
            initial_state=empty_battery_state,
            stop_on_failure=True
        )
        
        # Should only have executed one step
        assert len(simulation.steps) == 1
        assert len(simulation.get_failed_steps()) == 1
        assert len(simulation.get_successful_steps()) == 0
    
    def test_kettle_heating_sequence(self, setup_simulation_environment):
        """Test kettle power on/off sequence."""
        env = setup_simulation_environment
        kettle_type = env["kettle_type"]
        actions = env["actions"]
        
        # Create action sequence for kettle
        action_sequence = [
            ActionStep("set_power", {"to": "on"}, "Turn kettle power on"),
            ActionStep("set_power", {"to": "off"}, "Turn kettle power off"),
            ActionStep("set_power", {"to": "on"}, "Turn kettle power on again"),
        ]
        
        # Run simulation
        simulator = SequenceSimulator(kettle_type)
        simulation = simulator.simulate(
            actions=action_sequence,
            available_actions=actions,
            simulation_name="test_kettle_heating"
        )
        
        # Verify all steps succeeded
        assert len(simulation.steps) == 3
        assert len(simulation.get_successful_steps()) == 3
        assert len(simulation.get_failed_steps()) == 0
        
        # Check state progression
        initial_state = simulation.get_state_at_step(0)
        assert initial_state.values["power"] == "off"
        assert initial_state.values["temperature"] == "cold"
        assert initial_state.values["water_level"] == "mid"
        
        state_1 = simulation.get_state_at_step(1)  # Power on
        assert state_1.values["power"] == "on"
        assert state_1.values["temperature"] == "cold"  # Temperature doesn't change immediately
        
        state_2 = simulation.get_state_at_step(2)  # Power off
        assert state_2.values["power"] == "off"
        
        state_3 = simulation.get_state_at_step(3)  # Power on again
        assert state_3.values["power"] == "on"
    
    def test_simulation_io(self, setup_simulation_environment):
        """Test saving and loading simulations."""
        env = setup_simulation_environment
        flashlight_type = env["flashlight_type"]
        actions = env["actions"]
        
        # Create a simple simulation
        action_sequence = [
            ActionStep("flip_switch", {"to": "on"}, "Turn on"),
            ActionStep("flip_switch", {"to": "off"}, "Turn off"),
        ]
        
        simulator = SequenceSimulator(flashlight_type)
        original_simulation = simulator.simulate(
            actions=action_sequence,
            available_actions=actions,
            simulation_name="test_io_simulation",
            simulation_description="Test saving and loading"
        )
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_path = f.name
        
        try:
            save_simulation(original_simulation, temp_path)
            
            # Load the simulation data
            loaded_data = load_simulation_data(temp_path)
            
            # Verify loaded data matches original
            assert loaded_data["name"] == "test_io_simulation"
            assert loaded_data["description"] == "Test saving and loading"
            assert loaded_data["object_type"]["name"] == "flashlight"
            assert loaded_data["object_type"]["version"] == 1
            assert loaded_data["summary"]["total_steps"] == 2
            assert loaded_data["summary"]["successful_steps"] == 2
            assert loaded_data["summary"]["failed_steps"] == 0
            
            # Verify step data
            steps = loaded_data["steps"]
            assert len(steps) == 2
            
            step_1 = steps[0]
            assert step_1["step_number"] == 1
            assert step_1["action"]["name"] == "flip_switch"
            assert step_1["action"]["parameters"]["to"] == "on"
            assert step_1["result"]["status"] == "ok"
            assert len(step_1["result"]["diff"]) == 3  # switch, bulb, battery_level.trend
            
            step_2 = steps[1]
            assert step_2["step_number"] == 2
            assert step_2["action"]["parameters"]["to"] == "off"
            
        finally:
            # Clean up
            os.unlink(temp_path)
    
    def test_simulation_report_generation(self, setup_simulation_environment):
        """Test generating human-readable simulation reports."""
        env = setup_simulation_environment
        flashlight_type = env["flashlight_type"]
        actions = env["actions"]
        
        # Create simulation with mixed success/failure
        empty_battery_state = ObjectState(
            object_type=flashlight_type,
            values={"switch": "off", "bulb": "off", "battery_level": "empty"},
            trends={}
        )
        
        action_sequence = [
            ActionStep("flip_switch", {"to": "on"}, "Should fail - empty battery"),
            ActionStep("flip_switch", {"to": "off"}, "Should succeed - already off"),
        ]
        
        simulator = SequenceSimulator(flashlight_type)
        simulation = simulator.simulate(
            actions=action_sequence,
            available_actions=actions,
            initial_state=empty_battery_state,
            simulation_name="test_report_generation",
            stop_on_failure=False
        )
        
        # Generate report
        report = create_simulation_report(simulation)
        
        # Verify report contains expected sections
        assert "=== SIMULATION REPORT: test_report_generation ===" in report
        assert "Object Type: flashlight@v1" in report
        assert "SUMMARY:" in report
        assert "Total Steps: 2" in report
        assert "Successful: 1" in report
        assert "Failed: 1" in report
        assert "INITIAL STATE:" in report
        assert "STEP-BY-STEP HISTORY:" in report
        assert "✅ Step 2: flip_switch" in report  # Successful step
        assert "❌ Step 1: flip_switch" in report  # Failed step
        assert "FAILED: Precondition failed" in report
        assert "FINAL STATE:" in report
    
    def test_simulation_utilities(self, setup_simulation_environment):
        """Test various simulation utility methods."""
        env = setup_simulation_environment
        flashlight_type = env["flashlight_type"]
        actions = env["actions"]
        
        # Create a simulation with some steps
        action_sequence = [
            ActionStep("flip_switch", {"to": "on"}, "Turn on"),
            ActionStep("flip_switch", {"to": "off"}, "Turn off"),
            ActionStep("flip_switch", {"to": "on"}, "Turn on again"),
        ]
        
        simulator = SequenceSimulator(flashlight_type)
        simulation = simulator.simulate(
            actions=action_sequence,
            available_actions=actions,
            simulation_name="test_utilities"
        )
        
        # Test to_dict method
        sim_dict = simulation.to_dict()
        assert isinstance(sim_dict, dict)
        assert sim_dict["name"] == "test_utilities"
        assert "created_at" in sim_dict
        assert "summary" in sim_dict
        
        # Test step access methods
        successful_steps = simulation.get_successful_steps()
        assert len(successful_steps) == 3
        assert all(step.transition_result.was_successful() for step in successful_steps)
        
        failed_steps = simulation.get_failed_steps()
        assert len(failed_steps) == 0
        
        # Test state access at different steps
        for step_num in range(4):  # 0 to 3
            state = simulation.get_state_at_step(step_num)
            assert isinstance(state, ObjectState)
            assert state.object_type.name == "flashlight"
        
        # Test accessing invalid step
        with pytest.raises(ValueError, match="Step 5 not found"):
            simulation.get_state_at_step(5)
    
    def test_unknown_action_handling(self, setup_simulation_environment):
        """Test handling of unknown actions in sequences."""
        env = setup_simulation_environment
        flashlight_type = env["flashlight_type"]
        actions = env["actions"]
        
        # Include an unknown action
        action_sequence = [
            ActionStep("flip_switch", {"to": "on"}, "Valid action"),
            ActionStep("unknown_action", {"param": "value"}, "Invalid action"),
            ActionStep("flip_switch", {"to": "off"}, "Another valid action"),
        ]
        
        simulator = SequenceSimulator(flashlight_type)
        simulation = simulator.simulate(
            actions=action_sequence,
            available_actions=actions,
            stop_on_failure=False
        )
        
        # Should have 3 steps: 2 successful, 1 failed
        assert len(simulation.steps) == 3
        assert len(simulation.get_successful_steps()) == 2
        assert len(simulation.get_failed_steps()) == 1
        
        # Check the failed step
        failed_step = simulation.get_failed_steps()[0]
        assert failed_step.step_number == 2
        assert "Unknown action: unknown_action" in failed_step.transition_result.reason
    
    def test_state_comparison_across_steps(self, setup_simulation_environment):
        """Test comparing states across different simulation steps."""
        env = setup_simulation_environment
        flashlight_type = env["flashlight_type"]
        actions = env["actions"]
        
        action_sequence = [
            ActionStep("flip_switch", {"to": "on"}, "Turn on"),
            ActionStep("flip_switch", {"to": "off"}, "Turn off"),
        ]
        
        simulator = SequenceSimulator(flashlight_type)
        simulation = simulator.simulate(
            actions=action_sequence,
            available_actions=actions
        )
        
        # Compare initial and final states
        initial_state = simulation.get_state_at_step(0)
        final_state = simulation.get_final_state()
        
        # After on->off cycle, should be back to initial state values
        assert initial_state.values == final_state.values
        # Note: trends might be different (battery_level trend goes from none to none,
        # but trend tracking means final state might have explicit "none" trend)
        
        # But intermediate state should be different
        intermediate_state = simulation.get_state_at_step(1)
        assert intermediate_state.values != initial_state.values
        assert intermediate_state.values["switch"] == "on"
        assert intermediate_state.values["bulb"] == "on"
        assert intermediate_state.trends["battery_level"] == "down"


# Utility functions for interactive testing and debugging

def create_test_flashlight_simulation():
    """
    Create a test flashlight simulation for interactive use.
    
    Returns:
        SequenceSimulation: A completed simulation ready for analysis
    """
    # Load environment
    registry = load_object_types("kb/objects")
    actions = load_actions("kb/actions")
    flashlight_type = registry.get("flashlight", 1)
    
    # Create action sequence
    action_sequence = [
        ActionStep("flip_switch", {"to": "on"}, "Turn flashlight on"),
        ActionStep("flip_switch", {"to": "off"}, "Turn flashlight off"),
        ActionStep("flip_switch", {"to": "off"}, "Try to turn off again"),
        ActionStep("flip_switch", {"to": "on"}, "Turn on again"),
    ]
    
    # Run simulation
    simulator = SequenceSimulator(flashlight_type)
    return simulator.simulate(
        actions=action_sequence,
        available_actions=actions,
        simulation_name="interactive_test_flashlight",
        simulation_description="Interactive test simulation"
    )


def inspect_simulation_step(simulation: SequenceSimulation, step: int):
    """
    Utility function to inspect a specific step in detail.
    
    Args:
        simulation: The simulation to inspect
        step: Step number (0 = initial state, 1+ = after applying step)
    """
    print(f"\n=== STEP {step} INSPECTION ===")
    
    if step == 0:
        state = simulation.initial_state
        print("INITIAL STATE:")
    else:
        if step > len(simulation.steps):
            print(f"ERROR: Step {step} not found. Simulation has {len(simulation.steps)} steps.")
            return
        
        step_data = simulation.steps[step - 1]
        state = step_data.state_after
        
        if state is None:
            print(f"FAILED STEP {step}:")
            print(f"  Action: {step_data.action_applied.action_name}")
            print(f"  Parameters: {step_data.action_applied.parameters}")
            print(f"  Reason: {step_data.transition_result.reason}")
            return
        
        print(f"STATE AFTER STEP {step}:")
        print(f"  Action: {step_data.action_applied.action_name}")
        print(f"  Parameters: {step_data.action_applied.parameters}")
        if step_data.transition_result.diff:
            print("  Changes:")
            for diff in step_data.transition_result.diff:
                print(f"    - {diff.attribute}: {diff.before} → {diff.after}")
        else:
            print("  No changes")
    
    print("\nComponent Values:")
    for component, value in state.values.items():
        trend = state.trends.get(component, "none")
        trend_str = f" (trend: {trend})" if trend != "none" else ""
        print(f"  {component}: {value}{trend_str}")


def compare_simulation_states(simulation: SequenceSimulation, step1: int, step2: int):
    """
    Compare states between two steps in a simulation.
    
    Args:
        simulation: The simulation to analyze
        step1: First step number
        step2: Second step number
    """
    state1 = simulation.get_state_at_step(step1)
    state2 = simulation.get_state_at_step(step2)
    
    print(f"\n=== COMPARING STEP {step1} vs STEP {step2} ===")
    
    all_components = set(state1.values.keys()) | set(state2.values.keys())
    
    print("Value Changes:")
    for component in sorted(all_components):
        val1 = state1.values.get(component, "N/A")
        val2 = state2.values.get(component, "N/A")
        
        if val1 != val2:
            print(f"  {component}: {val1} → {val2}")
        else:
            print(f"  {component}: {val1} (no change)")
    
    print("\nTrend Changes:")
    all_trend_components = set(state1.trends.keys()) | set(state2.trends.keys())
    for component in sorted(all_trend_components):
        trend1 = state1.trends.get(component, "none")
        trend2 = state2.trends.get(component, "none")
        
        if trend1 != trend2:
            print(f"  {component}: {trend1} → {trend2}")
        else:
            print(f"  {component}: {trend1} (no change)")


if __name__ == "__main__":
    # Interactive testing when run directly
    print("Creating test simulation...")
    sim = create_test_flashlight_simulation()
    
    print(f"Simulation '{sim.name}' created with {len(sim.steps)} steps")
    print(f"Successful steps: {len(sim.get_successful_steps())}")
    print(f"Failed steps: {len(sim.get_failed_steps())}")
    
    # Demonstrate state inspection
    for step in range(len(sim.steps) + 1):
        inspect_simulation_step(sim, step)
    
    # Demonstrate state comparison
    compare_simulation_states(sim, 0, 2)  # Compare initial vs after turn off
    compare_simulation_states(sim, 1, 4)  # Compare two "on" states
