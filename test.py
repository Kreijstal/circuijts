# -*- coding: utf-8 -*-
"""Tests for circuit parser/validator/graph utilities."""

from circuijt.parser import ProtoCircuitParser
from circuijt.validator import CircuitValidator
from circuijt.ast_utils import summarize_circuit_elements, generate_proto_from_ast
from circuijt.graph_utils import (
    ast_to_graph,
    graph_to_structured_ast,
    get_preferred_net_name_for_reconstruction,
    get_component_connectivity,
)
from circuijt.ast_converter import ast_to_flattened_ast, flattened_ast_to_regular_ast


def test_validator(parsed_statements):
    print("\n--- Testing Validator ---")
    validator = CircuitValidator(parsed_statements)
    validation_errors, _ = validator.validate()  # Ensure tuple is unpacked

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


def _parse_initial_code(initial_code: str):
    """Parse initial code to AST and handle errors."""
    print("\n1. Parsing initial code to AST_1...")
    parser = ProtoCircuitParser()
    ast_1, parser_errors = parser.parse_text(initial_code)

    if parser_errors:
        print("Parser Errors for AST_1:")
        for error in parser_errors:
            print(error)
    if not ast_1 and parser_errors:
        print("Parsing failed critically.")
        return None, None
    elif not ast_1 and not parser_errors:
        print("Parsing resulted in empty AST (no errors). Continuing cautiously.")
    else:
        print("Parsing to AST_1 successful.")

    return ast_1, parser_errors


def _validate_ast(ast_statements, ast_name: str):
    """Validate AST statements and print results."""
    print(f"\nValidating {ast_name}...")
    validator = CircuitValidator(ast_statements)
    validation_errors, _ = validator.validate()
    if validation_errors:
        print(f"Validation Errors for {ast_name}:")
        for error in validation_errors:
            print(error)
    else:
        print(f"{ast_name} validation successful.")
    return validation_errors


def _convert_ast_to_graph(ast_statements, graph_name: str):
    """Convert AST to graph and handle errors."""
    print(f"\nConverting {graph_name}...")
    try:
        graph, dsu = ast_to_graph(ast_statements)
        print(f"{graph_name} created with {len(graph.nodes())} nodes.")
        return graph, dsu
    except Exception as e:
        print(f"Error during conversion: {e}")
        return None, None


def _generate_final_code(ast_statements):
    """Generate final code from AST."""
    try:
        code = generate_proto_from_ast(ast_statements)
        print("\nFinal Code:")
        print(code)
        return code
    except Exception as e:
        print(f"Error generating code: {e}")
        return f"; Error during code generation: {e}"


def transform_and_validate_loop(initial_code: str):
    """Performs transformations and validations in sequence."""
    print("\n--- Starting Transformation Loop ---")

    # Step 1: Parse initial code
    ast_1, parser_errors = _parse_initial_code(initial_code)
    if not ast_1 and parser_errors:
        return None, None, None, None

    # Step 2: Validate initial AST
    _validate_ast(ast_1, "AST_1")

    # Step 3: Convert to graph
    graph_1, dsu_1 = _convert_ast_to_graph(ast_1, "Graph_1")
    if not graph_1:
        return ast_1, None, None, None

    # Step 4: Reconstruct AST from graph
    ast_2 = graph_to_structured_ast(graph_1, dsu_1)
    print(f"\nAST_2 reconstructed with {len(ast_2 or [])} statements.")

    # Step 5: Validate reconstructed AST
    if ast_2:
        _validate_ast(ast_2, "AST_2")

    # Step 6: Generate final code
    code_final = _generate_final_code(ast_2) if ast_2 else "; No AST to generate code"

    print("\n--- Transformation Loop Finished ---")
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
    return nmos_instance_name  # Fallback to full name if no common pattern matched


