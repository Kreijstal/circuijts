# -*- coding: utf-8 -*-
"""AST utility functions for circuit analysis."""


def _handle_declaration(stmt, declared_component_instances, component_counts):
    inst_name = stmt.get("instance_name")
    comp_type = stmt.get("component_type")
    if inst_name:  # Parser ensures format, validator checks for duplicates/type
        declared_component_instances.add(inst_name)
        if comp_type == "Nmos":
            component_counts["total_nmos"] += 1
        elif comp_type == "R":
            component_counts["total_resistors"] += 1
        elif comp_type == "C":
            component_counts["total_capacitors"] += 1
        elif comp_type == "V":
            component_counts["total_voltages"] += 1


def _handle_component_connection(stmt, explicit_nodes):
    comp_name = stmt.get("component_name")  # Assumed declared by validator
    for conn in stmt.get("connections", []):
        if conn.get("node"):
            explicit_nodes.add(conn["node"])
        if comp_name and conn.get("terminal"):  # comp_name validity checked by validator
            explicit_nodes.add(f"{comp_name}.{conn['terminal']}")


def _handle_direct_assignment(stmt, explicit_nodes):
    if stmt.get("source_node"):
        explicit_nodes.add(stmt["source_node"])
    if stmt.get("target_node"):
        explicit_nodes.add(stmt["target_node"])


def _generate_implicit_nodes(structural_path_elements, implicit_node_counter):
    implicit_nodes_generated = set()

    # Implicit node at the end if needed
    last_el_in_structural_path = structural_path_elements[-1]
    if last_el_in_structural_path.get("type") not in ["node"]:
        implicit_node_counter += 1
        implicit_nodes_generated.add(f"_implicit_node_{implicit_node_counter}")

    # Implicit nodes between structural elements if neither is a node
    for i in range(len(structural_path_elements) - 1):
        el_current = structural_path_elements[i]
        el_next = structural_path_elements[i + 1]

        if el_current.get("type") not in ["node"] and el_next.get("type") not in ["node"]:
            implicit_node_counter += 1
            implicit_nodes_generated.add(f"_implicit_node_{implicit_node_counter}")

    return implicit_nodes_generated, implicit_node_counter


def _handle_series_connection(
    stmt,
    explicit_nodes,
    implicit_nodes_generated,
    implicit_node_counter,
    component_counts,
):
    if stmt.get("_invalid_start"):  # Path structure compromised, skip for implicit node analysis
        return

    structural_path_elements = []
    for el in stmt.get("path", []):
        el_type = el.get("type")
        if el_type in ["node", "component", "source", "parallel_block"]:
            structural_path_elements.append(el)

    if not structural_path_elements:
        return

    # Add explicit nodes from this path
    for el in structural_path_elements:
        if el.get("type") == "node" and el.get("name"):
            explicit_nodes.add(el["name"])

    # --- Implicit Node Generation for this series path ---
    implicit_nodes_generated, implicit_node_counter = _generate_implicit_nodes(structural_path_elements, implicit_node_counter)

    for el in stmt.get("path", []):
        if el.get("type") == "parallel_block":
            component_counts["total_parallel_blocks"] += 1


def summarize_circuit_elements(parsed_statements):
    explicit_nodes = set()
    declared_component_instances = set()  # Store names of declared components
    implicit_nodes_generated = set()
    implicit_node_counter = 0
    component_counts = {
        "total_nmos": 0,
        "total_resistors": 0,
        "total_capacitors": 0,
        "total_voltages": 0,
        "total_parallel_blocks": 0,
    }

    for stmt in parsed_statements:
        stmt_type = stmt.get("type")

        if stmt_type == "declaration":
            _handle_declaration(stmt, declared_component_instances, component_counts)

        elif stmt_type == "component_connection_block":
            _handle_component_connection(stmt, explicit_nodes)

        elif stmt_type == "direct_assignment":
            _handle_direct_assignment(stmt, explicit_nodes)

        elif stmt_type == "series_connection":
            _handle_series_connection(
                stmt,
                explicit_nodes,
                implicit_nodes_generated,
                implicit_node_counter,
                component_counts,
            )

    all_nodes_combined = explicit_nodes.union(implicit_nodes_generated)

    return {
        "num_total_nodes": len(all_nodes_combined),
        "node_list": sorted(list(all_nodes_combined)),
        "total_components": len(declared_component_instances),
        "component_list": sorted(list(declared_component_instances)),
        "details": {
            "explicit_nodes": sorted(list(explicit_nodes)),
            "implicit_nodes": sorted(list(implicit_nodes_generated)),
        },
        **component_counts,
    }


