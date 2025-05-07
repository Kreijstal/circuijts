# -*- coding: utf-8 -*-
"""Graph utilities for circuit analysis."""

import networkx as nx

class DSU:
    """
    Disjoint Set Union (DSU) data structure, also known as Union-Find.
    Used here to manage equivalences between electrical net names.
    """
    def __init__(self):
        self.parent = {}
        self.num_sets = 0

    def add_set(self, item):
        """Ensures an item is part of the DSU, creating a new set if it's new."""
        if item not in self.parent:
            self.parent[item] = item
            self.num_sets += 1

    def find(self, item):
        """Finds the representative (root) of the set containing item, with path compression."""
        self.add_set(item) # Ensure item is in DSU before finding
        if self.parent[item] == item:
            return item
        self.parent[item] = self.find(self.parent[item])  # Path compression
        return self.parent[item]

    def union(self, item1, item2):
        """Merges the sets containing item1 and item2."""
        root1 = self.find(item1)
        root2 = self.find(item2)
        if root1 != root2:
            self.parent[root1] = root2  # Simple union: make root1 child of root2
            self.num_sets -= 1
            return True  # Union occurred
        return False # Already in the same set

    def get_all_canonical_representatives(self):
        """Returns a set of all canonical representatives."""
        return {self.find(item) for item in self.parent}

    def get_set_members(self, representative_item):
        """Returns all items belonging to the same set as representative_item."""
        canonical_rep = self.find(representative_item)
        return {item for item in self.parent if self.find(item) == canonical_rep}


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
    G = nx.Graph()
    # Store component declarations: name -> {type, line, instance_node_name (same as name)}
    declared_components = {}
    # DSU to manage equivalence classes of electrical net names
    electrical_nets_dsu = DSU()

    implicit_node_idx = 0
    # For naming internally generated components like VCCS from parallel blocks
    internal_component_idx = 0

    # --- Pass 1: Process declarations and pre-populate DSU with known explicit net names ---
    for stmt in parsed_statements:
        stmt_type = stmt.get('type')
        if stmt_type == 'declaration':
            comp_type = stmt['component_type']
            inst_name = stmt['instance_name']
            # Store declaration info and add component instance node to graph
            declared_components[inst_name] = {'type': comp_type, 'line': stmt['line'], 'instance_node_name': inst_name}
            G.add_node(inst_name, node_kind='component_instance', instance_type=comp_type)

        # Pre-scan for all explicitly named nodes to add them to DSU early.
        # This helps in ensuring `find` always works on known items.
        elif stmt_type == 'component_connection_block':
            comp_name = stmt['component_name']
            for conn in stmt.get('connections', []):
                electrical_nets_dsu.add_set(conn['node']) # e.g., (node_gate)
                electrical_nets_dsu.add_set(f"{comp_name}.{conn['terminal']}") # e.g., (M1.G)
        elif stmt_type == 'direct_assignment':
            electrical_nets_dsu.add_set(stmt['source_node'])
            electrical_nets_dsu.add_set(stmt['target_node'])
        elif stmt_type == 'series_connection':
            for item in stmt.get('path', []):
                if item.get('type') == 'node':
                    electrical_nets_dsu.add_set(item['name'])
