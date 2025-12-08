# -*- coding: utf-8 -*-
"""Circuit class for encapsulating a networkx.Graph, DSU, and metadata."""

import networkx as nx
from .graph_utils import DSU


class Circuit:
    """
    Circuit class that encapsulates a networkx.Graph, DSU, and metadata.

    This class provides the foundation for circuit manipulation and rule application.
    """

    def __init__(self, graph=None, dsu=None, metadata=None):
        """
        Initialize a Circuit object.

        Args:
            graph (nx.Graph, optional): NetworkX graph representing the circuit.
                                      If None, creates an empty graph.
            dsu (DSU, optional): Disjoint Set Union for electrical nets.
                                If None, creates a new DSU instance.
            metadata (dict, optional): Additional metadata about the circuit.
                                     If None, creates an empty dict.
        """
        self.graph = graph if graph is not None else nx.Graph()
        self.dsu = dsu if dsu is not None else DSU()
        self.metadata = metadata if metadata is not None else {}

    def apply_rule_once(self, rule):
        """
        Apply a rule to the circuit once, finding and transforming a single candidate.

        Args:
            rule: A rule object conforming to RuleInterface that can find candidates
                  and apply transformations.

        Returns:
            bool: True if a transformation was applied, False if no candidates found.
        """
        # Find candidates using the rule
        candidates = rule.find_candidates(self)

        if not candidates:
            return False

        # Apply the rule to the first candidate found
        first_candidate = candidates[0]
        rule.apply_to_candidate(self, first_candidate)

        return True

    def copy(self):
        """
        Create a deep copy of the circuit.

        Returns:
            Circuit: A new Circuit instance with copied graph, DSU, and metadata.
        """
        # Deep copy the graph
        new_graph = self.graph.copy()

        # Create a new DSU with the same state
        new_dsu = DSU(preferred_roots=self.dsu.preferred_roots)
        new_dsu.parent = self.dsu.parent.copy()
        new_dsu.num_sets = self.dsu.num_sets

        # Deep copy metadata
        new_metadata = self.metadata.copy()

        return Circuit(graph=new_graph, dsu=new_dsu, metadata=new_metadata)

    def get_nodes(self, node_kind=None):
        """
        Get nodes from the graph, optionally filtered by node kind.

        Args:
            node_kind (str, optional): Filter nodes by their 'node_kind' attribute.
                                     If None, returns all nodes.

        Returns:
            list: List of node identifiers matching the criteria.
        """
        if node_kind is None:
            return list(self.graph.nodes())

        return [node for node, data in self.graph.nodes(data=True) if data.get("node_kind") == node_kind]

    def get_edges(self):
        """
        Get all edges from the graph.

        Returns:
            list: List of edges in the graph.
        """
        return list(self.graph.edges(data=True))

    def get_component_nodes(self):
        """
        Get all component instance nodes from the graph.

        Returns:
            list: List of component node identifiers.
        """
        return self.get_nodes(node_kind="component_instance")

    def __str__(self):
        """String representation of the circuit."""
        num_nodes = len(self.graph.nodes())
        num_edges = len(self.graph.edges())
        num_components = len(self.get_component_nodes())
        return f"Circuit(nodes={num_nodes}, edges={num_edges}, components={num_components})"

    def __repr__(self):
        """Detailed representation of the circuit."""
        return self.__str__()
