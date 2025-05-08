# -*- coding: utf-8 -*-
"""Database of components and their properties."""


class ComponentDatabase:  # pylint: disable=too-few-public-methods
    """Manages the database of known circuit components and their properties."""

    def __init__(self):
        # Define the database of components and their properties
        self.components = {
            "R": {"arity": 2},  # Resistor
            "C": {"arity": 2},  # Capacitor
            "L": {"arity": 2},  # Inductor
            "Nmos": {"arity": 4, "terminals": ["G", "D", "S", "B"]},
            "Pmos": {"arity": 4, "terminals": ["G", "D", "S", "B"]},
            "V": {"arity": 2, "terminals": ["pos", "neg"]},
            "I": {"arity": 2, "terminals": ["pos", "neg"]},
            "Opamp": {
                "arity": 3,
                "terminals": ["IN+", "IN-", "OUT"],
            },  # Basic, could be 5
            # Behavioral / Internal types used by transformations or advanced features
            "controlled_source": {
                "arity": 2,
                "behavioral": True,
                "terminals": ["par_t1", "par_t2"],
            },
            "noise_source": {
                "arity": 2,
                "behavioral": True,
                "terminals": ["par_t1", "par_t2"],
            },
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
