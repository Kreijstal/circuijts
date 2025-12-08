# -*- coding: utf-8 -*-
"""Concrete implementation of circuit transformation rules."""

from typing import List, Dict, Any
from .abc import RuleInterface
from .helpers import RuleHelperCollection


class BasicSeriesResistorRule(RuleInterface):
    """
    A concrete rule for combining series resistors.

    This rule identifies pairs of resistors connected in series and combines them
    into a single equivalent resistor with the sum of their resistance values.
    """

    def get_name(self) -> str:
        """Get the name of this rule."""
        return "BasicSeriesResistorRule"

    def get_description(self) -> str:
        """Get a description of what this rule does."""
        return "Combines two resistors connected in series into a single equivalent resistor"

    def find_candidates(self, circuit) -> List[Dict[str, Any]]:
        """
        Find all pairs of resistors connected in series.

        A series connection is identified when:
        1. Two resistors are connected to the same electrical net
        2. That electrical net connects to exactly these two resistors
        3. Each resistor has exactly two connections (standard 2-terminal resistor)

        Args:
            circuit: Circuit object to search for candidates.

        Returns:
            List[Dict[str, Any]]: List of candidate dictionaries, each containing:
                - 'resistor1': First resistor node name
                - 'resistor2': Second resistor node name
                - 'connecting_net': Net node connecting them
                - 'r1_value': Value of first resistor
                - 'r2_value': Value of second resistor
                - 'r1_other_net': The other net connected to resistor1
                - 'r2_other_net': The other net connected to resistor2
        """
        candidates = []

        # Get all resistor components
        resistor_nodes = [node for node in circuit.get_component_nodes() if RuleHelperCollection.is_resistor(circuit, node)]

        # Get all electrical net nodes
        net_nodes = circuit.get_nodes(node_kind="electrical_net")

        # Check each electrical net for series resistor connections
        for net_node in net_nodes:
            # Find all resistors connected to this net
            connected_resistors = []
            for resistor in resistor_nodes:
                if circuit.graph.has_edge(resistor, net_node):
                    connected_resistors.append(resistor)

            # If exactly 2 resistors are connected to this net, check if they form a series
            if len(connected_resistors) == 2:
                r1, r2 = connected_resistors

                # Verify each resistor has exactly 2 connections (2-terminal components)
                r1_connections = list(circuit.graph.neighbors(r1))
                r2_connections = list(circuit.graph.neighbors(r2))

                if len(r1_connections) == 2 and len(r2_connections) == 2:
                    # Find the other nets each resistor connects to
                    r1_other_net = None
                    r2_other_net = None

                    for net in r1_connections:
                        if net != net_node:
                            r1_other_net = net
                            break

                    for net in r2_connections:
                        if net != net_node:
                            r2_other_net = net
                            break

                    # Ensure the other nets are different (not the same resistor loop)
                    if r1_other_net and r2_other_net and r1_other_net != r2_other_net:
                        # Extract resistor values
                        r1_value = RuleHelperCollection.extract_component_value_from_node(circuit, r1)
                        r2_value = RuleHelperCollection.extract_component_value_from_node(circuit, r2)

                        # Default to 1.0 if no value found (unit resistor)
                        if r1_value is None:
                            r1_value = 1.0
                        if r2_value is None:
                            r2_value = 1.0

                        candidate = {
                            "resistor1": r1,
                            "resistor2": r2,
                            "connecting_net": net_node,
                            "r1_value": r1_value,
                            "r2_value": r2_value,
                            "r1_other_net": r1_other_net,
                            "r2_other_net": r2_other_net,
                        }
                        candidates.append(candidate)

        return candidates

    def apply_to_candidate(self, circuit, candidate: Dict[str, Any]) -> None:
        """
        Apply the series resistor combination to a specific candidate.

        This method:
        1. Calculates the combined resistance value
        2. Creates a new resistor node with the combined value
        3. Connects the new resistor between the two external nets
        4. Removes the original resistors and intermediate net
        5. Updates the DSU to reflect the net changes

        Args:
            circuit: Circuit object to modify.
            candidate: Candidate dictionary from find_candidates().
        """
        r1 = candidate["resistor1"]
        r2 = candidate["resistor2"]
        connecting_net = candidate["connecting_net"]
        r1_value = candidate["r1_value"]
        r2_value = candidate["r2_value"]
        r1_other_net = candidate["r1_other_net"]
        r2_other_net = candidate["r2_other_net"]

        # Calculate combined resistance
        combined_value = RuleHelperCollection.combine_resistor_values(r1_value, r2_value)

        # Generate a new unique name for the combined resistor
        new_resistor_name = RuleHelperCollection.generate_unique_id("R_combined")

        # Create the new combined resistor node
        circuit.graph.add_node(new_resistor_name, node_kind="component_instance", instance_type="R")

        # Set the combined value on the new resistor
        RuleHelperCollection.set_component_value_on_node(circuit, new_resistor_name, combined_value, "ohm")

        # Connect the new resistor between the two external nets
        circuit.graph.add_edge(new_resistor_name, r1_other_net, terminal="t1_series")
        circuit.graph.add_edge(new_resistor_name, r2_other_net, terminal="t2_series")

        # Remove the original resistors and their edges
        circuit.graph.remove_node(r1)
        circuit.graph.remove_node(r2)

        # Remove the intermediate connecting net if it has no other connections
        if circuit.graph.has_node(connecting_net):
            # Check if the connecting net has any remaining connections
            if len(list(circuit.graph.neighbors(connecting_net))) == 0:
                circuit.graph.remove_node(connecting_net)

        # Update DSU: since we're removing the intermediate net, we need to union
        # the two external nets in the DSU to reflect the direct connection
        # through the new combined resistor
        circuit.dsu.union(
            r1_other_net,
            r2_other_net,
            "series_resistor_combination",
            {"original_resistors": [r1, r2], "new_resistor": new_resistor_name, "combined_value": combined_value},
        )

        # Update circuit metadata if present
        if "transformations" not in circuit.metadata:
            circuit.metadata["transformations"] = []

        circuit.metadata["transformations"].append(
            {
                "rule": self.get_name(),
                "action": "series_resistor_combination",
                "original_components": [r1, r2],
                "new_component": new_resistor_name,
                "original_values": [r1_value, r2_value],
                "combined_value": combined_value,
                "removed_net": connecting_net,
            }
        )
