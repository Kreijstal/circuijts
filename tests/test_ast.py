# -*- coding: utf-8 -*-
"""Test cases for AST manipulation utilities."""

from circuijt.ast_utils import (
    find_statements_of_type,
    find_declarations_by_type,
    summarize_circuit_elements,
)
from circuijt.parser import ProtoCircuitParser


def test_declaration_ast():
    parser = ProtoCircuitParser()
    code = """
    R R1
    C C_bypass
    Nmos M1
    """
    statements, errors = parser.parse_text(code)
    assert not errors

    # Check declaration AST structure
    declarations = [s for s in statements if s["type"] == "declaration"]
    assert len(declarations) == 3

    r1_decl = declarations[0]
    assert r1_decl["type"] == "declaration"
    assert r1_decl["component_type"] == "R"
    assert r1_decl["instance_name"] == "R1"

    c1_decl = declarations[1]
    assert c1_decl["component_type"] == "C"
    assert c1_decl["instance_name"] == "C_bypass"


def test_series_connection_ast():
    parser = ProtoCircuitParser()
    code = "(input) -- R1 -- V1(-+) -- (output)"
    statements, errors = parser.parse_text(code)
    assert not errors

    series = statements[0]
    assert series["type"] == "series_connection"
    path = series["path"]

    # Check path structure
    assert path[0]["type"] == "node"
    assert path[0]["name"] == "input"

    assert path[1]["type"] == "component"
    assert path[1]["name"] == "R1"

    assert path[2]["type"] == "source"
    assert path[2]["name"] == "V1"
    assert path[2]["polarity"] == "-+"

    assert path[3]["type"] == "node"
    assert path[3]["name"] == "output"


def test_parallel_block_ast():
    parser = ProtoCircuitParser()
    code = "(out) -- [ R1 || C1 || gm*v1 (->) ] -- (gnd)"
    statements, errors = parser.parse_text(code)
    assert not errors

    parallel = statements[0]
    assert parallel["type"] == "series_connection"

    # Check parallel block structure
    parallel_block = None
    for element in parallel["path"]:
        if "elements" in element:
            parallel_block = element
            break

    assert parallel_block is not None
    assert parallel_block["type"] == "parallel_block"
    elements = parallel_block["elements"]

    # Check parallel elements
    assert len(elements) == 3
    assert elements[0]["type"] == "component"
    assert elements[0]["name"] == "R1"
    assert elements[1]["type"] == "component"
    assert elements[1]["name"] == "C1"
    assert elements[2]["type"] == "controlled_source"
    assert elements[2]["expression"] == "gm*v1"
    assert elements[2]["direction"] == "->"


def test_connection_block_ast():
    parser = ProtoCircuitParser()
    code = "M1 { G:(in), S:(gnd), D:(out), B:(gnd) }"
    statements, errors = parser.parse_text(code)
    assert not errors

    block = statements[0]
    assert block["type"] == "component_connection_block"
    assert block["component_name"] == "M1"

    connections = block["connections"]
    assert len(connections) == 4

    # Check each terminal connection
    terminals = {conn["terminal"]: conn["node"] for conn in connections}
    assert terminals["G"] == "in"
    assert terminals["S"] == "gnd"
    assert terminals["D"] == "out"
    assert terminals["B"] == "gnd"


def test_direct_assignment_ast():
    parser = ProtoCircuitParser()
    code = "(node1):(node2)"
    statements, errors = parser.parse_text(code)
    assert not errors

    assignment = statements[0]
    assert assignment["type"] == "direct_assignment"
    assert assignment["source_node"] == "node1"
    assert assignment["target_node"] == "node2"


def test_named_current_ast():
    parser = ProtoCircuitParser()
    code = "(VDD) -- ->I_supply -- R1 -- (out)"
    statements, errors = parser.parse_text(code)
    assert not errors

    series = statements[0]
    path = series["path"]

    # Find named current in path
    current = next(p for p in path if "type" in p and p["type"] == "named_current")
    assert current["type"] == "named_current"
    assert current["direction"] == "->"
    assert current["name"] == "I_supply"


