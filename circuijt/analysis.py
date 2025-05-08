"""
Circuit analysis functions, including short circuit detection.
"""

from .graph_utils import get_component_connectivity, get_preferred_net_name_for_reconstruction
# from .components import ComponentDatabase # Not strictly needed for current topological shorts

def detect_short_circuits(graph, dsu):
    """
    Detects topological short circuits in a circuit graph.

    Args:
        graph (nx.MultiGraph): The circuit graph from ast_to_graph.
        dsu (DSU): The Disjoint Set Union object for net canonicalization.

    Returns:
        list: A list of dictionaries, each describing a detected short circuit.
              Possible short types:
              - 'component_self_short': Multiple terminals of a single component
                                        are connected to the same electrical net.
              - 'global_short': Two distinct key nets (e.g., VDD and GND) are
                                connected together.
    """
    detected_shorts = []

    # 1. Check for components shorting their own terminals
    component_instance_nodes = [
        n for n, data in graph.nodes(data=True)
        if data.get('node_kind') == 'component_instance'
    ]

    for comp_name in component_instance_nodes:
        term_to_canonical_net_map, _ = get_component_connectivity(graph, comp_name)

        # Group terminals by the canonical net they connect to
        net_to_terminals_map = {}
        for terminal, canonical_net in term_to_canonical_net_map.items():
            if canonical_net not in net_to_terminals_map:
                net_to_terminals_map[canonical_net] = []
            net_to_terminals_map[canonical_net].append(terminal)

        # Check if any net connects to more than one terminal of this component
        for canonical_net, terminals_list in net_to_terminals_map.items():
            if len(terminals_list) > 1:
                # This component has multiple terminals connected to the same net
                preferred_net_name = get_preferred_net_name_for_reconstruction(
                    canonical_net, dsu, allow_implicit_if_only_option=True
                )
                detected_shorts.append({
                    'type': 'component_self_short',
                    'component': comp_name,
                    'component_type': graph.nodes[comp_name].get('instance_type', 'Unknown'),
                    'terminals': sorted(list(set(terminals_list))),
                    'net': preferred_net_name,
                    'canonical_net': canonical_net
                })

    # 2. Check for global shorts between predefined important nets
    key_nets_to_check = ["VDD", "GND", "VSS", "VCC"] 
    # Filter to only those potentially relevant based on DSU's known items
    # This avoids issues if, e.g., 'VSS' was never mentioned in the circuit.
    # DSU.find() adds items, so we need to be a bit careful.
    # A net is "relevant" if it was explicitly part of the DSU's construction.
    relevant_key_nets = [net for net in key_nets_to_check if net in dsu.parent]


    for i in range(len(relevant_key_nets)):
        for j in range(i + 1, len(relevant_key_nets)):
            net1_raw = relevant_key_nets[i]
            net2_raw = relevant_key_nets[j]

            # dsu.find() will correctly return canonical representatives.
            # If net1_raw or net2_raw were not in dsu.parent, find would make them
            # their own new sets. The relevant_key_nets filter helps here.
            canonical_net1 = dsu.find(net1_raw)
            canonical_net2 = dsu.find(net2_raw)

            if canonical_net1 == canonical_net2:
                # These two distinct key nets are shorted together.
                detected_shorts.append({
                    'type': 'global_short',
                    'nets': sorted([net1_raw, net2_raw]),
                    'canonical_net': canonical_net1
                })
    
    return detected_shorts

def format_short_circuit_report(detected_shorts):
    """
    Formats a list of detected short circuits into a human-readable string.
    """
    if not detected_shorts:
        return "No topological short circuits detected."

    report_lines = ["Detected Topological Short Circuits:"]
    for short in detected_shorts:
        if short['type'] == 'component_self_short':
            report_lines.append(
                f"  - Component Short: '{short['component']}' (Type: {short['component_type']}) "
                f"has terminals {short['terminals']} connected to the same net '{short['net']}' "
                f"(canonical: '{short['canonical_net']}')."
            )
        elif short['type'] == 'global_short':
            report_lines.append(
                f"  - Global Short: Key nets {short['nets']} are connected together. "
                f"(Canonical net: '{short['canonical_net']}')"
            )
        else:
            report_lines.append(f"  - Unknown short type: {short}")
    return "\n".join(report_lines)