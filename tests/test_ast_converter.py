import pytest
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
    decls = [s for s in flattened if s['type'] == 'declaration']
    assert len(decls) == 2
    assert any(d['instance_name'] == 'R1' and d['component_type'] == 'R' for d in decls)
    assert any(d['instance_name'] == 'C1' and d['component_type'] == 'C' for d in decls)

    # Check pin connections
    pins = [s for s in flattened if s['type'] == 'pin_connection']
    assert len(pins) == 4  # R1: 2 pins, C1: 2 pins

    # Verify R1 connections
    r1_pins = [p for p in pins if p['component_instance'] == 'R1']
    assert len(r1_pins) == 2
    r1_nets = {p['net'] for p in r1_pins}
    assert 'in' in r1_nets or any(s['canonical_net'] == 'in' for s in flattened if s['type'] == 'net_alias')
    assert 'mid' in r1_nets or any(s['canonical_net'] == 'mid' for s in flattened if s['type'] == 'net_alias')

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
    aliases = [s for s in flattened if s['type'] == 'net_alias']
    
    # Should find node1:VDD alias
    found_alias = False
    for alias in aliases:
        if (alias['source_net'] == 'node1' and alias['canonical_net'] == 'VDD') or \
           (alias['source_net'] == 'VDD' and alias['canonical_net'] == 'node1'):
            found_alias = True
            break
    assert found_alias

def test_roundtrip_conversion():
    parser = ProtoCircuitParser()
    circuit = """
    R R1
    C C1
    (VDD) -- [ R1 || C1 ] -- (GND)
    """
    original_statements, errors = parser.parse_text(circuit)
    assert not errors

    # Convert to flattened form
    _, dsu = ast_to_graph(original_statements)
    flattened = ast_to_flattened_ast(original_statements, dsu)
    
    # Convert back to regular
    reconstructed = flattened_ast_to_regular_ast(flattened)
    
    # Check essential elements preserved
    # Both ASTs should have same declarations
    orig_decls = {(s['instance_name'], s['component_type']) 
                 for s in original_statements if s['type'] == 'declaration'}
    recon_decls = {(s['instance_name'], s['component_type']) 
                  for s in reconstructed if s['type'] == 'declaration'}
    assert orig_decls == recon_decls

    # Check parallel structure preserved (might be in different format but components should be parallel)
    parallel_found = False
    for stmt in reconstructed:
        if stmt['type'] == 'parallel_connection':
            components = {e['name'] for e in stmt['elements'] if e['type'] == 'component'}
            if components == {'R1', 'C1'}:
                parallel_found = True
                break
    assert parallel_found

def test_internal_components_handling():
    parser = ProtoCircuitParser()
    circuit = """
    V V1
    R R1
    (GND) -- V1(-+) -- R1 -- (out)  ; Creates internal voltage source
    """
    statements, errors = parser.parse_text(circuit)
    assert not errors

    _, dsu = ast_to_graph(statements)
    flattened = ast_to_flattened_ast(statements, dsu)
    
    # Check internal voltage source connections are preserved
    internal_pins = [p for p in flattened if p['type'] == 'pin_connection' 
                    and p['component_instance'].startswith('_internal_')]
    assert len(internal_pins) > 0  # Should have some internal component connections

def test_terminal_preservation():
    parser = ProtoCircuitParser()
    circuit = """
    Nmos M1
    M1 { G:(in), S:(GND), D:(out), B:(GND) }
    """
    statements, errors = parser.parse_text(circuit)
    assert not errors

    _, dsu = ast_to_graph(statements)
    flattened = ast_to_flattened_ast(statements, dsu)
    
    # Check all MOSFET terminals preserved
    m1_pins = [p for p in flattened if p['type'] == 'pin_connection' 
               and p['component_instance'] == 'M1']
    
    terminals = {p['terminal'] for p in m1_pins}
    assert terminals == {'G', 'S', 'D', 'B'}
    
    # Check correct nets
    pin_nets = {p['terminal']: p['net'] for p in m1_pins}
    assert pin_nets['G'] == 'in' or any(a['canonical_net'] == 'in' 
           for a in flattened if a['type'] == 'net_alias' and a['source_net'] == pin_nets['G'])
    assert pin_nets['S'] == 'GND'
    assert pin_nets['B'] == 'GND'