# -*- coding: utf-8 -*-
"""Tests for circuit parser/validator/graph utilities."""

import pytest
from circuijt.parser import ProtoCircuitParser
from circuijt.validator import CircuitValidator
from circuijt.ast_utils import summarize_circuit_elements, generate_proto_from_ast
from circuijt.graph_utils import ast_to_graph, graph_to_structured_ast


@pytest.fixture
def test_circuit_description():
    """Provides a sample circuit description string for testing."""
    return """
; Test Circuit for Proto-Language Parser and Validator

; Declarations
V Vs1          ; Voltage Source
R R1           ; Resistor 1
Nmos M1        ; NMOS Transistor
R R2           ; Resistor 2
C C1           ; Capacitor C1
L L_test       ; Inductor for variety

; Component Connection Block for M1 (NOW SINGLE LINE)
M1 { G:(node_gate), S:(GND), D:(node_drain), B:(GND) }

; Series Connections
(node_input) -- Vs1 (-+) -- R1 -- (node_gate)
(node_drain) -- C1 -- (GND)

; Parallel Block example
(node_drain) -- [ R2 || C1 ] -- (GND)

; Controlled Source in Parallel Block
(node_drain) -- [ gm1*vgs1 (->) || R2 ] -- (GND)

; Named Current
(VDD) -- ->I_supply -- R2 -- (node_drain)

; Direct Assignment (Node Aliasing)
(Vout) : (node_drain)
(AnotherNode) : (M1.S)
"""


@pytest.fixture
def invalid_circuit_description():
    """Provides an invalid circuit description string for testing."""
    return """
; Test Circuit for Proto-Language Parser and Validator with invalid R2 connections

; Declarations
V Vs1          ; Voltage Source
R R1           ; Resistor 1
Nmos M1        ; NMOS Transistor
R R2           ; Resistor 2
C C1           ; Capacitor C1
L L_test       ; Inductor for variety

; Component Connection Block for M1 (NOW SINGLE LINE)
M1 { G:(node_gate), S:(GND), D:(node_drain), B:(GND) }

; Series Connections
(node_input) -- Vs1 (-+) -- R1 -- (node_gate)
(node_drain) -- C1 -- (GND)

; Parallel Block example
(node_drain) -- [ R2 || C1 ] -- (GND)

; Controlled Source in Parallel Block
(node_drain) -- [ gm1*vgs1 (->) || R2 ] -- (GND)

; Named Current
(VDD) -- ->I_supply -- R2 -- (node_drain)

; Direct Assignment (Node Aliasing)
(Vout) : (node_drain)
(AnotherNode) : (M1.S)
"""


@pytest.fixture
def valid_circuit_description():
    """Provides a valid circuit description string for testing."""
    return """
; Test Circuit for Proto-Language Parser and Validator (Valid Circuit)

; Declarations
V Vs1          ; Voltage Source
R R1           ; Resistor 1
R R2           ; Resistor 2
R R3           ; Additional resistor
C C1           ; Capacitor
Nmos M1        ; NMOS Transistor

; Component Connection Block for M1
M1 { G:(node_gate), S:(GND), D:(node_drain), B:(GND) }

; Input stage
(VDD) -- Vs1 (-+) -- R1 -- (node_gate)

; Output stage with proper component usage
(node_drain) -- [ R2 || C1 ] -- (GND)
(node_drain) -- R3 -- (VDD)

; Node aliasing
(Vout) : (node_drain)
"""


@pytest.fixture
def parsed_statements(test_circuit_description):
    """Parses the test_circuit_description and returns AST statements."""
    parser = ProtoCircuitParser()
    statements, errors = parser.parse_text(test_circuit_description)
    assert not errors, f"Parser errors found: {errors}"
    return statements


@pytest.fixture
# TODO: Ask: why we assert not errors here?
def invalid_parsed_statements(invalid_circuit_description):
    """Parses the invalid_circuit_description and returns AST statements."""
    parser = ProtoCircuitParser()
    statements, errors = parser.parse_text(invalid_circuit_description)
    assert not errors, f"Parser errors found: {errors}"
    return statements


