# -*- coding: utf-8 -*-
"""Tests for circuit parser/validator/graph utilities."""

from circuit.parser import ProtoCircuitParser
from circuit.validator import CircuitValidator # Updated import
from circuit.ast_utils import summarize_circuit_elements, generate_proto_from_ast
from circuit.graph_utils import ast_to_graph, graph_to_structured_ast

test_circuit_description = """
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

def test_parser():
    print("\n--- Testing Parser ---")
    parser = ProtoCircuitParser()
    parsed_statements, parser_errors = parser.parse_text(test_circuit_description)
    
    if (parser_errors):
        print("Parser Errors:")
        for error in parser_errors:
            print(error)
    else:
        print("Parser successful, no errors.")
    
    return parsed_statements

def test_validator(parsed_statements):
    print("\n--- Testing Validator ---")
    validator = CircuitValidator(parsed_statements) # Use the new general validator
    validation_errors = validator.validate()
    
    if validation_errors:
        print("Validation Errors:")
        for error in validation_errors:
            print(error)
    else:
        print("Validation successful, no errors.")

def test_ast_utils(parsed_statements):
    print("\n--- Testing AST Utilities ---")
    summary = summarize_circuit_elements(parsed_statements)
    print("Circuit Summary:")
    print(f"Total Nodes: {summary['num_total_nodes']}")
    print(f"Components: {summary['num_total_components']}")
    print(f"Explicit Nodes: {summary['details']['explicit_nodes']}")
    print(f"Implicit Nodes: {summary['details']['implicit_nodes']}")

    reconstructed = generate_proto_from_ast(parsed_statements)
    print("\nReconstructed Circuit:")
    print(reconstructed)

def test_graph_utils(parsed_statements):
    print("\n--- Testing Graph Utilities ---")
    graph, dsu = ast_to_graph(parsed_statements)
    print(f"Graph nodes: {len(graph.nodes())}")
    print(f"Graph edges: {len(graph.edges())}")
    
    reconstructed_ast = graph_to_structured_ast(graph, dsu)
    print("\nReconstructed AST from graph:")
    print(f"Statements: {len(reconstructed_ast)}")
    
    reconstructed_code = generate_proto_from_ast(reconstructed_ast)
    print("\nReconstructed Code from graph:")
    print(reconstructed_code)

if __name__ == "__main__":
    parsed = test_parser()
    test_validator(parsed)
    test_ast_utils(parsed)
    test_graph_utils(parsed)