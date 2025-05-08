# -*- coding: utf-8 -*-
"""Graph utilities for circuit analysis."""

import networkx as nx


class DSU:
    """
    Disjoint Set Union (DSU) data structure, also known as Union-Find.
    Used here to manage equivalences between electrical net names.
    """

    def __init__(self, preferred_roots=None):
        self.parent = {}
        self.num_sets = 0
        if preferred_roots is None:
            self.preferred_roots = {"GND", "VDD"}  # Default preferred roots
        else:
            self.preferred_roots = set(preferred_roots)

        # Define a hierarchy for preferred roots if they are unioned
        # Lower index = higher preference (e.g., GND is most preferred)
        self.preferred_root_order = ["GND", "VDD"]  # Extend as needed

    def add_set(self, item):
        """Ensures an item is part of the DSU, creating a new set if it's new."""
        if item not in self.parent:
            self.parent[item] = item
            self.num_sets += 1

    def find(self, item):
        """Finds the representative (root) of the set containing item, with path compression."""
        self.add_set(item)  # Ensure item is in DSU before finding
        if self.parent[item] == item:
            return item
        self.parent[item] = self.find(self.parent[item])  # Path compression
        return self.parent[item]

    def union(self, item1, item2):
        """Merges the sets containing item1 and item2, preferring special net names as canonical."""
        root1 = self.find(item1)
        root2 = self.find(item2)

        if root1 != root2:
            is_root1_preferred = root1 in self.preferred_roots
            is_root2_preferred = root2 in self.preferred_roots

            if is_root1_preferred and not is_root2_preferred:
                # root1 is preferred, root2 is not; root1 becomes the new representative
                self.parent[root2] = root1
            elif not is_root1_preferred and is_root2_preferred:
                # root2 is preferred, root1 is not; root2 becomes the new representative
                self.parent[root1] = root2
            elif is_root1_preferred and is_root2_preferred:
                # Both are preferred. Use the defined order to break ties.
                try:
                    idx1 = self.preferred_root_order.index(root1)
                except ValueError:  # root1 is preferred but not in order list
                    idx1 = float("inf")
                try:
                    idx2 = self.preferred_root_order.index(root2)
                except ValueError:  # root2 is preferred but not in order list
                    idx2 = float("inf")

                if idx1 < idx2:  # root1 has higher preference
                    self.parent[root2] = root1
                elif idx2 < idx1:  # root2 has higher preference
                    self.parent[root1] = root2
                else:  # Same preference or both not in ordered list (but are in self.preferred_roots)
                    # Fallback to alphabetical or let root2 win for determinism
                    if root1 < root2:  # Arbitrary but deterministic tie-break
                        self.parent[root2] = root1
                    else:
                        self.parent[root1] = root2
            else:
                # Neither is preferred; let root2's original root become the representative (original behavior)
                self.parent[root1] = root2

            self.num_sets -= 1
            return True
        return False

    def get_all_canonical_representatives(self):
        """Returns a set of all canonical representatives."""
        return {self.find(item) for item in self.parent}

    def get_set_members(self, representative_item):
        """Returns all items belonging to the same set as representative_item."""
        canonical_rep = self.find(representative_item)
        return {item for item in self.parent if self.find(item) == canonical_rep}


def _process_declarations(G, parsed_statements, electrical_nets_dsu):
    """Process declarations and pre-populate DSU with known explicit net names."""
    declared_components = {}
    for stmt in parsed_statements:
        stmt_type = stmt.get("type")
        if stmt_type == "declaration":
            comp_type = stmt["component_type"]
            inst_name = stmt["instance_name"]
            declared_components[inst_name] = {
                "type": comp_type,
                "line": stmt["line"],
                "instance_node_name": inst_name,
            }
            G.add_node(
                inst_name, node_kind="component_instance", instance_type=comp_type
            )
        elif stmt_type == "component_connection_block":
            comp_name = stmt["component_name"]
            for conn in stmt.get("connections", []):
                electrical_nets_dsu.add_set(conn["node"])
                electrical_nets_dsu.add_set(f"{comp_name}.{conn['terminal']}")
        elif stmt_type == "direct_assignment":
            electrical_nets_dsu.add_set(stmt["source_node"])
            electrical_nets_dsu.add_set(stmt["target_node"])
        elif stmt_type == "series_connection":
            for item in stmt.get("path", []):
                if item.get("type") == "node":
                    electrical_nets_dsu.add_set(item["name"])
    return declared_components


