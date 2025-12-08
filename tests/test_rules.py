# -*- coding: utf-8 -*-
"""Tests for the RuleInterface and BasicSeriesResistorRule."""

import pytest
import networkx as nx
from circuijt.circuit import Circuit
from circuijt.rules.abc import RuleInterface
from circuijt.rules.concrete_rules import BasicSeriesResistorRule


class TestRuleInterface:
    """Test suite for RuleInterface abstract base class."""
    
    def test_cannot_instantiate_abstract_class(self):
        """Test that RuleInterface cannot be instantiated directly."""
        with pytest.raises(TypeError):
            RuleInterface()
    
    def test_subclass_must_implement_abstract_methods(self):
        """Test that subclasses must implement all abstract methods."""
        class IncompleteRule(RuleInterface):
            def get_name(self):
                return "Incomplete"
        
        with pytest.raises(TypeError):
            IncompleteRule()
    
    def test_complete_subclass_works(self):
        """Test that complete implementation works."""
        class CompleteRule(RuleInterface):
            def get_name(self):
                return "Complete"
            
            def find_candidates(self, circuit):
                return []
            
            def apply_to_candidate(self, circuit, candidate):
                pass
        
        rule = CompleteRule()
        assert rule.get_name() == "Complete"
        assert rule.find_candidates(None) == []
        assert rule.can_apply(Circuit()) is False  # No candidates
        assert "Complete" in rule.get_description()


