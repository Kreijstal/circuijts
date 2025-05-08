"""Tests for graph utility functions."""

from circuijt.parser import ProtoCircuitParser
from circuijt.graph_utils import ast_to_graph, graph_to_structured_ast


# Helper functions to reduce complexity and locals in tests


def _check_parallel_component_terminals(graph, comp_name, net1_canonical, net2_canonical, expected_terminals_set):
    """Checks that a component in a parallel branch connects to two nets with expected terminals."""
    edge_data_comp_net1_map = graph.get_edge_data(comp_name, net1_canonical)
    edge_data_comp_net2_map = graph.get_edge_data(comp_name, net2_canonical)

    terminal1 = list(edge_data_comp_net1_map.values())[0]["terminal"] if edge_data_comp_net1_map else None
    terminal2 = list(edge_data_comp_net2_map.values())[0]["terminal"] if edge_data_comp_net2_map else None

    assert {terminal1, terminal2} == expected_terminals_set


def _get_component_connections(graph, comp_name):
    """Helper to get terminal connections for a component."""
    connections = {}
    for _, neighbor_node, edge_data in graph.edges(comp_name, data=True):
        terminal = edge_data.get("terminal")
        if terminal:
            connections[terminal] = neighbor_node
    return connections


def _collect_components_from_element(element, components_set):
    """Collects component names from a path element into components_set."""
    if element.get("type") == "component":
        components_set.add(element["name"])
    elif element.get("type") == "parallel_block":
        for pel in element.get("elements", []):
            if pel.get("type") == "component":
                components_set.add(pel["name"])


def test_simple_series_graph():
    """Test graph creation for a simple RC series circuit"""
    parser = ProtoCircuitParser()
    circuit = """
    R R1
    C C1
    (in) -- R1 -- (mid) -- C1 -- (GND)
    """
    statements, errors = parser.parse_text(circuit)
    assert not errors

    graph, dsu = ast_to_graph(statements)

    try:
        # Canonical net names
        in_net = dsu.find("in")
        mid_net = dsu.find("mid")
        gnd_net = dsu.find("GND")

        # Check component and net nodes exist
        assert "R1" in graph.nodes() and graph.nodes["R1"]["node_kind"] == "component_instance"
        assert "C1" in graph.nodes() and graph.nodes["C1"]["node_kind"] == "component_instance"
        assert in_net in graph.nodes() and graph.nodes[in_net]["node_kind"] == "electrical_net"
        assert mid_net in graph.nodes() and graph.nodes[mid_net]["node_kind"] == "electrical_net"
        assert gnd_net in graph.nodes() and graph.nodes[gnd_net]["node_kind"] == "electrical_net"

        # Check edges (connections)
        # (in) -- R1
        assert graph.has_edge(in_net, "R1") or graph.has_edge("R1", in_net)
        # R1 -- (mid)
        assert graph.has_edge("R1", mid_net) or graph.has_edge(mid_net, "R1")
        # (mid) -- C1
        assert graph.has_edge(mid_net, "C1") or graph.has_edge("C1", mid_net)
        # C1 -- (GND)
        assert graph.has_edge("C1", gnd_net) or graph.has_edge(gnd_net, "C1")
    except AssertionError as e:
        print("\n--- Test Failed: test_simple_series_graph ---")
        print(f"Circuit:\n{circuit}")
        print(f"Parser errors: {errors}")
        print(f"Graph nodes: {list(graph.nodes(data=True))}")
        print(f"Graph edges: {list(graph.edges(data=True))}")
        print(f"DSU parents: {dsu.parent}")
        raise e


