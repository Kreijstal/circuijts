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
            self.preferred_roots = {'GND', 'VDD'} # Default preferred roots
        else:
            self.preferred_roots = set(preferred_roots)
        
        # Define a hierarchy for preferred roots if they are unioned
        # Lower index = higher preference (e.g., GND is most preferred)
        self.preferred_root_order = ['GND', 'VDD'] # Extend as needed

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
                except ValueError: # root1 is preferred but not in order list
                    idx1 = float('inf')
                try:
                    idx2 = self.preferred_root_order.index(root2)
                except ValueError: # root2 is preferred but not in order list
                    idx2 = float('inf')

                if idx1 < idx2: # root1 has higher preference
                    self.parent[root2] = root1
                elif idx2 < idx1: # root2 has higher preference
                    self.parent[root1] = root2
                else: # Same preference or both not in ordered list (but are in self.preferred_roots)
                      # Fallback to alphabetical or let root2 win for determinism
                    if root1 < root2: # Arbitrary but deterministic tie-break
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
    G = nx.MultiGraph()  # Changed from Graph() to properly handle multiple terminals to same net
    # Store component declarations: name -> {type, line, instance_node_name (same as name)}
    declared_components = {}
    # DSU to manage equivalence classes of electrical net names
    electrical_nets_dsu = DSU()

    # Initialize special nodes like GND and VDD in DSU first
    # This ensures they become canonical representatives for their sets
    for special_node in ['GND', 'VDD']:
        electrical_nets_dsu.add_set(special_node)

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

                # MODIFICATION START: Ensure connectivity for referenced device terminals
                if '.' in explicit_net_name_in_connection:
                    referenced_comp_name, referenced_term_name = explicit_net_name_in_connection.split('.', 1)
                    if referenced_comp_name in declared_components:
                        # Connect the referenced component (e.g., M1) to this same canonical_net_name
                        # (which is find(M1.D)) via its specified terminal (e.g., D).
                        G.add_edge(referenced_comp_name, canonical_net_name, terminal=referenced_term_name)
                # MODIFICATION END

        elif stmt_type == 'direct_assignment':
            s_node, t_node = stmt['source_node'], stmt['target_node']
            electrical_nets_dsu.union(s_node, t_node)
            canonical_net = electrical_nets_dsu.find(s_node)  # Both s_node and t_node now map to same canonical net

            # Ensure the canonical net exists in graph
            if not G.has_node(canonical_net):
                G.add_node(canonical_net, node_kind='electrical_net')
            
            # Handle device terminals in direct assignments
            for node_name in [s_node, t_node]:
                if '.' in node_name:  # It's a device terminal like M1.D
                    comp_name, term = node_name.split('.', 1)
                    if comp_name in declared_components:
                        G.add_edge(comp_name, canonical_net, terminal=term)

        elif stmt_type == 'series_connection':
            path = stmt.get('path', [])
            if not path or path[0].get('type') != 'node':
                # Parser should ensure paths start with a node.
                print(f"AST_TO_GRAPH_WARNING: Series path malformed or empty: {stmt.get('_path_str', 'N/A')}")
                continue

            # `current_attach_point` is always the canonical name of an electrical net.
            start_node_original_name = path[0]['name']
            current_attach_point_canonical = electrical_nets_dsu.find(start_node_original_name)
            if not G.has_node(current_attach_point_canonical):
                 G.add_node(current_attach_point_canonical, node_kind='electrical_net')

            # MODIFICATION START: Ensure connectivity for start node if it's a device terminal
            if '.' in start_node_original_name:
                comp_part, term_part = start_node_original_name.split('.', 1)
                if comp_part in declared_components:
                    G.add_edge(comp_part, current_attach_point_canonical, terminal=term_part)
            # MODIFICATION END

            # Process elements from the second item onwards
            for i in range(1, len(path)):
                item = path[i]
                item_type = item.get('type')

                # Skip if item is a node - it becomes the new current_attach_point for next iteration
                if item_type == 'node':
                    original_node_name_in_path = item['name']
                    current_attach_point_canonical = electrical_nets_dsu.find(original_node_name_in_path)
                    if not G.has_node(current_attach_point_canonical):
                         G.add_node(current_attach_point_canonical, node_kind='electrical_net')
                    if '.' in original_node_name_in_path:
                        comp_part, term_part = original_node_name_in_path.split('.', 1)
                        if comp_part in declared_components:
                            G.add_edge(comp_part, current_attach_point_canonical, terminal=term_part)
                    continue

                # Item is a component, source, or parallel_block - determine next attach point
                next_attach_point_canonical = None
                created_new_implicit_node = False

                if i + 1 < len(path) and path[i+1].get('type') == 'node':
                    next_explicit_node_name = path[i+1]['name']
                    next_attach_point_canonical = electrical_nets_dsu.find(next_explicit_node_name)
                else:
                    # Need an implicit node after this item
                    implicit_node_name_raw = f"_implicit_{implicit_node_idx}"
                    next_attach_point_canonical = electrical_nets_dsu.find(implicit_node_name_raw)
                    if not G.has_node(next_attach_point_canonical):
                        created_new_implicit_node = True
                
                if next_attach_point_canonical and not G.has_node(next_attach_point_canonical):
                    G.add_node(next_attach_point_canonical, node_kind='electrical_net')

                # Handle structural items (component, source, parallel_block)
                if item_type == 'component':
                    comp_name = item['name']
                    if comp_name not in declared_components: continue
                    comp_node_name = declared_components[comp_name]['instance_node_name']
                    G.add_edge(comp_node_name, current_attach_point_canonical, terminal='t1_series', key='t1_series')
                    G.add_edge(comp_node_name, next_attach_point_canonical, terminal='t2_series', key='t2_series')

                elif item_type == 'source':
                    source_name = item['name']
                    polarity = item['polarity'] # Expected to be "-+" or "+-"
                    if source_name not in declared_components: continue
                    source_node_name = declared_components[source_name]['instance_node_name']
                    G.nodes[source_node_name]['polarity'] = polarity
                    
                    # Determine if standard polarity (-+) is used
                    # Standard: neg terminal connects to current_attach_point, pos to next_attach_point
                    # Reversed: pos terminal connects to current_attach_point, neg to next_attach_point
                    is_standard_polarity = False # Default to False (reversed or unspecified)
                    if polarity == "-+":
                        is_standard_polarity = True
                    # No explicit else needed, if polarity is not "-+", is_standard_polarity remains False,
                    # implying reversed polarity for "+-" or other cases.

                    if is_standard_polarity:
                        G.add_edge(source_name, current_attach_point_canonical, terminal='neg', key='neg')
                        G.add_edge(source_name, next_attach_point_canonical, terminal='pos', key='pos')
                    else: # Handles reversed polarity like "+-"
                        G.add_edge(source_name, current_attach_point_canonical, terminal='pos', key='pos')
                        G.add_edge(source_name, next_attach_point_canonical, terminal='neg', key='neg')
                
                elif item_type == 'parallel_block':
                    for pel in item.get('elements', []):
                        element_node_name_in_graph = None
                        attrs = {'node_kind': 'component_instance'}
                        if pel['type'] == 'component':
                            if pel['name'] in declared_components:
                                element_node_name_in_graph = declared_components[pel['name']]['instance_node_name']
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
                            G.add_edge(element_node_name_in_graph, current_attach_point_canonical, terminal='par_t1', key='par_t1')
                            G.add_edge(element_node_name_in_graph, next_attach_point_canonical, terminal='par_t2', key='par_t2')

                # Update current attach point and implicit node counter
                current_attach_point_canonical = next_attach_point_canonical
                if created_new_implicit_node:
                    implicit_node_idx += 1

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

    # Priority:
    # 1. User-defined, non-device terminal, non-significant common rail names (prefer shorter, then alpha)
    user_named = sorted([m for m in members if not m.startswith("_implicit_") and '.' not in m and m not in known_significant_nodes], key=lambda x: (len(x), x))
    if user_named: return user_named[0]

    # 2. Known significant common rails (prefer shorter, then alpha)
    sigs = sorted([m for m in members if m in known_significant_nodes], key=lambda x: (len(x), x))
    if sigs: return sigs[0]

    # 3. User-defined device terminals (e.g., M1.G) (prefer shorter, then alpha)
    dev_terms = sorted([m for m in members if '.' in m and not m.startswith("_implicit_")], key=lambda x: (len(x), x))
    if dev_terms: return dev_terms[0]
    
    # 4. Any other non-implicit name
    non_implicit = sorted([m for m in members if not m.startswith("_implicit_")], key=lambda x: (len(x),x))
    if non_implicit: return non_implicit[0]


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
    """ Helper to find nets a component is connected to and via which terminals. """
    connections = {} # terminal_name -> canonical_net_name
    raw_connections = [] # list of {'term': ..., 'net_canon': ...} for ordering later if needed
    
    # For MultiGraph, we need to handle potentially multiple edges per node pair
    for u, v, edge_data in graph.edges(comp_name, data=True):
        neighbor_net_canonical = v if u == comp_name else u
        if graph.nodes[neighbor_net_canonical].get('node_kind') == 'electrical_net':
            terminal = edge_data.get('terminal')
            if terminal:
                if terminal not in connections:  # Keep first occurrence of each terminal
                    connections[terminal] = neighbor_net_canonical
                raw_connections.append({'term': terminal, 'net_canon': neighbor_net_canonical})
    return connections, raw_connections


