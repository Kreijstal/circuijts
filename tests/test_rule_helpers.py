# -*- coding: utf-8 -*-
"""Tests for rule helper utilities."""

import pytest
from circuijt.rules.helpers import RuleHelperCollection
from circuijt.circuit import Circuit
import networkx as nx


def test_generate_unique_id():
    """Test unique ID generation."""
    # Test default prefix
    id1 = RuleHelperCollection.generate_unique_id()
    id2 = RuleHelperCollection.generate_unique_id()
    
    assert id1.startswith("node_")
    assert id2.startswith("node_")
    assert id1 != id2  # Should be unique
    
    # Test custom prefix
    custom_id = RuleHelperCollection.generate_unique_id("resistor")
    assert custom_id.startswith("resistor_")
    
    # Test multiple calls produce unique results
    ids = [RuleHelperCollection.generate_unique_id("test") for _ in range(10)]
    assert len(set(ids)) == 10  # All should be unique


def test_parse_component_value():
    """Test component value parsing."""
    # Test simple numbers
    result = RuleHelperCollection.parse_component_value("100")
    assert result['value'] == 100.0
    assert result['unit'] == ''
    assert result['original'] == "100"
    
    # Test with decimal
    result = RuleHelperCollection.parse_component_value("1.5")
    assert result['value'] == 1.5
    
    # Test with units
    result = RuleHelperCollection.parse_component_value("10ohm")
    assert result['value'] == 10.0
    assert result['unit'] == 'ohm'
    
    # Test with prefixes
    result = RuleHelperCollection.parse_component_value("10k")
    assert result['value'] == 10000.0
    assert result['unit'] == ''
    
    result = RuleHelperCollection.parse_component_value("1.5M")
    assert result['value'] == 1500000.0
    
    result = RuleHelperCollection.parse_component_value("100m")
    assert result['value'] == 0.1
    
    result = RuleHelperCollection.parse_component_value("10uF")
    assert abs(result['value'] - 10e-6) < 1e-12  # Allow for floating point precision
    assert result['unit'] == 'F'
    
    result = RuleHelperCollection.parse_component_value("1nH")
    assert result['value'] == 1e-9
    assert result['unit'] == 'H'
    
    result = RuleHelperCollection.parse_component_value("100pF")
    assert result['value'] == 100e-12
    assert result['unit'] == 'F'
    
    # Test invalid input
    result = RuleHelperCollection.parse_component_value("")
    assert result['value'] == 0.0
    
    result = RuleHelperCollection.parse_component_value("invalid")
    assert result['value'] == 0.0


def test_format_component_value():
    """Test component value formatting."""
    # Test zero
    assert RuleHelperCollection.format_component_value(0.0) == "0"
    assert RuleHelperCollection.format_component_value(0.0, "ohm") == "0ohm"
    
    # Test base values
    assert RuleHelperCollection.format_component_value(100.0) == "100"
    assert RuleHelperCollection.format_component_value(100.0, "ohm") == "100ohm"
    
    # Test kilo values
    assert RuleHelperCollection.format_component_value(1000.0) == "1k"
    assert RuleHelperCollection.format_component_value(1500.0) == "1.5k"
    assert RuleHelperCollection.format_component_value(10000.0, "ohm") == "10kohm"
    
    # Test mega values
    assert RuleHelperCollection.format_component_value(1000000.0) == "1M"
    assert RuleHelperCollection.format_component_value(2500000.0) == "2.5M"
    
    # Test milli values
    assert RuleHelperCollection.format_component_value(0.001) == "1m"
    assert RuleHelperCollection.format_component_value(0.0015) == "1.5m"
    
    # Test micro values
    assert RuleHelperCollection.format_component_value(0.000001) == "1u"
    assert RuleHelperCollection.format_component_value(0.00001, "F") == "10uF"
    
    # Test nano values
    assert RuleHelperCollection.format_component_value(1e-9) == "1n"
    
    # Test pico values
    assert RuleHelperCollection.format_component_value(1e-12) == "1p"
    
    # Test very small values (scientific notation)
    result = RuleHelperCollection.format_component_value(1e-15)
    assert "e" in result.lower()


def test_combine_resistor_values():
    """Test resistor value combination."""
    # Test simple addition
    assert RuleHelperCollection.combine_resistor_values(10.0, 20.0) == 30.0
    assert RuleHelperCollection.combine_resistor_values(0.0, 5.0) == 5.0
    assert RuleHelperCollection.combine_resistor_values(1.5, 2.5) == 4.0


def test_extract_component_value_from_node():
    """Test extracting component values from graph nodes."""
    circuit = Circuit()
    
    # Test with numeric value attribute
    circuit.graph.add_node("R1", value=100.0)
    value = RuleHelperCollection.extract_component_value_from_node(circuit, "R1")
    assert value == 100.0
    
    # Test with string value attribute
    circuit.graph.add_node("R2", value="10k")
    value = RuleHelperCollection.extract_component_value_from_node(circuit, "R2")
    assert value == 10000.0
    
    # Test with resistance attribute
    circuit.graph.add_node("R3", resistance="1.5M")
    value = RuleHelperCollection.extract_component_value_from_node(circuit, "R3")
    assert value == 1500000.0
    
    # Test with no value attribute
    circuit.graph.add_node("R4", instance_type="R")
    value = RuleHelperCollection.extract_component_value_from_node(circuit, "R4")
    assert value is None
    
    # Test with non-existent node
    value = RuleHelperCollection.extract_component_value_from_node(circuit, "NonExistent")
    assert value is None


def test_set_component_value_on_node():
    """Test setting component values on graph nodes."""
    circuit = Circuit()
    circuit.graph.add_node("R1", instance_type="R")
    
    # Set value without unit
    RuleHelperCollection.set_component_value_on_node(circuit, "R1", 1000.0)
    assert circuit.graph.nodes["R1"]["value"] == "1k"
    
    # Set value with unit
    RuleHelperCollection.set_component_value_on_node(circuit, "R1", 0.001, "F")
    assert circuit.graph.nodes["R1"]["value"] == "1mF"
    
    # Test with non-existent node (should not raise error)
    RuleHelperCollection.set_component_value_on_node(circuit, "NonExistent", 100.0)


def test_get_component_type():
    """Test getting component type from nodes."""
    circuit = Circuit()
    circuit.graph.add_node("R1", instance_type="R")
    circuit.graph.add_node("C1", instance_type="C")
    circuit.graph.add_node("net1", node_kind="electrical_net")
    
    assert RuleHelperCollection.get_component_type(circuit, "R1") == "R"
    assert RuleHelperCollection.get_component_type(circuit, "C1") == "C"
    assert RuleHelperCollection.get_component_type(circuit, "net1") is None
    assert RuleHelperCollection.get_component_type(circuit, "NonExistent") is None


def test_is_resistor():
    """Test resistor identification."""
    circuit = Circuit()
    circuit.graph.add_node("R1", instance_type="R")
    circuit.graph.add_node("C1", instance_type="C")
    circuit.graph.add_node("net1", node_kind="electrical_net")
    
    assert RuleHelperCollection.is_resistor(circuit, "R1") is True
    assert RuleHelperCollection.is_resistor(circuit, "C1") is False
    assert RuleHelperCollection.is_resistor(circuit, "net1") is False
    assert RuleHelperCollection.is_resistor(circuit, "NonExistent") is False