def test_parallel_graph():
    """Test graph creation for parallel components"""
    parser = ProtoCircuitParser()
    circuit = """
    R R1
    C C1
    (out) -- [ R1 || C1 ] -- (GND)
    """
    try:
        statements, errors = parser.parse_text(circuit)
        assert not errors

        graph, dsu = ast_to_graph(statements)

        out_canonical = dsu.find("out")
        gnd_canonical = dsu.find("GND")

        # Check component nodes
        assert "R1" in graph.nodes() and graph.nodes["R1"]["node_kind"] == "component_instance"
        assert "C1" in graph.nodes() and graph.nodes["C1"]["node_kind"] == "component_instance"

        # Check net nodes
        assert out_canonical in graph.nodes() and graph.nodes[out_canonical]["node_kind"] == "electrical_net"
        assert gnd_canonical in graph.nodes() and graph.nodes[gnd_canonical]["node_kind"] == "electrical_net"

        # Check R1 connections
        r1_neighbors = set(graph.neighbors("R1"))
        assert r1_neighbors == {out_canonical, gnd_canonical}

        # Check C1 connections
        c1_neighbors = set(graph.neighbors("C1"))
        assert c1_neighbors == {out_canonical, gnd_canonical}

        # Optional: Check terminal attributes using helper
        expected_terms = {"par_t1", "par_t2"}
        _check_parallel_component_terminals(graph, "R1", out_canonical, gnd_canonical, expected_terms)
        _check_parallel_component_terminals(graph, "C1", out_canonical, gnd_canonical, expected_terms)

    except AssertionError as e:
        print("\n--- Test Failed: test_parallel_graph ---")
        print("Circuit:\n", circuit)
        print("Parser errors:", errors)
        print("Graph nodes:", list(graph.nodes(data=True)))
        print("Graph edges:", list(graph.edges(data=True)))
        print("DSU parents:", dsu.parent)
        raise e


def test_transistor_graph():
    """Test graph creation for a transistor with multiple terminals"""
    parser = ProtoCircuitParser()
    circuit = """
    Nmos M1
    M1 { G:(in), S:(GND), D:(out), B:(GND) }
    """
    try:
        statements, errors = parser.parse_text(circuit)
        assert not errors

        graph, dsu = ast_to_graph(statements)

        # Canonical net names
        in_net = dsu.find("in")
        gnd_net = dsu.find("GND")
        out_net = dsu.find("out")

        # Check component node
        assert "M1" in graph.nodes() and graph.nodes["M1"]["node_kind"] == "component_instance"

        # Check net nodes
        assert in_net in graph.nodes() and graph.nodes[in_net]["node_kind"] == "electrical_net"
        assert gnd_net in graph.nodes() and graph.nodes[gnd_net]["node_kind"] == "electrical_net"
        assert out_net in graph.nodes() and graph.nodes[out_net]["node_kind"] == "electrical_net"

        # Check terminal connections from M1 using helper
        m1_connections = _get_component_connections(graph, "M1")

        assert m1_connections.get("G") == in_net
        assert m1_connections.get("S") == gnd_net
        assert m1_connections.get("D") == out_net
        assert m1_connections.get("B") == gnd_net
        assert len(m1_connections) == 4  # Ensure all 4 terminals were processed
    except AssertionError as e:
        print("\n--- Test Failed: test_transistor_graph ---")
        print("Circuit:\n", circuit)
        print("Parser errors:", errors)
        print("Graph nodes:", list(graph.nodes(data=True)))
        print("Graph edges:", list(graph.edges(data=True)))
        print("DSU parents:", dsu.parent)
        raise e


