# -*- coding: utf-8 -*-
"""AST conversion utilities."""

from .graph_utils import DSU


def _process_parallel_elements(elements):
    """Process elements within a parallel block."""
    processed = []
    for element in elements:
        if element["type"] == "component":
            processed.append({"type": "component_instance", "name": element["name"]})
        elif element["type"] in ("controlled_source", "noise_source"):
            processed.append(
                {
                    "type": element["type"],
                    **{k: element[k] for k in element if k != "type"},
                }
            )
    return processed


def _flatten_series_path(path_elements, context):
    """Helper function to flatten series path elements."""
    type_handlers = {
        "parallel_block": lambda e: {
            "type": "parallel_block",
            "elements": _process_parallel_elements(e["elements"]),
        },
        "component": lambda e: {"type": "component_instance", "name": e["name"]},
        "source": lambda e: {
            "type": "voltage_source",
            "name": e["name"],
            "polarity": e["polarity"],
        },
        "named_current": lambda e: {
            "type": "named_current",
            "name": e["name"],
            "direction": e["direction"],
        },
        "node": lambda e: {"type": "node", "name": e["name"]},
    }

    return [
        type_handlers[e["type"]](e) for e in path_elements if e["type"] in type_handlers
    ]


def ast_to_flattened_ast(ast, dsu=None):
    """Convert a parsed AST to a flattened format for analysis."""
    if dsu is None:
        dsu = DSU()

    flattened = []

    # Process declarations
    for statement in ast:
        if statement["type"] == "declaration":
            flattened.append(
                {
                    "type": "declaration",
                    "component_type": statement["component_type"],
                    "instance_name": statement["instance_name"],
                }
            )
        elif statement["type"] == "component_connection_block":
            for conn in statement["connections"]:
                flattened.append(
                    {
                        "type": "pin_connection",
                        "component_instance": statement["component_name"],
                        "terminal": conn["terminal"],
                        "net": conn["node"],
                    }
                )
        elif statement["type"] == "series_connection":
            if "_invalid_start" not in statement:
                # Nodes are only used for internal path processing
                _ = [e for e in statement["path"] if e["type"] == "node"]
                for i, element in enumerate(statement["path"]):
                    if element["type"] == "node":
                        canonical_net = dsu.find(element["name"])
                        if canonical_net != element["name"]:
                            flattened.append(
                                {
                                    "type": "net_alias",
                                    "source_net": element["name"],
                                    "canonical_net": canonical_net,
                                }
                            )
                    elif element["type"] == "component":
                        # Find adjacent nodes
                        prev_node = None
                        next_node = None
                        for j in range(i - 1, -1, -1):
                            if statement["path"][j]["type"] == "node":
                                prev_node = statement["path"][j]["name"]
                                break
                        for j in range(i + 1, len(statement["path"])):
                            if statement["path"][j]["type"] == "node":
                                next_node = statement["path"][j]["name"]
                                break
                        if prev_node:
                            flattened.append(
                                {
                                    "type": "pin_connection",
                                    "component_instance": element["name"],
                                    "terminal": "p1",
                                    "net": prev_node,
                                }
                            )
                        if next_node:
                            flattened.append(
                                {
                                    "type": "pin_connection",
                                    "component_instance": element["name"],
                                    "terminal": "p2",
                                    "net": next_node,
                                }
                            )
                    elif element["type"] == "source":
                        prev_node = None
                        next_node = None
                        for j in range(i - 1, -1, -1):
                            if statement["path"][j]["type"] == "node":
                                prev_node = statement["path"][j]["name"]
                                break
                        for j in range(i + 1, len(statement["path"])):
                            if statement["path"][j]["type"] == "node":
                                next_node = statement["path"][j]["name"]
                                break
                        terminal_map = {"-+": ("neg", "pos"), "+-": ("pos", "neg")}
                        first_term, second_term = terminal_map[element["polarity"]]
                        if prev_node:
                            flattened.append(
                                {
                                    "type": "pin_connection",
                                    "component_instance": element["name"],
                                    "terminal": first_term,
                                    "net": prev_node,
                                }
                            )
                        if next_node:
                            flattened.append(
                                {
                                    "type": "pin_connection",
                                    "component_instance": element["name"],
                                    "terminal": second_term,
                                    "net": next_node,
                                }
                            )
                    elif element["type"] == "parallel_block":
                        prev_node = next_node = None
                        for j in range(i - 1, -1, -1):
                            if statement["path"][j]["type"] == "node":
                                prev_node = statement["path"][j]["name"]
                                break
                        for j in range(i + 1, len(statement["path"])):
                            if statement["path"][j]["type"] == "node":
                                next_node = statement["path"][j]["name"]
                                break

                        for parallel_element in element["elements"]:
                            if parallel_element["type"] == "component":
                                if prev_node:
                                    flattened.append(
                                        {
                                            "type": "pin_connection",
                                            "component_instance": parallel_element[
                                                "name"
                                            ],
                                            "terminal": "p1",
                                            "net": prev_node,
                                        }
                                    )
                                if next_node:
                                    flattened.append(
                                        {
                                            "type": "pin_connection",
                                            "component_instance": parallel_element[
                                                "name"
                                            ],
                                            "terminal": "p2",
                                            "net": next_node,
                                        }
                                    )
        elif statement["type"] == "direct_assignment":
            source = statement["source_node"]
            target = statement["target_node"]
            canonical = dsu.find(target)
            if canonical != source:
                flattened.append(
                    {
                        "type": "net_alias",
                        "source_net": source,
                        "canonical_net": canonical,
                    }
                )

    return flattened


