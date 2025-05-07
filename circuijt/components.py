# -*- coding: utf-8 -*-
"""Database of components and their properties."""

class ComponentDatabase:
    """A database for storing component properties like arity."""

    def __init__(self):
        # Define the database of components and their properties
        self.components = {
            "R": {"arity": 2},  # Resistor
            "C": {"arity": 2},  # Capacitor
            "L": {"arity": 2},  # Inductor
            "Nmos": {"arity": 4},  # NMOS Transistor
            "Pmos": {"arity": 4},  # PMOS Transistor
            "V": {"arity": 2},  # Voltage Source
            "I": {"arity": 2},  # Current Source
            "Opamp": {"arity": 3},  # Operational Amplifier
        }

    def get_arity(self, component_type):
        """Get the arity of a component type.

        Args:
            component_type (str): The type of the component (e.g., "R", "C").

        Returns:
            int: The arity of the component, or None if the component is not found.
        """
        return self.components.get(component_type, {}).get("arity")

# Example usage
if __name__ == "__main__":
    db = ComponentDatabase()
    print("Arity of R:", db.get_arity("R"))  # Output: 2
    print("Arity of Nmos:", db.get_arity("Nmos"))  # Output: 4
    print("Arity of Unknown:", db.get_arity("Unknown"))  # Output: None