def test_voltage_source_graph():
    """Test graph creation for voltage sources with polarity"""
    parser = ProtoCircuitParser()
    circuit = """
    V V1
    R R1
    (GND) -- V1(-+) -- R1 -- (out)
    """
    try:
        statements, errors = parser.parse_text(circuit)
        assert not errors

        graph, dsu = ast_to_graph(statements)

        gnd_canonical = dsu.find("GND")
        out_canonical = dsu.find("out")

        # Check component nodes
        assert "V1" in graph.nodes() and graph.nodes["V1"]["node_kind"] == "component_instance"
        assert "R1" in graph.nodes() and graph.nodes["R1"]["node_kind"] == "component_instance"

        # V1 connections using helper
        v1_connections = _get_component_connections(graph, "V1")

        assert len(v1_connections) == 2  # neg and pos terminals
        assert dsu.find(v1_connections.get("neg")) == gnd_canonical

        # The 'pos' terminal of V1 connects to an implicit node, which then connects to R1
        implicit_node_v1_r1 = v1_connections.get("pos")
        assert implicit_node_v1_r1 is not None
        assert graph.nodes[implicit_node_v1_r1]["node_kind"] == "electrical_net"

        # R1 connections using helper
        r1_connections = _get_component_connections(graph, "R1")

        assert len(r1_connections) == 2  # t1_series and t2_series
        assert r1_connections.get("t1_series") == implicit_node_v1_r1 or r1_connections.get("t2_series") == implicit_node_v1_r1
        assert r1_connections.get("t1_series") == out_canonical or r1_connections.get("t2_series") == out_canonical
        assert r1_connections.get("t1_series") != r1_connections.get("t2_series")  # Must connect to two different nets
    except AssertionError as e:
        print("\n--- Test Failed: test_voltage_source_graph ---")
        print("Circuit:\n", circuit)
        print("Parser errors:", errors)
        print("Graph nodes:", list(graph.nodes(data=True)))
        print("Graph edges:", list(graph.edges(data=True)))
        print("DSU parents:", dsu.parent)
        raise e


def test_complex_circuit_graph():
    """Test graph creation for a more complex circuit with multiple features"""
    parser = ProtoCircuitParser()
    circuit = """
    Nmos M1
    R Rd
    R Rs
    C Cgs
    V Vin

    M1 { G:(node_g), B:(GND) }
    (GND) -- Vin(-+) -- (node_g)
    (VDD) -- Rd -- (node_d) -- [ gm1*vgs1 (->) || Cgs ] -- (GND)
    (M1.D):(node_d)
    (M1.S):(GND)
    """
    try:
        statements, errors = parser.parse_text(circuit)
        assert not errors

        graph, dsu = ast_to_graph(statements)

        # Canonical net names
        nets = {name: dsu.find(name) for name in ["node_g", "GND", "VDD", "node_d"]}

        # Check essential component nodes (Rs is declared but not used)
        for comp in ["M1", "Rd", "Cgs", "Vin", "Rs"]:
            assert comp in graph.nodes()

        # Check Rd connections: (VDD) -- Rd -- (node_d)
        rd_neighbors = set(graph.neighbors("Rd"))
        assert rd_neighbors == {nets["VDD"], nets["node_d"]}

        # Find the controlled source node (internal)
        cs_nodes = [
            n
            for n, node_data in graph.nodes(data=True)
            if node_data.get("instance_type") == "controlled_source" and node_data.get("expression") == "gm1*vgs1"
        ]
        assert len(cs_nodes) == 1
        cs_node_name = cs_nodes[0]

        # Controlled source and Cgs are in parallel between node_d_canonical and gnd_canonical
        cs_neighbors = set(graph.neighbors(cs_node_name))
        assert cs_neighbors == {nets["node_d"], nets["GND"]}

        cgs_neighbors = set(graph.neighbors("Cgs"))
        assert cgs_neighbors == {nets["node_d"], nets["GND"]}

        # M1 connections from block and direct assignments, using helper
        m1_connections = _get_component_connections(graph, "M1")

        assert m1_connections.get("G") == nets["node_g"]
        assert m1_connections.get("B") == nets["GND"]
        assert m1_connections.get("D") == nets["node_d"]
        assert m1_connections.get("S") == nets["GND"]
    except AssertionError as e:
        print("\n--- Test Failed: test_complex_circuit_graph ---")
        print("Circuit:\n", circuit)
        print("Parser errors:", errors)
        print("Graph nodes:", list(graph.nodes(data=True)))
        print("Graph edges:", list(graph.edges(data=True)))
        print("DSU parents:", dsu.parent)
        raise e


