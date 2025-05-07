# -*- coding: utf-8 -*-
"""Tests for circuit parser/validator/graph utilities."""

from circuijt.parser import ProtoCircuitParser
from circuijt.validator import CircuitValidator
from circuijt.ast_utils import summarize_circuit_elements, generate_proto_from_ast
from circuijt.graph_utils import ast_to_graph, graph_to_structured_ast, DSU, get_preferred_net_name_for_reconstruction
from circuijt.ast_converter import ast_to_flattened_ast

def test_validator(parsed_statements):
    print("\n--- Testing Validator ---")
    validator = CircuitValidator(parsed_statements)
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

def transform_and_validate_loop(initial_code: str):
    """Performs a loop of transformations and validations."""
    print("\n--- Starting Transformation and Validation Loop ---")

    # Step 1: Code to AST_1 (Parse)
    print("\n1. Parsing initial code to AST_1...")
    parser = ProtoCircuitParser()
    ast_1, parser_errors = parser.parse_text(initial_code)
    
    if parser_errors:
        print("Parser Errors for AST_1:")
        for error in parser_errors:
            print(error)
    if not ast_1 and parser_errors: 
        print("Parsing failed critically. Aborting loop.")
        return None, None, None, None
    elif not ast_1 and not parser_errors: 
        print("Parsing resulted in an empty AST (no errors reported). Continuing cautiously.")
    else:
        print("Parsing to AST_1 successful.")
    
    assert ast_1 is not None, "AST_1 should not be None after parsing."
    if not ast_1 and not parser_errors: 
        print("Warning: AST_1 is empty but no parser errors reported.")
    elif not ast_1 and parser_errors:
        print("Critical: AST_1 is empty and parser errors were reported.")

    print("AST_1 (Initial):")
    for stmt_idx, stmt in enumerate(ast_1): print(f"  AST_1 Stmt {stmt_idx}: {stmt}")

    # Step 2: Validate AST_1
    print("\n2. Validating AST_1...")
    validator_ast1 = CircuitValidator(ast_1)
    validation_errors_ast1 = validator_ast1.validate()
    if validation_errors_ast1:
        print("Validation Errors for AST_1:")
        for error in validation_errors_ast1:
            print(error)
    else:
        print("AST_1 validation successful.")

    # Step 3: AST_1 to Graph_1
    print("\n3. Converting AST_1 to Graph_1...")
    graph_1 = None
    dsu_1 = None
    try:
        graph_1, dsu_1 = ast_to_graph(ast_1)
        print(f"Graph_1 created with {len(graph_1.nodes())} nodes and {len(graph_1.edges())} edges.")
        assert graph_1 is not None, "Graph_1 should not be None after ast_to_graph."
        assert len(graph_1.nodes()) > 0 if ast_1 else True, "Graph_1 should have nodes if AST_1 was not empty."
    except Exception as e:
        print(f"Error during AST_1 to Graph_1 conversion: {e}")
        print("Aborting loop due to graph conversion failure.")
        return ast_1, None, None, None
    
    print("Graph_1 nodes:", list(graph_1.nodes(data=True)))
    print("DSU_1 structure (first 5 items):", dict(list(dsu_1.parent.items())[:5]) if dsu_1 else "No DSU object")

    # Step 4: Graph_1 to AST_2
    print("\n4. Converting Graph_1 to AST_2...")
    ast_2 = None
    try:
        ast_2 = graph_to_structured_ast(graph_1, dsu_1)
        print(f"AST_2 reconstructed with {len(ast_2)} statements.")
        assert ast_2 is not None, "AST_2 should not be None after graph_to_structured_ast."
    except Exception as e:
        print(f"Error during Graph_1 to AST_2 conversion: {e}")
        print("Continuing loop despite AST reconstruction error to allow further steps if possible.")
        
    print("AST_2 (Reconstructed from graph):")
    if ast_2:
        for stmt_idx, stmt in enumerate(ast_2): print(f"  AST_2 Stmt {stmt_idx}: {stmt}")
    else:
        print("  AST_2 is None or empty.")

    # Step 5: Validate AST_2
    print("\n5. Validating AST_2...")
    if not ast_2:
        print("AST_2 is empty or None, skipping validation.")
    else:
        validator_ast2 = CircuitValidator(ast_2)
        validation_errors_ast2 = validator_ast2.validate()
        if validation_errors_ast2:
            print("Validation Errors for AST_2:")
            for error in validation_errors_ast2:
                print(error)
        else:
            print("AST_2 validation successful.")

    # Step 6: AST_2 to Code_final
    print("\n6. Generating final code from AST_2...")
    code_final = ""
    if not ast_2:
        print("AST_2 is empty or None, cannot generate code.")
        code_final = "; AST_2 was empty or None, no code generated."
    else:
        try:
            code_final = generate_proto_from_ast(ast_2)
            print("Final Code (from AST_2):")
            print(code_final)
        except Exception as e:
            print(f"Error generating code from AST_2: {e}")
            code_final = f"; Error during code generation from AST_2: {e}"

    print("\n--- Transformation and Validation Loop Finished ---")
    return ast_1, graph_1, ast_2, code_final