def test_complete_circuit_ast():
    parser = ProtoCircuitParser()
    code = """
    ; Declarations
    Nmos M1
    R R_load
    C C_bypass
    V V_in

    ; Device connections
    M1 { S:(GND), B:(GND) }
    
    ; Input path
    (GND) -- V_in(-+) -- (M1.G)
    
    ; Output path with parallel load
    (M1.D) -- [ R_load || C_bypass ] -- (GND)
    """
    statements, errors = parser.parse_text(code)
    assert not errors

    # Check declarations
    declarations = [s for s in statements if s["type"] == "declaration"]
    assert len(declarations) == 4
    component_types = {d["component_type"] for d in declarations}
    assert component_types == {"Nmos", "R", "C", "V"}

    # Check component block
    blocks = [s for s in statements if s["type"] == "component_connection_block"]
    assert len(blocks) == 1
    assert blocks[0]["component_name"] == "M1"
    assert len(blocks[0]["connections"]) == 2

    # Check series connections
    series = [s for s in statements if s["type"] == "series_connection"]
    assert len(series) == 2

    # Check parallel block
    parallel_series = next(s for s in series if any("elements" in p for p in s["path"]))
    parallel_block = next(p for p in parallel_series["path"] if "elements" in p)
    assert len(parallel_block["elements"]) == 2


def test_find_parallel_block():
    """Test finding parallel blocks in AST."""
    code = """
    ; Declarations
    Nmos M1
    R R_load
    C C_bypass
    V V_in

    ; Device connections
    M1 { S:(GND), B:(GND) }

    ; Input path
    (GND) -- V_in(-+) -- (M1.G)

    ; Output path with parallel load
    (M1.D) -- [ R_load || C_bypass ] -- (GND)
    """

    parser = ProtoCircuitParser()
    statements, errors = parser.parse_text(code)
    assert not errors

    # Find parallel blocks
    parallel_blocks = find_statements_of_type(statements, "parallel_block")
    assert len(parallel_blocks) == 1

    block = parallel_blocks[0]
    assert block["type"] == "parallel_block"

    # Check contained elements
    elements = block["elements"]
    assert len(elements) == 2
    assert elements[0]["type"] == "component"
    assert elements[0]["name"] == "R_load"
    assert elements[1]["type"] == "component"
    assert elements[1]["name"] == "C_bypass"


def test_find_declarations_by_type():
    """Test finding declarations by component type."""
    code = """
    ; Declarations
    Nmos M1
    R R_load
    C C_bypass
    V V_in
    """

    parser = ProtoCircuitParser()
    statements, errors = parser.parse_text(code)
    assert not errors

    # Find declarations
    nmos_decls = find_declarations_by_type(statements, "Nmos")
    assert len(nmos_decls) == 1
    assert nmos_decls[0]["instance_name"] == "M1"

    res_decls = find_declarations_by_type(statements, "R")
    assert len(res_decls) == 1
    assert res_decls[0]["instance_name"] == "R_load"

    cap_decls = find_declarations_by_type(statements, "C")
    assert len(cap_decls) == 1
    assert cap_decls[0]["instance_name"] == "C_bypass"

    volt_decls = find_declarations_by_type(statements, "V")
    assert len(volt_decls) == 1
    assert volt_decls[0]["instance_name"] == "V_in"


def test_summarize_circuit_elements():
    """Test circuit element summary."""
    code = """
    ; Declarations
    Nmos M1
    R R_load
    C C_bypass
    V V_in

    ; Device connections
    M1 { S:(GND), B:(GND) }

    ; Input path
    (GND) -- V_in(-+) -- (M1.G)

    ; Output path with parallel load
    (M1.D) -- [ R_load || C_bypass ] -- (GND)
    """

    parser = ProtoCircuitParser()
    statements, errors = parser.parse_text(code)
    assert not errors

    summary = summarize_circuit_elements(statements)
    assert summary["total_components"] == 4
    assert summary["total_nmos"] == 1
    assert summary["total_resistors"] == 1
    assert summary["total_capacitors"] == 1
    assert summary["total_voltages"] == 1
    assert summary["total_parallel_blocks"] == 1
