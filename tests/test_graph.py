import pytest
from circuijt.parser import ProtoCircuitParser
from circuijt.graph_utils import ast_to_graph, graph_to_structured_ast

# from circuijt.validator import CircuitValidator # Not strictly needed for these graph tests


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
        assert (
            "R1" in graph.nodes()
            and graph.nodes["R1"]["node_kind"] == "component_instance"
        )
        assert (
            "C1" in graph.nodes()
            and graph.nodes["C1"]["node_kind"] == "component_instance"
        )
        assert (
            in_net in graph.nodes()
            and graph.nodes[in_net]["node_kind"] == "electrical_net"
        )
        assert (
            mid_net in graph.nodes()
            and graph.nodes[mid_net]["node_kind"] == "electrical_net"
        )
        assert (
            gnd_net in graph.nodes()
            and graph.nodes[gnd_net]["node_kind"] == "electrical_net"
        )

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
        assert (
            "R1" in graph.nodes()
            and graph.nodes["R1"]["node_kind"] == "component_instance"
        )
        assert (
            "C1" in graph.nodes()
            and graph.nodes["C1"]["node_kind"] == "component_instance"
        )

        # Check net nodes
        assert (
            out_canonical in graph.nodes()
            and graph.nodes[out_canonical]["node_kind"] == "electrical_net"
        )
        assert (
            gnd_canonical in graph.nodes()
            and graph.nodes[gnd_canonical]["node_kind"] == "electrical_net"
        )

        # Check R1 connections
        r1_neighbors = set(graph.neighbors("R1"))
        assert r1_neighbors == {out_canonical, gnd_canonical}

        # Check C1 connections
        c1_neighbors = set(graph.neighbors("C1"))
        assert c1_neighbors == {out_canonical, gnd_canonical}

        # Optional: Check terminal attributes
        edge_data_r1_out = graph.get_edge_data("R1", out_canonical)
        edge_data_r1_gnd = graph.get_edge_data("R1", gnd_canonical)
        # For MultiGraph, get_edge_data returns a dict of edge keys to edge data
        # Get the first edge's data since we know there's only one edge between these nodes
        edge_data_r1_out = (
            list(edge_data_r1_out.values())[0] if edge_data_r1_out else None
        )
        edge_data_r1_gnd = (
            list(edge_data_r1_gnd.values())[0] if edge_data_r1_gnd else None
        )
        assert {edge_data_r1_out["terminal"], edge_data_r1_gnd["terminal"]} == {
            "par_t1",
            "par_t2",
        }

        edge_data_c1_out_map = graph.get_edge_data("C1", out_canonical)
        edge_data_c1_gnd_map = graph.get_edge_data("C1", gnd_canonical)
        edge_data_c1_out = (
            list(edge_data_c1_out_map.values())[0] if edge_data_c1_out_map else None
        )
        edge_data_c1_gnd = (
            list(edge_data_c1_gnd_map.values())[0] if edge_data_c1_gnd_map else None
        )
        assert {edge_data_c1_out["terminal"], edge_data_c1_gnd["terminal"]} == {
            "par_t1",
            "par_t2",
        }

    except AssertionError as e:
        print("\\n--- Test Failed: test_parallel_graph ---")
        print(f"Circuit:\\n{circuit}")
        print(f"Parser errors: {errors}")
        print(f"Graph nodes: {list(graph.nodes(data=True))}")
        print(f"Graph edges: {list(graph.edges(data=True))}")
        print(f"DSU parents: {dsu.parent}")
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
        assert (
            "M1" in graph.nodes()
            and graph.nodes["M1"]["node_kind"] == "component_instance"
        )

        # Check net nodes
        assert (
            in_net in graph.nodes()
            and graph.nodes[in_net]["node_kind"] == "electrical_net"
        )
        assert (
            gnd_net in graph.nodes()
            and graph.nodes[gnd_net]["node_kind"] == "electrical_net"
        )
        assert (
            out_net in graph.nodes()
            and graph.nodes[out_net]["node_kind"] == "electrical_net"
        )

        # Check terminal connections from M1
        terminals_connected_to_nets = {}  # terminal_name -> connected_net_canonical

        for _, net_node, data in graph.edges(
            "M1", data=True
        ):  # Iterates edges connected to M1
            terminal = data.get("terminal")
            if terminal:
                # Handle cases where multiple terminals might connect to the same net (though not for M1's distinct G,D here)
                # For S and B connecting to GND, this check method is fine.
                if (
                    terminal in terminals_connected_to_nets
                ):  # e.g. if S already pointed to GND, and B also points to GND
                    assert (
                        terminals_connected_to_nets[terminal] == net_node
                    )  # Ensure consistency if re-adding
                terminals_connected_to_nets[terminal] = net_node

        assert terminals_connected_to_nets.get("G") == in_net
        assert terminals_connected_to_nets.get("S") == gnd_net
        assert terminals_connected_to_nets.get("D") == out_net
        assert terminals_connected_to_nets.get("B") == gnd_net
        assert (
            len(terminals_connected_to_nets) == 4
        )  # Ensure all 4 terminals were processed
    except AssertionError as e:
        print("\\n--- Test Failed: test_transistor_graph ---")
        print(f"Circuit:\\n{circuit}")
        print(f"Parser errors: {errors}")
        print(f"Graph nodes: {list(graph.nodes(data=True))}")
        print(f"Graph edges: {list(graph.edges(data=True))}")
        print(f"DSU parents: {dsu.parent}")
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
        assert (
            "V1" in graph.nodes()
            and graph.nodes["V1"]["node_kind"] == "component_instance"
        )
        assert (
            "R1" in graph.nodes()
            and graph.nodes["R1"]["node_kind"] == "component_instance"
        )

        # V1 connections
        v1_connections = {}  # terminal -> net
        for u_node, v_node, data in graph.edges("V1", data=True):
            net_node_for_terminal = v_node if u_node == "V1" else u_node
            if "terminal" in data:
                v1_connections[data["terminal"]] = net_node_for_terminal

        assert len(v1_connections) == 2  # neg and pos terminals
        assert dsu.find(v1_connections.get("neg")) == gnd_canonical

        # The 'pos' terminal of V1 connects to an implicit node, which then connects to R1
        implicit_node_v1_r1 = v1_connections.get("pos")
        assert implicit_node_v1_r1 is not None
        assert graph.nodes[implicit_node_v1_r1]["node_kind"] == "electrical_net"

        # R1 connections
        r1_connections = {}  # terminal -> net
        for _, net_node, data in graph.edges("R1", data=True):
            r1_connections[data["terminal"]] = net_node

        assert len(r1_connections) == 2  # t1_series and t2_series
        assert (
            r1_connections.get("t1_series") == implicit_node_v1_r1
            or r1_connections.get("t2_series") == implicit_node_v1_r1
        )
        assert (
            r1_connections.get("t1_series") == out_canonical
            or r1_connections.get("t2_series") == out_canonical
        )
        assert r1_connections.get("t1_series") != r1_connections.get(
            "t2_series"
        )  # Must connect to two different nets
    except AssertionError as e:
        print("\\n--- Test Failed: test_voltage_source_graph ---")
        print(f"Circuit:\\n{circuit}")
        print(f"Parser errors: {errors}")
        print(f"Graph nodes: {list(graph.nodes(data=True))}")
        print(f"Graph edges: {list(graph.edges(data=True))}")
        print(f"DSU parents: {dsu.parent}")
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
        node_g_canonical = dsu.find("node_g")
        gnd_canonical = dsu.find("GND")
        vdd_canonical = dsu.find("VDD")
        node_d_canonical = dsu.find("node_d")
        # M1.D is aliased to node_d, M1.S to GND. DSU handles this.

        # Check essential component nodes
        assert "M1" in graph.nodes()
        assert "Rd" in graph.nodes()
        assert "Cgs" in graph.nodes()
        assert "Vin" in graph.nodes()
        # Rs is declared but not used; should still be a node.
        assert "Rs" in graph.nodes()

        # Check Rd connections: (VDD) -- Rd -- (node_d)
        rd_neighbors = set(graph.neighbors("Rd"))
        assert rd_neighbors == {vdd_canonical, node_d_canonical}

        # Find the controlled source node (internal)
        cs_nodes = [
            n
            for n, data in graph.nodes(data=True)
            if data.get("instance_type") == "controlled_source"
            and data.get("expression") == "gm1*vgs1"
        ]
        assert len(cs_nodes) == 1
        cs_node_name = cs_nodes[0]

        # Controlled source and Cgs are in parallel between node_d_canonical and gnd_canonical
        cs_neighbors = set(graph.neighbors(cs_node_name))
        assert cs_neighbors == {node_d_canonical, gnd_canonical}

        cgs_neighbors = set(graph.neighbors("Cgs"))
        assert cgs_neighbors == {node_d_canonical, gnd_canonical}

        # M1 connections from block and direct assignments
        m1_connections_from_graph = {}
        for _, net_node, data in graph.edges("M1", data=True):
            m1_connections_from_graph[data["terminal"]] = net_node

        assert m1_connections_from_graph.get("G") == node_g_canonical
        assert m1_connections_from_graph.get("B") == gnd_canonical
        assert (
            m1_connections_from_graph.get("D") == node_d_canonical
        )  # From (M1.D):(node_d) via DSU
        assert (
            m1_connections_from_graph.get("S") == gnd_canonical
        )  # From (M1.S):(GND) via DSU
    except AssertionError as e:
        print("\\n--- Test Failed: test_complex_circuit_graph ---")
        print(f"Circuit:\\n{circuit}")
        print(f"Parser errors: {errors}")
        print(f"Graph nodes: {list(graph.nodes(data=True))}")
        print(f"Graph edges: {list(graph.edges(data=True))}")
        print(f"DSU parents: {dsu.parent}")
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

        # Check V_std (-+)
        v_std_edges = list(graph.edges("V_std", data=True))
        assert len(v_std_edges) == 2
        v_std_connections = {}
        for u, v, data in v_std_edges:
            net_node = v if u == "V_std" else u
            v_std_connections[data["terminal"]] = net_node
        assert (
            v_std_connections.get("neg") == n1_c
        ), f"V_std neg expected {n1_c}, got {v_std_connections.get('neg')}"
        assert (
            v_std_connections.get("pos") == n2_c
        ), f"V_std pos expected {n2_c}, got {v_std_connections.get('pos')}"

        # Check V_rev (+-)
        v_rev_edges = list(graph.edges("V_rev", data=True))
        assert len(v_rev_edges) == 2
        v_rev_connections = {}
        for u, v, data in v_rev_edges:
            net_node = v if u == "V_rev" else u
            v_rev_connections[data["terminal"]] = net_node
        assert (
            v_rev_connections.get("pos") == n3_c
        ), f"V_rev pos expected {n3_c}, got {v_rev_connections.get('pos')}"
        assert (
            v_rev_connections.get("neg") == n4_c
        ), f"V_rev neg expected {n4_c}, got {v_rev_connections.get('neg')}"

        # Check R1 and R2 connections to ensure graph integrity
        assert graph.has_edge("R1", n2_c) or graph.has_edge(n2_c, "R1")
        assert graph.has_edge("R1", gnd_c) or graph.has_edge(gnd_c, "R1")
        assert graph.has_edge("R2", n4_c) or graph.has_edge(n4_c, "R2")
        assert graph.has_edge("R2", gnd_c) or graph.has_edge(gnd_c, "R2")
    except AssertionError as e:
        print("\\n--- Test Failed: test_voltage_source_polarity_variations ---")
        print(f"Circuit:\\n{circuit}")
        print(f"Parser errors: {errors}")
        print(f"Graph nodes: {list(graph.nodes(data=True))}")
        print(f"Graph edges: {list(graph.edges(data=True))}")
        print(f"DSU parents: {dsu.parent}")
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
        r_par1_nodes = [n for n in graph.nodes() if n == "R_par1"]
        assert (
            len(r_par1_nodes) == 1
        ), "R_par1 should appear exactly once in graph nodes"
        r_par2_nodes = [n for n in graph.nodes() if n == "R_par2"]
        assert (
            len(r_par2_nodes) == 1
        ), "R_par2 should appear exactly once in graph nodes"

        # Check connections for R_par1
        in_c, mid_c = dsu.find("in"), dsu.find("mid")
        r_par1_neighbors = set()
        for u, v, data in graph.edges("R_par1", data=True):
            neighbor = v if u == "R_par1" else u
            r_par1_neighbors.add(neighbor)
        assert r_par1_neighbors == {
            in_c,
            mid_c,
        }, f"R_par1 connections incorrect. Expected {in_c, mid_c}, got {r_par1_neighbors}"

        # Check connections for R_par2
        r_par2_neighbors = set()
        for u, v, data in graph.edges("R_par2", data=True):
            neighbor = v if u == "R_par2" else u
            r_par2_neighbors.add(neighbor)
        assert r_par2_neighbors == {
            in_c,
            mid_c,
        }, f"R_par2 connections incorrect. Expected {in_c, mid_c}, got {r_par2_neighbors}"

        # Check number of edges for R_par1 and R_par2 (should be 2 each, one to 'in', one to 'mid')
        assert (
            len(list(graph.edges("R_par1"))) == 2
        ), "R_par1 should have exactly 2 edges"
        assert (
            len(list(graph.edges("R_par2"))) == 2
        ), "R_par2 should have exactly 2 edges"
    except AssertionError as e:
        print("\\n--- Test Failed: test_no_duplicate_parallel_elements ---")
        print(f"Circuit:\\n{circuit}")
        print(f"Parser errors: {errors}")
        print(f"Graph nodes: {list(graph.nodes(data=True))}")
        print(f"Graph edges: {list(graph.edges(data=True))}")
        print(f"DSU parents: {dsu.parent}")
        raise e


