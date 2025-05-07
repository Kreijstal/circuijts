# -*- coding: utf-8 -*-
"""Legacy single-file version - imports from new module structure."""

from circuijt.parser import ProtoCircuitParser
from circuijt.validator import ProtoCircuitValidator
from circuijt.ast_utils import summarize_circuit_elements, generate_proto_from_ast
from circuijt.graph_utils import ast_to_graph, graph_to_structured_ast

# Maintain backward compatibility with old imports
__all__ = [
    'ProtoCircuitParser',
    'ProtoCircuitValidator',
    'summarize_circuit_elements',
    'generate_proto_from_ast',
    'ast_to_graph',
    'graph_to_structured_ast'
]
