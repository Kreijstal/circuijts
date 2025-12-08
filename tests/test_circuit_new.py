# -*- coding: utf-8 -*-
"""Tests for the Circuit class."""

import pytest
import networkx as nx
from circuijt.circuit import Circuit
from circuijt.graph_utils import DSU
from circuijt.rules.abc import RuleInterface
from circuijt.rules.concrete_rules import BasicSeriesResistorRule


class MockRule(RuleInterface):
    """Mock rule for testing Circuit.apply_rule_once()."""
    
    def __init__(self, has_candidates=True):
        self.has_candidates = has_candidates
        self.applied = False
        self.candidate_used = None
    
    def get_name(self):
        return "MockRule"
    
    def find_candidates(self, circuit):
        if self.has_candidates:
            return [{"mock": "candidate"}]
        return []
    
    def apply_to_candidate(self, circuit, candidate):
        self.applied = True
        self.candidate_used = candidate


def test_circuit_initialization():
    """Test Circuit initialization with default and custom parameters."""
    # Test default initialization
    circuit = Circuit()
    assert isinstance(circuit.graph, nx.Graph)
    assert isinstance(circuit.dsu, DSU)
    assert isinstance(circuit.metadata, dict)
    assert len(circuit.metadata) == 0
    
    # Test custom initialization
    custom_graph = nx.Graph()
    custom_graph.add_node("test_node")
    custom_dsu = DSU()
    custom_metadata = {"test": "value"}
    
    circuit = Circuit(graph=custom_graph, dsu=custom_dsu, metadata=custom_metadata)
    assert circuit.graph is custom_graph
    assert circuit.dsu is custom_dsu
    assert circuit.metadata is custom_metadata
    assert "test_node" in circuit.graph.nodes()


def test_circuit_copy():
    """Test Circuit.copy() method creates independent copies."""
    # Create original circuit with some data
    original = Circuit()
    original.graph.add_node("R1", node_kind="component_instance", instance_type="R")
    original.graph.add_node("net1", node_kind="electrical_net")
    original.graph.add_edge("R1", "net1", terminal="t1")
    original.dsu.add_set("net1")
    original.metadata["test"] = "original"
    
    # Create copy
    copy_circuit = original.copy()
    
    # Verify independence
    assert copy_circuit is not original
    assert copy_circuit.graph is not original.graph
    assert copy_circuit.dsu is not original.dsu
    assert copy_circuit.metadata is not original.metadata
    
    # Verify content is preserved
    assert "R1" in copy_circuit.graph.nodes()
    assert "net1" in copy_circuit.graph.nodes()
    assert copy_circuit.graph.has_edge("R1", "net1")
    assert copy_circuit.metadata["test"] == "original"
    
    # Verify modifications to copy don't affect original
    copy_circuit.graph.add_node("R2")
    copy_circuit.metadata["test"] = "copy"
    
    assert "R2" not in original.graph.nodes()
    assert original.metadata["test"] == "original"


def test_circuit_get_nodes():
    """Test Circuit.get_nodes() method with and without filtering."""
    circuit = Circuit()
    circuit.graph.add_node("R1", node_kind="component_instance", instance_type="R")
    circuit.graph.add_node("R2", node_kind="component_instance", instance_type="R")
    circuit.graph.add_node("net1", node_kind="electrical_net")
    circuit.graph.add_node("net2", node_kind="electrical_net")
    
    # Test getting all nodes
    all_nodes = circuit.get_nodes()
    assert len(all_nodes) == 4
    assert "R1" in all_nodes
    assert "R2" in all_nodes
    assert "net1" in all_nodes
    assert "net2" in all_nodes
    
    # Test filtering by node_kind
    component_nodes = circuit.get_nodes(node_kind="component_instance")
    assert len(component_nodes) == 2
    assert "R1" in component_nodes
    assert "R2" in component_nodes
    
    net_nodes = circuit.get_nodes(node_kind="electrical_net")
    assert len(net_nodes) == 2
    assert "net1" in net_nodes
    assert "net2" in net_nodes


