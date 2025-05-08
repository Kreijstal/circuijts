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

    return [type_handlers[e["type"]](e) for e in path_elements if e["type"] in type_handlers]


def _find_adjacent_nodes(path, index):
    """Find previous and next nodes in path relative to index."""
    prev_node = next_node = None
    for j in range(index - 1, -1, -1):
        if path[j]["type"] == "node":
            prev_node = path[j]["name"]
            break
    for j in range(index + 1, len(path)):
        if path[j]["type"] == "node":
            next_node = path[j]["name"]
            break
    return prev_node, next_node


def _process_component_element(element, prev_node, next_node):
    """Process a component element in series path."""
    connections = []
    if prev_node:
        connections.append(
            {
                "type": "pin_connection",
                "component_instance": element["name"],
                "terminal": "p1",
                "net": prev_node,
            }
        )
    if next_node:
        connections.append(
            {
                "type": "pin_connection",
                "component_instance": element["name"],
                "terminal": "p2",
                "net": next_node,
            }
        )
    return connections


def _process_source_element(element, prev_node, next_node):
    """Process a source element in series path."""
    connections = []
    terminal_map = {"-+": ("neg", "pos"), "+-": ("pos", "neg")}
    first_term, second_term = terminal_map[element["polarity"]]
    if prev_node:
        connections.append(
            {
                "type": "pin_connection",
                "component_instance": element["name"],
                "terminal": first_term,
                "net": prev_node,
            }
        )
    if next_node:
        connections.append(
            {
                "type": "pin_connection",
                "component_instance": element["name"],
                "terminal": second_term,
                "net": next_node,
            }
        )
    return connections


def _process_parallel_block(element, prev_node, next_node):
    """Process a parallel block element in series path."""
    connections = []
    for parallel_element in element["elements"]:
        if parallel_element["type"] == "component":
            if prev_node:
                connections.append(
                    {
                        "type": "pin_connection",
                        "component_instance": parallel_element["name"],
                        "terminal": "p1",
                        "net": prev_node,
                    }
                )
            if next_node:
                connections.append(
                    {
                        "type": "pin_connection",
                        "component_instance": parallel_element["name"],
                        "terminal": "p2",
                        "net": next_node,
                    }
                )
    return connections


def _process_declaration(statement):
    """Process a declaration statement."""
    return {
        "type": "declaration",
        "component_type": statement["component_type"],
        "instance_name": statement["instance_name"],
    }


def _process_component_connection_block(statement):
    """Process a component connection block."""
    connections = []
    for conn in statement["connections"]:
        connections.append(
            {
                "type": "pin_connection",
                "component_instance": statement["component_name"],
                "terminal": conn["terminal"],
                "net": conn["node"],
            }
        )
    return connections


def _process_series_connection(statement, dsu, element_processors):
    """Process a series connection statement."""
    flattened = []
    if "_invalid_start" not in statement:
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
            elif element["type"] in element_processors:
                prev_node, next_node = _find_adjacent_nodes(statement["path"], i)
                flattened.extend(element_processors[element["type"]](element, prev_node, next_node))
    return flattened


def _process_direct_assignment(statement, dsu):
    """Process a direct assignment statement."""
    canonical = dsu.find(statement["target_node"])
    if canonical != statement["source_node"]:
        return {
            "type": "net_alias",
            "source_net": statement["source_node"],
            "canonical_net": canonical,
        }
    return None


def ast_to_flattened_ast(ast, dsu=None):
    """Convert a parsed AST to a flattened format for analysis."""
    if dsu is None:
        dsu = DSU()

    flattened = []
    element_processors = {
        "component": _process_component_element,
        "source": _process_source_element,
        "parallel_block": _process_parallel_block,
    }

    statement_processors = {
        "declaration": _process_declaration,
        "component_connection_block": _process_component_connection_block,
        "series_connection": lambda s: _process_series_connection(s, dsu, element_processors),
        "direct_assignment": lambda s: _process_direct_assignment(s, dsu),
    }

    for statement in ast:
        if statement["type"] in statement_processors:
            result = statement_processors[statement["type"]](statement)
            if isinstance(result, list):
                flattened.extend(result)
            elif result is not None:
                flattened.append(result)

    return flattened


