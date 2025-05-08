#!/usr/bin/env python3
"""
CLI tool to generate small signal models from circuit files with rule annotations.
Creates output in a 'small_signal_models' subdirectory.
"""

import os
import argparse
import pprint  # Added for debug dumping
from circuijt.parser import ProtoCircuitParser
from circuijt.graph_utils import (
    ast_to_graph,
    get_component_connectivity,
    get_preferred_net_name_for_reconstruction,
)


# Functions generate_nmos_small_signal_model, generate_pmos_small_signal_model remain unchanged...
def generate_nmos_small_signal_model(nmos_name, external_nets_map):
    """Generate small signal model AST for an NMOS transistor."""
    id_suffix = nmos_name[1:] if nmos_name.startswith("M") else nmos_name
    rds_name = f"rds_{id_suffix}"
    gm_expr = f"gm_{id_suffix}*VGS_{id_suffix}"
    gmb_expr = f"gmB_{id_suffix}*VBS_{id_suffix}"

    model_statements = []

    # 1. Resistor declaration
    model_statements.append(
        {
            "type": "declaration",
            "component_type": "R",
            "instance_name": rds_name,
            "line": 0,
        }
    )

    # 2. Bulk connection
    if "B" in external_nets_map:
        model_statements.append(
            {
                "type": "direct_assignment",
                "source_node": external_nets_map["B"],
                "target_node": "GND",
                "line": 0,
            }
        )

    # 3. D-S path with parallel elements
    if "D" in external_nets_map and "S" in external_nets_map:
        parallel_elements = [
            {"type": "controlled_source", "expression": gm_expr, "direction": "->"},
            {"type": "controlled_source", "expression": gmb_expr, "direction": "->"},
            {"type": "component", "name": rds_name},
        ]
        model_statements.append(
            {
                "type": "series_connection",
                "path": [
                    {"type": "node", "name": external_nets_map["D"]},
                    {"type": "parallel_block", "elements": parallel_elements},
                    {"type": "node", "name": external_nets_map["S"]},
                ],
                "line": 0,
            }
        )

    return model_statements, {
        "component_type": "Nmos",
        "original_instance": nmos_name,
        "model_instance": rds_name,
        "control_voltages": f"VGS_{id_suffix}, VBS_{id_suffix}",
        "voltage_defs": f"VGS_{id_suffix}=V({external_nets_map.get('G', 'G')})-V({external_nets_map.get('S', 'S')}), "
        f"VBS_{id_suffix}=V({external_nets_map.get('B', 'B')})-V({external_nets_map.get('S', 'S')})",
        "connections": f"{external_nets_map.get('B', 'B')}:GND, "
        f"{external_nets_map.get('D', 'D')}:[{gm_expr}||{gmb_expr}||{rds_name}], "
        f"{external_nets_map.get('S', 'S')}",
    }


def generate_pmos_small_signal_model(pmos_name, external_nets_map):
    """Generate small signal model AST for a PMOS transistor."""
    id_suffix = pmos_name[1:] if pmos_name.startswith("M") else pmos_name
    rds_name = f"rds_{id_suffix}"
    gm_expr = f"-gm_{id_suffix}*VSG_{id_suffix}"  # Negative for PMOS
    gmb_expr = f"-gmB_{id_suffix}*VSB_{id_suffix}"  # Negative for PMOS

    model_statements = []

    # 1. Resistor declaration
    model_statements.append(
        {
            "type": "declaration",
            "component_type": "R",
            "instance_name": rds_name,
            "line": 0,
        }
    )

    # 2. Bulk connection (PMOS bulk often tied to VDD)
    if "B" in external_nets_map:
        model_statements.append(
            {
                "type": "direct_assignment",
                "source_node": external_nets_map["B"],
                "target_node": "VDD",
                "line": 0,
            }
        )

    # 3. D-S path with parallel elements
    if "D" in external_nets_map and "S" in external_nets_map:
        parallel_elements = [
            {
                "type": "controlled_source",
                "expression": gm_expr,
                "direction": "<-",
            },  # Reverse direction
            {
                "type": "controlled_source",
                "expression": gmb_expr,
                "direction": "<-",
            },  # Reverse direction
            {"type": "component", "name": rds_name},
        ]
        model_statements.append(
            {
                "type": "series_connection",
                "path": [
                    {"type": "node", "name": external_nets_map["D"]},
                    {"type": "parallel_block", "elements": parallel_elements},
                    {"type": "node", "name": external_nets_map["S"]},
                ],
                "line": 0,
            }
        )

    return model_statements, {
        "component_type": "Pmos",
        "original_instance": pmos_name,
        "model_instance": rds_name,
        "control_voltages": f"VSG_{id_suffix}, VSB_{id_suffix}",  # VSG instead of VGS for PMOS
        "voltage_defs": f"VSG_{id_suffix}=V({external_nets_map.get('S', 'S')})-V({external_nets_map.get('G', 'G')}), "
        f"VSB_{id_suffix}=V({external_nets_map.get('S', 'S')})-V({external_nets_map.get('B', 'B')})",
        "connections": f"{external_nets_map.get('B', 'B')}:VDD, "
        f"{external_nets_map.get('D', 'D')}:[{gm_expr}||{gmb_expr}||{rds_name}], "
        f"{external_nets_map.get('S', 'S')}",
    }


