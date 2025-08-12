#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Example demonstrating the Circuit class, RuleInterface, and BasicSeriesResistorRule.

This example shows how to:
1. Create a Circuit object from a parsed circuit description
2. Apply transformation rules to simplify the circuit
3. Inspect the results of the transformations
"""

from circuijt.parser import ProtoCircuitParser
from circuijt.graph_utils import ast_to_graph
from circuijt.circuit import Circuit
from circuijt.rules.concrete_rules import BasicSeriesResistorRule


def demonstrate_series_resistor_simplification():
    """Demonstrate simplifying a circuit with series resistors."""
    print("=" * 60)
    print("CIRCUIT SIMPLIFICATION DEMONSTRATION")
    print("=" * 60)
    
    # Define a circuit with series resistors
    circuit_description = """
; Example Circuit with Series Resistors
R R1           ; 100 ohm resistor
R R2           ; 200 ohm resistor  
R R3           ; 300 ohm resistor

; Three resistors in series: (input) -- R1 -- R2 -- R3 -- (output)
(input) -- R1 -- R2 -- R3 -- (output)
"""
    
    print("Original Circuit Description:")
    print(circuit_description)
    
    # Parse the circuit
    parser = ProtoCircuitParser()
    statements, errors = parser.parse_text(circuit_description)
    
    if errors:
        print(f"Parser errors: {errors}")
        return
    
    # Convert to graph and create Circuit object
    graph, dsu = ast_to_graph(statements)
    circuit = Circuit(graph=graph, dsu=dsu)
    
    print(f"Initial circuit: {circuit}")
    print(f"Initial components: {circuit.get_component_nodes()}")
    
    # Set resistance values on components
    resistor_values = {"R1": 100.0, "R2": 200.0, "R3": 300.0}
    for comp, value in resistor_values.items():
        if comp in circuit.graph.nodes:
            circuit.graph.nodes[comp]['value'] = f"{value}ohm"
    
    # Create the series resistor rule
    rule = BasicSeriesResistorRule()
    print(f"\nUsing rule: {rule.get_description()}")
    
    # Apply the rule iteratively until no more transformations possible
    transformations = 0
    while rule.can_apply(circuit):
        print(f"\n--- Transformation {transformations + 1} ---")
        print(f"Components before: {len(circuit.get_component_nodes())}")
        
        candidates = rule.find_candidates(circuit)
        print(f"Found {len(candidates)} candidate(s) for transformation")
        
        if candidates:
            candidate = candidates[0]
            print(f"Applying rule to candidate: {candidate['resistor1']} + {candidate['resistor2']}")
            print(f"Values: {candidate['r1_value']} + {candidate['r2_value']} = {candidate['r1_value'] + candidate['r2_value']}")
        
        result = circuit.apply_rule_once(rule)
        
        if result:
            transformations += 1
            print(f"Components after: {len(circuit.get_component_nodes())}")
        else:
            print("No transformation applied")
            break
    
    print(f"\n--- Final Results ---")
    print(f"Total transformations applied: {transformations}")
    print(f"Final circuit: {circuit}")
    print(f"Final components: {circuit.get_component_nodes()}")
    
    # Show transformation history
    if 'transformations' in circuit.metadata:
        print(f"\nTransformation History:")
        for i, trans in enumerate(circuit.metadata['transformations']):
            print(f"  {i+1}. Combined {trans['original_components']} -> {trans['new_component']}")
            print(f"     Values: {trans['original_values']} -> {trans['combined_value']}")
    
    # Show final combined resistor value
    final_components = circuit.get_component_nodes()
    if final_components:
        final_resistor = final_components[0]
        final_value = circuit.graph.nodes[final_resistor].get('value', 'unknown')
        print(f"\nFinal combined resistor '{final_resistor}' has value: {final_value}")
        print(f"Expected total: {sum(resistor_values.values())}ohm")


def demonstrate_parallel_resistors():
    """Demonstrate that parallel resistors are NOT simplified by the series rule."""
    print("\n" + "=" * 60)
    print("PARALLEL RESISTORS (NOT SIMPLIFIED)")
    print("=" * 60)
    
    # Create a circuit with parallel resistors manually
    circuit = Circuit()
    
    # Add resistor nodes
    circuit.graph.add_node("R1", node_kind="component_instance", instance_type="R", value="100ohm")
    circuit.graph.add_node("R2", node_kind="component_instance", instance_type="R", value="200ohm")
    
    # Add net nodes
    circuit.graph.add_node("input", node_kind="electrical_net")
    circuit.graph.add_node("output", node_kind="electrical_net")
    
    # Connect in parallel: both resistors connect input to output
    circuit.graph.add_edge("R1", "input", terminal="t1")
    circuit.graph.add_edge("R1", "output", terminal="t2")
    circuit.graph.add_edge("R2", "input", terminal="t1")
    circuit.graph.add_edge("R2", "output", terminal="t2")
    
    print(f"Parallel circuit: {circuit}")
    print(f"Components: {circuit.get_component_nodes()}")
    
    rule = BasicSeriesResistorRule()
    can_apply = rule.can_apply(circuit)
    print(f"Can apply series resistor rule: {can_apply}")
    
    if can_apply:
        print("ERROR: Series rule should not apply to parallel resistors!")
    else:
        print("Correct: Series rule does not apply to parallel resistors.")


def demonstrate_mixed_components():
    """Demonstrate that the rule only affects resistors."""
    print("\n" + "=" * 60)
    print("MIXED COMPONENTS (SELECTIVE SIMPLIFICATION)")
    print("=" * 60)
    
    circuit = Circuit()
    
    # Add mixed components
    circuit.graph.add_node("R1", node_kind="component_instance", instance_type="R", value="100ohm")
    circuit.graph.add_node("C1", node_kind="component_instance", instance_type="C", value="1uF")
    circuit.graph.add_node("R2", node_kind="component_instance", instance_type="R", value="200ohm")
    
    # Add nets
    circuit.graph.add_node("net1", node_kind="electrical_net")
    circuit.graph.add_node("net2", node_kind="electrical_net")
    circuit.graph.add_node("net3", node_kind="electrical_net")
    circuit.graph.add_node("net4", node_kind="electrical_net")
    
    # Connect: net1 -- R1 -- net2 -- C1 -- net3 -- R2 -- net4
    circuit.graph.add_edge("R1", "net1", terminal="t1")
    circuit.graph.add_edge("R1", "net2", terminal="t2")
    circuit.graph.add_edge("C1", "net2", terminal="t1")
    circuit.graph.add_edge("C1", "net3", terminal="t2")
    circuit.graph.add_edge("R2", "net3", terminal="t1")
    circuit.graph.add_edge("R2", "net4", terminal="t2")
    
    print(f"Mixed circuit: {circuit}")
    print(f"Components: {circuit.get_component_nodes()}")
    
    # Check component types
    for comp in circuit.get_component_nodes():
        comp_type = circuit.graph.nodes[comp].get('instance_type', 'unknown')
        comp_value = circuit.graph.nodes[comp].get('value', 'unknown')
        print(f"  {comp}: {comp_type} = {comp_value}")
    
    rule = BasicSeriesResistorRule()
    can_apply = rule.can_apply(circuit)
    print(f"\nCan apply series resistor rule: {can_apply}")
    
    if can_apply:
        print("ERROR: No series resistors should be found!")
    else:
        print("Correct: Resistors are separated by capacitor, so no series combination possible.")


if __name__ == "__main__":
    demonstrate_series_resistor_simplification()
    demonstrate_parallel_resistors()
    demonstrate_mixed_components()
    
    print("\n" + "=" * 60)
    print("DEMONSTRATION COMPLETE")
    print("=" * 60)