def _process_parallel_node_elements(elements):
    """Process elements within a parallel block for node creation."""
    processed = []
    for element in elements:
        if element["type"] == "component_instance":
            processed.append({"type": "component", "name": element["name"]})
        elif element["type"] in ("controlled_source", "noise_source"):
            processed.append(
                {
                    "type": element["type"],
                    **{k: element[k] for k in element if k != "type"},
                }
            )
    return processed


def _create_node_elements(elements):
    """Helper function to create node elements for regular AST."""
    type_handlers = {
        "node": lambda e: {"type": "node", "name": e["name"]},
        "component_instance": lambda e: {"type": "component", "name": e["name"]},
        "voltage_source": lambda e: {
            "type": "source",
            "name": e["name"],
            "polarity": e["polarity"],
        },
        "named_current": lambda e: {
            "type": "named_current",
            "name": e["name"],
            "direction": e["direction"],
        },
        "parallel_block": lambda e: {
            "type": "parallel_block",
            "elements": _process_parallel_node_elements(e["elements"]),
        },
    }

    return [type_handlers[e["type"]](e) for e in elements if e["type"] in type_handlers]


def _find_net_pairs(pin_connections):
    """Find all unique net pairs connected by components."""
    net_pairs = set()
    for pin in pin_connections:
        for other_pin in pin_connections:
            if pin["component_instance"] == other_pin["component_instance"] and pin["terminal"] != other_pin["terminal"]:
                net_pairs.add(tuple(sorted((pin["net"], other_pin["net"]))))
    return net_pairs


def _build_ast_path(net1, net2, components, node_components, pin_connections):
    """Build AST path segment between two nets."""
    if len(components) > 1:
        return {
            "type": "series_connection",
            "path": [
                {"type": "node", "name": net1},
                {
                    "type": "parallel_block",
                    "elements": [{"type": "component", "name": comp} for comp in components],
                },
                {"type": "node", "name": net2},
            ],
        }
    elif len(components) == 1:
        return {
            "type": "series_connection",
            "path": [
                {"type": "node", "name": net1},
                {"type": "component", "name": components[0]},
                {"type": "node", "name": net2},
            ],
        }
    return None


def flattened_ast_to_regular_ast(flattened_ast):
    """Convert a flattened AST back to regular format."""
    regular_ast = []

    # Process declarations
    regular_ast.extend(
        {
            "type": "declaration",
            "component_type": d["component_type"],
            "instance_name": d["instance_name"],
        }
        for d in flattened_ast
        if d["type"] == "declaration"
    )

    # Group pin connections by nodes
    pin_connections = [s for s in flattened_ast if s["type"] == "pin_connection"]
    node_components = {}
    for pin in pin_connections:
        node_components.setdefault(pin["net"], []).append((pin["component_instance"], pin["terminal"]))

    # Process net pairs
    net_pairs = _find_net_pairs(pin_connections)
    for net1, net2 in net_pairs:
        components = [
            comp
            for comp, term in node_components.get(net1, [])
            if any(p["component_instance"] == comp and p["net"] == net2 for p in pin_connections if p["terminal"] != term)
        ]

        if path := _build_ast_path(net1, net2, components, node_components, pin_connections):
            regular_ast.append(path)

    return regular_ast


def ast_to_graph(
    parsed_statements,
    dsu_structure=None,
    debug=False,
):  # pylint: disable=unused-argument
    """Convert AST to a graph representation."""
    dsu = DSU()

    # First pass - process declarations and build DSU structure
    for statement in parsed_statements:
        if statement["type"] == "declaration":
            dsu.add(statement["instance_name"])

    # Second pass - process connections and build graph edges
    edges = []
    for statement in parsed_statements:
        if statement["type"] == "component_connection_block":
            for conn in statement["connections"]:
                edges.append(
                    {
                        "type": "edge",
                        "source": conn["node"],
                        "target": statement["component_name"],
                        "terminal": conn["terminal"],
                    }
                )
        elif statement["type"] == "series_connection":
            for i, element in enumerate(statement["path"]):
                if element["type"] == "node":
                    continue
                prev_node, next_node = _find_adjacent_nodes(statement["path"], i)
                if element["type"] == "component":
                    edges.extend(
                        _process_component_element(element, prev_node, next_node)
                    )
                elif element["type"] == "source":
                    edges.extend(_process_source_element(element, prev_node, next_node))
                elif element["type"] == "parallel_block":
                    edges.extend(_process_parallel_block(element, prev_node, next_node))

    return {"nodes": dsu.get_all(), "edges": edges}
