# -*- coding: utf-8 -*-
"""AST conversion utilities between regular and flattened representations."""

from .graph_utils import ast_to_graph, graph_to_structured_ast, DSU
import networkx as nx

def ast_to_flattened_ast(regular_ast_statements, dsu):
    """
    Converts a regular AST (potentially with series/parallel constructs)
    into a "flattened" AST consisting mainly of declarations and
    direct pin-to-canonical_net connections.

    Args:
        regular_ast_statements (list): List of AST statements from parser or graph_to_structured_ast.
        dsu (DSU): The Disjoint Set Union object containing canonical net mappings
                   relevant to the `regular_ast_statements`.

    Returns:
        list: A list of "flattened" AST statements.
    """
    flattened_statements = []
    # To quickly find existing declarations by instance name for updates
    declaration_indices = {}
    # To store original info, though graph node data might be more comprehensive for type
    # declared_components_info = {}

    # Pass 1: Process declarations from the input regular_ast_statements
    for stmt in regular_ast_statements:
        if stmt['type'] == 'declaration':
            instance_name = stmt['instance_name']
            decl_idx = len(flattened_statements)
            flattened_statements.append({
                'type': 'declaration',
                'component_type': stmt['component_type'],
                'instance_name': instance_name,
                'line': stmt.get('line', 0)
                # Preserve other attributes from original declaration if any
            })
            declaration_indices[instance_name] = decl_idx
            # declared_components_info[instance_name] = {
            #     'type': stmt['component_type'],
            #     'line': stmt.get('line', 0)
            # }

    # Generate graph from the same regular_ast_statements.
    # The DSU from this graph build (`temp_dsu_for_graph`) is used internally by ast_to_graph
    # to resolve net names to canonical forms *within the graph structure*.
    # The `dsu` argument passed to *this function* is for interpreting net names
    # when generating `net_alias` statements at the end.
    graph, _ = ast_to_graph(regular_ast_statements)

    # Pass 2: Iterate graph nodes. Add declarations for new internal components.
    # Update existing declarations with details derived from graph (e.g., polarity for sources).
    for node_name, node_data in graph.nodes(data=True):
        if node_data.get('node_kind') == 'component_instance':
            comp_instance_name = node_name
            instance_graph_type = node_data.get('instance_type') # Type from graph node

            if comp_instance_name.startswith("_internal_"):
                # This is an internal component (e.g., controlled source from parallel block).
                # Add its declaration if it wasn't somehow already present (e.g. if regular_ast was already flattened).
                if comp_instance_name not in declaration_indices:
                    internal_decl_attrs = {
                        'expression': node_data.get('expression'),
                        'direction': node_data.get('direction'),
                        'id': node_data.get('id'),
                        'polarity': node_data.get('polarity') # For internal V/I sources if any
                    }
                    internal_decl_stmt = {
                        'type': 'declaration',
                        'component_type': instance_graph_type,
                        'instance_name': comp_instance_name,
                        'internal': True,
                        'line': node_data.get('line', 0), # Or a default line
                        **{k:v for k,v in internal_decl_attrs.items() if v is not None}
                    }
                    flattened_statements.append(internal_decl_stmt)
                    declaration_indices[comp_instance_name] = len(flattened_statements) - 1
            else:
                # This is a regular, user-declared component (e.g., "V1", "R1").
                # Its declaration should ideally exist from Pass 1.
                if comp_instance_name in declaration_indices:
                    existing_decl_idx = declaration_indices[comp_instance_name]
                    # Update it with info from graph if not already present (e.g., polarity for sources)
                    if 'polarity' in node_data and 'polarity' not in flattened_statements[existing_decl_idx]:
                        flattened_statements[existing_decl_idx]['polarity'] = node_data['polarity']
                        # flattened_statements[existing_decl_idx]['_graph_augmented'] = True # Optional marker
                else:
                    # Anomaly: component in graph wasn't in original regular_ast declarations and isn't internal.
                    # This might indicate an issue with the input regular_ast_statements.
                    # ASTValidator should catch undeclared components if regular_ast was from parser.
                    # If regular_ast itself was a transformation output, it might be missing a decl.
                    print(f"Warning (ast_to_flattened_ast): Graph component '{comp_instance_name}' (type: {instance_graph_type}) "
                          f"was not found in original declarations and is not an '_internal_' component. Adding a basic declaration.")
                    basic_decl = {
                        'type': 'declaration',
                        'component_type': instance_graph_type,
                        'instance_name': comp_instance_name,
                        'line': node_data.get('line',0),
                    }
                    if 'polarity' in node_data: basic_decl['polarity'] = node_data['polarity']
                    # Add other relevant attributes if available and appropriate
                    flattened_statements.append(basic_decl)
                    declaration_indices[comp_instance_name] = len(flattened_statements) - 1


    # Pass 3: Add pin_connection statements from graph edges
    component_pins_connected = set() # To avoid duplicate pin_connection entries
    for node_name, node_data in graph.nodes(data=True): # Iterate components in graph
        if node_data.get('node_kind') == 'component_instance':
            comp_instance_name = node_name
            
            # Iterate over edges connected to this component instance
            for _, neighbor_name, edge_data in graph.edges(comp_instance_name, data=True):
                if graph.nodes[neighbor_name].get('node_kind') == 'electrical_net':
                    terminal_name = edge_data.get('terminal')
                    # neighbor_name is already a canonical net name from the graph construction (ast_to_graph)
                    canonical_net_name = neighbor_name
                    
                    if terminal_name: # Ensure there is a terminal specified on the edge
                        pin_key = (comp_instance_name, terminal_name, canonical_net_name) # Include net to distinguish multi-pin to same net
                        if pin_key not in component_pins_connected:
                            pin_conn = {
                                'type': 'pin_connection',
                                'component_instance': comp_instance_name,
                                'terminal': terminal_name,
                                'net': canonical_net_name,
                                'line': 0 # Line number for pin connections is hard to trace back accurately
                            }
                            flattened_statements.append(pin_conn)
                            component_pins_connected.add(pin_key)

    # Pass 4: Add net aliases for equivalent nets, using the DSU passed into this function.
    added_aliases = set()
    # Ensure all nets involved in aliases are in DSU for find to work without auto-adding
    # This can be done by iterating through all unique net names seen in pin_connections
    # and adding them to the DSU if not present. Or assume the DSU is comprehensive.
    for net_name_original_case in dsu.parent: # Iterate over all known net names in the DSU
        canonical_net = dsu.find(net_name_original_case)
        # Only add alias if the original name is different from its canonical form
        # and this specific alias pair (order-insensitive) hasn't been added.
        # Also, avoid aliasing a net to itself if it's already canonical.
        if net_name_original_case != canonical_net:
            alias_pair = tuple(sorted((net_name_original_case, canonical_net)))
            if alias_pair not in added_aliases:
                flattened_statements.append({
                    'type': 'net_alias',
                    'source_net': net_name_original_case, # The non-canonical name
                    'canonical_net': canonical_net,    # Its canonical representative
                    'line': 0
                })
                added_aliases.add(alias_pair)

    return flattened_statements