def test_voltage_source_polarity_variations():
    """Test graph creation for voltage sources with both (-+) and (+-) polarities."""
    parser = ProtoCircuitParser()
    circuit = """
    V V_std ; Standard polarity
    V V_rev ; Reversed polarity
    R R1
    R R2
    (n1) -- V_std(-+) -- (n2) -- R1 -- (GND)
    (n3) -- V_rev(+-) -- (n4) -- R2 -- (GND)
    """
    try:
        statements, errors = parser.parse_text(circuit)
        assert not errors, f"Parser failed: {errors}"

        graph, dsu = ast_to_graph(statements)

        # Canonical net names
        n1_c, n2_c, n3_c, n4_c, gnd_c = (
            dsu.find("n1"),
            dsu.find("n2"),
            dsu.find("n3"),
            dsu.find("n4"),
            dsu.find("GND"),
        )

        # Check V_std (-+) using helper
        v_std_connections = _get_component_connections(graph, "V_std")
        assert len(v_std_connections) == 2
        assert v_std_connections.get("neg") == n1_c, f"V_std neg expected {n1_c}, got {v_std_connections.get('neg')}"
        assert v_std_connections.get("pos") == n2_c, f"V_std pos expected {n2_c}, got {v_std_connections.get('pos')}"

        # Check V_rev (+-) using helper
        v_rev_connections = _get_component_connections(graph, "V_rev")
        assert len(v_rev_connections) == 2
        assert v_rev_connections.get("pos") == n3_c, f"V_rev pos expected {n3_c}, got {v_rev_connections.get('pos')}"
        assert v_rev_connections.get("neg") == n4_c, f"V_rev neg expected {n4_c}, got {v_rev_connections.get('neg')}"

        # Check R1 and R2 connections to ensure graph integrity
        assert graph.has_edge("R1", n2_c) or graph.has_edge(n2_c, "R1")
        assert graph.has_edge("R1", gnd_c) or graph.has_edge(gnd_c, "R1")
        assert graph.has_edge("R2", n4_c) or graph.has_edge(n4_c, "R2")
        assert graph.has_edge("R2", gnd_c) or graph.has_edge(gnd_c, "R2")
    except AssertionError as e:
        print("\n--- Test Failed: test_voltage_source_polarity_variations ---")
        print("Circuit:\n", circuit)
        print("Parser errors:", errors)
        print("Graph nodes:", list(graph.nodes(data=True)))
        print("Graph edges:", list(graph.edges(data=True)))
        print("DSU parents:", dsu.parent)
        raise e


def test_no_duplicate_parallel_elements():
    """Test that parallel elements are not duplicated during graph construction."""
    parser = ProtoCircuitParser()
    circuit = """
    R R_par1
    R R_par2
    C C_series
    (in) -- [ R_par1 || R_par2 ] -- (mid) -- C_series -- (GND)
    """
    try:
        statements, errors = parser.parse_text(circuit)
        assert not errors, f"Parser failed: {errors}"

        graph, dsu = ast_to_graph(statements)

        # Check that R_par1 and R_par2 appear only once
        for comp_name in ["R_par1", "R_par2"]:
            comp_nodes = [n for n in graph.nodes() if n == comp_name]
            assert len(comp_nodes) == 1, f"{comp_name} should appear exactly once"

        # Check connections
        nets = {name: dsu.find(name) for name in ["in", "mid"]}
        expected_neighbors = {nets["in"], nets["mid"]}

        for comp_name in ["R_par1", "R_par2"]:
            neighbors = set()
            for u, v, _ in graph.edges(comp_name, data=True):
                neighbor = v if u == comp_name else u
                neighbors.add(neighbor)
            assert (
                neighbors == expected_neighbors
            ), f"{comp_name} connections incorrect. Expected {expected_neighbors}, got {neighbors}"
            assert len(list(graph.edges(comp_name))) == 2, f"{comp_name} should have 2 edges"

    except AssertionError as e:
        print("\\n--- Test Failed: test_no_duplicate_parallel_elements ---")
        print(f"Circuit:\\n{circuit}")
        print(f"Parser errors: {errors}")
        print("Graph nodes:", list(graph.nodes(data=True)))
        print("Graph edges:", list(graph.edges(data=True)))
        print("DSU parents:", dsu.parent)
        raise e


