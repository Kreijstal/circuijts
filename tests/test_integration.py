# -*- coding: utf-8 -*-
"""Integration tests showing Circuit and rules working together."""

import pytest
from circuijt.circuit import Circuit
from circuijt.graph_utils import ast_to_graph
from circuijt.parser import ProtoCircuitParser
from circuijt.rules.concrete_rules import BasicSeriesResistorRule


def test_integration_parse_and_simplify_series_resistors():
    """
    Integration test: Parse a circuit description with series resistors,
    convert to Circuit object, and apply rule simplification.
    """
    # Circuit description with series resistors
    circuit_description = """
; Test Circuit with Series Resistors
R R1           ; Resistor 1
R R2           ; Resistor 2

; Series connection: (input) -- R1 -- R2 -- (output)
(input) -- R1 -- R2 -- (output)
"""
    
    # Parse the circuit description
    parser = ProtoCircuitParser()
    statements, errors = parser.parse_text(circuit_description)
    assert not errors, f"Parser errors: {errors}"
    
    # Convert to graph
    graph, dsu = ast_to_graph(statements)
    
    # Create Circuit object
    circuit = Circuit(graph=graph, dsu=dsu)
    
    # Verify initial state
    initial_components = circuit.get_component_nodes()
    assert len(initial_components) == 2
    assert all("R" in comp for comp in initial_components)
    
    # Apply series resistor rule
    rule = BasicSeriesResistorRule()
    
    # Check that rule can be applied
    assert rule.can_apply(circuit) is True
    
    # Apply the rule once
    result = circuit.apply_rule_once(rule)
    assert result is True
    
    # Verify transformation
    final_components = circuit.get_component_nodes()
    assert len(final_components) == 1  # Combined into one resistor
    
    # The new resistor should connect input and output
    new_resistor = final_components[0]
    neighbors = list(circuit.graph.neighbors(new_resistor))
    
    # Find the canonical names for input and output nodes
    input_canonical = circuit.dsu.find("input")
    output_canonical = circuit.dsu.find("output")
    
    assert len(neighbors) == 2
    assert input_canonical in neighbors
    assert output_canonical in neighbors
    
    # Check metadata records the transformation
    assert 'transformations' in circuit.metadata
    assert len(circuit.metadata['transformations']) == 1
    transformation = circuit.metadata['transformations'][0]
    assert transformation['rule'] == 'BasicSeriesResistorRule'
    assert transformation['action'] == 'series_resistor_combination'


def test_integration_multiple_rule_applications():
    """
    Test applying rules multiple times to fully simplify a circuit.
    """
    # Create a circuit with a chain of 3 resistors in series
    circuit = Circuit()
    
    # Add resistor nodes with values
    circuit.graph.add_node("R1", node_kind="component_instance", instance_type="R", value="10")
    circuit.graph.add_node("R2", node_kind="component_instance", instance_type="R", value="20")
    circuit.graph.add_node("R3", node_kind="component_instance", instance_type="R", value="30")
    
    # Add net nodes
    circuit.graph.add_node("net1", node_kind="electrical_net")
    circuit.graph.add_node("net2", node_kind="electrical_net")
    circuit.graph.add_node("net3", node_kind="electrical_net")
    circuit.graph.add_node("net4", node_kind="electrical_net")
    
    # Connect in series: net1 -- R1 -- net2 -- R2 -- net3 -- R3 -- net4
    circuit.graph.add_edge("R1", "net1", terminal="t1")
    circuit.graph.add_edge("R1", "net2", terminal="t2")
    circuit.graph.add_edge("R2", "net2", terminal="t1")
    circuit.graph.add_edge("R2", "net3", terminal="t2")
    circuit.graph.add_edge("R3", "net3", terminal="t1")
    circuit.graph.add_edge("R3", "net4", terminal="t2")
    
    rule = BasicSeriesResistorRule()
    
    # Initially should have 3 resistors
    assert len(circuit.get_component_nodes()) == 3
    
    # First application: should combine two of them
    result1 = circuit.apply_rule_once(rule)
    assert result1 is True
    assert len(circuit.get_component_nodes()) == 2
    
    # Second application: should combine the remaining two
    result2 = circuit.apply_rule_once(rule)
    assert result2 is True
    assert len(circuit.get_component_nodes()) == 1
    
    # Third application: should find no more candidates
    result3 = circuit.apply_rule_once(rule)
    assert result3 is False
    assert len(circuit.get_component_nodes()) == 1
    
    # Final resistor should connect net1 and net4
    final_resistor = circuit.get_component_nodes()[0]
    neighbors = list(circuit.graph.neighbors(final_resistor))
    assert len(neighbors) == 2
    assert "net1" in neighbors
    assert "net4" in neighbors
    
    # Check that transformations were recorded
    assert len(circuit.metadata['transformations']) == 2


def test_integration_no_applicable_rules():
    """
    Test circuit where no rules can be applied.
    """
    # Create a circuit with parallel resistors (not series)
    circuit = Circuit()
    
    circuit.graph.add_node("R1", node_kind="component_instance", instance_type="R")
    circuit.graph.add_node("R2", node_kind="component_instance", instance_type="R")
    circuit.graph.add_node("net1", node_kind="electrical_net")
    circuit.graph.add_node("net2", node_kind="electrical_net")
    
    # Both resistors connect same nets (parallel)
    circuit.graph.add_edge("R1", "net1", terminal="t1")
    circuit.graph.add_edge("R1", "net2", terminal="t2")
    circuit.graph.add_edge("R2", "net1", terminal="t1")
    circuit.graph.add_edge("R2", "net2", terminal="t2")
    
    rule = BasicSeriesResistorRule()
    
    # Rule should not be applicable
    assert rule.can_apply(circuit) is False
    
    # Applying rule should return False (no transformation)
    result = circuit.apply_rule_once(rule)
    assert result is False
    
    # Circuit should remain unchanged
    assert len(circuit.get_component_nodes()) == 2
    assert 'transformations' not in circuit.metadata


def test_integration_mixed_components():
    """
    Test that rule only affects resistors, not other components.
    """
    circuit = Circuit()
    
    # Add mixed components in series
    circuit.graph.add_node("R1", node_kind="component_instance", instance_type="R", value="10")
    circuit.graph.add_node("C1", node_kind="component_instance", instance_type="C", value="1u")
    circuit.graph.add_node("R2", node_kind="component_instance", instance_type="R", value="20")
    
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
    
    rule = BasicSeriesResistorRule()
    
    # No series resistors (they're separated by capacitor)
    assert rule.can_apply(circuit) is False
    
    result = circuit.apply_rule_once(rule)
    assert result is False
    
    # All components should remain
    assert len(circuit.get_component_nodes()) == 3