@pytest.fixture
def valid_parsed_statements(valid_circuit_description):
    """Parses the valid_circuit_description and returns AST statements."""
    parser = ProtoCircuitParser()
    statements, errors = parser.parse_text(valid_circuit_description)
    assert not errors, f"Parser errors found: {errors}"
    return statements


def test_parser(test_circuit_description):
    """Test the circuit parser with a sample circuit description."""
    parser = ProtoCircuitParser()
    parsed_stmts, parser_errors = parser.parse_text(test_circuit_description)
    assert not parser_errors, f"Parser errors found: {parser_errors}"
    assert len(parsed_stmts) > 0, "No statements were parsed"


def test_invalid_circuit_validator(invalid_parsed_statements):
    """Test the circuit validator with an invalid circuit (R2 arity error)."""
    print("\n--- Testing Invalid Circuit Validator ---")
    validator = CircuitValidator(invalid_parsed_statements)
    validation_errors, debug_info = validator.validate()

    # Expect validation error for R2 having too many connections
    assert validation_errors, "Expected validation errors but found none"

    # Print debug info on failure
    if not any("R2" in error and "arity" in error.lower() for error in validation_errors):
        print("\nDebug Information:")
        if "ast_validation" in debug_info:
            print("\nAST Validation Details:")
            for info in debug_info["ast_validation"]:
                print(f"Total statements: {info['total_statements']}")
                print(f"Declarations: {[d['instance_name'] for d in info['declarations']]}")
                print(f"Component types: {info['components']}")

        if "graph_construction" in debug_info:
            print("\nGraph Construction Details:")
            for info in debug_info["graph_construction"]:
                print(f"Total nodes: {info['nodes']}")
                print(f"Total edges: {info['edges']}")
                print(f"Net nodes: {info['nets']}")
                print(f"Component nodes: {info['components']}")

        raise AssertionError("Expected error about R2 having incorrect arity. Debug info above.")
    print("Validation failed as expected with R2 arity error")


def test_valid_circuit_validator(valid_parsed_statements):
    """Test the circuit validator with a valid circuit description."""
    print("\n--- Testing Valid Circuit Validator ---")
    validator = CircuitValidator(valid_parsed_statements)
    validation_errors, debug_info = validator.validate()

    # On failure, print debug info
    if validation_errors:
        print("\nUnexpected Validation Errors:")
        for error in validation_errors:
            print(f"  {error}")

        print("\nDebug Information:")
        if "ast_validation" in debug_info:
            print("\nAST Validation Details:")
            for info in debug_info["ast_validation"]:
                print(f"Total statements: {info['total_statements']}")
                print(f"Declarations: {[d['instance_name'] for d in info['declarations']]}")
                print(f"Component types: {info['components']}")

        if "graph_construction" in debug_info:
            print("\nGraph Construction Details:")
            for info in debug_info["graph_construction"]:
                print(f"Total nodes: {info['nodes']}")
                print(f"Total edges: {info['edges']}")
                print(f"Net nodes: {info['nets']}")
                print(f"Component nodes: {info['components']}")

        raise AssertionError("Unexpected validation errors found. Debug info above.")
    print("Valid circuit passed validation as expected")


def test_ast_utils(parsed_statements):
    """Test AST utility functions like summarize_circuit_elements and generate_proto_from_ast."""
    summary = summarize_circuit_elements(parsed_statements)
    assert summary["num_total_nodes"] > 0, "No nodes found in circuit"
    assert summary["total_components"] > 0, "No components found in circuit"
    assert len(summary["details"]["explicit_nodes"]) > 0, "No explicit nodes found"

    reconstructed = generate_proto_from_ast(parsed_statements)
    assert reconstructed, "Failed to generate proto from AST"


def test_graph_utils(parsed_statements):
    """Test graph utility functions like ast_to_graph and graph_to_structured_ast."""
    graph, dsu = ast_to_graph(parsed_statements)
    assert len(graph.nodes()) > 0, "No nodes in generated graph"
    assert len(graph.edges()) > 0, "No edges in generated graph"

    reconstructed_ast = graph_to_structured_ast(graph, dsu)
    assert len(reconstructed_ast) > 0, "Failed to reconstruct AST from graph"