def _create_node_elements(elements):
    """Helper function to create node elements for regular AST."""
    node_elements = []
    for element in elements:
        if element["type"] == "node":
            node_elements.append({"type": "node", "name": element["name"]})
        elif element["type"] == "component_instance":
            node_elements.append({"type": "component", "name": element["name"]})
        elif element["type"] == "voltage_source":
            node_elements.append(
                {
                    "type": "source",
                    "name": element["name"],
                    "polarity": element["polarity"],
                }
            )
        elif element["type"] == "named_current":
            node_elements.append(
                {
                    "type": "named_current",
                    "name": element["name"],
                    "direction": element["direction"],
                }
            )
        elif element["type"] == "parallel_block":
            parallel_elements = []
            for parallel_element in element["elements"]:
                if parallel_element["type"] == "component_instance":
                    parallel_elements.append(
                        {"type": "component", "name": parallel_element["name"]}
                    )
                elif parallel_element["type"] == "controlled_source":
                    parallel_elements.append(
                        {
                            "type": "controlled_source",
                            "expression": parallel_element["expression"],
                            "direction": parallel_element["direction"],
                        }
                    )
                elif parallel_element["type"] == "noise_source":
                    parallel_elements.append(
                        {
                            "type": "noise_source",
                            "id": parallel_element["id"],
                            "direction": parallel_element["direction"],
                        }
                    )
            node_elements.append(
                {"type": "parallel_block", "elements": parallel_elements}
            )
    return node_elements


def flattened_ast_to_regular_ast(flattened_ast):
    """Convert a flattened AST back to regular format."""
    regular_ast = []

    # Group by type to reconstruct the AST  # noqa: W293
    declarations = [s for s in flattened_ast if s["type"] == "declaration"]
    pin_connections = [s for s in flattened_ast if s["type"] == "pin_connection"]

    # Process declarations  # noqa: W293
    for decl in declarations:
        regular_ast.append(
            {
                "type": "declaration",
                "component_type": decl["component_type"],
                "instance_name": decl["instance_name"],
            }
        )

    # Group pin connections by nodes  # noqa: W293
    node_components = {}
    for pin in pin_connections:
        net = pin["net"]
        if net not in node_components:
            node_components[net] = []
        node_components[net].append((pin["component_instance"], pin["terminal"]))

    # Find parallel structures  # noqa: W293
    net_pairs = []
    for pin in pin_connections:
        for other_pin in pin_connections:
            if (
                pin["component_instance"] == other_pin["component_instance"]
                and pin["terminal"] != other_pin["terminal"]
            ):
                net_pair = tuple(sorted([pin["net"], other_pin["net"]]))
                if net_pair not in net_pairs:
                    net_pairs.append(net_pair)

    # Construct series paths with parallel blocks  # noqa: W293
    for net1, net2 in net_pairs:
        components = []
        for comp, term in node_components.get(net1, []):
            if any(
                p["component_instance"] == comp and p["net"] == net2
                for p in pin_connections
                if p["terminal"] != term
            ):
                components.append(comp)

        if len(components) > 1:  # noqa: W293
            # This is a parallel block
            regular_ast.append(
                {
                    "type": "series_connection",
                    "path": [
                        {"type": "node", "name": net1},
                        {
                            "type": "parallel_block",
                            "elements": [
                                {"type": "component", "name": comp}
                                for comp in components
                            ],
                        },
                        {"type": "node", "name": net2},
                    ],
                }
            )
        elif len(components) == 1:
            # Single component
            regular_ast.append(
                {
                    "type": "series_connection",
                    "path": [
                        {"type": "node", "name": net1},
                        {"type": "component", "name": components[0]},
                        {"type": "node", "name": net2},
                    ],
                }
            )

    return regular_ast  # noqa: W293
