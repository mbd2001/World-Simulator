from __future__ import annotations
import json
from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table
from simulator.io.yaml_loader import load_object_types
from simulator.io.actions_loader import load_actions
from simulator.core.action_engine import ActionEngine
from simulator.core.state import ObjectState
from simulator.core.sequence_simulator import SequenceSimulator, ActionStep
from simulator.io.simulation_io import save_simulation, load_action_sequence, create_simulation_report, load_simulation_data

app = typer.Typer(help="""Simulator CLI: validate/inspect (Phase 1) + apply actions (Phase 2).""")
console = Console()


def _kb_obj_path(path: str | None) -> str:
    return path or str(Path.cwd() / "kb" / "objects")

def _kb_act_path(path: str | None) -> str:
    return path or str(Path.cwd() / "kb" / "actions")


@app.command()
def validate(objs: str | None = typer.Option(None, help="Path to kb/objects folder"),
             acts: str | None = typer.Option(None, help="Path to kb/actions folder")) -> None:
    kb = _kb_obj_path(objs)
    try:
        reg = load_object_types(kb)
    except Exception as e:
        console.print(f"[red]Object type validation failed:[/red] {e}")
        raise typer.Exit(code=1)
    types = list(reg.all())
    console.print(f"[green]OK[/green] Loaded {len(types)} object type(s) from {kb}")
    for t in types:
        part_count = len(t.parts)
        attr_count = len(t.attributes)
        total_count = part_count + attr_count
        component_str = f"{part_count} parts, {attr_count} attrs" if part_count > 0 else f"{attr_count} attrs"
        console.print(f" - {t.name}@v{t.version} ({component_str})")

    if acts is not None:
        try:
            actions = load_actions(_kb_act_path(acts))
        except Exception as e:
            console.print(f"[red]Action validation failed:[/red] {e}")
            raise typer.Exit(code=1)
        console.print(f"[green]OK[/green] Loaded {len(actions)} action(s) from {_kb_act_path(acts)}")


@app.command("show")
def show_object(
    what: str = typer.Argument(..., help="What to show: 'object'"),
    name: str = typer.Argument(..., help="Object type name"),
    version: int = typer.Option(..., "--version", "-v", help="Version"),
    path: str | None = typer.Option(None, help="Path to kb/objects folder"),
) -> None:
    if what != "object":
        console.print("[red]Only 'object' is supported for 'show'[/red]")
        raise typer.Exit(code=2)

    reg = load_object_types(_kb_obj_path(path))
    obj = reg.get(name, version)

    table = Table(title=f"{obj.name}@v{obj.version}")
    table.add_column("Component")
    table.add_column("Type")
    table.add_column("Space (ordered)")
    table.add_column("Mutable")
    table.add_column("Default")
    
    # Show parts first
    for part_name, part in obj.parts.items():
        table.add_row(
            part_name, 
            "[blue]part[/blue]", 
            ", ".join(part.space.levels), 
            str(part.mutable), 
            str(part.get_effective_default())
        )
    
    # Then show attributes
    for attr_name, attr in obj.attributes.items():
        table.add_row(
            attr_name, 
            "[green]attribute[/green]", 
            ", ".join(attr.space.levels), 
            str(attr.mutable), 
            str(attr.get_effective_default())
        )
    
    console.print(table)

    state_json = obj.default_state().model_dump()
    console.print("\n[bold]Default state[/bold]:")
    console.print_json(data=state_json)


@app.command()
def apply(
    object_name: str = typer.Argument(..., help="Object type name"),
    version: int = typer.Option(..., "--version", "-v", help="Object type version"),
    action_name: str = typer.Argument(..., help="Action name"),
    params: list[str] = typer.Option([], "--param", "-p", help="key=value pairs"),
    state_path: str | None = typer.Option(None, "--state", "-s", help="Path to JSON state (optional)"),
    objs: str | None = typer.Option(None, help="Path to kb/objects folder"),
    acts: str | None = typer.Option(None, help="Path to kb/actions folder"),
) -> None:
    reg = load_object_types(_kb_obj_path(objs))
    obj = reg.get(object_name, version)
    actions = load_actions(_kb_act_path(acts))

    key = (object_name, action_name)
    if key not in actions:
        console.print(f"[red]Unknown action[/red]: {object_name}/{action_name}")
        raise typer.Exit(code=2)
    action = actions[key]

    p: dict[str, str] = {}
    for kv in params:
        if "=" not in kv:
            console.print(f"[red]Bad --param[/red] (expected k=v): {kv}")
            raise typer.Exit(code=2)
        k, v = kv.split("=", 1)
        p[k.strip()] = v.strip()

    if state_path is None:
        state = obj.default_state()
    else:
        from json import load
        with open(state_path, "r", encoding="utf-8") as f:
            data = load(f)
        if "values" in data:
            vals = data["values"]
            tr = data.get("trends", {})
        else:
            console.print("[red]State JSON must contain a 'values' mapping[/red]")
            raise typer.Exit(code=2)
        state = ObjectState(object_type=obj, values=vals, trends=tr)

    engine = ActionEngine(obj)
    result = engine.apply(state, action, p)

    console.print("\n[bold]Result[/bold]:")
    console.print_json(data=result.model_dump())

    if result.diff:
        table = Table(title="Diff")
        table.add_column("Attribute")
        table.add_column("Before")
        table.add_column("After")
        table.add_column("Kind")
        for d in result.diff:
            table.add_row(d.attribute, d.before, d.after, d.kind)
        console.print(table)