# --- NMOS Small-Signal Model Transformation Logic ---

def get_nmos_id_suffix(nmos_instance_name: str) -> str:
    """Extracts suffix from NMOS instance name (e.g., '1' from 'M1')."""
    if not nmos_instance_name:
        return "default_id"
    if nmos_instance_name.startswith("M") and len(nmos_instance_name) > 1 and nmos_instance_name[1:].isdigit():
        return nmos_instance_name[1:]
    if nmos_instance_name[0].isalpha() and len(nmos_instance_name) > 1:
        return nmos_instance_name[1:]
    return nmos_instance_name

def generate_nmos_small_signal_model_ast(nmos_original_instance_name: str, external_nets_map: dict):
    """Generates AST statements for NMOS small-signal model."""
    id_suffix = get_nmos_id_suffix(nmos_original_instance_name)

    rds_model_instance_name = f"rDS{id_suffix}"
    gm_expr = f"gm{id_suffix}*VGS"
    gmb_expr = f"gmB{id_suffix}*VBS"

    model_ast_statements = []

    # 1. Declaration for rDS component
    model_ast_statements.append({
        'type': 'declaration',
        'component_type': 'R',
        'instance_name': rds_model_instance_name,
        'line': 0
    })

    # 2. Connection "(B):(GND)"
    original_b_net = external_nets_map.get('B')
    if original_b_net:
        model_ast_statements.append({
            'type': 'direct_assignment',
            'source_node': original_b_net,
            'target_node': 'GND',
            'line': 0
        })
    else:
        print(f"Note: Terminal 'B' of {nmos_original_instance_name} was not found in external_nets_map.")

    # 3. Series connection for D-S path
    original_d_net = external_nets_map.get('D')
    original_s_net = external_nets_map.get('S')

    if original_d_net and original_s_net:
        parallel_elements_ds_path = [
            {'type': 'controlled_source', 'expression': gm_expr, 'direction': '->'},
            {'type': 'controlled_source', 'expression': gmb_expr, 'direction': '->'},
            {'type': 'component', 'name': rds_model_instance_name}
        ]
        model_ast_statements.append({
            'type': 'series_connection',
            'path': [
                {'type': 'node', 'name': original_d_net},
                {'type': 'parallel_block', 'elements': parallel_elements_ds_path},
                {'type': 'node', 'name': original_s_net}
            ],
            'line': 0
        })
    else:
        missing_terms = []
        if not original_d_net: missing_terms.append("'D'")
        if not original_s_net: missing_terms.append("'S'")
        print(f"Warning: Terminal(s) {', '.join(missing_terms)} of {nmos_original_instance_name} not found.")

    return model_ast_statements

def print_transformation_rule_description(nmos_original_instance_name="M1"):
    """Prints description of the transformation rule."""
    id_suffix = get_nmos_id_suffix(nmos_original_instance_name)
    rds_name = f"rDS{id_suffix}"
    gm_expr = f"gm{id_suffix}*VGS"
    gmb_expr = f"gmB{id_suffix}*VBS"

    rule_description = f"""
Transformation Rule for NMOS instance (e.g., '{nmos_original_instance_name}'):
The NMOS instance '{nmos_original_instance_name}' connected to external nets (Net_G), (Net_D), (Net_S), (Net_B)
will be replaced by the following small-signal model structure:

1. Declare internal resistor:
   R {rds_name}

2. Define model connections:
   (Net_B) : (GND)
   (Net_D) -- [ {gm_expr} (->) || {gmb_expr} (->) || {rds_name} ] -- (Net_S)
"""
    print(rule_description)

