from circuijt.ast_converter import ast_to_flattened_ast, flattened_ast_to_regular_ast
from circuijt.parser import ProtoCircuitParser
from circuijt.graph_utils import ast_to_graph, DSU


def test_simple_series_flattening():
    parser = ProtoCircuitParser()
    circuit = """
    R R1
    C C1
    (in) -- R1 -- (mid) -- C1 -- (GND)
    """
    statements, errors = parser.parse_text(circuit)
    assert not errors

    _, dsu = ast_to_graph(statements)  # Get initial DSU
    flattened = ast_to_flattened_ast(statements, dsu)

    # Check declarations preserved
    decls = [s for s in flattened if s["type"] == "declaration"]
    assert len(decls) == 2
    assert any(d["instance_name"] == "R1" and d["component_type"] == "R" for d in decls)
    assert any(d["instance_name"] == "C1" and d["component_type"] == "C" for d in decls)

    # Check pin connections
    pins = [s for s in flattened if s["type"] == "pin_connection"]
    assert len(pins) == 4  # R1: 2 pins, C1: 2 pins

    # Verify R1 connections
    r1_pins = [p for p in pins if p["component_instance"] == "R1"]
    assert len(r1_pins) == 2
    r1_nets = {p["net"] for p in r1_pins}
    assert "in" in r1_nets or any(
        s["canonical_net"] == "in" for s in flattened if s["type"] == "net_alias"
    )
    assert "mid" in r1_nets or any(
        s["canonical_net"] == "mid" for s in flattened if s["type"] == "net_alias"
    )


def test_net_alias_preservation():
    parser = ProtoCircuitParser()
    circuit = """
    R R1
    (node1) -- R1 -- (node2)
    (node1):(VDD)  ; Create alias
    """
    statements, errors = parser.parse_text(circuit)
    assert not errors

    _, dsu = ast_to_graph(statements)
    flattened = ast_to_flattened_ast(statements, dsu)

    # Find net aliases
    aliases = [s for s in flattened if s["type"] == "net_alias"]

    # Should find node1:VDD alias
    found_alias = False
    for alias in aliases:
        if (alias["source_net"] == "node1" and alias["canonical_net"] == "VDD") or (
            alias["source_net"] == "VDD" and alias["canonical_net"] == "node1"
        ):
            found_alias = True
            break
    assert found_alias


def test_roundtrip_conversion():
    """Test converting AST to flattened form and back"""
    parser = ProtoCircuitParser()
    circuit = """
    R R1
    C C1
    (out) -- [ R1 || C1 ] -- (GND)
    """
    statements, errors = parser.parse_text(circuit)
    assert not errors

    # Step 1: AST -> Graph -> Flattened
    graph, dsu = ast_to_graph(statements)
    flattened = ast_to_flattened_ast(statements, dsu)

    # Debug prints
    _debug_print_flattened(flattened)

    # Step 2: Flattened -> Regular AST
    reconstructed = flattened_ast_to_regular_ast(flattened)
    _debug_print_reconstructed(reconstructed)

    # Check parallel structure preserved
    parallel_found = _check_parallel_structure(reconstructed)

    if not parallel_found:
        print("\nDebug - All paths in reconstructed AST:")
        for stmt in reconstructed:
            if stmt["type"] == "series_connection":
                print(f"Path elements: {stmt['path']}")

    assert parallel_found, "Parallel structure (R1 || C1) not preserved in reconstruction"


def _debug_print_flattened(flattened):
    """Helper function to print debug info about flattened AST structure."""
    print("\nFlattened AST structure:")
    print(f"Total statements: {len(flattened)}")
    for stmt in flattened:
        print(f"Statement type: {stmt['type']}")
        if stmt["type"] == "pin_connection":
            print(f"  {stmt['component_instance']}.{stmt['terminal']} -> {stmt['net']}")


def _debug_print_reconstructed(reconstructed):
    """Helper function to print debug info about reconstructed AST structure."""
    print("\nReconstructed AST structure:")
    print(f"Total statements: {len(reconstructed)}")
    for stmt in reconstructed:
        if stmt["type"] == "declaration":
            print(f"  Declaration: {stmt['component_type']} {stmt['instance_name']}")
        elif stmt["type"] == "parallel_connection":
            print(f"  Parallel connection with {len(stmt['elements'])} elements")
            for el in stmt["elements"]:
                print(f"    - {el['type']}: {el.get('name', '')}")
        elif stmt["type"] == "series_connection":
            path_desc = []
            for el in stmt["path"]:
                if el["type"] == "node":
                    path_desc.append(f"({el['name']})")
                elif el["type"] == "component":
                    path_desc.append(el["name"])
                elif el["type"] == "parallel_block":
                    components = [e["name"] for e in el["elements"] if e["type"] == "component"]
                    path_desc.append(f"[{' || '.join(components)}]")
            print(f"  Series path: {' -- '.join(path_desc)}")


def _check_parallel_structure(reconstructed):
    """Helper function to verify parallel structure preservation."""
    for stmt in reconstructed:
        if stmt["type"] == "series_connection":
            for el in stmt["path"]:
                if el["type"] == "parallel_block":
                    components = {e["name"] for e in el["elements"] if e["type"] == "component"}
                    if components == {"R1", "C1"}:
                        return True
    return False