@app.command()
def simulate(
    object_name: str = typer.Argument(..., help="Object type name"),
    version: int = typer.Option(..., "--version", "-v", help="Object type version"),
    actions: list[str] = typer.Option(..., "--action", "-a", help="Action in format 'action_name:param1=value1,param2=value2'"),
    output_file: str = typer.Option("simulation.yaml", "--output", "-o", help="Output simulation file"),
    state_path: str | None = typer.Option(None, "--state", "-s", help="Path to initial state JSON (optional)"),
    simulation_name: str | None = typer.Option(None, "--name", "-n", help="Name for the simulation"),
    description: str | None = typer.Option(None, "--description", "-d", help="Description of the simulation"),
    stop_on_failure: bool = typer.Option(False, "--stop-on-failure", help="Stop simulation on first failed action"),
    show_report: bool = typer.Option(True, "--report/--no-report", help="Show text report after simulation"),
    objs: str | None = typer.Option(None, help="Path to kb/objects folder"),
    acts: str | None = typer.Option(None, help="Path to kb/actions folder"),
) -> None:
    """
    Run a sequence of actions on an object and save the simulation history.
    
    Examples:
        # Simple sequence: turn flashlight on then off
        sim simulate flashlight -v 1 -a "flip_switch:to=on" -a "flip_switch:to=off" -o flashlight_cycle.yaml
        
        # With custom name and description
        sim simulate kettle -v 1 -a "set_power:to=on" -n "kettle_heating" -d "Test kettle heating process"
        
        # With custom initial state
        sim simulate flashlight -v 1 -a "flip_switch:to=on" -s low_battery.json --stop-on-failure
    """
    # Load object types and actions
    reg = load_object_types(_kb_obj_path(objs))
    obj_type = reg.get(object_name, version)
    available_actions = load_actions(_kb_act_path(acts))
    
    # Parse initial state
    if state_path is None:
        initial_state = obj_type.default_state()
    else:
        with open(state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "values" in data:
            vals = data["values"]
            tr = data.get("trends", {})
        else:
            console.print("[red]State JSON must contain a 'values' mapping[/red]")
            raise typer.Exit(code=2)
        initial_state = ObjectState(object_type=obj_type, values=vals, trends=tr)
    
    # Parse actions
    action_steps = []
    for i, action_str in enumerate(actions, 1):
        try:
            if ":" in action_str:
                action_name, params_str = action_str.split(":", 1)
                params = {}
                if params_str:
                    for param_pair in params_str.split(","):
                        if "=" in param_pair:
                            k, v = param_pair.split("=", 1)
                            params[k.strip()] = v.strip()
            else:
                action_name = action_str
                params = {}
            
            action_step = ActionStep(
                action_name=action_name.strip(),
                parameters=params,
                description=f"Step {i}: Apply {action_name}"
            )
            action_steps.append(action_step)
            
        except Exception as e:
            console.print(f"[red]Error parsing action '{action_str}': {e}[/red]")
            raise typer.Exit(code=2)
    
    if not action_steps:
        console.print("[red]No actions specified. Use --action/-a to specify actions.[/red]")
        raise typer.Exit(code=2)
    
    # Create simulator and run simulation
    simulator = SequenceSimulator(obj_type)
    
    sim_name = simulation_name or f"{object_name}_simulation"
    sim_description = description or f"Simulation of {len(action_steps)} actions on {object_name}"
    
    console.print(f"[blue]Running simulation:[/blue] {sim_name}")
    console.print(f"[blue]Object:[/blue] {object_name}@v{version}")
    console.print(f"[blue]Actions:[/blue] {len(action_steps)} steps")
    
    simulation = simulator.simulate(
        actions=action_steps,
        available_actions=available_actions,
        initial_state=initial_state,
        simulation_name=sim_name,
        simulation_description=sim_description,
        stop_on_failure=stop_on_failure
    )
    
    # Save simulation
    save_simulation(simulation, output_file)
    console.print(f"[green]✅ Simulation saved to:[/green] {output_file}")
    
    # Show summary
    successful = len(simulation.get_successful_steps())
    failed = len(simulation.get_failed_steps())
    total = len(simulation.steps)
    
    console.print(f"\n[bold]Simulation Summary:[/bold]")
    console.print(f"  Total steps: {total}")
    console.print(f"  Successful: [green]{successful}[/green]")
    console.print(f"  Failed: [red]{failed}[/red]")
    
    if failed > 0:
        console.print(f"\n[yellow]Failed steps:[/yellow]")
        for step in simulation.get_failed_steps():
            console.print(f"  Step {step.step_number}: {step.action_applied.action_name} - {step.transition_result.reason}")
    
    # Show report if requested
    if show_report:
        console.print(f"\n[bold]Detailed Report:[/bold]")
        report = create_simulation_report(simulation)
        console.print(report)


@app.command()
def replay(
    simulation_file: str = typer.Argument(..., help="Path to simulation YAML file"),
    step: int | None = typer.Option(None, "--step", "-s", help="Show state at specific step (0=initial, 1=after step 1, etc.)"),
    show_report: bool = typer.Option(True, "--report/--no-report", help="Show full text report"),
    show_table: bool = typer.Option(False, "--table", help="Show state as table at specified step"),
) -> None:
    """
    Replay and analyze a saved simulation.
    
    Examples:
        # Show full report
        sim replay flashlight_cycle.yaml
        
        # Show state after step 2
        sim replay simulation.yaml --step 2 --table
        
        # Just show the report without extra output
        sim replay simulation.yaml --no-report
    """
    try:
        data = load_simulation_data(simulation_file)
    except Exception as e:
        console.print(f"[red]Error loading simulation: {e}[/red]")
        raise typer.Exit(code=1)
    
    console.print(f"[blue]Simulation:[/blue] {data['name']}")
    console.print(f"[blue]Created:[/blue] {data['created_at']}")
    if data.get('description'):
        console.print(f"[blue]Description:[/blue] {data['description']}")
    
    summary = data['summary']
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  Total steps: {summary['total_steps']}")
    console.print(f"  Successful: [green]{summary['successful_steps']}[/green]")
    console.print(f"  Failed: [red]{summary['failed_steps']}[/red]")
    
    if step is not None:
        # Show specific step
        console.print(f"\n[bold]State at step {step}:[/bold]")
        
        if step == 0:
            state_data = data['initial_state']['values']
            console.print("[blue]Initial state:[/blue]")
        else:
            if step > len(data['steps']):
                console.print(f"[red]Error: Step {step} not found. Simulation has {len(data['steps'])} steps.[/red]")
                raise typer.Exit(code=1)
            
            step_data = data['steps'][step - 1]
            if step_data['state_after'] is None:
                console.print(f"[red]Error: Step {step} failed: {step_data['result']['reason']}[/red]")
                raise typer.Exit(code=1)
            
            state_data = step_data['state_after']['values']
            console.print(f"[blue]State after step {step} ({step_data['action']['name']}):[/blue]")
        
        if show_table:
            # Show as table
            table = Table(title=f"State at Step {step}")
            table.add_column("Component")
            table.add_column("Value")
            
            for component, value in state_data.items():
                table.add_row(component, str(value))
            
            console.print(table)
        else:
            # Show as simple list
            for component, value in state_data.items():
                console.print(f"  {component}: {value}")
    
    if show_report:
        console.print(f"\n[bold]Detailed Report:[/bold]")
        
        # Reconstruct simulation for report generation
        # This is a simplified version that doesn't need the full object types
        console.print(f"\n=== SIMULATION REPORT: {data['name']} ===")
        console.print(f"Object Type: {data['object_type']['name']}@v{data['object_type']['version']}")
        console.print(f"Created: {data['created_at']}")
        if data.get('description'):
            console.print(f"Description: {data['description']}")
        console.print("")
        
        console.print("INITIAL STATE:")
        for component, value in data['initial_state']['values'].items():
            console.print(f"  {component}: {value}")
        console.print("")
        
        console.print("STEP-BY-STEP HISTORY:")
        for step_data in data['steps']:
            status_icon = "✅" if step_data['result']['status'] == 'ok' else "❌"
            console.print(f"{status_icon} Step {step_data['step_number']}: {step_data['action']['name']}")
            
            if step_data['action']['parameters']:
                params = ", ".join(f"{k}={v}" for k, v in step_data['action']['parameters'].items())
                console.print(f"   Parameters: {params}")
            
            if step_data['action'].get('description'):
                console.print(f"   Description: {step_data['action']['description']}")
            
            if step_data['result']['status'] == 'ok':
                if step_data['result']['diff']:
                    console.print("   Changes:")
                    for diff in step_data['result']['diff']:
                        console.print(f"     - {diff['attribute']}: {diff['before']} → {diff['after']}")
                else:
                    console.print("   No changes")
            else:
                console.print(f"   FAILED: {step_data['result']['reason']}")
            
            console.print("")
        
        console.print("FINAL STATE:")
        final_state = summary['final_state']['values']
        initial_state = data['initial_state']['values']
        for component, value in final_state.items():
            initial_value = initial_state.get(component, "N/A")
            if value != initial_value:
                console.print(f"  {component}: {initial_value} → {value}")
            else:
                console.print(f"  {component}: {value}")