def _process_parallel_block(block_elements, component_map, node_map, current_node, edges, path_id):
    for pel in block_elements:
        pel_type = pel.get("type")
        if pel_type == "component":
            edges.append((current_node, pel["name"], {"path_id": path_id, "type": "series"}))
            node_map.add(current_node)
            node_map.add(pel["name"])
        elif pel_type == "controlled_source":
            ctrl_source_id = f"ctrl_{path_id}"
            edges.append((current_node, ctrl_source_id, {"path_id": path_id, "type": "series"}))
            node_map.add(current_node)
            node_map.add(ctrl_source_id)
        elif pel_type == "noise_source":
            noise_source_id = f"noise_{path_id}"
            edges.append((current_node, noise_source_id, {"path_id": path_id, "type": "series"}))
            node_map.add(current_node)
            node_map.add(noise_source_id)
        elif pel_type == "error":  # If AST can contain errors within blocks
            error_id = f"error_{path_id}"
            edges.append((current_node, error_id, {"path_id": path_id, "type": "series"}))
            node_map.add(current_node)
            node_map.add(error_id)


def _proto_handle_declaration(stmt):
    """Handle declaration statement type for proto generation."""
    return f"{stmt['component_type']} {stmt['instance_name']}"


def _proto_handle_component_connection_block(stmt):
    """Handle component connection block statement type for proto generation."""
    assignments = [f"{conn['terminal']}:({conn['node']})" for conn in stmt.get("connections", [])]
    return f"{stmt['component_name']} {{ {', '.join(assignments)} }}"


def _proto_handle_direct_assignment(stmt):
    """Handle direct assignment statement type for proto generation."""
    return f"({stmt['source_node']}):({stmt['target_node']})"


def _proto_handle_series_connection(stmt):
    """Handle series connection statement type for proto generation."""
    path_parts = []
    for item in stmt.get("path", []):
        item_type = item.get("type")
        if item_type == "node":
            path_parts.append(f"({item['name']})")
        elif item_type == "component":
            path_parts.append(item["name"])
        elif item_type == "source":
            path_parts.append(f"{item['name']} ({item['polarity']})")
        elif item_type == "named_current":
            path_parts.append(f"{item['direction']}{item['name']}")
        elif item_type == "parallel_block":
            path_parts.append(_proto_handle_parallel_block(item))
        elif item_type == "error":
            path_parts.append(f"<ERROR_IN_PATH: {item.get('message', 'Malformed element')}>")
        else:
            path_parts.append(f"<UNKNOWN_PATH_TYPE: {item_type}>")
    return " -- ".join(path_parts)


def _proto_handle_parallel_block(item):
    """Handle parallel block elements for proto generation."""
    elements_strs = []
    for pel in item.get("elements", []):
        pel_type = pel.get("type")
        if pel_type == "component":
            elements_strs.append(pel["name"])
        elif pel_type == "controlled_source":
            elements_strs.append(f"{pel['expression']} ({pel['direction']})")
        elif pel_type == "noise_source":
            elements_strs.append(f"{pel['id']} ({pel['direction']})")
        elif pel_type == "error":
            elements_strs.append(f"<ERROR_IN_PARALLEL: {pel.get('message', 'Malformed element')}>")
        else:
            elements_strs.append(f"<UNKNOWN_PARALLEL_TYPE: {pel_type}>")
    return f"[ {' || '.join(elements_strs)} ]"