def perform_nmos_ss_transformation_and_flatten(initial_circuit_code: str, nmos_to_replace: str):
    """Performs NMOS small-signal transformation and outputs flattened AST."""
    print(f"\n--- Performing NMOS Small-Signal Transformation for '{nmos_to_replace}' ---")
    parser = ProtoCircuitParser()

    print_transformation_rule_description(nmos_to_replace)

    # Parse initial circuit
    initial_ast, parse_errors = parser.parse_text(initial_circuit_code)
    if parse_errors:
        print("Initial parsing errors:", parse_errors)
        return
    if not initial_ast:
        print("Initial parsing yielded no AST.")
        return

    # Get original NMOS connections
    initial_graph, initial_dsu = ast_to_graph(initial_ast)
    nmos_external_connections = {}
    if nmos_to_replace in initial_graph:
        node_data = initial_graph.nodes[nmos_to_replace]
        if node_data.get('node_kind') == 'component_instance' and node_data.get('instance_type') == 'Nmos':
            for u, v, edge_data in initial_graph.edges(nmos_to_replace, data=True):
                terminal = edge_data.get('terminal')
                net_node_canonical = v if u == nmos_to_replace else u
                if initial_graph.nodes[net_node_canonical].get('node_kind') == 'electrical_net':
                    preferred_net_name = get_preferred_net_name_for_reconstruction(
                        net_node_canonical, initial_dsu, allow_implicit_if_only_option=True)
                    nmos_external_connections[terminal] = preferred_net_name
        else:
            print(f"Error: '{nmos_to_replace}' is not an NMOS instance.")
            return
    else:
        print(f"Error: Instance '{nmos_to_replace}' not found.")
        return
    
    print(f"\nOriginal connections for {nmos_to_replace}: {nmos_external_connections}")

    # Generate AST for small-signal model
    ss_model_ast_stmts = generate_nmos_small_signal_model_ast(nmos_to_replace, nmos_external_connections)

    # Combine ASTs
    combined_ast_statements = []
    
    # Add declarations from original (excluding replaced NMOS) and from SS model
    for stmt in initial_ast:
        if stmt['type'] == 'declaration':
            if stmt['instance_name'] == nmos_to_replace: continue
            combined_ast_statements.append(stmt)
    for ss_stmt in ss_model_ast_stmts:
        if ss_stmt['type'] == 'declaration': combined_ast_statements.append(ss_stmt)
    
    # Add connection statements from original (excluding replaced NMOS) and from SS model
    for stmt in initial_ast:
        if stmt['type'] != 'declaration':
            if stmt['type'] == 'component_connection_block' and stmt['component_name'] == nmos_to_replace: continue
            combined_ast_statements.append(stmt)
    for ss_stmt in ss_model_ast_stmts:
        if ss_stmt['type'] != 'declaration': combined_ast_statements.append(ss_stmt)

    # Generate final flattened AST
    final_graph_modified, final_dsu_modified = ast_to_graph(combined_ast_statements)
    final_flattened_ast = ast_to_flattened_ast(combined_ast_statements, final_dsu_modified)

    print("\n--- Resulting Flattened AST ---")
    if not final_flattened_ast:
        print("No flattened AST generated.")
    else:
        for i, stmt in enumerate(final_flattened_ast):
            print(f"[{i:02d}] {stmt}")
        
        # Validate the final flattened AST
        print("\n--- Validating Final Flattened AST ---")
        validator = CircuitValidator(final_flattened_ast)
        validation_errors = validator.validate()
        if validation_errors:
            print("Validation Errors in Flattened AST:")
            for error in validation_errors:
                print(error)
        else:
            print("Flattened AST validation successful.")
        
        # Print reconstructed code for verification
        print("\n--- Reconstructed Circuit from Flattened AST ---")
        reconstructed_code = generate_proto_from_ast(final_flattened_ast)
        print(reconstructed_code)

# Main execution block
if __name__ == "__main__":
    test_circuit_for_nmos_replacement = """
    ; Example circuit with NMOS M1 and M25ext
    Nmos M1
    Nmos M25ext
    R Rin
    R Rload
    V Vin_src
    V Vsupply

    M1 { G:(gate_m1), D:(drain_m1), S:(source_m1), B:(bulk_m1) }
    M25ext { G:(gate_m2), D:(drain_m2), S:(GND), B:(GND) }

    (GND) -- Vin_src (-+) -- Rin -- (gate_m1)
    (VDD) -- Vsupply (+-) -- (GND)
    (VDD) -- Rload -- (drain_m1)
    (source_m1) : (GND)
    (bulk_m1) : (GND)
    
    (gate_m2) -- Rload -- (drain_m2)
    (drain_m2) -- (VDD)
    """
    perform_nmos_ss_transformation_and_flatten(test_circuit_for_nmos_replacement, "M1")
    
    print("\n\n===================================\nNow trying with M25ext\n===================================")
    perform_nmos_ss_transformation_and_flatten(test_circuit_for_nmos_replacement, "M25ext")