# --- Pass 2: Process connections and build graph structure using canonical net names ---
    for stmt in parsed_statements:
        stmt_type = stmt.get('type')

        if stmt_type == 'declaration':
            continue # Already handled

        elif stmt_type == 'component_connection_block':
            comp_name = stmt['component_name']
            if comp_name not in declared_components:
                # This case should ideally be caught by a validator before this stage
                print(f"AST_TO_GRAPH_WARNING: Component '{comp_name}' in block not declared. Skipping.")
                continue

            comp_node_name = declared_components[comp_name]['instance_node_name']

            for conn in stmt.get('connections', []):
                terminal_name = conn['terminal']
                # Net name explicitly mentioned in the connection, e.g., "node_gate"
                explicit_net_name_in_connection = conn['node']
                # The device terminal itself is also an electrical net, e.g., "M1.G"
                device_terminal_as_net_name = f"{comp_name}.{terminal_name}"

                # Crucial: This block implies these two nets are the same.
                electrical_nets_dsu.union(device_terminal_as_net_name, explicit_net_name_in_connection)

                # Connect the component to the *canonical representative* of this unified net.
                canonical_net_name = electrical_nets_dsu.find(explicit_net_name_in_connection)
                if not G.has_node(canonical_net_name): # Ensure canonical net node exists
                    G.add_node(canonical_net_name, node_kind='electrical_net')

                G.add_edge(comp_node_name, canonical_net_name, terminal=terminal_name)

        elif stmt_type == 'direct_assignment':
            # These two net names are declared to be the same net.
            electrical_nets_dsu.union(stmt['source_node'], stmt['target_node'])

            # Ensure canonical nodes exist in graph (if not already from pre-sscan or other stmts)
            for raw_node_name in [stmt['source_node'], stmt['target_node']]:
                canonical_name = electrical_nets_dsu.find(raw_node_name)
                if not G.has_node(canonical_name):
                    G.add_node(canonical_name, node_kind='electrical_net')

        elif stmt_type == 'series_connection':
            path = stmt.get('path', [])
            if not path or path[0].get('type') != 'node':
                # Parser should ensure paths start with a node.
                print(f"AST_TO_GRAPH_WARNING: Series path malformed or empty: {stmt.get('_path_str', 'N/A')}")
                continue

            # `current_attach_point` is always the canonical name of an electrical net.
            current_attach_point_canonical = electrical_nets_dsu.find(path[0]['name'])
            if not G.has_node(current_attach_point_canonical):
                 G.add_node(current_attach_point_canonical, node_kind='electrical_net')

            # Process elements from the second item onwards
            for i in range(1, len(path)):
                item = path[i]
                item_type = item.get('type')

                # Determine the `next_attach_point_canonical`
                # If the element after `item` is an explicit node, that's the next attach point.
                # Otherwise, if `item` is a connecting element (component, source, parallel_block),
                # an implicit node is needed.
                next_attach_point_canonical = None
                is_next_point_implicit = False

                if i + 1 < len(path) and path[i+1].get('type') == 'node':
                    next_attach_point_canonical = electrical_nets_dsu.find(path[i+1]['name'])
                elif item_type not in ['node', 'named_current', 'error']: # component, source, parallel_block
                    # This element needs a connection point after it, which will be implicit.
                    implicit_node_name_raw = f"_implicit_{implicit_node_idx}"
                    next_attach_point_canonical = electrical_nets_dsu.find(implicit_node_name_raw) # adds to DSU
                    is_next_point_implicit = True

                if next_attach_point_canonical and not G.has_node(next_attach_point_canonical):
                    G.add_node(next_attach_point_canonical, node_kind='electrical_net')

                # Handle the current item
                if item_type == 'component':
                    comp_name = item['name']
                    if comp_name not in declared_components: continue # Error already handled by validator ideally
                    comp_node_name = declared_components[comp_name]['instance_node_name']

                    # For 2-terminal components in series, use generic terminal names
                    G.add_edge(comp_node_name, current_attach_point_canonical, terminal='t1_series')
                    G.add_edge(comp_node_name, next_attach_point_canonical, terminal='t2_series')
                    current_attach_point_canonical = next_attach_point_canonical
                    if is_next_point_implicit: implicit_node_idx += 1

                elif item_type == 'source':
                    source_name = item['name']
                    if source_name not in declared_components: continue
                    source_node_name = declared_components[source_name]['instance_node_name']
                    polarity = item['polarity']

                    term_connected_to_current_attach = 'neg' if polarity == '(-+)' else 'pos'
                    term_connected_to_next_attach = 'pos' if polarity == '(-+)' else 'neg'

                    G.add_edge(source_node_name, current_attach_point_canonical, terminal=term_connected_to_current_attach)
                    G.add_edge(source_node_name, next_attach_point_canonical, terminal=term_connected_to_next_attach)
                    current_attach_point_canonical = next_attach_point_canonical
                    if is_next_point_implicit: implicit_node_idx += 1

                elif item_type == 'node': # This node becomes the new current_attach_point
                    current_attach_point_canonical = electrical_nets_dsu.find(item['name'])
                    # Ensure it exists in graph (should from pre-scan or previous step)
                    if not G.has_node(current_attach_point_canonical):
                         G.add_node(current_attach_point_canonical, node_kind='electrical_net')

                elif item_type == 'parallel_block':
                    parallel_start_node_canonical = current_attach_point_canonical
                    parallel_end_node_canonical = next_attach_point_canonical

                    for pel in item.get('elements', []):
                        element_node_name_in_graph = None
                        attrs = {'node_kind': 'component_instance'}

                        if pel['type'] == 'component':
                            if pel['name'] in declared_components:
                                element_node_name_in_graph = declared_components[pel['name']]['instance_node_name']
                            else: continue # Error
                        elif pel['type'] == 'controlled_source':
                            element_node_name_in_graph = f"_internal_cs_{internal_component_idx}"
                            attrs.update({'instance_type': 'controlled_source',
                                          'expression': pel['expression'], 'direction': pel['direction']})
                            internal_component_idx += 1
                        elif pel['type'] == 'noise_source':
                            element_node_name_in_graph = f"_internal_ns_{internal_component_idx}"
                            attrs.update({'instance_type': 'noise_source',
                                          'id': pel['id'], 'direction': pel['direction']})
                            internal_component_idx += 1

                        if element_node_name_in_graph:
                            if not G.has_node(element_node_name_in_graph):
                                G.add_node(element_node_name_in_graph, **attrs)
                            # Generic terminal names for elements within a parallel block
                            G.add_edge(element_node_name_in_graph, parallel_start_node_canonical, terminal='par_t1')
                            G.add_edge(element_node_name_in_graph, parallel_end_node_canonical, terminal='par_t2')

                    current_attach_point_canonical = parallel_end_node_canonical
                    if is_next_point_implicit: implicit_node_idx += 1

                elif item_type == 'named_current':
                    # Named currents are annotations on connections.
                    # This requires identifying the specific edge representing the "wire segment".
                    # For example, if path[i-1] was a component C, and it connected to
                    # current_attach_point_canonical via terminal T_prev of C.
                    # The edge (C_node, current_attach_point_canonical) with terminal=T_prev
                    # would get an attribute for this named current.
                    # This is advanced and depends on precise edge identification.
                    # For now, we'll skip adding it directly to the graph's structure
                    # but it could be added as an attribute to current_attach_point_canonical
                    # or the component connected *before* the current, if identifiable.
                    # print(f"AST_TO_GRAPH_INFO: Named current '{item['name']}' encountered, representation in graph TBD.")
                    pass


    # Optional: Create a "cleaner" graph where all net nodes are guaranteed to be their canonical names
    # This involves relabeling or creating a new graph.
    # For now, the existing graph G uses canonical names for edges, but some non-canonical
    # net nodes might exist if they were added before all unions were processed.
    # However, DSU lookups (`electrical_nets_dsu.find()`) ensure logical correctness.

    return G, electrical_nets_dsu

