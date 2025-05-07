import pytest
from circuijt.parser import ProtoCircuitParser
from circuijt.graph_utils import ast_to_graph, graph_to_structured_ast

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
    
    # Check nodes exist
    assert "in" in graph.nodes()
    assert "mid" in graph.nodes()
    assert "GND" in graph.nodes()
    
    # Check edges (connections)
    assert graph.has_edge("in", "mid")  # R1 connection
    assert graph.has_edge("mid", "GND")  # C1 connection
    
    # Check edge data
    r1_edge = [e for e in graph.edges(data=True) if e[2].get('component') == 'R1'][0]
    assert r1_edge[2]['type'] == 'component'
    
    c1_edge = [e for e in graph.edges(data=True) if e[2].get('component') == 'C1'][0]
    assert c1_edge[2]['type'] == 'component'

def test_parallel_graph():
    """Test graph creation for parallel components"""
    parser = ProtoCircuitParser()
    circuit = """
    R R1
    C C1
    (out) -- [ R1 || C1 ] -- (GND)
    """
    statements, errors = parser.parse_text(circuit)
    assert not errors

    graph, dsu = ast_to_graph(statements)
    
    # Check nodes
    assert "out" in graph.nodes()
    assert "GND" in graph.nodes()
    
    # Both components should create edges between the same nodes
    r1_edges = [e for e in graph.edges(data=True) if e[2].get('component') == 'R1']
    c1_edges = [e for e in graph.edges(data=True) if e[2].get('component') == 'C1']
    
    assert len(r1_edges) == 1
    assert len(c1_edges) == 1
    assert r1_edges[0][0:2] == c1_edges[0][0:2]  # Same endpoints

def test_transistor_graph():
    """Test graph creation for a transistor with multiple terminals"""
    parser = ProtoCircuitParser()
    circuit = """
    Nmos M1
    M1 { G:(in), S:(GND), D:(out), B:(GND) }
    """
    statements, errors = parser.parse_text(circuit)
    assert not errors

    graph, dsu = ast_to_graph(statements)
    
    # Check nodes
    assert "in" in graph.nodes()
    assert "out" in graph.nodes()
    assert "GND" in graph.nodes()
    
    # Check terminal connections
    gate_conn = [e for e in graph.edges(data=True) if e[2].get('terminal') == 'G']
    source_conn = [e for e in graph.edges(data=True) if e[2].get('terminal') == 'S']
    drain_conn = [e for e in graph.edges(data=True) if e[2].get('terminal') == 'D']
    bulk_conn = [e for e in graph.edges(data=True) if e[2].get('terminal') == 'B']
    
    assert len(gate_conn) == 1
    assert len(source_conn) == 1
    assert len(drain_conn) == 1
    assert len(bulk_conn) == 1

def test_voltage_source_graph():
    """Test graph creation for voltage sources with polarity"""
    parser = ProtoCircuitParser()
    circuit = """
    V V1
    R R1
    (GND) -- V1(-+) -- R1 -- (out)
    """
    statements, errors = parser.parse_text(circuit)
    assert not errors

    graph, dsu = ast_to_graph(statements)
    
    # Check nodes
    assert "GND" in graph.nodes()
    assert "out" in graph.nodes()
    
    # Check source connection and polarity
    source_edges = [e for e in graph.edges(data=True) if e[2].get('component') == 'V1']
    assert len(source_edges) == 1
    assert source_edges[0][2].get('polarity') == '-+'

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
    statements, errors = parser.parse_text(circuit)
    assert not errors

    graph, dsu = ast_to_graph(statements)
    
    # Check essential nodes exist
    assert "node_g" in graph.nodes()
    assert "node_d" in graph.nodes()
    assert "GND" in graph.nodes()
    assert "VDD" in graph.nodes()
    
    # Check key connections
    rd_edges = [e for e in graph.edges(data=True) if e[2].get('component') == 'Rd']
    assert len(rd_edges) == 1
    
    # Check controlled source in parallel block
    controlled_source = [e for e in graph.edges(data=True) 
                        if e[2].get('type') == 'controlled_source']
    assert len(controlled_source) == 1
    
    # Check parallel connections share endpoints
    cgs_edges = [e for e in graph.edges(data=True) if e[2].get('component') == 'Cgs']
    assert controlled_source[0][0:2] == cgs_edges[0][0:2]  # Same endpoints

def test_graph_to_ast_conversion():
    """Test converting graph back to AST structure"""
    parser = ProtoCircuitParser()
    original_circuit = """
    R R1
    C C1
    (in) -- R1 -- (mid) -- C1 -- (GND)
    """
    statements, errors = parser.parse_text(original_circuit)
    assert not errors

    # Convert to graph
    graph, dsu = ast_to_graph(statements)
    
    # Convert back to AST
    reconstructed_ast = graph_to_structured_ast(graph, dsu)
    
    # Verify essential elements are preserved
    decls = [s for s in reconstructed_ast if s["type"] == "declaration"]
    assert len(decls) == 2  # R1 and C1
    
    series = [s for s in reconstructed_ast if s["type"] == "series_connection"]
    assert len(series) > 0
    
    # Check components are in the path
    components = []
    for s in series:
        for element in s["path"]:
            if element.get("type") == "component":
                components.append(element["name"])
    
    assert "R1" in components
    assert "C1" in components