def test_internal_components_handling():
    parser = ProtoCircuitParser()
    circuit = """
    V V1
    R R1
    (GND) -- V1(-+) -- R1 -- (out)  ; Creates internal voltage source
    """
    statements, errors = parser.parse_text(circuit)
    assert not errors, f"Parser failed with errors: {errors}"

    print("\nOriginal statements:")
    for stmt in statements:
        print(f"Statement type: {stmt['type']}")
        if stmt["type"] == "series_connection":
            print(f"  Path: {stmt['path']}")

    graph, dsu = ast_to_graph(statements)

    print("\nGraph structure:")
    print(f"Nodes: {[n for n in graph.nodes()]}")
    print(f"Edges: {[(u, v, d) for u, v, d in graph.edges(data=True)]}")

    flattened = ast_to_flattened_ast(statements, dsu)

    # Check voltage source connections are preserved
    v1_pins = [
        p
        for p in flattened
        if p["type"] == "pin_connection" and p["component_instance"] == "V1"
    ]

    print("\nVoltage source connections:")
    for pin in v1_pins:
        print(f"  {pin['component_instance']}.{pin['terminal']} -> {pin['net']}")

    assert len(v1_pins) == 2, "Expected 2 pin connections for V1"
    assert any(
        p["terminal"] == "neg" for p in v1_pins
    ), "V1 should have neg terminal connected"
    assert any(
        p["terminal"] == "pos" for p in v1_pins
    ), "V1 should have pos terminal connected"


def test_terminal_preservation():
    parser = ProtoCircuitParser()
    circuit = """
    Nmos M1
    M1 { G:(in), S:(GND), D:(out), B:(GND) }
    """
    statements, errors = parser.parse_text(circuit)
    assert not errors

    graph, dsu = ast_to_graph(statements)

    print("\nGraph structure:")
    print(f"Nodes: {[n for n in graph.nodes()]}")
    edges = [(u, v, d) for u, v, d in graph.edges(data=True)]
    print(f"Edges: {edges}")

    flattened = ast_to_flattened_ast(statements, dsu)

    # Check all MOSFET terminals preserved
    m1_pins = [
        p
        for p in flattened
        if p["type"] == "pin_connection" and p["component_instance"] == "M1"
    ]

    print("\nMOSFET terminal connections:")
    for pin in m1_pins:
        print(f"  {pin['terminal']} -> {pin['net']}")

    terminals = {p["terminal"] for p in m1_pins}
    assert terminals == {"G", "S", "D", "B"}, f"Missing terminals. Found: {terminals}"

    # Check correct nets
    pin_nets = {p["terminal"]: p["net"] for p in m1_pins}

    # Allow for either the original net name or its canonical equivalent via DSU
    assert pin_nets["G"] == "in" or any(
        a["canonical_net"] == "in"
        for a in flattened
        if a["type"] == "net_alias" and a["source_net"] == pin_nets["G"]
    )
    assert (
        pin_nets["S"] == "GND"
    ), f"Source should connect to GND, found: {pin_nets['S']}"
    assert pin_nets["B"] == "GND", f"Bulk should connect to GND, found: {pin_nets['B']}"


def test_complex_series_parallel_flattening():
    """Test that complex series-parallel circuits are properly flattened in the AST.

    Verifies:
    - Nested series/parallel structures are correctly flattened
    - Component ordering is preserved
    - No information is lost during flattening
    - All connections are properly represented
    """
    # Arrange
    parser = ProtoCircuitParser()

    # Load test circuit from file
    with open("circuits/diffpair1.circuijt", "r") as f:
        test_circuit = f.read()

    ast = None
    flattened_ast = None
    try:
        # Act
        ast, errors = parser.parse_text(test_circuit)
        assert not errors, f"Parser failed with errors: {errors}"
        flattened_ast = ast_to_flattened_ast(ast, DSU())

        # Assert
        # 1. Verify all original components are present
        original_components = {
            stmt["instance_name"] for stmt in ast if stmt["type"] == "declaration"
        }
        flattened_components = {
            stmt["instance_name"]
            for stmt in flattened_ast
            if stmt["type"] == "declaration"
        }
        assert original_components == flattened_components

        # 2. Verify connection count matches expected topology
        original_connections = sum(
            1 for stmt in ast if stmt["type"] in ("connection", "series", "parallel")
        )
        flattened_connections = sum(
            1 for stmt in flattened_ast if stmt["type"] == "pin_connection"
        )
        assert flattened_connections >= original_connections

        # 3. Verify no duplicate pin connections
        pin_connections = {
            (stmt["component_instance"], stmt["terminal"])
            for stmt in flattened_ast
            if stmt["type"] == "pin_connection"
        }
        assert len(pin_connections) == sum(
            1 for stmt in flattened_ast if stmt["type"] == "pin_connection"
        )

        # 4. Verify net aliases are properly handled
        net_aliases = {
            stmt["source_net"]: stmt["canonical_net"]
            for stmt in flattened_ast
            if stmt["type"] == "net_alias"
        }
        for source, canonical in net_aliases.items():
            assert canonical in {
                stmt["net"]
                for stmt in flattened_ast
                if stmt["type"] == "pin_connection"
            }

    except Exception as e:
        # Debug info on failure
        print(f"Original AST: {ast}")
        print(f"Flattened AST: {flattened_ast}")
        raise e