def get_preferred_net_name_for_reconstruction(canonical_net_name, dsu,
                                            known_significant_nodes=None,
                                            allow_implicit_if_only_option=False):
    if known_significant_nodes is None:
        known_significant_nodes = {'GND', 'VDD'}

    if not dsu or canonical_net_name not in dsu.parent:
        return canonical_net_name

    members = dsu.get_set_members(canonical_net_name)
    if not members: return canonical_net_name

    # Priority order for selecting a display name for a net
    # 1. User-defined, non-device terminal, non-significant common rail names
    user_named = sorted([m for m in members if not m.startswith("_implicit_") and '.' not in m and m not in known_significant_nodes])
    if user_named: return user_named[0]

    # 2. Known significant common rails
    sigs = sorted([m for m in members if m in known_significant_nodes])
    if sigs: return sigs[0]

    # 3. User-defined device terminals (e.g., M1.G)
    dev_terms = sorted([m for m in members if '.' in m and not m.startswith("_implicit_")])
    if dev_terms: return dev_terms[0]

    # 4. Any other non-implicit name (should be covered by user_named if exists)
    non_implicit = sorted([m for m in members if not m.startswith("_implicit_")])
    if non_implicit: return non_implicit[0]

    # 5. Implicit name, only if allowed or no other option
    if allow_implicit_if_only_option:
        return canonical_net_name # Which would be an implicit name if all others failed

    # Fallback: if we must return something and implicit is not allowed, this indicates an issue or an purely internal net.
    # For reconstruction, we might prefer to show its canonical form if it's an endpoint of a path.
    return canonical_net_name


