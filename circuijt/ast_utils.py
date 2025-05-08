# -*- coding: utf-8 -*-
"""AST utility functions for circuit analysis."""


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

        elif stmt_type == "component_connection_block":
            comp_name = stmt.get("component_name")  # Assumed declared by validator
            for conn in stmt.get("connections", []):
                if conn.get("node"):
                    explicit_nodes.add(conn["node"])
                if comp_name and conn.get(
                    "terminal"
                ):  # comp_name validity checked by validator
                    explicit_nodes.add(f"{comp_name}.{conn['terminal']}")

        elif stmt_type == "direct_assignment":
            if stmt.get("source_node"):
                explicit_nodes.add(stmt["source_node"])
            if stmt.get("target_node"):
                explicit_nodes.add(stmt["target_node"])

        elif stmt_type == "series_connection":
            if stmt.get(
                "_invalid_start"
            ):  # Path structure compromised, skip for implicit node analysis
                continue

            structural_path_elements = []
            for el in stmt.get("path", []):
                el_type = el.get("type")
                if el_type in ["node", "component", "source", "parallel_block"]:
                    structural_path_elements.append(el)
                # Explicit nodes from path are added below

            if not structural_path_elements:
                continue

            # Add explicit nodes from this path
            for el in structural_path_elements:
                if el.get("type") == "node" and el.get("name"):
                    explicit_nodes.add(el["name"])

            # --- Implicit Node Generation for this series path ---
            # Path must start with a node, so no implicit node at the very start.
            # structural_path_elements[0] is guaranteed to be a node if _invalid_start is false.

            # Implicit node at the end if needed
            last_el_in_structural_path = structural_path_elements[-1]
            # An implicit node is needed at the end if the path has any non-node elements,
            # and the very last element itself is not a node.
            if last_el_in_structural_path.get("type") not in ["node"]:
                implicit_node_counter += 1
                implicit_nodes_generated.add(f"_implicit_node_{implicit_node_counter}")

            # Implicit nodes between structural elements if neither is a node
            for i in range(len(structural_path_elements) - 1):
                el_current = structural_path_elements[i]
                el_next = structural_path_elements[i + 1]

                # An implicit node is needed between two elements if they are directly connected
                # AND neither is an explicit node acting as the connection point.
                # R1 -- C1 needs implicit node. (N1) -- R1 needs no implicit node. R1 -- (N2) needs no implicit node.
                if el_current.get("type") not in ["node"] and el_next.get(
                    "type"
                ) not in ["node"]:
                    implicit_node_counter += 1
                    implicit_nodes_generated.add(
                        f"_implicit_node_{implicit_node_counter}"
                    )

            for el in stmt.get("path", []):
                if el.get("type") == "parallel_block":
                    component_counts["total_parallel_blocks"] += 1

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


def generate_proto_from_ast(parsed_statements):
    """
    Generates a Proto-Language circuit description string from its AST.

    Args:
        parsed_statements (list): A list of dictionaries, where each dictionary
                                  represents an AST node (a parsed statement).

    Returns:
        str: A string representing the reconstructed circuit description.
    """
    output_lines = []

    for stmt in parsed_statements:
        stmt_type = stmt.get("type")
        line_str = ""  # Initialize line string for the current statement

        if stmt_type == "declaration":
            line_str = f"{stmt['component_type']} {stmt['instance_name']}"

        elif stmt_type == "component_connection_block":
            assignments = []
            for conn in stmt.get("connections", []):
                assignments.append(f"{conn['terminal']}:({conn['node']})")
            assignments_str = ", ".join(assignments)
            # Ensure space after '{' and before '}' as per typical spec examples
            line_str = f"{stmt['component_name']} {{ {assignments_str} }}"

        elif stmt_type == "direct_assignment":
            line_str = f"({stmt['source_node']}):({stmt['target_node']})"

        elif stmt_type == "series_connection":
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
                    elements_strs = []
                    for pel in item.get("elements", []):
                        pel_type = pel.get("type")
                        if pel_type == "component":
                            elements_strs.append(pel["name"])
                        elif pel_type == "controlled_source":
                            elements_strs.append(
                                f"{pel['expression']} ({pel['direction']})"
                            )
                        elif pel_type == "noise_source":
                            elements_strs.append(f"{pel['id']} ({pel['direction']})")
                        elif (
                            pel_type == "error"
                        ):  # If AST can contain errors within blocks
                            elements_strs.append(
                                f"<ERROR_IN_PARALLEL: {pel.get('message', 'Malformed element')}>"
                            )
                        else:
                            elements_strs.append(f"<UNKNOWN_PARALLEL_TYPE: {pel_type}>")

                    parallel_content = " || ".join(elements_strs)
                    # Ensure space after '[' and before ']'
                    path_parts.append(f"[ {parallel_content} ]")
                elif item_type == "error":  # If AST can contain errors within paths
                    path_parts.append(
                        f"<ERROR_IN_PATH: {item.get('message', 'Malformed element')}>"
                    )
                else:
                    path_parts.append(f"<UNKNOWN_PATH_TYPE: {item_type}>")

            line_str = " -- ".join(path_parts)

        elif (
            stmt_type == "error"
        ):  # If AST directly contains top-level error statements
            # This assumes an error statement in the AST would signify a line that couldn't be parsed
            # and we are just commenting it out or noting it.
            original_content = stmt.get(
                "original_line_content", ""
            )  # if parser stores this
            message = stmt.get("message", "Unknown parsing error")
            line_str = f"; ERROR IN ORIGINAL INPUT (L{stmt.get('line', '?')}): {message} -> {original_content}"

        else:
            # Fallback for any unknown statement types in the AST
            line_str = f"; UNKNOWN_AST_STATEMENT_TYPE: {stmt_type} - DATA: {stmt}"

        if line_str:  # Add the reconstructed line if it's not empty
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
    return [
        stmt
        for stmt in statements
        if stmt.get("type") == "declaration"
        and stmt.get("component_type") == component_type
    ]