def test_circuit_get_component_nodes():
    """Test Circuit.get_component_nodes() method."""
    circuit = Circuit()
    circuit.graph.add_node("R1", node_kind="component_instance", instance_type="R")
    circuit.graph.add_node("C1", node_kind="component_instance", instance_type="C")
    circuit.graph.add_node("net1", node_kind="electrical_net")
    
    component_nodes = circuit.get_component_nodes()
    assert len(component_nodes) == 2
    assert "R1" in component_nodes
    assert "C1" in component_nodes
    assert "net1" not in component_nodes


def test_circuit_get_edges():
    """Test Circuit.get_edges() method."""
    circuit = Circuit()
    circuit.graph.add_node("R1", node_kind="component_instance")
    circuit.graph.add_node("net1", node_kind="electrical_net")
    circuit.graph.add_edge("R1", "net1", terminal="t1")
    
    edges = circuit.get_edges()
    assert len(edges) == 1
    edge = edges[0]
    assert edge[0] == "R1"
    assert edge[1] == "net1"
    assert edge[2]["terminal"] == "t1"


def test_circuit_apply_rule_once_with_candidates():
    """Test Circuit.apply_rule_once() when rule has candidates."""
    circuit = Circuit()
    rule = MockRule(has_candidates=True)
    
    result = circuit.apply_rule_once(rule)
    
    assert result is True
    assert rule.applied is True
    assert rule.candidate_used == {"mock": "candidate"}


def test_circuit_apply_rule_once_no_candidates():
    """Test Circuit.apply_rule_once() when rule has no candidates."""
    circuit = Circuit()
    rule = MockRule(has_candidates=False)
    
    result = circuit.apply_rule_once(rule)
    
    assert result is False
    assert rule.applied is False
    assert rule.candidate_used is None


def test_circuit_apply_rule_once_with_real_rule():
    """Test Circuit.apply_rule_once() with BasicSeriesResistorRule."""
    # Create a circuit with two series resistors
    circuit = Circuit()
    
    # Add resistor nodes
    circuit.graph.add_node("R1", node_kind="component_instance", instance_type="R", value="10ohm")
    circuit.graph.add_node("R2", node_kind="component_instance", instance_type="R", value="20ohm")
    
    # Add net nodes
    circuit.graph.add_node("net1", node_kind="electrical_net")
    circuit.graph.add_node("net2", node_kind="electrical_net")  
    circuit.graph.add_node("net3", node_kind="electrical_net")
    
    # Connect resistors in series: net1 -- R1 -- net2 -- R2 -- net3
    circuit.graph.add_edge("R1", "net1", terminal="t1")
    circuit.graph.add_edge("R1", "net2", terminal="t2")
    circuit.graph.add_edge("R2", "net2", terminal="t1")
    circuit.graph.add_edge("R2", "net3", terminal="t2")
    
    # Apply the rule
    rule = BasicSeriesResistorRule()
    result = circuit.apply_rule_once(rule)
    
    assert result is True
    
    # Verify transformation occurred
    component_nodes = circuit.get_component_nodes()
    assert len(component_nodes) == 1  # Should have one combined resistor
    
    # The original resistors should be gone
    assert "R1" not in circuit.graph.nodes()
    assert "R2" not in circuit.graph.nodes()
    
    # Should have a new combined resistor
    new_resistor = component_nodes[0]
    assert circuit.graph.nodes[new_resistor]['instance_type'] == 'R'
    
    # Verify it connects the external nets
    neighbors = list(circuit.graph.neighbors(new_resistor))
    assert len(neighbors) == 2
    assert "net1" in neighbors
    assert "net3" in neighbors


def test_circuit_str_repr():
    """Test Circuit string representations."""
    circuit = Circuit()
    circuit.graph.add_node("R1", node_kind="component_instance")
    circuit.graph.add_node("net1", node_kind="electrical_net")
    circuit.graph.add_edge("R1", "net1")
    
    str_repr = str(circuit)
    assert "Circuit" in str_repr
    assert "nodes=2" in str_repr
    assert "edges=1" in str_repr
    assert "components=1" in str_repr
    
    # __repr__ should be the same as __str__
    assert repr(circuit) == str(circuit)