def generate_nmos_small_signal_model_ast(nmos_original_instance_name: str, external_nets_map: dict):
    """Generates AST statements for NMOS small-signal model."""
    id_suffix = get_nmos_id_suffix(nmos_original_instance_name)

    # Updated naming convention
    rds_model_instance_name = f"rds_{id_suffix}"
    gm_expr = f"gm_{id_suffix}*VGS_{id_suffix}"
    gmb_expr = f"gmB_{id_suffix}*VBS_{id_suffix}"

    model_ast_statements = []

    # 1. Declaration for rds_ component
    model_ast_statements.append(
        {
            "type": "declaration",
            "component_type": "R",
            "instance_name": rds_model_instance_name,
            "line": 0,  # Placeholder line number
        }
    )

    # 2. Connection "(Net_B):(GND)" - using original external net for B
    original_b_net = external_nets_map.get("B")
    if original_b_net:
        model_ast_statements.append(
            {
                "type": "direct_assignment",
                "source_node": original_b_net,  # The original net connected to B
                "target_node": "GND",  # Body is typically grounded in SS model
                "line": 0,
            }
        )
    else:
        print(
            f"Note: Terminal 'B' of {nmos_original_instance_name} was not found in external_nets_map during model generation."
        )

    # 3. Series connection for D-S path, using original external nets for D and S
    original_d_net = external_nets_map.get("D")
    original_s_net = external_nets_map.get("S")

    if original_d_net and original_s_net:
        parallel_elements_ds_path = [
            {"type": "controlled_source", "expression": gm_expr, "direction": "->"},
            {"type": "controlled_source", "expression": gmb_expr, "direction": "->"},
            {"type": "component", "name": rds_model_instance_name},
        ]
        model_ast_statements.append(
            {
                "type": "series_connection",
                "path": [
                    {
                        "type": "node",
                        "name": original_d_net,
                    },  # Connects to original Drain net
                    {"type": "parallel_block", "elements": parallel_elements_ds_path},
                    {
                        "type": "node",
                        "name": original_s_net,
                    },  # Connects to original Source net
                ],
                "line": 0,
            }
        )
    else:
        missing_terms = []
        if not original_d_net:
            missing_terms.append("'D'")
        if not original_s_net:
            missing_terms.append("'S'")
        print(
            f"Warning: Small-signal model D-S path for {nmos_original_instance_name} "
            f"cannot be fully generated. Missing external net(s) for terminal(s): "
            f"{', '.join(missing_terms)}."
        )

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


def _get_nmos_connections(initial_graph, initial_dsu, nmos_to_replace):
    """Analyze and return NMOS terminal connections."""
    if nmos_to_replace not in initial_graph:
        print(f"Error: Instance '{nmos_to_replace}' not found in graph.")
        return None

    node_data = initial_graph.nodes[nmos_to_replace]
    if not (node_data.get("node_kind") == "component_instance" and node_data.get("instance_type") == "Nmos"):
        print(f"Error: '{nmos_to_replace}' is not an NMOS instance.")
        return None

    print(f"Found NMOS instance '{nmos_to_replace}' with connections:")
    term_to_canonical_net_map, _ = get_component_connectivity(initial_graph, nmos_to_replace)

    connections = {}
    for terminal, canonical_net_name in term_to_canonical_net_map.items():
        preferred_net_name = get_preferred_net_name_for_reconstruction(
            canonical_net_name, initial_dsu, allow_implicit_if_only_option=True
        )
        connections[terminal] = preferred_net_name
        print(f"  Terminal {terminal} -> Net '{preferred_net_name}'")

    return connections


def _validate_nmos_connections(connections, nmos_to_replace):
    """Validate NMOS has required connections for model."""
    required_terminals = {"D", "S", "B"}
    if not required_terminals.issubset(connections.keys()):
        missing = required_terminals - connections.keys()
        print(f"Error: Missing connections for terminals: {missing}")
        return False
    return True