def _setup_graph_conversion_test():
    """Helper function to set up basic circuit for graph conversion tests"""
    parser = ProtoCircuitParser()
    original_circuit = """
    R R1
    C C1
    (in) -- R1 -- (mid) -- C1 -- (GND)
    """
    statements, errors = parser.parse_text(original_circuit)
    assert not errors, f"Parser failed with errors: {errors}"
    return original_circuit, statements


def test_graph_to_ast_basic_structure():
    """Test basic graph to AST conversion structure"""
    try:
        _, statements = _setup_graph_conversion_test()

        # Convert to graph
        graph, dsu = ast_to_graph(statements)
        reconstructed_ast = graph_to_structured_ast(graph, dsu)

        # Verify basic structure
        assert reconstructed_ast, "Reconstructed AST should not be empty"
        assert isinstance(reconstructed_ast, list), "Reconstructed AST should be a list"
    except AssertionError as e:
        print("\n--- Test Failed: test_graph_to_ast_basic_structure ---")
        print(f"Graph nodes: {list(graph.nodes(data=True))}")
        print(f"Graph edges: {list(graph.edges(data=True))}")
        print(f"DSU parents: {dsu.parent}")
        print(f"Reconstructed AST: {reconstructed_ast}")
        raise e


def test_graph_to_ast_declarations():
    """Test that declarations are properly preserved in graph to AST conversion"""
    try:
        _, statements = _setup_graph_conversion_test()

        graph, dsu = ast_to_graph(statements)
        reconstructed_ast = graph_to_structured_ast(graph, dsu)

        # Verify declarations
        decls = [s for s in reconstructed_ast if s["type"] == "declaration"]
        err_msg = f"Expected 2 declarations (R1, C1), found {len(decls)}: {decls}"
        assert len(decls) == 2, err_msg

        # Check specific components are declared
        component_types = {(d["component_type"], d["instance_name"]) for d in decls}
        assert ("R", "R1") in component_types, "Missing R1 declaration"
        assert ("C", "C1") in component_types, "Missing C1 declaration"
    except AssertionError as e:
        print("\n--- Test Failed: test_graph_to_ast_declarations ---")
        print(f"Graph nodes: {list(graph.nodes(data=True))}")
        print(f"Graph edges: {list(graph.edges(data=True))}")
        print(f"DSU parents: {dsu.parent}")
        print(f"Reconstructed AST: {reconstructed_ast}")
        raise e


def test_graph_to_ast_connections():
    """Test that component connections are properly preserved in graph to AST conversion"""
    try:
        _, statements = _setup_graph_conversion_test()

        graph, dsu = ast_to_graph(statements)
        reconstructed_ast = graph_to_structured_ast(graph, dsu)

        # Verify series connections
        series_connections = [s for s in reconstructed_ast if s["type"] == "series_connection"]
        assert series_connections, "No series connections found in reconstructed AST"

        # Check all components are present in connections using helper
        components_in_series = set()
        for conn in series_connections:
            for element in conn["path"]:
                _collect_components_from_element(element, components_in_series)

        missing_comps = {"R1", "C1"} - components_in_series
        err_msg = f"Components missing from series connections: {missing_comps}. " f"Found: {components_in_series}"
        assert not missing_comps, err_msg
    except AssertionError as e:
        print("\n--- Test Failed: test_graph_to_ast_connections ---")
        print(f"Graph nodes: {list(graph.nodes(data=True))}")
        print(f"Graph edges: {list(graph.edges(data=True))}")
        print(f"DSU parents: {dsu.parent}")
        print(f"Reconstructed AST: {reconstructed_ast}")
        raise e
