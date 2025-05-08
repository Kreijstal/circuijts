# -*- coding: utf-8 -*-
"""Tests for circuit parser/validator/graph utilities."""

from circuijt.parser import ProtoCircuitParser
from circuijt.validator import CircuitValidator
from circuijt.ast_utils import summarize_circuit_elements, generate_proto_from_ast
from circuijt.graph_utils import ast_to_graph, graph_to_structured_ast, DSU, get_preferred_net_name_for_reconstruction, get_component_connectivity
from circuijt.ast_converter import ast_to_flattened_ast, flattened_ast_to_regular_ast

def test_validator(parsed_statements):
    print("\n--- Testing Validator ---")
    validator = CircuitValidator(parsed_statements)
    validation_errors, _ = validator.validate() # Ensure tuple is unpacked
    
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
    validation_errors_ast1, _ = validator_ast1.validate() # Unpack tuple
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
        validation_errors_ast2, _ = validator_ast2.validate() # Unpack tuple
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
    """Extracts suffix from NMOS instance name (e.g., 'm1' from 'M1', 'm25ext' from 'M25ext')."""
    if not nmos_instance_name:
        return "default_id"
    # Handles M1, M12 -> m1, m12 (preserve 'm' prefix)
    if nmos_instance_name.startswith("M") and len(nmos_instance_name) > 1:
        return "m" + nmos_instance_name[1:]
    # Handles other alpha-prefixed names (Tinput -> tinput)
    if nmos_instance_name[0].isalpha() and len(nmos_instance_name) > 1:
        return nmos_instance_name[0].lower() + nmos_instance_name[1:]
    return nmos_instance_name # Fallback to full name if no common pattern matched

def generate_nmos_small_signal_model_ast(nmos_original_instance_name: str, external_nets_map: dict):
    """Generates AST statements for NMOS small-signal model."""
    id_suffix = get_nmos_id_suffix(nmos_original_instance_name)

    # Updated naming convention
    rds_model_instance_name = f"rds_{id_suffix}"
    gm_expr = f"gm_{id_suffix}*VGS_{id_suffix}"
    gmb_expr = f"gmB_{id_suffix}*VBS_{id_suffix}"

    model_ast_statements = []

    # 1. Declaration for rds_ component
    model_ast_statements.append({
        'type': 'declaration', 
        'component_type': 'R',
        'instance_name': rds_model_instance_name,
        'line': 0 # Placeholder line number
    })

    # 2. Connection "(Net_B):(GND)" - using original external net for B
    original_b_net = external_nets_map.get('B')
    if original_b_net:
        model_ast_statements.append({
            'type': 'direct_assignment',
            'source_node': original_b_net, # The original net connected to B
            'target_node': 'GND', # Body is typically grounded in SS model
            'line': 0
        })
    else:
        print(f"Note: Terminal 'B' of {nmos_original_instance_name} was not found in external_nets_map during model generation.")

    # 3. Series connection for D-S path, using original external nets for D and S
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
                {'type': 'node', 'name': original_d_net}, # Connects to original Drain net
                {'type': 'parallel_block', 'elements': parallel_elements_ds_path},
                {'type': 'node', 'name': original_s_net}  # Connects to original Source net
            ],
            'line': 0
        })
    else:
        missing_terms = []
        if not original_d_net: missing_terms.append("'D'")
        if not original_s_net: missing_terms.append("'S'")
        print(f"Warning: Small-signal model D-S path for {nmos_original_instance_name} cannot be fully generated. Missing external net(s) for terminal(s): {', '.join(missing_terms)}.")

    return model_ast_statements

