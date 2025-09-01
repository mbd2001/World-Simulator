"""
Object Type Definitions

This module defines ObjectType, which represents the schema for a type of object
in the simulation. It aggregates attributes and provides methods for creating
default instances.

Key concepts:
- Object types are versioned schemas defining what attributes an object has
- Each object type can create default states for simulation
- Validation ensures all object types have at least one attribute
"""

from __future__ import annotations
from pydantic import BaseModel, field_validator
from typing import Dict, TYPE_CHECKING
from simulator.core.attributes import AttributeType

if TYPE_CHECKING:
    from simulator.core.state import ObjectState


class ObjectType(BaseModel):
    """
    Schema definition for a type of object in the simulation.
    
    ObjectType defines what parts and attributes an object has, their value spaces,
    and how to create default instances. It serves as the template from
    which ObjectState instances are created.
    
    The new structure distinguishes between:
    - Parts: Physical components that can be controlled (e.g., switch, bulb)
    - Attributes: Properties or states (e.g., battery_level, temperature)
    
    Attributes:
        name: Unique identifier for this object type
        version: Schema version number (increment for breaking changes)
        parts: Dictionary mapping part names to their definitions
        attributes: Dictionary mapping attribute names to their definitions
        
    Examples:
        >>> from simulator.core.quantity import QuantitySpace
        >>> from simulator.core.attributes import AttributeType
        >>> 
        >>> # Define parts (physical components)
        >>> switch_space = QuantitySpace(name="switch", levels=["off", "on"])
        >>> switch_part = AttributeType(name="switch", space=switch_space, default="off")
        >>> 
        >>> # Define attributes (properties/states)
        >>> battery_space = QuantitySpace(name="battery", levels=["empty", "low", "med", "high"])
        >>> battery_attr = AttributeType(name="battery_level", space=battery_space, default="med")
        >>> 
        >>> # Create object type
        >>> flashlight = ObjectType(
        ...     name="flashlight",
        ...     version=1,
        ...     parts={"switch": switch_part},
        ...     attributes={"battery_level": battery_attr}
        ... )
    """
    name: str
    version: int
    parts: Dict[str, AttributeType] = {}
    attributes: Dict[str, AttributeType] = {}

    @field_validator("parts", "attributes")
    @classmethod
    def _validate_object_has_components(cls, v: Dict[str, AttributeType], info) -> Dict[str, AttributeType]:
        """
        Ensure that object types have at least one part or attribute.
        
        Args:
            v: Dictionary of parts or attributes to validate
            info: Validation context information
            
        Returns:
            The validated dictionary
            
        Raises:
            ValueError: If the object has no parts and no attributes
        """
        # We'll check the total at model level
        return v

    def model_post_init(self, __context) -> None:
        """Post-initialization validation to ensure object has at least one component."""
        if not self.parts and not self.attributes:
            raise ValueError("ObjectType must have at least one part or attribute")

    def default_state(self) -> "ObjectState":
        """
        Create a default state instance for this object type.
        
        Uses each part and attribute's effective default value (explicit default if set,
        otherwise the first value in the quantity space).
        
        Returns:
            ObjectState with all parts and attributes set to their default values
            
        Examples:
            >>> flashlight_type = ObjectType(...)  # Assume defined above
            >>> default_state = flashlight_type.default_state()
            >>> print(default_state.values)
            {'switch': 'off', 'bulb': 'off', 'battery_level': 'med'}
        """
        values = {}
        # Add default values for all parts
        for part_name, part in self.parts.items():
            values[part_name] = part.get_effective_default()
        # Add default values for all attributes
        for attr_name, attr in self.attributes.items():
            values[attr_name] = attr.get_effective_default()
        # Import here to avoid circular dependency
        from simulator.core.state import ObjectState
        return ObjectState(object_type=self, values=values)

    def has_component(self, component_name: str) -> bool:
        """
        Check if this object type has a specific part or attribute.
        
        Args:
            component_name: Name of the part or attribute to check
            
        Returns:
            True if the component exists, False otherwise
        """
        return component_name in self.parts or component_name in self.attributes

    def has_attribute(self, attr_name: str) -> bool:
        """
        Check if this object type has a specific attribute (backward compatibility).
        
        Args:
            attr_name: Name of the component to check
            
        Returns:
            True if the component exists (part or attribute), False otherwise
        """
        return self.has_component(attr_name)

    def get_component(self, component_name: str) -> AttributeType:
        """
        Get a part or attribute definition by name.
        
        Args:
            component_name: Name of the part or attribute to retrieve
            
        Returns:
            The AttributeType for the specified component
            
        Raises:
            KeyError: If the component doesn't exist
        """
        if component_name in self.parts:
            return self.parts[component_name]
        elif component_name in self.attributes:
            return self.attributes[component_name]
        else:
            raise KeyError(f"Component '{component_name}' not found in object type '{self.name}'")

    def get_attribute(self, attr_name: str) -> AttributeType:
        """
        Get an attribute definition by name (backward compatibility).
        
        Args:
            attr_name: Name of the component to retrieve
            
        Returns:
            The AttributeType for the specified component
            
        Raises:
            KeyError: If the component doesn't exist
        """
        return self.get_component(attr_name)

    def validate_state_values(self, values: Dict[str, str]) -> None:
        """
        Validate that a set of component values is compatible with this object type.
        
        Args:
            values: Dictionary mapping component names to values
            
        Raises:
            ValueError: If any component is missing, unknown, or has invalid values
        """
        # Get all expected component names (parts + attributes)
        all_components = set(self.parts.keys()) | set(self.attributes.keys())
        
        # Check for missing required components
        missing_components = all_components - set(values.keys())
        if missing_components:
            raise ValueError(f"Missing required components: {sorted(missing_components)}")
        
        # Check for unknown components
        unknown_components = set(values.keys()) - all_components
        if unknown_components:
            raise ValueError(f"Unknown components for {self.name}: {sorted(unknown_components)}")
        
        # Validate each component value
        for component_name, value in values.items():
            component = self.get_component(component_name)
            component.validate_value(value)

    def get_identifier(self) -> str:
        """
        Get a unique identifier string for this object type.
        
        Returns:
            String in format "name@vN" (e.g., "flashlight@v1")
        """
        return f"{self.name}@v{self.version}"

    def __str__(self) -> str:
        """Human-readable string representation."""
        part_count = len(self.parts)
        attr_count = len(self.attributes)
        total_count = part_count + attr_count
        components = []
        if self.parts:
            components.extend(f"{name}(part)" for name in self.parts.keys())
        if self.attributes:
            components.extend(f"{name}(attr)" for name in self.attributes.keys())
        component_str = ", ".join(components)
        return f"ObjectType({self.get_identifier()}: {total_count} components [{component_str}])"

    def __repr__(self) -> str:
        """Detailed string representation for debugging."""
        return (
            f"ObjectType(name='{self.name}', version={self.version}, "
            f"parts={list(self.parts.keys())}, attributes={list(self.attributes.keys())})"
        )