def _combine_asts(initial_ast, ss_model_ast, nmos_to_replace):
    """Combine initial AST with small-signal model AST."""
    combined = []
    processed_decls = set()

    # Add declarations from initial AST (excluding replaced NMOS)
    for stmt in initial_ast:
        if stmt["type"] == "declaration" and stmt["instance_name"] != nmos_to_replace:
            combined.append(stmt)
            processed_decls.add(stmt["instance_name"])

    # Add new declarations from model AST
    for stmt in ss_model_ast:
        if stmt["type"] == "declaration" and stmt["instance_name"] not in processed_decls:
            combined.append(stmt)
            processed_decls.add(stmt["instance_name"])

    # Add non-declaration statements with filtering
    for stmt in initial_ast:
        if stmt["type"] != "declaration":
            if _should_skip_statement(stmt, nmos_to_replace):
                print(f"Skipping statement related to {nmos_to_replace}")
                continue
            combined.append(stmt)

    # Add model connections
    for stmt in ss_model_ast:
        if stmt["type"] != "declaration":
            combined.append(stmt)

    return combined


def _should_skip_statement(stmt, nmos_to_replace):
    """Determine if statement should be skipped due to NMOS replacement."""
    if stmt["type"] == "component_connection_block" and stmt["component_name"] == nmos_to_replace:
        return True
    if stmt["type"] == "direct_assignment":
        return stmt.get("source_node", "").startswith(nmos_to_replace + ".") or stmt.get("target_node", "").startswith(
            nmos_to_replace + "."
        )
    if stmt["type"] == "series_connection":
        return any(
            item.get("name", "") == nmos_to_replace or item.get("name", "").startswith(nmos_to_replace + ".")
            for item in stmt.get("path", [])
        )
    return False


def _generate_and_validate_flattened_ast(combined_ast, transformed_dsu):
    """Generate and validate flattened AST."""
    flattened_ast = ast_to_flattened_ast(combined_ast, transformed_dsu)
    if not flattened_ast:
        print("No flattened AST generated.")
        return None

    print("\nValidating Flattened AST:")
    validator = CircuitValidator(flattened_ast)
    errors, _ = validator.validate()
    if errors:
        print("Validation Errors:")
        for error in errors:
            print(error)
    else:
        print("Validation successful.")

    return flattened_ast


def perform_nmos_ss_transformation_and_flatten(initial_code: str, nmos_to_replace: str):
    """Perform NMOS small-signal transformation and output flattened AST."""
    print(f"\n--- NMOS Transformation for '{nmos_to_replace}' ---")
    print_transformation_rule_description(nmos_to_replace)

    # Parse initial circuit
    parser = ProtoCircuitParser()
    initial_ast, parse_errors = parser.parse_text(initial_code)
    if parse_errors or not initial_ast:
        print("Parsing failed." if parse_errors else "Empty AST from parsing.")
        return

    # Build initial graph and get NMOS connections
    initial_graph, initial_dsu = ast_to_graph(initial_ast)
    connections = _get_nmos_connections(initial_graph, initial_dsu, nmos_to_replace)
    if not connections or not _validate_nmos_connections(connections, nmos_to_replace):
        return

    # Generate small-signal model AST
    ss_model_ast = generate_nmos_small_signal_model_ast(nmos_to_replace, connections)
    if not ss_model_ast:
        print("Failed to generate small-signal model.")
        return

    # Combine ASTs
    combined_ast = _combine_asts(initial_ast, ss_model_ast, nmos_to_replace)
    if not combined_ast:
        print("Failed to combine ASTs.")
        return

    # Generate transformed graph
    transformed_graph, transformed_dsu = ast_to_graph(combined_ast)
    if not transformed_graph:
        print("Failed to generate transformed graph.")
        return

    # Generate and validate flattened AST
    flattened_ast = _generate_and_validate_flattened_ast(combined_ast, transformed_dsu)
    if not flattened_ast:
        return

    # Generate final code
    regular_ast = flattened_ast_to_regular_ast(flattened_ast)
    if regular_ast:
        print("\nFinal Circuit Code:")
        print(generate_proto_from_ast(regular_ast))


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