def _handle_component_connection(G, stmt, declared_components, electrical_nets_dsu):
    """Handle component connection block statements."""
    comp_name = stmt["component_name"]
    if comp_name not in declared_components:
        print(
            f"AST_TO_GRAPH_WARNING: Component '{comp_name}' in block not declared. Skipping."
        )
        return

    comp_node_name = declared_components[comp_name]["instance_node_name"]
    for conn in stmt.get("connections", []):
        terminal_name = conn["terminal"]
        explicit_net_name = conn["node"]
        device_terminal = f"{comp_name}.{terminal_name}"

        electrical_nets_dsu.union(device_terminal, explicit_net_name)
        canonical_net = electrical_nets_dsu.find(explicit_net_name)
        if not G.has_node(canonical_net):
            G.add_node(canonical_net, node_kind="electrical_net")
        G.add_edge(comp_node_name, canonical_net, terminal=terminal_name)

        if "." in explicit_net_name:
            ref_comp, ref_term = explicit_net_name.split(".", 1)
            if ref_comp in declared_components:
                G.add_edge(ref_comp, canonical_net, terminal=ref_term)


def _handle_direct_assignment(G, stmt, declared_components, electrical_nets_dsu):
    """Handle direct assignment statements."""
    s_node, t_node = stmt["source_node"], stmt["target_node"]
    electrical_nets_dsu.union(s_node, t_node)
    canonical_net = electrical_nets_dsu.find(s_node)
    if not G.has_node(canonical_net):
        G.add_node(canonical_net, node_kind="electrical_net")

    for node_name in [s_node, t_node]:
        if "." in node_name:
            comp_name, term = node_name.split(".", 1)
            if comp_name in declared_components:
                G.add_edge(comp_name, canonical_net, terminal=term)


def _handle_series_connection(
    G,
    stmt,
    declared_components,
    electrical_nets_dsu,
    implicit_node_idx,
    internal_component_idx,
):
    """Handle series connection statements."""
    path = stmt.get("path", [])
    if not path or path[0].get("type") != "node":
        print(
            f"AST_TO_GRAPH_WARNING: Series path malformed or empty: {stmt.get('_path_str', 'N/A')}"
        )
        return implicit_node_idx, internal_component_idx

    # Process start node
    start_node_original_name = path[0]["name"]
    current_attach_point = electrical_nets_dsu.find(start_node_original_name)
    if not G.has_node(current_attach_point):
        G.add_node(current_attach_point, node_kind="electrical_net")

    if "." in start_node_original_name:
        comp_part, term_part = start_node_original_name.split(".", 1)
        if comp_part in declared_components:
            G.add_edge(comp_part, current_attach_point, terminal=term_part)

    # Process remaining path elements
    for i in range(1, len(path)):
        item = path[i]
        item_type = item.get("type")

        if item_type == "node":
            node_name = item["name"]
            current_attach_point = electrical_nets_dsu.find(node_name)
            if not G.has_node(current_attach_point):
                G.add_node(current_attach_point, node_kind="electrical_net")
            if "." in node_name:
                comp_part, term_part = node_name.split(".", 1)
                if comp_part in declared_components:
                    G.add_edge(comp_part, current_attach_point, terminal=term_part)
            continue

        # Determine next attach point
        next_attach_point = None
        created_new_implicit_node = False

        if i + 1 < len(path) and path[i + 1].get("type") == "node":
            next_node_name = path[i + 1]["name"]
            next_attach_point = electrical_nets_dsu.find(next_node_name)
        else:
            implicit_node_name = f"_implicit_{implicit_node_idx}"
            next_attach_point = electrical_nets_dsu.find(implicit_node_name)
            if not G.has_node(next_attach_point):
                created_new_implicit_node = True

        if next_attach_point and not G.has_node(next_attach_point):
            G.add_node(next_attach_point, node_kind="electrical_net")

        # Handle different item types
        if item_type == "component":
            _handle_series_component(
                G, item, declared_components, current_attach_point, next_attach_point
            )
        elif item_type == "source":
            _handle_series_source(
                G, item, declared_components, current_attach_point, next_attach_point
            )
        elif item_type == "parallel_block":
            internal_component_idx = _handle_parallel_block(
                G,
                item,
                declared_components,
                current_attach_point,
                next_attach_point,
                internal_component_idx,
            )

        current_attach_point = next_attach_point
        if created_new_implicit_node:
            implicit_node_idx += 1

    return implicit_node_idx, internal_component_idx


