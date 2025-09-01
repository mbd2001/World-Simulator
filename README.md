# Mental Models Simulator

> **Ground-Truth Qualitative Simulator for Benchmark Dataset Generation**

A deterministic, qualitative simulator for everyday objects designed to generate labeled state transitions for AI model evaluation. This is **NOT** an LLM-facing tool—it defines what *correct* world model updates should look like.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Current Status](#current-status)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Knowledge Base Authoring](#knowledge-base-authoring)
- [CLI Reference](#cli-reference)
- [Development](#development)
- [Implementation Roadmap](#implementation-roadmap)
- [Design Principles](#design-principles)

---

## Project Overview

### Purpose

The Mental Models Simulator creates **deterministic, labeled state transitions** for everyday objects to serve as ground truth for evaluating AI world models. It operates on **qualitative values** (e.g., `empty`, `low`, `medium`, `high`) rather than quantitative measurements.

### Key Features

- ✅ **Deterministic**: Same inputs always produce identical outputs
- ✅ **Safe**: No Python `eval()` - uses AST-whitelisted domain-specific language
- ✅ **Validated**: Strict validation of all states, actions, and transitions
- ✅ **Traceable**: Comprehensive diff tracking for every state change
- ✅ **Versioned**: Schema versioning for objects and actions
- ✅ **File-First**: Human-readable YAML definitions for rapid iteration

### Example Use Cases

```bash
# Validate knowledge base
uv run sim validate --acts kb/actions

# Show object definition with parts and attributes
uv run sim show object flashlight --version 1

# Apply single action to object
uv run sim apply flashlight -v 1 flip_switch -p to=on

# Run action sequence and save simulation
uv run sim simulate flashlight -v 1 -a "flip_switch:to=on" -a "flip_switch:to=off" -o flashlight_cycle.yaml

# Replay and analyze simulation
uv run sim replay flashlight_cycle.yaml --step 2 --table
```

---

## Current Status

### ✅ Phase 1 - Core Object Model (COMPLETE)

**Core Components:**
- **QuantitySpace**: Ordered qualitative value spaces with stepping operations
- **AttributeType**: Attribute definitions with validation and mutability
- **ObjectType**: Versioned object schemas with attribute collections  
- **ObjectState**: Validated state instances with value and trend tracking
- **Registry**: In-memory storage and retrieval for object types

**CLI Commands:**
- `sim validate [--acts <path>]` - Validate object types and actions
- `sim show object <name> --version <v>` - Display object schema and default state

### ✅ Phase 2 - Actions & Transition Engine (COMPLETE)

**Core Components:**
- **Safe Mini-DSL**: AST-based expression evaluator with whitelisted operations
- **ActionType**: Action definitions with parameters, preconditions, and effects
- **ActionEngine**: Core transition engine with validation and effect application
- **TransitionResult**: Structured results with diffs and status tracking

**Effects Grammar:**
- `attr = <expr>` - Value assignment with expression evaluation
- `attr trend = "up"|"down"|"none"` - Trend metadata assignment
- `attr inc` / `attr dec` - Quantity space stepping operations

**CLI Commands:**
- `sim apply <object> -v <ver> <action> -p key=value [-s state.json]` - Apply actions

**DSL Features:**
- Names, string literals, lists, tuples
- Comparisons: `==`, `!=`, `in`, `not in`  
- Boolean logic: `and`, `or`, `not`
- Conditionals: `value if condition else other_value`
- Implication sugar: `A -> B` (becomes `(not A) or B`)

### ✅ Phase 2.5 - Enhanced Object Structure & Action Readability (COMPLETE)

**Object Structure Improvements:**
- **Parts**: Physical components that can be controlled (switch, bulb, power)
- **Attributes**: Properties and states that are measured (battery_level, temperature)
- Clear semantic separation with backward compatibility

**Human-Readable Action Format:**
- **Structured Preconditions**: Clear parameter validation and logic constraints
- **Structured Effects**: Organized assignments, trends, and stepping operations
- **Self-Documenting**: Descriptions and readable if-then logic
- **Legacy Support**: Old DSL format still works alongside new structure

**CLI Commands:**
- `sim simulate <object> -v <ver> -a "action:param=value" [-o output.yaml]` - Run action sequences
- `sim replay <simulation.yaml> [--step N] [--table]` - Analyze saved simulations

### 🔄 Next: Phase 3 - Unknowns & Blocked Outcomes

Allow `unknown` values in states and handle blocked transitions when preconditions reference unknown attributes.

---

## Quick Start

### Prerequisites

- Python 3.10+
- UV package manager

### Installation

```bash
# Clone repository
git clone <repo-url>
cd mental-models-simulator

# Install dependencies
uv sync

# Validate installation
uv run sim validate
```

### Basic Usage

```bash
# Validate knowledge base
uv run sim validate --acts kb/actions

# Explore flashlight object
uv run sim show object flashlight --version 1

# Turn on flashlight
uv run sim apply flashlight -v 1 flip_switch -p to=on

# Turn off with custom state
echo '{"values":{"switch":"on","bulb":"on","battery_level":"low"},"trends":{"battery_level":"down"}}' > state.json
uv run sim apply flashlight -v 1 flip_switch -p to=off -s state.json
```

---

## Architecture

### Repository Structure

```
src/simulator/
├── core/                   # Core simulation engine
│   ├── quantity.py         # QuantitySpace (qualitative values)
│   ├── attributes.py       # AttributeType definitions
│   ├── object_types.py     # ObjectType schemas
│   ├── state.py            # ObjectState with validation
│   ├── registry.py         # In-memory type storage
│   ├── dsl.py              # Safe expression evaluator
│   ├── actions.py          # ActionType, TransitionResult
│   └── action_engine.py    # Core transition engine
├── io/                     # Knowledge base I/O
│   ├── yaml_loader.py      # Object type loading
│   └── actions_loader.py   # Action loading
└── cli/                    # Command-line interface
    └── app.py              # CLI commands

kb/                         # Knowledge base
├── objects/                # Object type definitions
│   ├── flashlight.yaml
│   └── kettle.yaml
└── actions/                # Action definitions
    ├── flashlight/
    │   └── flip_switch.yaml
    └── kettle/
        └── set_power.yaml

tests/                      # Test suite
├── test_phase1_smoke.py    # Basic functionality tests
└── test_phase2_actions.py  # Action engine tests
```

### Core Data Flow

```
YAML Files → Loaders → Registry → CLI Commands
     ↓            ↓        ↓          ↓
Object Types → Validation → Storage → User Interface
Action Types → Validation → Engine → State Transitions
```

### Component Relationships

1. **QuantitySpace** defines ordered qualitative values (`[empty, low, med, high]`)
2. **AttributeType** combines QuantitySpace with mutability and defaults
3. **ObjectType** aggregates AttributeTypes into versioned schemas
4. **ObjectState** represents validated instances of ObjectTypes
5. **ActionType** defines parameterized state transitions
6. **ActionEngine** applies ActionTypes to ObjectStates with full validation

---

## Knowledge Base Authoring

### Object Types

Object types are defined in `kb/objects/*.yaml` files with a clear separation between physical parts and measurable attributes:

```yaml
# kb/objects/flashlight.yaml
type: flashlight
version: 1

# Physical components that can be directly controlled
parts:
  switch:
    space: ["off", "on"]       # Binary state space
    mutable: true              # Can be changed by actions
    default: "off"             # Starts in off position
  
  bulb:
    space: ["off", "on"]       # Binary state space
    mutable: true              # Controlled by switch state
    default: "off"             # Starts off (follows switch)

# Properties and states that are measured or tracked
attributes:
  battery_level:
    space: ["empty", "low", "med", "high"]  # Ordered qualitative levels
    mutable: true              # Decreases over time/use
    default: "med"             # Starts with medium charge
```

**Schema Rules:**
- `type`: Unique object type name
- `version`: Integer version (increment on breaking changes)
- `parts`: Physical components that can be controlled (optional)
- `attributes`: Properties and states that are measured (optional)
  - `space`: Ordered list of qualitative values (strings)
  - `mutable`: Boolean (default: true)
  - `default`: Default value (must be in space, or first value used)

**Legacy Format:** Objects using only `attributes` (no `parts`) are still fully supported.

### Actions

Actions are defined in `kb/actions/<object_type>/*.yaml` files with a new human-readable structured format:

```yaml
# kb/actions/flashlight/flip_switch.yaml
action: flip_switch
object_type: flashlight

parameters:
  to:
    space: ["off", "on"]      # Must be valid switch position

structured_preconditions:
  parameter_validation:
    - parameter: to
      must_be_in: ["off", "on"]
      description: "Switch can only be set to off or on"
  
  logic_constraints:
    - if: 'to == "on"'
      then: 'battery_level != "empty"'
      description: "Cannot turn on flashlight with empty battery"

structured_effects:
  assignments:
    - component: switch
      value: to
      description: "Set switch to requested position"
    
    - component: bulb
      value: '"on" if switch == "on" else "off"'
      description: "Bulb follows switch state automatically"
  
  trends:
    - component: battery_level
      trend: down
      condition: 'switch == "on"'
      description: "Battery drains when light is on"
```

**Schema Rules:**
- `action`: Action name (unique within object type)
- `object_type`: Target object type name
- `parameters`: Map of parameter specifications
  - `space`: Optional list constraining parameter values
- `structured_preconditions`: Human-readable precondition rules
  - `parameter_validation`: List of parameter validation rules
  - `logic_constraints`: List of if-then logic constraints
- `structured_effects`: Organized effect definitions
  - `assignments`: Component value assignments
  - `trends`: Trend direction changes
  - `steps`: Quantity space stepping operations (inc/dec)

**Legacy Format:** Actions using `preconditions` and `effects` (raw DSL) are still fully supported.

### DSL Expression Reference

**Supported Operations:**
```python
# Literals and variables
"string_literal"
variable_name
[list, of, values]

# Comparisons
attr == "value"
param != "other"
value in ["list", "of", "options"]
result not in excluded_values

# Boolean logic
condition1 and condition2
condition1 or condition2
not condition

# Conditional expressions
"yes" if condition else "no"

# Implication (syntactic sugar)
A -> B  # Equivalent to: (not A) or B
```

**Effect Types:**
```python
# Value assignment
attribute = expression

# Trend assignment  
attribute trend = "up"|"down"|"none"

# Quantity space stepping
attribute inc  # Move up one level
attribute dec  # Move down one level
```

---

## CLI Reference

### `sim validate`

Validate object types and optionally actions.

```bash
sim validate [OPTIONS]

Options:
  --objs PATH   Path to kb/objects folder (default: kb/objects)
  --acts PATH   Path to kb/actions folder (validates actions if provided)
```

**Examples:**
```bash
sim validate                    # Validate objects only
sim validate --acts kb/actions  # Validate objects and actions
```

### `sim show`

Display object type information.

```bash
sim show object NAME --version VERSION [OPTIONS]

Arguments:
  NAME        Object type name
  VERSION     Object type version

Options:
  --path PATH  Path to kb/objects folder (default: kb/objects)
```

**Examples:**
```bash
sim show object flashlight --version 1
sim show object kettle -v 1 --path custom/objects
```

### `sim apply`

Apply an action to an object state.

```bash
sim apply OBJECT_NAME --version VERSION ACTION_NAME [OPTIONS]

Arguments:
  OBJECT_NAME  Object type name
  ACTION_NAME  Action name
  VERSION      Object type version

Options:
  -p, --param KEY=VALUE  Action parameters (repeatable)
  -s, --state PATH       JSON state file (uses default state if omitted)
  --objs PATH           Path to kb/objects folder
  --acts PATH           Path to kb/actions folder
```

**Examples:**
```bash
# Use default state
sim apply flashlight -v 1 flip_switch -p to=on

# Use custom state
sim apply flashlight -v 1 flip_switch -p to=off -s my_state.json

# Multiple parameters
sim apply complex_object -v 1 multi_param_action -p param1=value1 -p param2=value2
```

### `sim simulate`

Run a sequence of actions on an object and save the simulation history.

```bash
sim simulate OBJECT_NAME --version VERSION [OPTIONS]

Arguments:
  OBJECT_NAME  Object type name
  VERSION      Object type version

Options:
  -a, --action TEXT      Action in format 'action_name:param1=value1,param2=value2' (repeatable)
  -o, --output PATH      Output simulation file (default: simulation.yaml)
  -s, --state PATH       Path to initial state JSON (optional)
  -n, --name TEXT        Name for the simulation
  -d, --description TEXT Description of the simulation
  --stop-on-failure      Stop simulation on first failed action
  --report/--no-report   Show text report after simulation (default: show)
  --objs PATH           Path to kb/objects folder
  --acts PATH           Path to kb/actions folder
```

**Examples:**
```bash
# Simple flashlight on/off cycle
sim simulate flashlight -v 1 -a "flip_switch:to=on" -a "flip_switch:to=off" -o flashlight_cycle.yaml

# Kettle heating simulation with custom name
sim simulate kettle -v 1 -a "set_power:to=on" -n "kettle_heating" -d "Test kettle heating process"

# Use custom initial state and stop on first failure
sim simulate flashlight -v 1 -a "flip_switch:to=on" -s low_battery.json --stop-on-failure
```

### `sim replay`

Replay and analyze a saved simulation.

```bash
sim replay SIMULATION_FILE [OPTIONS]

Arguments:
  SIMULATION_FILE  Path to simulation YAML file

Options:
  -s, --step INTEGER     Show state at specific step (0=initial, 1=after step 1, etc.)
  --table               Show state as table at specified step
  --report/--no-report  Show full text report (default: show)
```

**Examples:**
```bash
# Show full simulation report
sim replay flashlight_cycle.yaml

# Show state after step 2 as a table
sim replay simulation.yaml --step 2 --table

# Show only specific step without full report
sim replay simulation.yaml --step 1 --no-report
```

**State JSON Format:**
```json
{
  "values": {
    "switch": "on",
    "bulb": "on", 
    "battery_level": "low"
  },
  "trends": {
    "battery_level": "down"
  }
}
```

---

## Development

### Setup

```bash
# Install dependencies
uv sync

# Install pre-commit hooks (if using)
uv run pre-commit install

# Run tests
uv run pytest tests/ -v

# Type checking
uv run mypy src/

# Linting
uv run ruff check src/ tests/
```

### Project Configuration

**Dependencies** (`pyproject.toml`):
- `pydantic>=2.4.0` - Data validation and parsing
- `PyYAML>=6.0` - YAML file processing  
- `typer>=0.12.0` - CLI framework
- `rich>=13.7.0` - Rich terminal output

**Quality Tools:**
- **Ruff**: Fast Python linter and formatter
- **MyPy**: Static type checking
- **Pytest**: Test framework

### Adding New Object Types

1. Create YAML file in `kb/objects/`:
```yaml
type: new_object
version: 1
attributes:
  attr_name: { space: [val1, val2, val3], mutable: true, default: val1 }
```

2. Validate definition:
```bash
uv run sim validate
uv run sim show object new_object --version 1
```

3. Add tests in `tests/`:
```python
def test_new_object():
    reg = load_object_types("kb/objects")
    obj = reg.get("new_object", 1)
    assert obj.name == "new_object"
    # ... additional assertions
```

### Adding New Actions

1. Create YAML file in `kb/actions/<object_type>/` using the new structured format:
```yaml
action: new_action
object_type: existing_object
parameters:
  param: { space: [option1, option2] }

structured_preconditions:
  parameter_validation:
    - parameter: param
      must_be_in: ["option1", "option2"]
      description: "Parameter must be valid option"

structured_effects:
  assignments:
    - component: target_attr
      value: param
      description: "Set target attribute to parameter value"
```

2. Validate and test:
```bash
uv run sim validate --acts kb/actions
uv run sim apply existing_object -v 1 new_action -p param=option1
```

3. Add comprehensive tests covering success and failure cases.

### Working with Simulations

Simulations provide a powerful way to test action sequences and analyze state progressions:

1. **Create simulation:**
```bash
uv run sim simulate flashlight -v 1 -a "flip_switch:to=on" -a "flip_switch:to=off" -o test_cycle.yaml
```

2. **Analyze results:**
```bash
# Full report
uv run sim replay test_cycle.yaml

# Specific state inspection
uv run sim replay test_cycle.yaml --step 1 --table

# Compare states
python -c "
from tests.test_sequence_simulation import create_test_flashlight_simulation, compare_simulation_states
sim = create_test_flashlight_simulation()
compare_simulation_states(sim, 0, 2)
"
```

3. **Simulation files** contain complete state transition history in YAML format:
   - Initial state and object type information
   - Step-by-step action applications with parameters
   - State diffs and transition results
   - Success/failure status and error reasons
   - Human-readable timestamps and descriptions

---

## Implementation Roadmap

### Phase 3 - Unknowns & Blocked Outcomes
**Status:** 🔄 Next Up

- Allow `unknown` as valid value in `ObjectState.values`
- Add `status="blocked"` to `TransitionResult` 
- Return blocked status when preconditions reference unknowns
- Add `sim resolve` command to fill unknown values
- Comprehensive tests for blocked/unblocked transitions

### Phase 4 - Environment Ticks (Single Object)
**Status:** 📋 Planned

- `EnvironmentRule` model with `when`/`do` predicates
- `tick(state, rules) -> state'` API for discrete processes
- CLI: `sim tick` command with configurable tick counts
- Deterministic step behavior with boundary clamping

### Phase 5 - Constraints & Immutability  
**Status:** 📋 Planned

- Enforce `AttributeType.mutable == False` in action engine
- Pluggable constraint validation system
- `TransitionResult.violations` for constraint failures
- Configurable policies (reject vs. warn on violations)

### Phase 6 - Authoring Ergonomics & Property Tests
**Status:** 📋 Planned

- CLI scaffolding: `sim new object`, `sim new action`
- Introspection: `sim diff types`, `sim where-used`
- Property-based tests with Hypothesis
- QuantitySpace monotonicity verification

### Phase 7 - SQLite Persistence (Optional)
**Status:** 📋 Planned

- Versioned storage for types and transitions
- Indexed queries for rollout analysis
- Migration tools: `sim migrate`, `sim export`
- Performance optimization for large datasets

### Phase 8 - Scenario Generator & Dataset Packaging
**Status:** 📋 Planned

- `ScenarioBuilder` for initial state sampling
- `ActionSequencer` for valid action sequences
- JSONL export with deterministic seeds
- Comprehensive benchmark dataset generation

### Phase 9 - Multi-Object World & Relations
**Status:** 📋 Planned

- `WorldState` with multiple object instances
- Multi-object actions with atomic semantics
- Cross-object environment rules
- Optional composition/relations modeling

---

## Design Principles

### Core Values

1. **Determinism First**: Same inputs must always produce identical outputs
2. **Safety**: Never use Python `eval()` - only AST-whitelisted DSL operations  
3. **Validation**: Strict validation at every boundary with helpful error messages
4. **Traceability**: Complete audit trail for every state change
5. **Composability**: Small, focused components with clear interfaces

### Quality Standards

- **Type Safety**: Full type hints with MyPy validation
- **Testing**: Comprehensive unit and integration test coverage
- **Documentation**: Living documentation that stays current with code
- **Performance**: Efficient algorithms suitable for large-scale dataset generation
- **Maintainability**: Clean, readable code following Python best practices

### Schema Evolution

- **Versioning**: All schemas use explicit version numbers
- **Backward Compatibility**: Breaking changes require version increments
- **Migration**: Clear migration paths between schema versions
- **Deprecation**: Graceful handling of deprecated features

---

## Contributing

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Add** comprehensive tests for new functionality
4. **Ensure** all quality checks pass (`uv run pytest`, `uv run mypy`, `uv run ruff check`)
5. **Update** documentation as needed
6. **Commit** changes (`git commit -m 'Add amazing feature'`)
7. **Push** to branch (`git push origin feature/amazing-feature`)
8. **Create** a Pull Request

### Development Guidelines

- Follow existing code style and patterns
- Add type hints to all public APIs
- Include docstrings for complex functions
- Write tests for both success and failure cases
- Update CLI help text and README for user-facing changes

---

## License

[Add your license information here]

## Citation

[Add citation information if this becomes a published research tool]