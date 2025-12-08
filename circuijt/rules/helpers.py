# -*- coding: utf-8 -*-
"""Helper utilities for circuit transformation rules."""

import uuid
import re
from typing import Dict, Any, Optional


class RuleHelperCollection:
    """
    Collection of utility methods for circuit transformation rules.

    Provides methods for parameter parsing, value formatting, and unique ID generation.
    """

    @staticmethod
    def generate_unique_id(prefix: str = "node") -> str:
        """
        Generate a unique identifier with an optional prefix.

        Args:
            prefix (str): Prefix for the generated ID. Defaults to "node".

        Returns:
            str: A unique identifier string.
        """
        unique_suffix = str(uuid.uuid4()).replace("-", "")[:8]
        return f"{prefix}_{unique_suffix}"

    @staticmethod
    def parse_component_value(value_str: str) -> Dict[str, Any]:
        """
        Parse a component value string (e.g., "10k", "1.5M", "100p").

        Args:
            value_str (str): String representation of the component value.

        Returns:
            Dict[str, Any]: Dictionary containing:
                - 'value': float value in base units
                - 'unit': string representing the unit
                - 'original': original input string
                - 'formatted': formatted string representation
        """
        if not value_str:
            return {"value": 0.0, "unit": "", "original": value_str, "formatted": "0"}

        # Define multiplier mapping for common prefixes
        multipliers = {
            "p": 1e-12,  # pico
            "n": 1e-9,  # nano
            "u": 1e-6,  # micro
            "m": 1e-3,  # milli
            "k": 1e3,  # kilo
            "M": 1e6,  # mega
            "G": 1e9,  # giga
        }

        # Regular expression to parse value and unit
        pattern = r"^([0-9]*\.?[0-9]+)\s*([a-zA-Z]*)$"
        match = re.match(pattern, value_str.strip())

        if not match:
            # If no match, assume it's just a number
            try:
                value = float(value_str)
                return {"value": value, "unit": "", "original": value_str, "formatted": str(value)}
            except ValueError:
                return {"value": 0.0, "unit": "", "original": value_str, "formatted": "0"}

        numeric_part, unit_part = match.groups()

        try:
            base_value = float(numeric_part)
        except ValueError:
            base_value = 0.0

        # Apply multiplier if unit has a prefix
        if unit_part and unit_part[0] in multipliers:
            multiplier = multipliers[unit_part[0]]
            actual_unit = unit_part[1:] if len(unit_part) > 1 else ""
            final_value = base_value * multiplier
        else:
            actual_unit = unit_part
            final_value = base_value

        return {
            "value": final_value,
            "unit": actual_unit,
            "original": value_str,
            "formatted": RuleHelperCollection.format_component_value(final_value, actual_unit),
        }

    @staticmethod
    def format_component_value(value: float, unit: str = "") -> str:
        """
        Format a component value with appropriate prefix and unit.

        Args:
            value (float): Numeric value in base units.
            unit (str): Unit string (e.g., 'ohm', 'F', 'H').

        Returns:
            str: Formatted string with appropriate prefix.
        """
        if value == 0:
            return f"0{unit}"

        # Define prefixes in order from largest to smallest
        prefixes = [
            ("G", 1e9),
            ("M", 1e6),
            ("k", 1e3),
            ("", 1),
            ("m", 1e-3),
            ("u", 1e-6),
            ("n", 1e-9),
            ("p", 1e-12),
        ]

        abs_value = abs(value)

        for prefix, multiplier in prefixes:
            if abs_value >= multiplier:
                scaled_value = value / multiplier
                # Format to remove unnecessary decimal places
                if scaled_value == int(scaled_value):
                    return f"{int(scaled_value)}{prefix}{unit}"
                else:
                    return f"{scaled_value:.3g}{prefix}{unit}"

        # If value is very small, use scientific notation
        return f"{value:.3g}{unit}"

    @staticmethod
    def combine_resistor_values(value1: float, value2: float) -> float:
        """
        Combine two resistor values in series (simple addition).

        Args:
            value1 (float): First resistor value in ohms.
            value2 (float): Second resistor value in ohms.

        Returns:
            float: Combined resistance value in ohms.
        """
        return value1 + value2

    @staticmethod
    def extract_component_value_from_node(circuit, component_node: str) -> Optional[float]:
        """
        Extract the numeric value of a component from its graph node data.

        Args:
            circuit: Circuit object containing the graph.
            component_node (str): Node identifier for the component.

        Returns:
            Optional[float]: Component value if found and parseable, None otherwise.
        """
        if component_node not in circuit.graph.nodes:
            return None

        node_data = circuit.graph.nodes[component_node]

        # Look for value in common attribute names
        for attr in ["value", "resistance", "capacitance", "inductance"]:
            if attr in node_data:
                value_data = node_data[attr]
                if isinstance(value_data, (int, float)):
                    return float(value_data)
                elif isinstance(value_data, str):
                    parsed = RuleHelperCollection.parse_component_value(value_data)
                    return parsed["value"]

        return None

    @staticmethod
    def set_component_value_on_node(circuit, component_node: str, value: float, unit: str = "") -> None:
        """
        Set the value attribute on a component node.

        Args:
            circuit: Circuit object containing the graph.
            component_node (str): Node identifier for the component.
            value (float): Numeric value to set.
            unit (str): Unit string for formatting.
        """
        if component_node in circuit.graph.nodes:
            formatted_value = RuleHelperCollection.format_component_value(value, unit)
            circuit.graph.nodes[component_node]["value"] = formatted_value

    @staticmethod
    def get_component_type(circuit, component_node: str) -> Optional[str]:
        """
        Get the component type from a component node.

        Args:
            circuit: Circuit object containing the graph.
            component_node (str): Node identifier for the component.

        Returns:
            Optional[str]: Component type if found, None otherwise.
        """
        if component_node not in circuit.graph.nodes:
            return None

        node_data = circuit.graph.nodes[component_node]
        return node_data.get("instance_type")

    @staticmethod
    def is_resistor(circuit, component_node: str) -> bool:
        """
        Check if a component node represents a resistor.

        Args:
            circuit: Circuit object containing the graph.
            component_node (str): Node identifier for the component.

        Returns:
            bool: True if the component is a resistor, False otherwise.
        """
        return RuleHelperCollection.get_component_type(circuit, component_node) == "R"