def _handle_series_component(
    G, item, declared_components, current_attach_point, next_attach_point
):
    """Handle component in series connection."""
    comp_name = item["name"]
    if comp_name not in declared_components:
        return
    comp_node_name = declared_components[comp_name]["instance_node_name"]
    G.add_edge(
        comp_node_name, current_attach_point, terminal="t1_series", key="t1_series"
    )
    G.add_edge(comp_node_name, next_attach_point, terminal="t2_series", key="t2_series")


def _handle_series_source(
    G, item, declared_components, current_attach_point, next_attach_point
):
    """Handle source in series connection."""
    source_name = item["name"]
    if source_name not in declared_components:
        return
    polarity = item["polarity"]
    source_node_name = declared_components[source_name]["instance_node_name"]
    G.nodes[source_node_name]["polarity"] = polarity

    if polarity == "-+":
        G.add_edge(source_name, current_attach_point, terminal="neg", key="neg")
        G.add_edge(source_name, next_attach_point, terminal="pos", key="pos")
    else:
        G.add_edge(source_name, current_attach_point, terminal="pos", key="pos")
        G.add_edge(source_name, next_attach_point, terminal="neg", key="neg")


def _handle_parallel_block(
    G,
    item,
    declared_components,
    current_attach_point,
    next_attach_point,
    internal_component_idx,
):
    """Handle parallel block in series connection."""
    for pel in item.get("elements", []):
        element_node_name = None
        attrs = {"node_kind": "component_instance"}

        if pel["type"] == "component":
            if pel["name"] in declared_components:
                element_node_name = declared_components[pel["name"]][
                    "instance_node_name"
                ]
        elif pel["type"] == "controlled_source":
            element_node_name = f"_internal_cs_{internal_component_idx}"
            attrs.update(
                {
                    "instance_type": "controlled_source",
                    "expression": pel["expression"],
                    "direction": pel["direction"],
                }
            )
            internal_component_idx += 1
        elif pel["type"] == "noise_source":
            element_node_name = f"_internal_ns_{internal_component_idx}"
            attrs.update(
                {
                    "instance_type": "noise_source",
                    "id": pel["id"],
                    "direction": pel["direction"],
                }
            )
            internal_component_idx += 1

        if element_node_name:
            if not G.has_node(element_node_name):
                G.add_node(element_node_name, **attrs)
            G.add_edge(
                element_node_name, current_attach_point, terminal="par_t1", key="par_t1"
            )
            G.add_edge(
                element_node_name, next_attach_point, terminal="par_t2", key="par_t2"
            )

    return internal_component_idx


def ast_to_graph(parsed_statements):
    """
    Converts a Proto-Language AST into a graph representation.

    Graph Nodes:
        - Component Instances (e.g., "R1", "M1"):
            Attributes: node_kind='component_instance', instance_type='R'/'Nmos'/etc.
        - Electrical Nets (e.g., "GND", "node_gate_canonical"):
            Attributes: node_kind='electrical_net'
            Net names are canonicalized using DSU.

    Graph Edges:
        - Connect a component instance node to an electrical net node.
        - Attribute: 'terminal' (e.g., 'G', 'D', 't1_series') indicating the
          component terminal involved in the connection.
    """
    G = nx.MultiGraph()
    electrical_nets_dsu = DSU()

    # Initialize special nodes
    for special_node in ["GND", "VDD"]:
        electrical_nets_dsu.add_set(special_node)

    implicit_node_idx = 0
    internal_component_idx = 0

    # Pass 1: Process declarations
    declared_components = _process_declarations(
        G, parsed_statements, electrical_nets_dsu
    )

    # Pass 2: Process connections
    for stmt in parsed_statements:
        stmt_type = stmt.get("type")
        if stmt_type == "declaration":
            continue
        elif stmt_type == "component_connection_block":
            _handle_component_connection(
                G, stmt, declared_components, electrical_nets_dsu
            )
        elif stmt_type == "direct_assignment":
            _handle_direct_assignment(G, stmt, declared_components, electrical_nets_dsu)
        elif stmt_type == "series_connection":
            implicit_node_idx, internal_component_idx = _handle_series_connection(
                G,
                stmt,
                declared_components,
                electrical_nets_dsu,
                implicit_node_idx,
                internal_component_idx,
            )

    # TODO: Optional: Create a "cleaner" graph where all net nodes are guaranteed to be their canonical names
    # This involves relabeling or creating a new graph.
    # For now, the existing graph G uses canonical names for edges, but some non-canonical
    # net nodes might exist if they were added before all unions were processed.
    # However, DSU lookups (`electrical_nets_dsu.find()`) ensure logical correctness.

    return G, electrical_nets_dsu