def process_circuit_file(
    input_file, output_dir=None, stdout=False, debug_dump=False
):  # Added debug_dump
    """Process a circuit file and generate small signal models."""
    if not stdout:
        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_file = os.path.join(output_dir, f"{base_name}_ssm.circuijt")
        annotation_file = os.path.join(output_dir, f"{base_name}_rules.txt")

    # Parse input circuit
    parser = ProtoCircuitParser()
    with open(input_file, "r") as f:
        circuit_text = f.read()

    ast, errors = parser.parse_text(circuit_text)

    if debug_dump:
        print("\n--- DEBUG DUMP: Initial AST (from parser) ---")
        pprint.pprint(ast)
        if errors:
            print("\n--- DEBUG DUMP: Parser Errors ---")
            pprint.pprint(errors)

    if errors:
        print(f"Parser errors in {input_file}:")
        for error in errors:
            print(error)
        # Decide whether to return or proceed. For SSM generation, errors are critical.
        if not ast:  # If AST is empty due to errors
            print("Critical parsing errors, cannot proceed with SSM generation.")
            return

    # Find all MOS transistors (both NMOS and PMOS)
    graph, dsu = ast_to_graph(ast)

    if debug_dump:
        print("\n--- DEBUG DUMP: Graph Structure ---")
        print("Nodes:")
        pprint.pprint(list(graph.nodes(data=True)))
        print("Edges:")
        pprint.pprint(list(graph.edges(data=True)))
        print("DSU Parent Map:")
        pprint.pprint(dsu.parent)

    nmos_transistors = [
        node
        for node, data in graph.nodes(data=True)
        if data.get("node_kind") == "component_instance"
        and data.get("instance_type") == "Nmos"
    ]
    pmos_transistors = [
        node
        for node, data in graph.nodes(data=True)
        if data.get("node_kind") == "component_instance"
        and data.get("instance_type") == "Pmos"
    ]

    if not nmos_transistors and not pmos_transistors:
        print(f"No MOS transistors found in {input_file}")
        return

    # Generate small signal models
    all_model_statements = []
    rule_annotations = []

    # Process NMOS transistors
    for nmos in nmos_transistors:
        # Get external connections
        term_to_canonical, _ = get_component_connectivity(graph, nmos)
        external_nets = {
            term: get_preferred_net_name_for_reconstruction(net, dsu)
            for term, net in term_to_canonical.items()
        }

        # Generate model
        model_statements, rule_data = generate_nmos_small_signal_model(
            nmos, external_nets
        )
        all_model_statements.extend(model_statements)

        # Format rule annotation
        rule_annotations.append(
            f"[{nmos} Small Signal Model]\n"
            f"Original: {nmos} with connections {external_nets}\n"
            f"Model: {rule_data}\n"
            "----------------------------------------\n"
        )

    # Process PMOS transistors
    for pmos in pmos_transistors:
        # Get external connections
        term_to_canonical, _ = get_component_connectivity(graph, pmos)
        external_nets = {
            term: get_preferred_net_name_for_reconstruction(net, dsu)
            for term, net in term_to_canonical.items()
        }

        # Generate model
        model_statements, rule_data = generate_pmos_small_signal_model(
            pmos, external_nets
        )
        all_model_statements.extend(model_statements)

        # Format rule annotation
        rule_annotations.append(
            f"[{pmos} Small Signal Model]\n"
            f"Original: {pmos} with connections {external_nets}\n"
            f"Model: {rule_data}\n"
            "----------------------------------------\n"
        )

    if debug_dump:
        print(
            "\n--- DEBUG DUMP: Generated Small-Signal Model AST (all_model_statements) ---"
        )
        pprint.pprint(all_model_statements)

    # Convert AST to circuit code
    from circuijt.ast_utils import generate_proto_from_ast

    # Write output
    if stdout:
        print("; Small Signal Model Generated Automatically")
        print(f"; Original circuit: {input_file}\n")
        print(generate_proto_from_ast(all_model_statements))

        print("\n\nSmall Signal Model Transformation Rules")
        print("======================================")
        print("".join(rule_annotations))
    else:
        with open(output_file, "w") as f:
            f.write("; Small Signal Model Generated Automatically\n")
            f.write(f"; Original circuit: {input_file}\n\n")
            f.write(generate_proto_from_ast(all_model_statements))

        with open(annotation_file, "w") as f:
            f.write("Small Signal Model Transformation Rules\n")
            f.write("======================================\n\n")
            f.writelines(rule_annotations)

        print(f"Generated small signal model in {output_file}")
        print(f"Transformation rules saved to {annotation_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate small signal models from circuit files"
    )
    parser.add_argument("circuit_file", help="Input circuit file to process")
    parser.add_argument(
        "-o",
        "--output-dir",
        default="small_signal_models",
        help="Output directory for generated models (default: small_signal_models)",
    )
    parser.add_argument(
        "-s",
        "--stdout",
        action="store_true",
        help="Print output to stdout instead of files",
    )
    parser.add_argument(  # Added debug_dump argument
        "--debug-dump",
        action="store_true",
        help="Dump intermediate AST and graph structures for debugging",
    )

    args = parser.parse_args()
    process_circuit_file(
        args.circuit_file, args.output_dir, args.stdout, args.debug_dump
    )  # Pass debug_dump


if __name__ == "__main__":
    main()