def print_transformation_rule_description(nmos_original_instance_name="M1"):
    """Prints description of the transformation rule with updated naming."""
    id_suffix = get_nmos_id_suffix(nmos_original_instance_name)
    
    # Updated naming convention
    rds_name = f"rds_{id_suffix}"
    gm_expr = f"gm_{id_suffix}*VGS_{id_suffix}"
    gmb_expr = f"gmB_{id_suffix}*VBS_{id_suffix}"

    rule_description = f"""
Rule: NMOS Small-Signal Model Transformation 

[STRUCTURED-DATA]
component_type=Nmos
original_instance={nmos_original_instance_name}
model_instance=rds_{id_suffix}
control_voltages=VGS_{id_suffix},VBS_{id_suffix}
voltage_defs=VGS_{id_suffix}=V(gate_net)-V(source_net),VBS_{id_suffix}=V(bulk_net)-V(source_net)
connections=bulk_net:GND,drain_net:[{gm_expr}||{gmb_expr}||{rds_name}],source_net
[/STRUCTURED-DATA]
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
    print(f"\n2. Building Graph_initial from AST_initial to find connections for '{nmos_to_replace}'...")
    initial_graph, initial_dsu = ast_to_graph(initial_ast)
    assert initial_graph is not None, "Initial graph should not be None."
    print(f"  Graph_initial: {len(initial_graph.nodes())} nodes, {len(initial_graph.edges())} edges.")
    print(f"  Graph_initial nodes: {list(initial_graph.nodes(data=True))}") 
    print(f"  DSU_initial (first 5 items): {dict(list(initial_dsu.parent.items())[:5])}")

    nmos_external_connections = {} # Stores terminal_name -> preferred_external_net_name
    if nmos_to_replace in initial_graph:
        node_data = initial_graph.nodes[nmos_to_replace]
        if node_data.get('node_kind') == 'component_instance' and node_data.get('instance_type') == 'Nmos':
            print(f"  Found NMOS instance '{nmos_to_replace}' with connections to canonical nets:")
            # Use get_component_connectivity to correctly map terminals to their canonical nets
            # Then use get_preferred_net_name_for_reconstruction for those canonical nets
            
            term_to_canonical_net_map, _ = get_component_connectivity(initial_graph, nmos_to_replace)

            for terminal, canonical_net_name in term_to_canonical_net_map.items():
                preferred_net_name = get_preferred_net_name_for_reconstruction(
                    canonical_net_name, initial_dsu, allow_implicit_if_only_option=True)
                nmos_external_connections[terminal] = preferred_net_name
                print(f"    Terminal {terminal} -> Canonical Net '{canonical_net_name}' (Preferred for model: '{preferred_net_name}')")

        else:
            print(f"Error: '{nmos_to_replace}' is not an NMOS instance in the graph.")
            return
    else:
        print(f"Error: Instance '{nmos_to_replace}' not found in the graph.")
        return
    
    print(f"\nOriginal connections for {nmos_to_replace} (using preferred net names for model generation): {nmos_external_connections}")
    # Required terminals for the current model structure: D, S, B. G is implicit via control voltages.
    required_terminals_for_model = {'D', 'S', 'B'}
    if not required_terminals_for_model.issubset(nmos_external_connections.keys()):
        missing = required_terminals_for_model - nmos_external_connections.keys()
        print(f"Error: Cannot generate model. Missing external connections for terminals: {missing} of {nmos_to_replace}.")
        return


    # Generate AST for small-signal model
    print("\n3. Generating AST_ss_model (Small-Signal Model parts)...")
    ss_model_ast_stmts = generate_nmos_small_signal_model_ast(nmos_to_replace, nmos_external_connections)
    print("AST_ss_model:")
    for i, stmt in enumerate(ss_model_ast_stmts): print(f"  [{i:02d}] {stmt}")
    assert ss_model_ast_stmts, "Small-signal model AST should not be empty."

    # Combine ASTs
    print("\n4. Combining AST_initial (filtered) and AST_ss_model into AST_combined...")
    combined_ast_statements = []
    processed_declarations = set()
    # Add declarations from initial_ast, skipping the one for nmos_to_replace
    for stmt in initial_ast:
        if stmt['type'] == 'declaration':
            if stmt['instance_name'] == nmos_to_replace: continue
            combined_ast_statements.append(stmt)
            processed_declarations.add(stmt['instance_name'])

    # Add new declarations from ss_model_ast_stmts (e.g., for rds_X)
    for ss_stmt in ss_model_ast_stmts:
        if ss_stmt['type'] == 'declaration':
            if ss_stmt['instance_name'] not in processed_declarations:
                combined_ast_statements.append(ss_stmt)
                processed_declarations.add(ss_stmt['instance_name'])
    
    # Add non-declaration statements from initial_ast, filtering out those related to nmos_to_replace
    for stmt in initial_ast:
        if stmt['type'] != 'declaration':
            # Filter out component_connection_block for the replaced NMOS
            if stmt['type'] == 'component_connection_block' and stmt['component_name'] == nmos_to_replace:
                print(f"  Skipping original component_connection_block for {nmos_to_replace}: {stmt}")
                continue
            
            # Filter out direct_assignments involving terminals of the replaced NMOS
            # The model re-establishes connections to original external nets.
            # Retaining these might create conflicts or redundant connections.
            if stmt['type'] == 'direct_assignment':
                is_related_direct_assign = False
                if stmt.get('source_node','').startswith(nmos_to_replace + ".") or \
                   stmt.get('target_node','').startswith(nmos_to_replace + "."):
                   is_related_direct_assign = True
                if is_related_direct_assign:
                    print(f"  Skipping original direct assignment stmt related to {nmos_to_replace}: {stmt}")
                    continue
            
            # Filter out series_connections where nmos_to_replace is a component in the path,
            # or where its terminals are explicit nodes in the path.
            # The model connects to original external nets; path segments through the device itself are replaced.
            if stmt['type'] == 'series_connection':
                is_related_series = False
                for item in stmt.get('path', []):
                    if item.get('type') == 'component' and item.get('name') == nmos_to_replace:
                        is_related_series = True; break
                    if item.get('type') == 'node' and item.get('name', '').startswith(nmos_to_replace + "."):
                        is_related_series = True; break
                if is_related_series:
                    print(f"  Skipping original series stmt involving {nmos_to_replace} or its terminals: {stmt}")
                    continue
            
            combined_ast_statements.append(stmt)

    # Add new non-declaration statements from ss_model_ast_stmts (the connections)
    for ss_stmt in ss_model_ast_stmts:
        if ss_stmt['type'] != 'declaration':
            combined_ast_statements.append(ss_stmt)
    
    print("AST_combined (Transformed):")
    for i, stmt in enumerate(combined_ast_statements): print(f"  [{i:02d}] {stmt}")
    assert combined_ast_statements, "Combined AST should not be empty."

    # Generate graph and DSU from the combined (transformed) AST
    print("\n5. Building Graph_transformed and DSU_transformed from AST_combined...")
    final_transformed_graph, final_transformed_dsu = ast_to_graph(combined_ast_statements)
    assert final_transformed_graph is not None, "Final transformed graph should not be None."
    print(f"  Graph_transformed: {len(final_transformed_graph.nodes())} nodes, {len(final_transformed_graph.edges())} edges.")
    print(f"  Graph_transformed nodes: {list(final_transformed_graph.nodes(data=True))}") 
    print(f"  DSU_transformed (first 5 items): {dict(list(final_transformed_dsu.parent.items())[:5])}")

    # Generate final flattened AST using the DSU from the transformed circuit
    print("\n6. Generating AST_flattened from AST_combined and DSU_transformed...")
    final_flattened_ast = ast_to_flattened_ast(combined_ast_statements, final_transformed_dsu)
    assert final_flattened_ast is not None, "Final flattened AST should not be None."

    print("\n--- Resulting Flattened AST ---")
    if not final_flattened_ast:
        print("No flattened AST generated.")
    else:
        for i, stmt in enumerate(final_flattened_ast):
            print(f"[{i:02d}] {stmt}")
        
        # Validate the final flattened AST
        print("\n--- Validating Final Flattened AST ---")
        validator = CircuitValidator(final_flattened_ast)
        validation_errors, _ = validator.validate() # Unpack the tuple
        if validation_errors:
            print("Validation Errors in Flattened AST:")
            for error in validation_errors:
                print(error)
        else:
            print("Flattened AST validation successful.")
        
        # Convert flattened AST back to a regular AST for code generation
        print("\n--- Reconstructing Regular AST from Flattened AST for Code Generation ---")
        regular_ast_from_flattened = flattened_ast_to_regular_ast(final_flattened_ast)

        if not regular_ast_from_flattened:
            print("Failed to reconstruct regular AST from flattened AST.")
            reconstructed_code = "; Could not reconstruct regular AST from flattened AST."
        else:
            print("\n--- Reconstructed Circuit Code (from Regular AST derived from Flattened AST) ---")
            reconstructed_code = generate_proto_from_ast(regular_ast_from_flattened)
        
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
    (source_m1) : (GND) ; Alias source_m1 to GND
    (bulk_m1) : (GND)   ; Alias bulk_m1 to GND
    
    (node_x) -- Rin -- (gate_m2) ; Another connection for gate_m2
    (drain_m2) -- (VDD)
    """
    perform_nmos_ss_transformation_and_flatten(test_circuit_for_nmos_replacement, "M1")
    
    print("\n\n===================================\nNow trying with M25ext\n===================================")
    perform_nmos_ss_transformation_and_flatten(test_circuit_for_nmos_replacement, "M25ext")