def get_preferred_net_name_for_reconstruction(
    canonical_net_name,
    dsu,
    known_significant_nodes=None,
    allow_implicit_if_only_option=False,
):
    if known_significant_nodes is None:
        known_significant_nodes = {"GND", "VDD"}

    if not dsu or canonical_net_name not in dsu.parent:
        return canonical_net_name

    members = dsu.get_set_members(canonical_net_name)
    if not members:
        return canonical_net_name

    # Priority:
    # 1. User-defined, non-device terminal, non-significant common rail names (prefer shorter, then alpha)
    user_named = sorted(
        [
            m
            for m in members
            if not m.startswith("_implicit_")
            and "." not in m
            and m not in known_significant_nodes
        ],
        key=lambda x: (len(x), x),
    )
    if user_named:
        return user_named[0]

    # 2. Known significant common rails (prefer shorter, then alpha)
    sigs = sorted(
        [m for m in members if m in known_significant_nodes], key=lambda x: (len(x), x)
    )
    if sigs:
        return sigs[0]

    # 3. User-defined device terminals (e.g., M1.G) (prefer shorter, then alpha)
    dev_terms = sorted(
        [m for m in members if "." in m and not m.startswith("_implicit_")],
        key=lambda x: (len(x), x),
    )
    if dev_terms:
        return dev_terms[0]

    # 4. Any other non-implicit name
    non_implicit = sorted(
        [m for m in members if not m.startswith("_implicit_")],
        key=lambda x: (len(x), x),
    )
    if non_implicit:
        return non_implicit[0]

    # 5. Implicit name, only if allowed or no other option
    # The canonical_net_name itself might be an implicit one. Use its preferred form.
    # If allow_implicit_if_only_option is True, or if it's the only option.
    # The DSU find operation already gives a canonical representative.
    # If all other attempts fail, this means the canonical_net_name is likely an _implicit_ node.
    if allow_implicit_if_only_option or canonical_net_name.startswith("_implicit_"):
        return canonical_net_name

    # Fallback, should ideally be covered by one of the above.
    return canonical_net_name


def get_component_connectivity(graph, comp_name):
    """Helper to find nets a component is connected to and via which terminals."""
    connections = {}  # terminal_name -> canonical_net_name
    raw_connections = (
        []
    )  # list of {'term': ..., 'net_canon': ...} for ordering later if needed

    # For MultiGraph, we need to handle potentially multiple edges per node pair
    for u, v, edge_data in graph.edges(comp_name, data=True):
        neighbor_net_canonical = v if u == comp_name else u
        if graph.nodes[neighbor_net_canonical].get("node_kind") == "electrical_net":
            terminal = edge_data.get("terminal")
            if terminal:
                if (
                    terminal not in connections
                ):  # Keep first occurrence of each terminal
                    connections[terminal] = neighbor_net_canonical
                raw_connections.append(
                    {"term": terminal, "net_canon": neighbor_net_canonical}
                )
    return connections, raw_connections


def _get_component_nodes_data(graph):
    """Get all component nodes with their full attributes."""
    return {
        n: graph.nodes[n]
        for n in graph.nodes
        if graph.nodes[n].get("node_kind") == "component_instance"
    }


def _emit_declarations(component_nodes_data):
    """Emit all component declarations."""
    ast_statements = []
    all_declared_comp_names = sorted(
        [
            n
            for n, data in component_nodes_data.items()
            if not n.startswith("_internal_") and data.get("instance_type")
        ]
    )

    for comp_name in all_declared_comp_names:
        ast_statements.append(
            {
                "type": "declaration",
                "component_type": component_nodes_data[comp_name]["instance_type"],
                "instance_name": comp_name,
                "line": 0,
            }
        )
    return ast_statements, all_declared_comp_names


def _reconstruct_multi_terminal_blocks(
    graph, component_nodes_data, dsu, comp_names, processed_components
):
    """Reconstruct connection blocks for multi-terminal components."""
    ast_statements = []
    MULTI_TERMINAL_TYPES = {"Nmos", "Pmos", "Opamp"}

    for comp_name in comp_names:
        comp_type = component_nodes_data[comp_name]["instance_type"]
        if comp_type in MULTI_TERMINAL_TYPES:
            connections_map, _ = get_component_connectivity(graph, comp_name)
            if connections_map:
                block_connections = _create_block_connections(
                    comp_type, connections_map, dsu
                )
                if block_connections:
                    ast_statements.append(
                        {
                            "type": "component_connection_block",
                            "component_name": comp_name,
                            "connections": block_connections,
                            "line": 0,
                        }
                    )
                    processed_components.add(comp_name)
    return ast_statements