def test_graph_to_ast_conversion():
    """Test converting graph back to AST structure"""
    parser = ProtoCircuitParser()
    original_circuit = """
    R R1
    C C1
    (in) -- R1 -- (mid) -- C1 -- (GND)
    """
    try:
        statements, errors = parser.parse_text(original_circuit)
        assert not errors, f"Parser failed with errors: {errors}"

        # Convert to graph
        graph, dsu = ast_to_graph(statements)

        # Print graph state for debugging
        print("\nGraph state before reconstruction:")
        print(f"Nodes: {[n for n in graph.nodes()]}")
        print(f"Edges: {[(u,v,d) for u,v,d in graph.edges(data=True)]}")
        print(f"Net equivalences (DSU): {[(n, dsu.find(n)) for n in dsu.parent]}")

        # Convert back to AST
        reconstructed_ast = graph_to_structured_ast(graph, dsu)

        # Print reconstructed AST for debugging
        print("\nReconstructed AST:")
        for stmt in reconstructed_ast:
            print(f"Statement type: {stmt['type']}")
            if stmt["type"] == "declaration":
                print(
                    f"  Declaration: {stmt['component_type']} {stmt['instance_name']}"
                )
            elif stmt["type"] == "series_connection":
                path_desc = []
                for el in stmt["path"]:
                    if el["type"] == "node":
                        path_desc.append(f"({el['name']})")
                    elif el["type"] == "component":
                        path_desc.append(el["name"])
                print(f"  Series path: {' -- '.join(path_desc)}")

        # Verify essential elements are preserved
        decls = [s for s in reconstructed_ast if s["type"] == "declaration"]
        assert (
            len(decls) == 2
        ), f"Expected 2 declarations (R1, C1), found {len(decls)}: {decls}"

        series_connections_found = [
            s for s in reconstructed_ast if s["type"] == "series_connection"
        ]
        # The reconstruction might create two series paths: (in)--R1--(mid) and (mid)--C1--(GND)
        # or one combined path depending on graph_to_structured_ast logic.
        # A simple check is that the components are part of some series connection.
        assert (
            len(series_connections_found) > 0
        ), f"No series connections found in reconstructed AST. Full AST: {reconstructed_ast}"

        components_in_reconstructed_series = set()
        for s_conn in series_connections_found:
            for element in s_conn["path"]:
                if element.get("type") == "component":
                    components_in_reconstructed_series.add(element["name"])
                elif (
                    element.get("type") == "parallel_block"
                ):  # Handle components inside parallel blocks too
                    for pel in element.get("elements", []):
                        if pel.get("type") == "component":
                            components_in_reconstructed_series.add(pel["name"])

        missing_comps = {"R1", "C1"} - components_in_reconstructed_series
        assert (
            not missing_comps
        ), f"Components missing from series connections: {missing_comps}. Found: {components_in_reconstructed_series}. Full AST: {reconstructed_ast}"
    except AssertionError as e:
        print("\\n--- Test Failed: test_graph_to_ast_conversion ---")
        print(f"Original circuit:\\n{original_circuit}")
        print(f"Parser errors: {errors}")
        print(f"Graph nodes: {list(graph.nodes(data=True))}")
        print(f"Graph edges: {list(graph.edges(data=True))}")
        print(f"DSU parents: {dsu.parent}")
        print(f"Reconstructed AST: {reconstructed_ast}")
        raise e