def graph_to_structured_ast(graph, dsu):
    ast_statements = []
    processed_components = set()

    component_nodes_data = {n: data for n, data in graph.nodes(data=True) if data.get('node_kind') == 'component_instance'}
    all_declared_comp_names = sorted([
        n for n, data in component_nodes_data.items()
        if not n.startswith('_internal_') and data.get('instance_type')
    ])

    # 1. Emit all declarations first
    for comp_name in all_declared_comp_names:
        ast_statements.append({
            'type': 'declaration',
            'component_type': component_nodes_data[comp_name]['instance_type'],
            'instance_name': comp_name,
            'line': 0
        })

    MULTI_TERMINAL_TYPES = {"Nmos", "Pmos", "Opamp"}

    # 2. Reconstruct Component Connection Blocks for multi-terminal components
    for comp_name in all_declared_comp_names:
        comp_type = component_nodes_data[comp_name]['instance_type']
        if comp_type in MULTI_TERMINAL_TYPES:
            connections_map, _ = get_component_connectivity(graph, comp_name)
            if connections_map:
                block_connections = []
                terminal_order_preference = []
                if comp_type in ["Nmos", "Pmos"]: terminal_order_preference = ['G', 'D', 'S', 'B']
                elif comp_type == "Opamp": terminal_order_preference = ['IN+', 'IN-', 'OUT', 'V+', 'V-']

                present_terminals = list(connections_map.keys())
                sorted_terminals_for_block = [t for t in terminal_order_preference if t in present_terminals]
                remaining_terminals = sorted([t for t in present_terminals if t not in sorted_terminals_for_block])
                final_sorted_terminals_for_block = sorted_terminals_for_block + remaining_terminals
                
                for term in final_sorted_terminals_for_block:
                    net_canonical = connections_map[term]
                    preferred_net_name = get_preferred_net_name_for_reconstruction(
                        net_canonical, dsu, allow_implicit_if_only_option=True
                    )
                    block_connections.append({'terminal': term, 'node': preferred_net_name})
                
                if block_connections:
                    ast_statements.append({
                        'type': 'component_connection_block',
                        'component_name': comp_name,
                        'connections': block_connections,
                        'line': 0
                    })
                    processed_components.add(comp_name)

    # 3. Reconstruct series/parallel paths for remaining components (including internal behavioral ones)
    net_pair_to_components = {}
    # Include both declared components and internal behavioral components
    #all_comp_names_in_graph = sorted([
    #    n for n, data in component_nodes_data.items()
    #    if (data.get('instance_type') and
    #       (not n.startswith('_internal_') or
    #       data.get('instance_type') in ['controlled_source', 'noise_source'])
    #])        remaining_for_paths = [c for c in all_declared_comp_names if c not in processed_components]

    #remaining_for_paths = [c for c in all_comp_names_in_graph if c not in processed_components]
    remaining_for_paths = [c for c in all_declared_comp_names if c not in processed_components]

    for comp_name in remaining_for_paths:
        comp_data = component_nodes_data[comp_name]
        comp_type = comp_data['instance_type']
        if comp_type not in MULTI_TERMINAL_TYPES: # R, C, L, V, I, controlled_source, noise_source
            connections_map, _ = get_component_connectivity(graph, comp_name)
            distinct_nets = set(connections_map.values())
            
            if len(distinct_nets) == 2:
                valid_terminals = set()
                if comp_type in ['V', 'I']:
                    if 'pos' in connections_map and 'neg' in connections_map:
                         valid_terminals.update(['pos', 'neg'])
                elif comp_type in ['R', 'C', 'L']:
                    path_terms = {'t1_series', 't2_series', 'par_t1', 'par_t2'}
                    found_path_terms = {t for t in connections_map if t in path_terms}
                    if len(found_path_terms) == 2:
                         valid_terminals.update(found_path_terms)
                
                if len(valid_terminals) == 2:
                    nets_for_key = tuple(sorted([connections_map[term] for term in valid_terminals]))
                    if nets_for_key not in net_pair_to_components:
                        net_pair_to_components[nets_for_key] = []
                    net_pair_to_components[nets_for_key].append(comp_name)

    # Create series paths with parallel blocks
    for (net1_canon, net2_canon), comps_in_group in net_pair_to_components.items():
        if not comps_in_group: continue

        path_elements = [{'type': 'node', 'name': get_preferred_net_name_for_reconstruction(net1_canon, dsu, allow_implicit_if_only_option=True)}]
        
        if len(comps_in_group) == 1:
            comp_name = comps_in_group[0]
            comp_data = component_nodes_data[comp_name]
            if comp_data['instance_type'] in ['V','I'] and 'polarity' in comp_data:
                path_elements.append({'type': 'source', 'name': comp_name, 'polarity': comp_data['polarity']})
            elif comp_name.startswith('_internal_'):
                if comp_data['instance_type'] == 'controlled_source':
                    path_elements.append({
                        'type': 'controlled_source',
                        'expression': comp_data.get('expression', 'ERROR_NO_EXPR'),
                        'direction': comp_data.get('direction', '->')
                    })
                elif comp_data['instance_type'] == 'noise_source':
                    path_elements.append({
                        'type': 'noise_source',
                        'id': comp_data.get('id', 'ERROR_NO_ID'),
                        'direction': comp_data.get('direction', '->')
                    })
            else:
                path_elements.append({'type': 'component', 'name': comp_name})
            processed_components.add(comp_name)
        else:
            parallel_block_elements = []
            for comp_name in sorted(comps_in_group):
                comp_data = component_nodes_data[comp_name]
                if comp_name.startswith('_internal_'):
                    if comp_data['instance_type'] == 'controlled_source':
                        parallel_block_elements.append({
                            'type': 'controlled_source',
                            'expression': comp_data.get('expression', 'ERROR_NO_EXPR'),
                            'direction': comp_data.get('direction', '->')
                        })
                    elif comp_data['instance_type'] == 'noise_source':
                        parallel_block_elements.append({
                            'type': 'noise_source',
                            'id': comp_data.get('id', 'ERROR_NO_ID'),
                            'direction': comp_data.get('direction', '->')
                        })
                elif comp_data['instance_type'] in ['V','I'] and 'polarity' in comp_data:
                    parallel_block_elements.append({
                        'type': 'source',
                        'name': comp_name,
                        'polarity': comp_data['polarity']
                    })
                else:
                    parallel_block_elements.append({'type': 'component', 'name': comp_name})
                processed_components.add(comp_name)
            path_elements.append({'type': 'parallel_block', 'elements': parallel_block_elements})
        
        path_elements.append({'type': 'node', 'name': get_preferred_net_name_for_reconstruction(net2_canon, dsu, allow_implicit_if_only_option=True)})
        
        ast_statements.append({
            'type': 'series_connection',
            'path': path_elements,
            'line': 0
        })

    # 4. Reconstruct Direct Assignments (Net Aliases)
    all_handled_aliases = set()
    all_canonical_representatives = dsu.get_all_canonical_representatives()
    for canonical_rep in sorted(list(all_canonical_representatives)):
        members = sorted(list(dsu.get_set_members(canonical_rep)))
        if len(members) > 1:
            preferred_target_name = get_preferred_net_name_for_reconstruction(
                canonical_rep, dsu, allow_implicit_if_only_option=True
            )
            for member_node in members:
                if member_node == preferred_target_name: continue
                if member_node.startswith("_implicit_") and not preferred_target_name.startswith("_implicit_"):
                    continue
                
                alias_pair_key = frozenset({member_node, preferred_target_name})
                if alias_pair_key not in all_handled_aliases:
                    ast_statements.append({
                        'type': 'direct_assignment',
                        'source_node': member_node,
                        'target_node': preferred_target_name,
                        'line': 0
                    })
                    all_handled_aliases.add(alias_pair_key)
                    
    return ast_statements