def _create_block_connections(comp_type, connections_map, dsu):
    """Create ordered block connections for a component."""
    terminal_order_preference = []
    if comp_type in ["Nmos", "Pmos"]:
        terminal_order_preference = ["G", "D", "S", "B"]
    elif comp_type == "Opamp":
        terminal_order_preference = ["IN+", "IN-", "OUT", "V+", "V-"]

    present_terminals = list(connections_map.keys())
    sorted_terminals = [t for t in terminal_order_preference if t in present_terminals]
    remaining_terminals = sorted(
        [t for t in present_terminals if t not in sorted_terminals]
    )
    final_sorted_terminals = sorted_terminals + remaining_terminals

    block_connections = []
    for term in final_sorted_terminals:
        net_canonical = connections_map[term]
        preferred_net_name = get_preferred_net_name_for_reconstruction(
            net_canonical, dsu, allow_implicit_if_only_option=True
        )
        block_connections.append({"terminal": term, "node": preferred_net_name})
    return block_connections


def _reconstruct_series_paths(graph, component_nodes_data, dsu, processed_components):
    """Reconstruct series and parallel paths."""
    ast_statements = []
    net_pair_to_components = _group_components_by_net_pairs(
        graph, component_nodes_data, processed_components
    )

    for (net1_canon, net2_canon), comps_in_group in net_pair_to_components.items():
        if not comps_in_group:
            continue

        path_elements = _create_path_elements(
            net1_canon, net2_canon, comps_in_group, component_nodes_data, dsu
        )
        ast_statements.append(
            {"type": "series_connection", "path": path_elements, "line": 0}
        )
        processed_components.update(comps_in_group)

    return ast_statements


def _group_components_by_net_pairs(graph, component_nodes_data, processed_components):
    """Group components by the nets they connect."""
    net_pair_to_components = {}
    MULTI_TERMINAL_TYPES = {"Nmos", "Pmos", "Opamp"}

    all_comp_names = sorted(
        [
            n
            for n, data in component_nodes_data.items()
            if data.get("instance_type")
            and (
                not n.startswith("_internal_")
                or data.get("instance_type") in ["controlled_source", "noise_source"]
            )
            and n not in processed_components
        ]
    )

    for comp_name in all_comp_names:
        comp_type = component_nodes_data[comp_name]["instance_type"]
        if comp_type not in MULTI_TERMINAL_TYPES:
            connections_map, _ = get_component_connectivity(graph, comp_name)
            distinct_nets = set(connections_map.values())

            if len(distinct_nets) == 2:
                valid_terminals = _get_valid_terminals(comp_type, connections_map)
                if len(valid_terminals) == 2:
                    nets_for_key = tuple(
                        sorted([connections_map[term] for term in valid_terminals])
                    )
                    if nets_for_key not in net_pair_to_components:
                        net_pair_to_components[nets_for_key] = []
                    net_pair_to_components[nets_for_key].append(comp_name)
    return net_pair_to_components


def _get_valid_terminals(comp_type, connections_map):
    """Get valid terminals for path reconstruction."""
    valid_terminals = set()
    if comp_type in ["V", "I"]:
        if "pos" in connections_map and "neg" in connections_map:
            valid_terminals.update(["pos", "neg"])
    elif comp_type in ["R", "C", "L", "controlled_source", "noise_source"]:
        path_terms = {"t1_series", "t2_series", "par_t1", "par_t2"}
        found_path_terms = {t for t in connections_map if t in path_terms}
        if len(found_path_terms) == 2:
            valid_terminals.update(found_path_terms)
    return valid_terminals


def _create_path_elements(
    net1_canon, net2_canon, comps_in_group, component_nodes_data, dsu
):
    """Create path elements for series/parallel reconstruction."""
    path_elements = [
        {
            "type": "node",
            "name": get_preferred_net_name_for_reconstruction(
                net1_canon, dsu, allow_implicit_if_only_option=True
            ),
        }
    ]

    if len(comps_in_group) == 1:
        path_elements.extend(
            _create_single_component_path(comps_in_group[0], component_nodes_data)
        )
    else:
        path_elements.append(
            _create_parallel_block(comps_in_group, component_nodes_data)
        )

    path_elements.append(
        {
            "type": "node",
            "name": get_preferred_net_name_for_reconstruction(
                net2_canon, dsu, allow_implicit_if_only_option=True
            ),
        }
    )
    return path_elements


