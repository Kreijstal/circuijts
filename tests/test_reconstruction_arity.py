"""Tests for ensuring correct arity after AST reconstruction from graph."""

import pytest
from circuijt.parser import ProtoCircuitParser
from circuijt.validator import CircuitValidator
from circuijt.graph_utils import ast_to_graph, graph_to_structured_ast


@pytest.fixture
def nmos_full_connection_circuit():
    return """
    ; Test circuit with a fully connected NMOS
    Nmos M1
    R R_gate
    R R_drain
    R R_source
    R R_bulk

    ; Explicitly connect all terminals of M1 using a connection block
    M1 { G:(node_g), D:(node_d), S:(node_s), B:(node_b) }

    ; Connect resistors to these nodes to make them non-trivial
    (input_g) -- R_gate -- (node_g)
    (VDD) -- R_drain -- (node_d)
    (GND) -- R_source -- (node_s)
    (VSS) -- R_bulk -- (node_b)
    """


def test_nmos_reconstruction_maintains_arity(nmos_full_connection_circuit):
    """
    Tests that an NMOS transistor, when its connections are converted
    to a graph and then back to an AST, still passes arity validation.
    This ensures that graph_to_structured_ast correctly reconstructs
    the component's connections in a way the validator understands.
    """
    parser = ProtoCircuitParser()

    # 1. Parse initial circuit to AST_1
    ast_1, parser_errors_1 = parser.parse_text(nmos_full_connection_circuit)
    assert not parser_errors_1, f"Parser errors in initial AST: {parser_errors_1}"
    assert ast_1, "Initial AST (AST_1) is empty."

    # Optional: Validate AST_1 (should pass)
    validator_1 = CircuitValidator(ast_1)
    validation_errors_1, _ = validator_1.validate()
    assert (
        not validation_errors_1
    ), f"Validation errors in initial AST_1: {validation_errors_1}"
    print("Initial AST_1 validation successful.")

    # 2. Convert AST_1 to Graph_1
    print("\nConverting AST_1 to Graph_1...")
    graph_1, dsu_1 = ast_to_graph(ast_1)
    assert graph_1 is not None, "Graph_1 is None."
    print(f"Graph_1: {len(graph_1.nodes())} nodes, {len(graph_1.edges())} edges.")

    # 3. Convert Graph_1 back to AST_2
    print("\nConverting Graph_1 to AST_2 (reconstructed)...")
    ast_2 = graph_to_structured_ast(graph_1, dsu_1)
    assert ast_2 is not None, "Reconstructed AST (AST_2) is None."
    print(f"AST_2 has {len(ast_2)} statements.")

    # 4. Validate AST_2
    print("\nValidating reconstructed AST_2...")
    validator_2 = CircuitValidator(ast_2)
    validation_errors_2, debug_info_2 = validator_2.validate()

    if validation_errors_2:
        print("\nValidation Errors for Reconstructed AST_2:")
        for error in validation_errors_2:
            print(error)
        print("\nDebug Info for AST_2 Validation:")
        print(debug_info_2)

    assert (
        not validation_errors_2
    ), f"Validation errors found in reconstructed AST_2, indicating potential arity/connection issues: {validation_errors_2}"

    print(
        "Reconstructed AST_2 validation successful (arity and connections preserved for M1)."
    )

    # 5. Check specifically that M1 was reconstructed as a component_connection_block
    #    and has 4 connections.
    m1_block_found = False
    m1_connections_count = 0
    for stmt in ast_2:
        if (
            stmt.get("type") == "component_connection_block"
            and stmt.get("component_name") == "M1"
        ):
            m1_block_found = True
            m1_connections_count = len(stmt.get("connections", []))
            print(f"Found M1 connection block in AST_2: {stmt}")
            break

    assert (
        m1_block_found
    ), "M1 was not reconstructed as a component_connection_block in AST_2."
    assert (
        m1_connections_count == 4
    ), f"M1 in reconstructed AST_2 does not have 4 connections in its block. Found {m1_connections_count}."

    print("M1 reconstruction check successful.")
