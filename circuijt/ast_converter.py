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
        dsu (DSU): The Disjoint Set Union object containing canonical net mappings.

    Returns:
        list: A list of "flattened" AST statements.
    """
    flattened_statements = []
    declared_components_info = {} # Store type for arity checks if needed, and to process only declared

    # Pass 1: Collect declarations and build a component info map
    for stmt in regular_ast_statements:
        if stmt['type'] == 'declaration':
            flattened_statements.append(stmt.copy()) # Keep declarations as is
            declared_components_info[stmt['instance_name']] = {
                'type': stmt['component_type'],
                'line': stmt.get('line', 0)
            }

    # Pass 2: Generate graph to easily get all explicit connections
    # This leverages the existing robust logic in ast_to_graph.
    # We are essentially using the graph as the most reliable way to "flatten"
    # the various connection syntaxes.
    graph, _ = ast_to_graph(regular_ast_statements) # DSU from ast_to_graph is re-created, use the passed one for lookups

    component_pins_connected = set() # To avoid duplicate pin_connection entries if multiple AST stmts refer to same connection

    for node_name, node_data in graph.nodes(data=True):
        if node_data.get('node_kind') == 'component_instance':
            comp_instance_name = node_name
            # Handle both declared and internal components
            is_internal = comp_instance_name.startswith("_internal_")
            if not is_internal and comp_instance_name not in declared_components_info:
                continue
            
            # For internal voltage sources, also include their attributes
            if 'polarity' in node_data:
                flattened_statements.append({
                    'type': 'declaration',
                    'component_type': 'V',  # It's a voltage source
                    'instance_name': comp_instance_name,
                    'polarity': node_data['polarity'],
                    'internal': True,
                    'line': 0
                })
            
            # Iterate over edges connected to this component instance
            for _, neighbor_name, edge_data in graph.edges(comp_instance_name, data=True):
                if graph.nodes[neighbor_name].get('node_kind') == 'electrical_net':
                    terminal_name = edge_data.get('terminal')
                    # The neighbor_name is already a canonical net name from the graph construction
                    canonical_net_name = neighbor_name 
                    
                    if terminal_name:
                        pin_key = (comp_instance_name, terminal_name)
                        if pin_key not in component_pins_connected:
                            pin_conn = {
                                'type': 'pin_connection',
                                'component_instance': comp_instance_name,
                                'terminal': terminal_name,
                                'net': canonical_net_name,
                                'line': declared_components_info.get(comp_instance_name, {}).get('line', 0)
                            }
                            # Add parallel_group flag if the component is in a parallel block
                            if node_data.get('in_parallel'):
                                pin_conn['parallel_group'] = True
                                pin_conn['parallel_nets'] = node_data.get('parallel_nets', [])
                            flattened_statements.append(pin_conn)
                            component_pins_connected.add(pin_key)

    # Pass 3: Add net aliases from the DSU structure
    # This makes the flattened AST more self-contained regarding net equivalences
    processed_dsu_roots = set()
    # Sort DSU items for deterministic output
    sorted_dsu_keys = sorted(list(dsu.parent.keys()))

    for item in sorted_dsu_keys:
        canonical_rep = dsu.find(item)
        if canonical_rep in processed_dsu_roots:
            continue
        
        members = sorted(list(dsu.get_set_members(canonical_rep)))
        for member_name in members:
            if member_name != canonical_rep and not member_name.startswith("_implicit_"): 
                # Add alias if member is not itself the canonical root and not an implicit node
                flattened_statements.append({
                    'type': 'net_alias',
                    'source_net': member_name, # The user-visible name
                    'canonical_net': canonical_rep,
                    'line': 0 # Aliases don't directly map to a single line from original AST
                })
        processed_dsu_roots.add(canonical_rep)
        
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