def _create_single_component_path(comp_name, component_nodes_data):
    """Create path elements for a single component."""
    comp_data = component_nodes_data[comp_name]
    if comp_data["instance_type"] in ["V", "I"] and "polarity" in comp_data:
        return [
            {
                "type": "source",
                "name": comp_name,
                "polarity": comp_data["polarity"],
            }
        ]
    elif comp_name.startswith("_internal_"):
        if comp_data["instance_type"] == "controlled_source":
            return [
                {
                    "type": "controlled_source",
                    "expression": comp_data.get("expression", "ERROR_NO_EXPR"),
                    "direction": comp_data.get("direction", "->"),
                }
            ]
        elif comp_data["instance_type"] == "noise_source":
            return [
                {
                    "type": "noise_source",
                    "id": comp_data.get("id", "ERROR_NO_ID"),
                    "direction": comp_data.get("direction", "->"),
                }
            ]
    return [{"type": "component", "name": comp_name}]


def _create_parallel_block(comps_in_group, component_nodes_data):
    """Create a parallel block element."""
    parallel_block_elements = []
    for comp_name in sorted(comps_in_group):
        comp_data = component_nodes_data[comp_name]
        if comp_name.startswith("_internal_"):
            if comp_data["instance_type"] == "controlled_source":
                parallel_block_elements.append(
                    {
                        "type": "controlled_source",
                        "expression": comp_data.get("expression", "ERROR_NO_EXPR"),
                        "direction": comp_data.get("direction", "->"),
                    }
                )
            elif comp_data["instance_type"] == "noise_source":
                parallel_block_elements.append(
                    {
                        "type": "noise_source",
                        "id": comp_data.get("id", "ERROR_NO_ID"),
                        "direction": comp_data.get("direction", "->"),
                    }
                )
        elif comp_data["instance_type"] in ["V", "I"] and "polarity" in comp_data:
            parallel_block_elements.append(
                {
                    "type": "source",
                    "name": comp_name,
                    "polarity": comp_data["polarity"],
                }
            )
        else:
            parallel_block_elements.append({"type": "component", "name": comp_name})
    return {"type": "parallel_block", "elements": parallel_block_elements}


def _reconstruct_direct_assignments(dsu):
    """Reconstruct direct assignment statements."""
    ast_statements = []
    all_handled_aliases = set()
    all_canonical_representatives = dsu.get_all_canonical_representatives()

    for canonical_rep in sorted(list(all_canonical_representatives)):
        members = sorted(list(dsu.get_set_members(canonical_rep)))
        if len(members) > 1:
            preferred_target_name = get_preferred_net_name_for_reconstruction(
                canonical_rep, dsu, allow_implicit_if_only_option=True
            )
            for member_node in members:
                if member_node == preferred_target_name:
                    continue
                if member_node.startswith(
                    "_implicit_"
                ) and not preferred_target_name.startswith("_implicit_"):
                    continue

                alias_pair_key = frozenset({member_node, preferred_target_name})
                if alias_pair_key not in all_handled_aliases:
                    ast_statements.append(
                        {
                            "type": "direct_assignment",
                            "source_node": member_node,
                            "target_node": preferred_target_name,
                            "line": 0,
                        }
                    )
                    all_handled_aliases.add(alias_pair_key)
    return ast_statements


def graph_to_structured_ast(graph, dsu):
    """Convert graph back to structured AST representation."""
    processed_components = set()
    component_nodes_data = _get_component_nodes_data(graph)

    # 1. Emit declarations
    ast_statements, all_declared_comp_names = _emit_declarations(component_nodes_data)

    # 2. Reconstruct multi-terminal component blocks
    ast_statements.extend(
        _reconstruct_multi_terminal_blocks(
            graph,
            component_nodes_data,
            dsu,
            all_declared_comp_names,
            processed_components,
        )
    )

    # 3. Reconstruct series/parallel paths
    ast_statements.extend(
        _reconstruct_series_paths(
            graph, component_nodes_data, dsu, processed_components
        )
    )

    # 4. Reconstruct direct assignments
    ast_statements.extend(_reconstruct_direct_assignments(dsu))

    return ast_statements
