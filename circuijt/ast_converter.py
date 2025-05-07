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

    # Pass 1: Extract declarations and start building component info
    declared_components_info = {}
    for stmt in regular_ast_statements:
        if stmt['type'] == 'declaration':
            declared_components_info[stmt['instance_name']] = {
                'type': stmt['component_type'],
                'line': stmt.get('line', 0)
            }
            flattened_statements.append({
                'type': 'declaration',
                'component_type': stmt['component_type'],
                'instance_name': stmt['instance_name'],
                'line': stmt.get('line', 0)
            })

    # Pass 2: Generate graph to easily get all explicit connections
    # This leverages the existing robust logic in ast_to_graph.
    # We are essentially using the graph as the most reliable way to "flatten"
    # the various connection syntaxes.
    graph, _ = ast_to_graph(regular_ast_statements) # DSU from ast_to_graph is re-created, use the passed one for lookups

    component_pins_connected = set() # To avoid duplicate pin_connection entries if multiple AST stmts refer to same connection

    # First handle any internal components from voltage sources or controlled sources
    for node_name, node_data in graph.nodes(data=True):
        if node_data.get('node_kind') == 'component_instance' and node_name.startswith('_internal_'):
            # Add declaration for internal component
            flattened_statements.append({
                'type': 'declaration',
                'component_type': node_data.get('instance_type', 'UNKNOWN'),
                'instance_name': node_name,
                'internal': True,
                'line': 0
            })
            
            # Add its connections
            for _, neighbor_name, edge_data in graph.edges(node_name, data=True):
                if graph.nodes[neighbor_name].get('node_kind') == 'electrical_net':
                    terminal_name = edge_data.get('terminal')
                    canonical_net_name = neighbor_name
                    
                    if terminal_name:
                        pin_conn = {
                            'type': 'pin_connection',
                            'component_instance': node_name,
                            'terminal': terminal_name,
                            'net': canonical_net_name,
                            'line': 0
                        }
                        flattened_statements.append(pin_conn)

    # Then handle regular components
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
                                'line': 0
                            }
                            flattened_statements.append(pin_conn)
                            component_pins_connected.add(pin_key)

    # Add net aliases for equivalent nets
    added_aliases = set()
    for net_name in dsu.parent:
        canonical_net = dsu.find(net_name)
        if net_name != canonical_net and (net_name, canonical_net) not in added_aliases:
            flattened_statements.append({
                'type': 'net_alias',
                'source_net': net_name,
                'canonical_net': canonical_net,
                'line': 0
            })
            added_aliases.add((net_name, canonical_net))

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