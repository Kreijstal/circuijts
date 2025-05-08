# -*- coding: utf-8 -*-
"""Tests for the ProtoCircuitParser."""
from circuijt.parser import ProtoCircuitParser


def test_parser_initialization():
    """Test that the parser initializes correctly."""
    parser = ProtoCircuitParser()
    assert not parser.parsed_statements
    assert not parser.errors


def test_basic_node_formats():
    """Test parsing of basic node formats."""
    parser = ProtoCircuitParser()
    # Regular node
    result = parser._parse_element("(node1)", 1)  # pylint: disable=protected-access
    assert result["type"] == "node"
    assert result["name"] == "node1"

    # Device terminal node
    result = parser._parse_element("(M1.G)", 1)  # pylint: disable=protected-access
    assert result["type"] == "node"
    assert result["name"] == "M1.G"

    # Special nodes
    result = parser._parse_element("(GND)", 1)  # pylint: disable=protected-access
    assert result["type"] == "node"
    assert result["name"] == "GND"

    result = parser._parse_element("(VDD)", 1)  # pylint: disable=protected-access
    assert result["type"] == "node"
    assert result["name"] == "VDD"


def test_invalid_node_formats():
    """Test parsing of invalid node formats."""
    parser = ProtoCircuitParser()
    # Invalid node name starting with number
    result = parser._parse_element("(123node)", 1)  # pylint: disable=protected-access
    assert result["type"] == "error"

    # Invalid characters in node name
    result = parser._parse_element("(node@123)", 1)  # pylint: disable=protected-access
    assert result["type"] == "error"

    # Multiple dots in device terminal
    result = parser._parse_element("(M1.G.D)", 1)  # pylint: disable=protected-access
    assert result["type"] == "error"


def test_component_declarations():
    """Test parsing of component declarations."""
    parser = ProtoCircuitParser()
    test_decls = [
        "R R1",  # Resistor
        "C C_load",  # Capacitor
        "L L_test",  # Inductor
        "Nmos M_nfet1",  # NMOS transistor
        "V Vs_in",  # Voltage source
        "Opamp U1A",  # Op-amp
    ]

    for decl in test_decls:
        statements, errors = parser.parse_text(decl)
        assert not errors, f"Declaration '{decl}' failed"
        assert len(statements) == 1
        assert statements[0]["type"] == "declaration"


def test_invalid_component_declarations():
    """Test parsing of invalid component declarations."""
    parser = ProtoCircuitParser()
    invalid_decls = [
        "123R R1",  # Type starting with number
        "R 1R1",  # Instance name starting with number
        "R R@1",  # Invalid character in instance name
        "R-type R1",  # Invalid character in type
    ]

    for decl in invalid_decls:
        _, errors = parser.parse_text(decl)  # Changed _statements to _
        assert errors, f"Invalid declaration '{decl}' should fail"


def test_source_polarity():
    """Test parsing of source polarity."""
    parser = ProtoCircuitParser()
    # Test both polarity formats
    result = parser._parse_element("V1(-+)", 1)  # pylint: disable=protected-access
    assert result["type"] == "source"
    assert result["polarity"] == "-+"

    result = parser._parse_element("V2(+-)", 1)  # pylint: disable=protected-access
    assert result["type"] == "source"
    assert result["polarity"] == "+-"


def test_component_connection_block():
    """Test parsing of component connection blocks."""
    parser = ProtoCircuitParser()
    block = """M1 { G:(node_gate), S:(GND), D:(node_drain), B:(GND) }"""
    statements, errors = parser.parse_text(block)
    assert not errors
    assert len(statements) == 1
    assert statements[0]["type"] == "component_connection_block"
    assert len(statements[0]["connections"]) == 4


def test_series_connections():
    """Test parsing of series connections."""
    parser = ProtoCircuitParser()
    # Basic series connection
    path = "(Vin) -- R1 -- (Vout)"
    statements, errors = parser.parse_text(path)
    assert not errors
    assert statements[0]["type"] == "series_connection"

    # Series with source
    path = "(GND) -- V1(-+) -- R1 -- (out)"
    statements, errors = parser.parse_text(path)
    assert not errors

    # Series with named current
    path = "(VDD) -- ->I_supply -- R1 -- (node1)"
    statements, errors = parser.parse_text(path)
    assert not errors


def test_parallel_blocks():
    """Test parsing of parallel blocks."""
    parser = ProtoCircuitParser()
    # Basic parallel components
    path = "(out) -- [ R1 || C1 ] -- (GND)"
    _, errors = parser.parse_text(path)  # Renamed statements to _
    assert not errors

    # Parallel with controlled source
    path = "(drain) -- [ gm1*vgs1 (->) || rds1 ] -- (source)"
    _, errors = parser.parse_text(path)  # Renamed statements to _
    assert not errors


def test_direct_assignments():
    """Test parsing of direct net assignments."""
    parser = ProtoCircuitParser()
    # Node to node assignment
    assign = "(node1):(node2)"
    _, errors = parser.parse_text(assign)  # Changed _statements to _
    assert not errors

    # Device terminal assignments
    assign = "(M1.D):(VDD)"
    _, errors = parser.parse_text(assign)  # Changed _statements to _
    assert not errors


def test_complete_circuit():
    """Test parsing of a complete circuit example."""
    parser = ProtoCircuitParser()
    circuit = """
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
    statements, errors = parser.parse_text(circuit)
    assert not errors, f"Errors found: {errors}"
    assert statements

    # Verify declarations
    decls = [s for s in statements if s["type"] == "declaration"]
    assert len(decls) == 4

    # Verify component block
    blocks = [s for s in statements if s["type"] == "component_connection_block"]
    assert len(blocks) == 1

    # Verify series connections
    series = [s for s in statements if s["type"] == "series_connection"]
    assert len(series) == 2
