"""
YAML Object Type Loader

This module handles loading object type definitions from YAML files in the
knowledge base. It parses the YAML structure and creates validated ObjectType
instances with their associated attributes and quantity spaces.

Key features:
- Recursive directory scanning for YAML files
- Comprehensive validation with helpful error messages
- Automatic type conversion and default handling
- Registry population for fast lookup
"""

from __future__ import annotations
import os
import glob
import yaml
from pathlib import Path
from typing import Dict, Any, List
from simulator.core.quantity import QuantitySpace
from simulator.core.attributes import AttributeType
from simulator.core.object_types import ObjectType
from simulator.core.registry import Registry


def load_object_types(path: str) -> Registry:
    """
    Load all object types from YAML files in a directory tree.
    
    Recursively scans the specified directory for YAML files and loads
    each one as an ObjectType definition. All loaded types are registered
    in a single Registry for fast lookup.
    
    Args:
        path: Root directory to scan for YAML files
        
    Returns:
        Registry containing all loaded object types
        
    Raises:
        ValueError: If any YAML file has invalid structure or content
        FileNotFoundError: If the path doesn't exist
        
    Examples:
        >>> registry = load_object_types("kb/objects")
        >>> flashlight = registry.get("flashlight", 1)
        >>> print(f"Loaded {registry.count()} object types")
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Object types directory not found: {path}")
    
    registry = Registry()
    
    # Find all YAML files recursively
    yaml_pattern = os.path.join(path, "**", "*.yaml")
    yaml_files = sorted(glob.glob(yaml_pattern, recursive=True))
    
    if not yaml_files:
        # Empty directory is valid, just return empty registry
        return registry
    
    # Load each YAML file
    for file_path in yaml_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {file_path}: {e}") from e
        except OSError as e:
            raise ValueError(f"Cannot read file {file_path}: {e}") from e
        
        # Parse and register the object type
        try:
            obj_type = _parse_object_type(data, source=file_path)
            registry.add_object_type(obj_type)
        except Exception as e:
            # Re-raise with file context if not already included
            if file_path not in str(e):
                raise ValueError(f"Error loading {file_path}: {e}") from e
            raise
    
    return registry


def _parse_object_type(data: Dict[str, Any], source: str) -> ObjectType:
    """
    Parse a single object type definition from YAML data.
    
    Validates the YAML structure and creates an ObjectType with all
    its attributes properly configured.
    
    Args:
        data: Parsed YAML data as a dictionary
        source: Source file path for error reporting
        
    Returns:
        Validated ObjectType instance
        
    Raises:
        ValueError: If the YAML structure is invalid or incomplete
    """
    # Validate required top-level fields
    if "type" not in data:
        raise ValueError(f"{source}: missing required field 'type'")
    if "version" not in data:
        raise ValueError(f"{source}: missing required field 'version'")
    
    # Extract and validate basic fields
    name = str(data["type"]).strip()
    if not name:
        raise ValueError(f"{source}: 'type' field cannot be empty")
    
    try:
        version = int(data["version"])
        if version < 1:
            raise ValueError(f"{source}: 'version' must be a positive integer")
    except (ValueError, TypeError) as e:
        raise ValueError(f"{source}: 'version' must be a positive integer") from e
    
    # Parse parts section (optional)
    parts_raw = data.get("parts", {})
    if not isinstance(parts_raw, dict):
        raise ValueError(f"{source}: 'parts' must be a mapping")
    
    # Parse attributes section (optional, but backward compatible with old format)
    attrs_raw = data.get("attributes", {})
    if not isinstance(attrs_raw, dict):
        raise ValueError(f"{source}: 'attributes' must be a mapping")
    
    # Backward compatibility: if no parts/attributes distinction, treat all as attributes
    if not parts_raw and attrs_raw and "parts" not in data:
        # Legacy format - all components are in attributes section
        pass
    
    # Ensure object has at least one part or attribute
    if not parts_raw and not attrs_raw:
        raise ValueError(f"{source}: object must have at least one part or attribute")
    
    # Parse each part
    parts: Dict[str, AttributeType] = {}
    for part_name, part_spec in parts_raw.items():
        try:
            part = _parse_component(part_name, part_spec, name, source, "part")
            parts[part_name] = part
        except Exception as e:
            raise ValueError(f"{source}: error in part '{part_name}': {e}") from e
    
    # Parse each attribute
    attributes: Dict[str, AttributeType] = {}
    for attr_name, attr_spec in attrs_raw.items():
        try:
            attribute = _parse_component(attr_name, attr_spec, name, source, "attribute")
            attributes[attr_name] = attribute
        except Exception as e:
            raise ValueError(f"{source}: error in attribute '{attr_name}': {e}") from e
    
    return ObjectType(name=name, version=version, parts=parts, attributes=attributes)


def _parse_component(component_name: str, spec: Dict[str, Any], object_name: str, source: str, component_type: str) -> AttributeType:
    """
    Parse a single component (part or attribute) definition from YAML data.
    
    Args:
        component_name: Name of the component
        spec: Component specification from YAML
        object_name: Name of the parent object type
        source: Source file path for error reporting
        component_type: Type of component ("part" or "attribute") for error messages
        
    Returns:
        Validated AttributeType instance
        
    Raises:
        ValueError: If the component specification is invalid
    """
    if not isinstance(spec, dict):
        raise ValueError(f"{component_type} specification must be a mapping")
    
    # Parse space (required)
    if "space" not in spec:
        raise ValueError("missing required field 'space'")
    
    space_levels = spec["space"]
    if not isinstance(space_levels, list):
        raise ValueError("'space' must be a list")
    if not space_levels:
        raise ValueError("'space' cannot be empty")
    
    # Convert all space levels to strings and validate uniqueness
    levels = [str(level) for level in space_levels]
    if len(set(levels)) != len(levels):
        raise ValueError(f"'space' values must be unique, got: {levels}")
    
    # Create quantity space
    space_name = f"{object_name}.{component_name}"
    space = QuantitySpace(name=space_name, levels=levels)
    
    # Parse mutability (optional, defaults to True)
    mutable = spec.get("mutable", True)
    if not isinstance(mutable, bool):
        raise ValueError("'mutable' must be true or false")
    
    # Parse default value (optional)
    default = spec.get("default", None)
    if default is not None:
        default = str(default)
        # Validate default is in the space
        if not space.has(default):
            raise ValueError(f"default value {default!r} not in space {levels}")
    
    return AttributeType(
        name=component_name,
        space=space,
        mutable=mutable,
        default=default
    )


def validate_object_types_directory(path: str) -> List[str]:
    """
    Validate all object type YAML files in a directory without loading them.
    
    Useful for checking the validity of a knowledge base before loading.
    
    Args:
        path: Directory path to validate
        
    Returns:
        List of validation error messages (empty if all files are valid)
    """
    errors = []
    
    if not os.path.exists(path):
        return [f"Directory not found: {path}"]
    
    yaml_pattern = os.path.join(path, "**", "*.yaml")
    yaml_files = sorted(glob.glob(yaml_pattern, recursive=True))
    
    for file_path in yaml_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            _parse_object_type(data, source=file_path)
        except Exception as e:
            errors.append(f"{file_path}: {e}")
    
    return errors


def get_object_type_files(path: str) -> List[str]:
    """
    Get a list of all YAML files in the object types directory.
    
    Args:
        path: Directory path to scan
        
    Returns:
        List of YAML file paths (relative to the input path)
    """
    if not os.path.exists(path):
        return []
    
    yaml_pattern = os.path.join(path, "**", "*.yaml")
    yaml_files = glob.glob(yaml_pattern, recursive=True)
    
    # Convert to relative paths
    base_path = Path(path)
    return [str(Path(f).relative_to(base_path)) for f in sorted(yaml_files)]