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
                    # Ensure GND/VDD special nodes remain canonical when creating implicit nodes
                    if current_attach_point_canonical in ['GND', 'VDD']:
                        # Don't create new implicit node - use the special node directly
                        next_attach_point_canonical = current_attach_point_canonical
                    else:
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
                    polarity = item['polarity']
                    if source_name not in declared_components: continue # Error already handled by validator ideally
                    source_node_name = declared_components[source_name]['instance_node_name']

                    # Store polarity as an attribute on the source component node
                    G.nodes[source_node_name]['polarity'] = polarity

                    # For (-+) polarity:
                    # - terminal 'neg' connects to current_attach_point (left side)
                    # - terminal 'pos' connects to next_attach_point (right side)
                    # For (+-) polarity, the opposite
                    if polarity == '(-+)':
                        G.add_edge(source_node_name, current_attach_point_canonical, terminal='neg')
                        G.add_edge(source_node_name, next_attach_point_canonical, terminal='pos')
                    else:
                        G.add_edge(source_node_name, current_attach_point_canonical, terminal='pos')
                        G.add_edge(source_node_name, next_attach_point_canonical, terminal='neg')
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
                            G.add_edge(element_node_name_in_graph, parallel_start_node_canonical, terminal='par_t1', key='par_t1')
                            G.add_edge(element_node_name_in_graph, parallel_end_node_canonical, terminal='par_t2', key='par_t2')

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


def graph_to_structured_ast(graph, dsu, remove_implicit_nodes=True):
    ast_statements = []
    processed_components = set()
    
    # Get all component and net nodes
    component_nodes = [n for n, data in graph.nodes(data=True) if data.get('node_kind') == 'component_instance']
    net_nodes = [n for n, data in graph.nodes(data=True) if data.get('node_kind') == 'electrical_net']
    comp_data_map = {name: graph.nodes[name] for name in component_nodes}

    # 1. Emit declarations
    for comp_name in sorted(n for n in component_nodes if not n.startswith('_internal_')):
        ast_statements.append({
            'type': 'declaration',
            'component_type': comp_data_map[comp_name]['instance_type'],
            'instance_name': comp_name,
            'line': 0
        })

    # 2. Find series paths
    def find_series_path(start_net):
        if start_net in visited_nets:
            return None
        
        path = [{'type': 'node', 'name': get_preferred_net_name_for_reconstruction(start_net, dsu)}]
        current_net = start_net
        visited_nets.add(current_net)
        
        while True:
            # Find unvisited components connected to current net
            connected_comps = []
            for comp in component_nodes:
                if comp in processed_components:
                    continue
                neighbors = list(graph.neighbors(comp))
                if current_net in neighbors:
                    connected_comps.append(comp)
            
            if not connected_comps:
                break
                
            # Take the first unvisited component
            comp_name = sorted(connected_comps)[0]
            processed_components.add(comp_name)
            
            # Add component to path
            comp_data = comp_data_map[comp_name]
            if comp_data.get('instance_type') == 'V':
                path.append({
                    'type': 'source',
                    'name': comp_name,
                    'polarity': comp_data.get('polarity', '(-+)')
                })
            else:
                path.append({
                    'type': 'component',
                    'name': comp_name
                })
            
            # Find next net
            next_nets = []
            for net in graph.neighbors(comp_name):
                if graph.nodes[net].get('node_kind') == 'electrical_net' and net != current_net and net not in visited_nets:
                    next_nets.append(net)
            
            if not next_nets:
                break
                
            next_net = next_nets[0]
            path.append({
                'type': 'node',
                'name': get_preferred_net_name_for_reconstruction(next_net, dsu)
            })
            current_net = next_net
            visited_nets.add(current_net)
        
        return path if len(path) > 1 else None

    # Process each valid starting net
    visited_nets = set()
    endpoint_nets = {n for n in net_nodes if len(list(graph.neighbors(n))) == 1}
    
    # First handle series paths
    for start_net in sorted(endpoint_nets):  # Sort for deterministic output
        path = find_series_path(start_net)
        if path:
            ast_statements.append({
                'type': 'series_connection',
                'path': path,
                'line': 0
            })

    # Mark remaining components as parallel if they share the same nets
    remaining_comps = [c for c in component_nodes if c not in processed_components]
    parallel_groups = {}
    
    for comp in remaining_comps:
        if comp in processed_components:
            continue
            
        comp_nets = frozenset(n for n in graph.neighbors(comp) if graph.nodes[n].get('node_kind') == 'electrical_net')
        if len(comp_nets) != 2:
            continue
            
        if comp_nets not in parallel_groups:
            parallel_groups[comp_nets] = []
        parallel_groups[comp_nets].append(comp)

    # Create series paths for parallel groups
    for nets, comps in parallel_groups.items():
        if not comps:
            continue
            
        nets_list = sorted(nets)
        path = [
            {'type': 'node', 'name': get_preferred_net_name_for_reconstruction(nets_list[0], dsu)},
            {'type': 'parallel_block', 'elements': [
                {'type': 'component', 'name': comp} for comp in sorted(comps)
            ]},
            {'type': 'node', 'name': get_preferred_net_name_for_reconstruction(nets_list[1], dsu)}
        ]
        
        ast_statements.append({
            'type': 'series_connection',
            'path': path,
            'line': 0
        })
        processed_components.update(comps)

    return ast_statements