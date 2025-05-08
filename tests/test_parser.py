import pytest
from circuijt.parser import ProtoCircuitParser


def test_parser_initialization():
    parser = ProtoCircuitParser()
    assert parser.parsed_statements == []
    assert parser.errors == []


def test_basic_node_formats():
    parser = ProtoCircuitParser()
    # Regular node
    result = parser._parse_element("(node1)", 1)
    assert result["type"] == "node"
    assert result["name"] == "node1"

    # Device terminal node
    result = parser._parse_element("(M1.G)", 1)
    assert result["type"] == "node"
    assert result["name"] == "M1.G"

    # Special nodes
    result = parser._parse_element("(GND)", 1)
    assert result["type"] == "node"
    assert result["name"] == "GND"

    result = parser._parse_element("(VDD)", 1)
    assert result["type"] == "node"
    assert result["name"] == "VDD"


def test_invalid_node_formats():
    parser = ProtoCircuitParser()
    # Invalid node name starting with number
    result = parser._parse_element("(123node)", 1)
    assert result["type"] == "error"

    # Invalid characters in node name
    result = parser._parse_element("(node@123)", 1)
    assert result["type"] == "error"

    # Multiple dots in device terminal
    result = parser._parse_element("(M1.G.D)", 1)
    assert result["type"] == "error"


def test_component_declarations():
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
        assert len(errors) == 0, f"Declaration '{decl}' failed"
        assert len(statements) == 1
        assert statements[0]["type"] == "declaration"


def test_invalid_component_declarations():
    parser = ProtoCircuitParser()
    invalid_decls = [
        "123R R1",  # Type starting with number
        "R 1R1",  # Instance name starting with number
        "R R@1",  # Invalid character in instance name
        "R-type R1",  # Invalid character in type
    ]

    for decl in invalid_decls:
        statements, errors = parser.parse_text(decl)
        assert len(errors) > 0, f"Invalid declaration '{decl}' should fail"


def test_source_polarity():
    parser = ProtoCircuitParser()
    # Test both polarity formats
    result = parser._parse_element("V1(-+)", 1)
    assert result["type"] == "source"
    assert result["polarity"] == "-+"

    result = parser._parse_element("V2(+-)", 1)
    assert result["type"] == "source"
    assert result["polarity"] == "+-"


def test_component_connection_block():
    parser = ProtoCircuitParser()
    block = """M1 { G:(node_gate), S:(GND), D:(node_drain), B:(GND) }"""
    statements, errors = parser.parse_text(block)
    assert len(errors) == 0
    assert len(statements) == 1
    assert statements[0]["type"] == "component_connection_block"
    assert len(statements[0]["connections"]) == 4


def test_series_connections():
    parser = ProtoCircuitParser()
    # Basic series connection
    path = "(Vin) -- R1 -- (Vout)"
    statements, errors = parser.parse_text(path)
    assert len(errors) == 0
    assert statements[0]["type"] == "series_connection"

    # Series with source
    path = "(GND) -- V1(-+) -- R1 -- (out)"
    statements, errors = parser.parse_text(path)
    assert len(errors) == 0

    # Series with named current
    path = "(VDD) -- ->I_supply -- R1 -- (node1)"
    statements, errors = parser.parse_text(path)
    assert len(errors) == 0


def test_parallel_blocks():
    parser = ProtoCircuitParser()
    # Basic parallel components
    path = "(out) -- [ R1 || C1 ] -- (GND)"
    statements, errors = parser.parse_text(path)
    assert len(errors) == 0

    # Parallel with controlled source
    path = "(drain) -- [ gm1*vgs1 (->) || rds1 ] -- (source)"
    statements, errors = parser.parse_text(path)
    assert len(errors) == 0


def test_direct_assignments():
    parser = ProtoCircuitParser()
    # Node to node assignment
    assign = "(node1):(node2)"
    statements, errors = parser.parse_text(assign)
    assert len(errors) == 0

    # Device terminal assignments
    assign = "(M1.D):(VDD)"
    statements, errors = parser.parse_text(assign)
    assert len(errors) == 0


def test_complete_circuit():
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
    assert len(errors) == 0, f"Errors found: {errors}"
    assert len(statements) > 0

    # Verify declarations
    decls = [s for s in statements if s["type"] == "declaration"]
    assert len(decls) == 4

    # Verify component block
    blocks = [s for s in statements if s["type"] == "component_connection_block"]
    assert len(blocks) == 1

    # Verify series connections
    series = [s for s in statements if s["type"] == "series_connection"]
    assert len(series) == 2