def _proto_handle_error(stmt):
    """Handle error statement type for proto generation."""
    original_content = stmt.get("original_line_content", "")
    message = stmt.get("message", "Unknown parsing error")
    return f"; ERROR IN ORIGINAL INPUT (L{stmt.get('line', '?')}): {message} -> {original_content}"


def _proto_handle_unknown(stmt):
    """Handle unknown statement types for proto generation."""
    return f"; UNKNOWN_AST_STATEMENT_TYPE: {stmt.get('type')} - DATA: {stmt}"


def generate_proto_from_ast(parsed_statements):
    """
    Generates a Proto-Language circuit description string from its AST.

    Args:
        parsed_statements (list): A list of dictionaries, where each dictionary
                                  represents an AST node (a parsed statement).

    Returns:
        str: A string representing the reconstructed circuit description.
    """
    handlers = {
        "declaration": _proto_handle_declaration,
        "component_connection_block": _proto_handle_component_connection_block,
        "direct_assignment": _proto_handle_direct_assignment,
        "series_connection": _proto_handle_series_connection,
        "error": _proto_handle_error,
    }

    output_lines = []
    for stmt in parsed_statements:
        stmt_type = stmt.get("type")
        handler = handlers.get(stmt_type, _proto_handle_unknown)
        line_str = handler(stmt)
        if line_str:
            output_lines.append(line_str)

    return "\n".join(output_lines)


def find_statements_of_type(statements, statement_type):
    """Find all statements of a specific type in the AST.

    Args:
        statements (list): List of AST statement dictionaries
        statement_type (str): Type of statement to find

    Returns:
        list: List of matching statements
    """
    matches = []
    for stmt in statements:
        if stmt.get("type") == statement_type:
            matches.append(stmt)
        # Check for nested statements in series connections
        elif stmt.get("type") == "series_connection":
            for path_element in stmt.get("path", []):
                if path_element.get("type") == statement_type:
                    matches.append(path_element)
    return matches


def find_declarations_by_type(statements, component_type):
    """Find all component declarations of a specific type.

    Args:
        statements (list): List of AST statement dictionaries
        component_type (str): Type of component to find declarations for

    Returns:
        list: List of matching declaration statements
    """
    return [stmt for stmt in statements if stmt.get("type") == "declaration" and stmt.get("component_type") == component_type]


def _flatten_series_path_element(
    element,
    dsu,
    current_net_name,
    flattened_elements,
    path_context,
    line_num,
):
    """Flatten a series path element for proto generation.

    Args:
        element (dict): The series path element AST node.
        dsu (object): The disjoint set union-find structure for tracking connected components.
        current_net_name (str): The current net name being processed.
        flattened_elements (set): Set of already flattened elements to avoid duplicates.
        path_context (list): The context of the path for hierarchical naming.
        line_num (int): The line number in the original source for error reporting.

    Returns:
        str: The flattened representation of the series path element.
    """
    element_type = element.get("type")

    if element_type == "node":
        return f"({element['name']})"

    elif element_type == "component":
        return element["name"]

    elif element_type == "source":
        return f"{element['name']} ({element['polarity']})"

    elif element_type == "named_current":
        return f"{element['direction']}{element['name']}"

    elif element_type == "parallel_block":
        return _proto_handle_parallel_block(element)

    elif element_type == "error":
        return f"<ERROR_IN_PATH: {element.get('message', 'Malformed element')}>"

    else:
        return f"<UNKNOWN_PATH_TYPE: {element_type}>"


def ast_to_flattened_ast(parsed_statements, dsu, component_map=None):  # pylint: disable=unused-argument
    """
    Converts a parsed AST to a "flattened" AST where all connections are explicit
    and nodes are canonicalized using the DSU structure.
    This is a step towards generating a graph or a canonical netlist.
    """
    return []  # Placeholder, actual implementation needed


def flattened_ast_to_regular_ast(flattened_ast_statements):
    """Converts a flattened AST back to a regular AST structure (if possible/needed)."""
    # This function might be complex depending on how different the flattened AST is.
    # For now, let's assume it's a direct pass-through or simple transformation.
    return flattened_ast_statements