def get_component_connectivity(graph, comp_name):
    """ Helper to find nets a component is connected to and via which terminals. """
    connections = {} # terminal_name -> canonical_net_name
    raw_connections = [] # list of {'term': ..., 'net_canon': ...} for ordering later if needed
    for _, neighbor_net_canonical, edge_data in graph.edges(comp_name, data=True):
        if graph.nodes[neighbor_net_canonical].get('node_kind') == 'electrical_net':
            terminal = edge_data.get('terminal')
            if terminal:
                connections[terminal] = neighbor_net_canonical
                raw_connections.append({'term': terminal, 'net_canon': neighbor_net_canonical})
    return connections, raw_connections


def graph_to_structured_ast(graph, dsu, remove_implicit_nodes=True):
    ast_statements = []
    processed_components = set()  # Components included in any AST statement
    visited_nets = set()  # Track visited nets to prevent infinite loops

    component_instance_nodes = [n for n, data in graph.nodes(data=True) if data.get('node_kind') == 'component_instance']
    comp_data_map = {name: graph.nodes[name] for name in component_instance_nodes}

    # 1. Emit Declarations
    for comp_name in component_instance_nodes:
        if not comp_name.startswith("_internal_"):  # Internal VCCS/Noise are not declared
            ast_statements.append({
                'type': 'declaration',
                'component_type': comp_data_map[comp_name]['instance_type'],
                'instance_name': comp_name,
                'line': 0  # Placeholder for reconstructed AST
            })

    # 2. Handle "Complex" Components (Multi-terminal like Nmos, or those with specific terminals)
    for comp_name in component_instance_nodes:
        if comp_name in processed_components or comp_name.startswith("_internal_"):
            continue

        instance_type = comp_data_map[comp_name]['instance_type']
        is_complex_type = instance_type in ["Nmos", "Pmos", "Opamp"]  # Add others

        _, raw_conns = get_component_connectivity(graph, comp_name)

        if is_complex_type or len(raw_conns) > 2:
            connections_ast = []
            for conn_info in sorted(raw_conns, key=lambda x: x['term']):
                connections_ast.append({
                    'terminal': conn_info['term'],
                    'node': get_preferred_net_name_for_reconstruction(conn_info['net_canon'], dsu, allow_implicit_if_only_option=True)
                })
            if connections_ast:
                ast_statements.append({
                    'type': 'component_connection_block',
                    'component_name': comp_name,
                    'connections': connections_ast,
                    'line': 0  # Placeholder for reconstructed AST
                })
                processed_components.add(comp_name)

    # 3. Iteratively find and emit series paths (incorporating parallel blocks)
    all_nets_canonical = [n for n, data in graph.nodes(data=True) if data.get('node_kind') == 'electrical_net']

    potential_path_starts_canon = sorted(
        [n_canon for n_canon in all_nets_canonical
         if not get_preferred_net_name_for_reconstruction(n_canon, dsu).startswith('_implicit_')],
        key=lambda x: get_preferred_net_name_for_reconstruction(x, dsu)
    )

    for start_net_canon in potential_path_starts_canon:
        if start_net_canon in visited_nets:
            continue

        stack = [(start_net_canon, [])]  # (current_net, current_path)

        while stack:
            current_net, current_path = stack.pop()

            if current_net in visited_nets:
                continue

            visited_nets.add(current_net)

            for comp_neighbor_name in graph.neighbors(current_net):
                if comp_neighbor_name in processed_components or \
                   graph.nodes[comp_neighbor_name].get('node_kind') != 'component_instance' or \
                   comp_neighbor_name.startswith("_internal_"):
                    continue

                comp_conns_map, _ = get_component_connectivity(graph, comp_neighbor_name)

                if current_net in comp_conns_map.values():
                    next_net = [net for term, net in comp_conns_map.items() if net != current_net]
                    if next_net:
                        next_net = next_net[0]
                        stack.append((next_net, current_path + [{'type': 'component', 'name': comp_neighbor_name}]))

                processed_components.add(comp_neighbor_name)

    return ast_statements