def flattened_ast_to_regular_ast(flattened_ast_statements):
    """
    Converts a "flattened" AST back into a regular, structured AST
    (similar to what graph_to_structured_ast produces).

    Args:
        flattened_ast_statements (list): List of "flattened" AST statements.

    Returns:
        list: A list of regular AST statements.
    """
    reconstructed_graph = nx.MultiGraph()
    reconstructed_dsu = DSU(preferred_roots={'GND', 'VDD'}) # Initialize with preferences
    
    declared_components_from_flat = {}
    parallel_components = set()  # Track components that should be in parallel

    # Pass 1: Populate DSU with all net names mentioned and process declarations
    for stmt in flattened_ast_statements:
        if stmt['type'] == 'declaration':
            comp_type = stmt['component_type']
            inst_name = stmt['instance_name']
            reconstructed_graph.add_node(inst_name, node_kind='component_instance', instance_type=comp_type)
            declared_components_from_flat[inst_name] = {'type': comp_type, 'line': stmt.get('line',0)}
        elif stmt['type'] == 'pin_connection':
            reconstructed_dsu.add_set(stmt['net'])
        elif stmt['type'] == 'net_alias':
            reconstructed_dsu.add_set(stmt['source_net'])
            reconstructed_dsu.add_set(stmt['canonical_net'])

    # Pass 2: Process net aliases to build DSU structure
    for stmt in flattened_ast_statements:
        if stmt['type'] == 'net_alias':
            reconstructed_dsu.union(stmt['source_net'], stmt['canonical_net'])

    # Pass 3: Process pin connections to build graph edges and identify parallel components
    component_connections = {}  # Track component terminal connections
    for stmt in flattened_ast_statements:
        if stmt['type'] == 'pin_connection':
            comp_instance = stmt['component_instance']
            terminal = stmt['terminal']
            net_from_pin_stmt = stmt['net']
            canonical_net_for_connection = reconstructed_dsu.find(net_from_pin_stmt)

            if not reconstructed_graph.has_node(canonical_net_for_connection):
                reconstructed_graph.add_node(canonical_net_for_connection, node_kind='electrical_net')
            
            # Ensure component node exists
            if not reconstructed_graph.has_node(comp_instance):
                if comp_instance.startswith("_internal_"):
                     print(f"Warning: Internal component {comp_instance} found in pin_connection, type info might be missing.")

            reconstructed_graph.add_edge(comp_instance, canonical_net_for_connection, key=terminal, terminal=terminal)

            # Track component connections for parallel detection
            if comp_instance not in component_connections:
                component_connections[comp_instance] = set()
            component_connections[comp_instance].add(canonical_net_for_connection)

    # Identify parallel components by finding those connected to the same nets
    for comp1, nets1 in component_connections.items():
        if len(nets1) == 2:  # Only consider 2-terminal components for parallel groups
            for comp2, nets2 in component_connections.items():
                if comp1 < comp2 and nets1 == nets2:  # Use < to avoid duplicate pairs
                    parallel_components.add(comp1)
                    parallel_components.add(comp2)
                    # Add parallel component attribute to graph nodes
                    reconstructed_graph.nodes[comp1]['in_parallel'] = True
                    reconstructed_graph.nodes[comp2]['in_parallel'] = True
                    # Add shared nets attribute to help graph_to_structured_ast
                    reconstructed_graph.nodes[comp1]['parallel_nets'] = list(nets1)
                    reconstructed_graph.nodes[comp2]['parallel_nets'] = list(nets1)

    # Pass 4: Call the existing graph_to_structured_ast with parallel info preserved
    regular_ast = graph_to_structured_ast(reconstructed_graph, reconstructed_dsu)
    
    return regular_ast