class TestBasicSeriesResistorRule:
    """Test suite for BasicSeriesResistorRule."""
    
    def test_rule_name_and_description(self):
        """Test rule name and description."""
        rule = BasicSeriesResistorRule()
        assert rule.get_name() == "BasicSeriesResistorRule"
        assert "series" in rule.get_description().lower()
        assert "resistor" in rule.get_description().lower()
    
    def test_find_candidates_empty_circuit(self):
        """Test finding candidates in an empty circuit."""
        rule = BasicSeriesResistorRule()
        circuit = Circuit()
        candidates = rule.find_candidates(circuit)
        assert candidates == []
    
    def test_find_candidates_single_resistor(self):
        """Test finding candidates with only one resistor."""
        rule = BasicSeriesResistorRule()
        circuit = Circuit()
        
        # Add single resistor
        circuit.graph.add_node("R1", node_kind="component_instance", instance_type="R")
        circuit.graph.add_node("net1", node_kind="electrical_net")
        circuit.graph.add_node("net2", node_kind="electrical_net")
        circuit.graph.add_edge("R1", "net1", terminal="t1")
        circuit.graph.add_edge("R1", "net2", terminal="t2")
        
        candidates = rule.find_candidates(circuit)
        assert candidates == []  # No series pair
    
    def test_find_candidates_series_resistors(self):
        """Test finding candidates with series resistors."""
        rule = BasicSeriesResistorRule()
        circuit = Circuit()
        
        # Create series resistors: net1 -- R1 -- net2 -- R2 -- net3
        circuit.graph.add_node("R1", node_kind="component_instance", instance_type="R", value="10")
        circuit.graph.add_node("R2", node_kind="component_instance", instance_type="R", value="20")
        circuit.graph.add_node("net1", node_kind="electrical_net")
        circuit.graph.add_node("net2", node_kind="electrical_net")
        circuit.graph.add_node("net3", node_kind="electrical_net")
        
        # Connect R1
        circuit.graph.add_edge("R1", "net1", terminal="t1")
        circuit.graph.add_edge("R1", "net2", terminal="t2")
        
        # Connect R2
        circuit.graph.add_edge("R2", "net2", terminal="t1")
        circuit.graph.add_edge("R2", "net3", terminal="t2")
        
        candidates = rule.find_candidates(circuit)
        assert len(candidates) == 1
        
        candidate = candidates[0]
        assert set([candidate['resistor1'], candidate['resistor2']]) == set(["R1", "R2"])
        assert candidate['connecting_net'] == "net2"
        assert candidate['r1_value'] == 10.0
        assert candidate['r2_value'] == 20.0
        assert set([candidate['r1_other_net'], candidate['r2_other_net']]) == set(["net1", "net3"])
    
    def test_find_candidates_parallel_resistors(self):
        """Test that parallel resistors are not identified as series."""
        rule = BasicSeriesResistorRule()
        circuit = Circuit()
        
        # Create parallel resistors: both R1 and R2 connect net1 to net2
        circuit.graph.add_node("R1", node_kind="component_instance", instance_type="R")
        circuit.graph.add_node("R2", node_kind="component_instance", instance_type="R")
        circuit.graph.add_node("net1", node_kind="electrical_net")
        circuit.graph.add_node("net2", node_kind="electrical_net")
        
        # Both resistors connect the same two nets (parallel)
        circuit.graph.add_edge("R1", "net1", terminal="t1")
        circuit.graph.add_edge("R1", "net2", terminal="t2")
        circuit.graph.add_edge("R2", "net1", terminal="t1")
        circuit.graph.add_edge("R2", "net2", terminal="t2")
        
        candidates = rule.find_candidates(circuit)
        assert candidates == []  # Parallel, not series
    
    def test_find_candidates_resistor_with_three_connections(self):
        """Test that resistors with more than 2 connections are ignored."""
        rule = BasicSeriesResistorRule()
        circuit = Circuit()
        
        # Create a resistor with 3 connections (abnormal)
        circuit.graph.add_node("R1", node_kind="component_instance", instance_type="R")
        circuit.graph.add_node("R2", node_kind="component_instance", instance_type="R")
        circuit.graph.add_node("net1", node_kind="electrical_net")
        circuit.graph.add_node("net2", node_kind="electrical_net")
        circuit.graph.add_node("net3", node_kind="electrical_net")
        
        # R1 has 3 connections
        circuit.graph.add_edge("R1", "net1", terminal="t1")
        circuit.graph.add_edge("R1", "net2", terminal="t2")
        circuit.graph.add_edge("R1", "net3", terminal="t3")  # Extra connection
        
        # R2 has normal 2 connections
        circuit.graph.add_edge("R2", "net2", terminal="t1")
        circuit.graph.add_edge("R2", "net3", terminal="t2")
        
        candidates = rule.find_candidates(circuit)
        assert candidates == []  # R1 has too many connections
    
    def test_find_candidates_default_values(self):
        """Test that default values are used when component values are missing."""
        rule = BasicSeriesResistorRule()
        circuit = Circuit()
        
        # Create series resistors without explicit values
        circuit.graph.add_node("R1", node_kind="component_instance", instance_type="R")
        circuit.graph.add_node("R2", node_kind="component_instance", instance_type="R")
        circuit.graph.add_node("net1", node_kind="electrical_net")
        circuit.graph.add_node("net2", node_kind="electrical_net")
        circuit.graph.add_node("net3", node_kind="electrical_net")
        
        circuit.graph.add_edge("R1", "net1", terminal="t1")
        circuit.graph.add_edge("R1", "net2", terminal="t2")
        circuit.graph.add_edge("R2", "net2", terminal="t1")
        circuit.graph.add_edge("R2", "net3", terminal="t2")
        
        candidates = rule.find_candidates(circuit)
        assert len(candidates) == 1
        
        candidate = candidates[0]
        assert candidate['r1_value'] == 1.0  # Default value
        assert candidate['r2_value'] == 1.0  # Default value
    
    def test_apply_to_candidate(self):
        """Test applying the rule to a candidate."""
        rule = BasicSeriesResistorRule()
        circuit = Circuit()
        
        # Set up series resistors
        circuit.graph.add_node("R1", node_kind="component_instance", instance_type="R", value="10")
        circuit.graph.add_node("R2", node_kind="component_instance", instance_type="R", value="20")
        circuit.graph.add_node("net1", node_kind="electrical_net")
        circuit.graph.add_node("net2", node_kind="electrical_net")
        circuit.graph.add_node("net3", node_kind="electrical_net")
        
        circuit.graph.add_edge("R1", "net1", terminal="t1")
        circuit.graph.add_edge("R1", "net2", terminal="t2")
        circuit.graph.add_edge("R2", "net2", terminal="t1")
        circuit.graph.add_edge("R2", "net3", terminal="t2")
        
        # Find candidate and apply rule
        candidates = rule.find_candidates(circuit)
        assert len(candidates) == 1
        
        original_nodes = set(circuit.graph.nodes())
        rule.apply_to_candidate(circuit, candidates[0])
        
        # Verify transformation
        # Original resistors should be removed
        assert "R1" not in circuit.graph.nodes()
        assert "R2" not in circuit.graph.nodes()
        
        # Should have one new resistor
        component_nodes = circuit.get_component_nodes()
        assert len(component_nodes) == 1
        new_resistor = component_nodes[0]
        
        # New resistor should be of type R
        assert circuit.graph.nodes[new_resistor]['instance_type'] == 'R'
        
        # New resistor should connect net1 and net3
        neighbors = list(circuit.graph.neighbors(new_resistor))
        assert len(neighbors) == 2
        assert "net1" in neighbors
        assert "net3" in neighbors
        
        # Intermediate net (net2) should be removed if no other connections
        assert "net2" not in circuit.graph.nodes()
        
        # Check metadata
        assert 'transformations' in circuit.metadata
        assert len(circuit.metadata['transformations']) == 1
        
        transformation = circuit.metadata['transformations'][0]
        assert transformation['rule'] == 'BasicSeriesResistorRule'
        assert transformation['action'] == 'series_resistor_combination'
        assert set(transformation['original_components']) == {"R1", "R2"}
        assert transformation['combined_value'] == 30.0  # 10 + 20
    
    def test_can_apply_method(self):
        """Test the can_apply method."""
        rule = BasicSeriesResistorRule()
        
        # Empty circuit
        circuit = Circuit()
        assert rule.can_apply(circuit) is False
        
        # Circuit with series resistors
        circuit.graph.add_node("R1", node_kind="component_instance", instance_type="R")
        circuit.graph.add_node("R2", node_kind="component_instance", instance_type="R")
        circuit.graph.add_node("net1", node_kind="electrical_net")
        circuit.graph.add_node("net2", node_kind="electrical_net")
        circuit.graph.add_node("net3", node_kind="electrical_net")
        
        circuit.graph.add_edge("R1", "net1", terminal="t1")
        circuit.graph.add_edge("R1", "net2", terminal="t2")
        circuit.graph.add_edge("R2", "net2", terminal="t1")
        circuit.graph.add_edge("R2", "net3", terminal="t2")
        
        assert rule.can_apply(circuit) is True
    
    def test_multiple_series_pairs(self):
        """Test finding multiple series resistor pairs."""
        rule = BasicSeriesResistorRule()
        circuit = Circuit()
        
        # Create two separate series pairs
        # Pair 1: net1 -- R1 -- net2 -- R2 -- net3
        circuit.graph.add_node("R1", node_kind="component_instance", instance_type="R")
        circuit.graph.add_node("R2", node_kind="component_instance", instance_type="R")
        circuit.graph.add_node("net1", node_kind="electrical_net")
        circuit.graph.add_node("net2", node_kind="electrical_net")
        circuit.graph.add_node("net3", node_kind="electrical_net")
        
        circuit.graph.add_edge("R1", "net1", terminal="t1")
        circuit.graph.add_edge("R1", "net2", terminal="t2")
        circuit.graph.add_edge("R2", "net2", terminal="t1")
        circuit.graph.add_edge("R2", "net3", terminal="t2")
        
        # Pair 2: net4 -- R3 -- net5 -- R4 -- net6
        circuit.graph.add_node("R3", node_kind="component_instance", instance_type="R")
        circuit.graph.add_node("R4", node_kind="component_instance", instance_type="R")
        circuit.graph.add_node("net4", node_kind="electrical_net")
        circuit.graph.add_node("net5", node_kind="electrical_net")
        circuit.graph.add_node("net6", node_kind="electrical_net")
        
        circuit.graph.add_edge("R3", "net4", terminal="t1")
        circuit.graph.add_edge("R3", "net5", terminal="t2")
        circuit.graph.add_edge("R4", "net5", terminal="t1")
        circuit.graph.add_edge("R4", "net6", terminal="t2")
        
        candidates = rule.find_candidates(circuit)
        assert len(candidates) == 2
        
        # Verify both pairs are found
        resistor_pairs = [(c['resistor1'], c['resistor2']) for c in candidates]
        resistor_sets = [set(pair) for pair in resistor_pairs]
        
        assert {("R1", "R2")} <= set(tuple(sorted(s)) for s in resistor_sets)
        assert {("R3", "R4")} <= set(tuple(sorted(s)) for s in resistor_sets)