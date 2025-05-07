# -*- coding: utf-8 -*-
"""Circuit validator implementation."""

import re
from .components import ComponentDatabase
from .graph_utils import ast_to_graph, get_component_connectivity

class ASTValidator:
    def __init__(self, parsed_statements):
        self.parsed_statements = parsed_statements
        self.errors = []
        self.component_db = ComponentDatabase()
        self.VALID_COMPONENT_TYPES = set(self.component_db.components.keys())
        self.declared_component_types = {}  # InstanceName -> {"type": TypeStr, "line": line_num}
        self.explicitly_defined_nodes = set()
        self.node_connection_points = {}

    def _add_error(self, message, line_num=None):
        prefix = f"L{line_num}: AST Validation Error: " if line_num is not None else "AST Validation Error: "
        self.errors.append(f"{prefix}{message}")

    def _check_and_register_node(self, node_name, line_num, connected_to_info=""):
        if not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?', node_name):
            self._add_error(f"Node name '{node_name}' has an invalid format.", line_num)
            return False # Invalid node format

        if '.' in node_name:
            dev_part, term_part = node_name.split('.', 1)
            if dev_part not in self.declared_component_types:
                self._add_error(f"Node '{node_name}' (terminal '{term_part}') refers to undeclared component instance '{dev_part}'. Declare '{dev_part}' first.", line_num)
                return False # Component not declared

        self.explicitly_defined_nodes.add(node_name)
        if connected_to_info:
            if node_name not in self.node_connection_points:
                self.node_connection_points[node_name] = []
            self.node_connection_points[node_name].append(connected_to_info)
        return True


    def validate(self):
        self.errors = []
        self.declared_component_types = {}
        self.explicitly_defined_nodes = set()
        self.node_connection_points = {}

        # --- Pass 1: Process Declarations ---
        for stmt in self.parsed_statements:
            if stmt['type'] == 'declaration':
                line_num = stmt.get('line')
                comp_type = stmt['component_type']
                inst_name = stmt['instance_name']

                if not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]*', comp_type): # Parser also checks
                    self._add_error(f"Component type name '{comp_type}' in declaration has invalid format.", line_num)
                elif comp_type not in self.VALID_COMPONENT_TYPES:
                    self._add_error(f"Unknown component type '{comp_type}' for instance '{inst_name}'. Valid types: {sorted(list(self.VALID_COMPONENT_TYPES))}", line_num)

                if not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]*', inst_name): # Parser also checks
                    self._add_error(f"Component instance name '{inst_name}' in declaration has invalid format.", line_num)

                if inst_name in self.declared_component_types:
                    prev_decl_line = self.declared_component_types[inst_name]['line']
                    self._add_error(f"Component instance '{inst_name}' re-declared. Previously declared on L{prev_decl_line}.", line_num)
                else:
                    self.declared_component_types[inst_name] = {"type": comp_type, "line": line_num}

        # --- Pass 2: Validate connections, component usage, and structure ---
        for stmt in self.parsed_statements:
            line_num = stmt.get('line')
            stmt_type = stmt['type']

            if stmt_type == 'declaration': # Already processed
                continue

            if stmt_type == 'component_connection_block':
                comp_name = stmt['component_name']
                original_assignments_str = stmt.get("_original_assignments_str", "").strip()

                if comp_name not in self.declared_component_types:
                    self._add_error(f"Component instance '{comp_name}' used in connection block but not declared.", line_num)
                    # Continue to check assignments for further errors, but connections involving this comp are invalid

                if not stmt['connections'] and original_assignments_str:
                    self._add_error(f"Block for '{comp_name}' ('{original_assignments_str}') had no valid 'Terminal:(Node)' assigns.", line_num)
                elif not stmt['connections'] and not original_assignments_str:
                    self._add_error(f"Component block for '{comp_name}' is empty.", line_num)

                # Validate arity for this specific block
                comp_type_from_decl = self.declared_component_types.get(comp_name, {}).get("type")
                if comp_type_from_decl: # Only if component was declared
                    expected_arity = self.component_db.get_arity(comp_type_from_decl)
                    if expected_arity is not None and len(stmt['connections']) > expected_arity:
                        self._add_error(f"Component '{comp_name}' of type '{comp_type_from_decl}' in connection block defines {len(stmt['connections'])} terminals, exceeding its arity of {expected_arity}.", line_num)

                for conn in stmt['connections']:
                    if not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]*', conn['terminal']): # Parser checks
                         self._add_error(f"Terminal name '{conn['terminal']}' for '{comp_name}' is invalid.", line_num)

                    self._check_and_register_node(f"{comp_name}.{conn['terminal']}", line_num, f"block assignment to ({conn['node']})")
                    self._check_and_register_node(conn['node'], line_num, f"{comp_name}.{conn['terminal']}")


            elif stmt_type == 'series_connection':
                if stmt.get("_invalid_start"): 
                    continue

                path = stmt.get('path', [])
                if not path: 
                    self._add_error("Series connection path is empty after parsing.", line_num)
                    continue

                first_el_type = path[0].get('type')
                if first_el_type != 'node':
                    self._add_error(f"Series path does not start with a node (Validator final check). First element: {path[0]}", line_num)
                    continue

                is_structurally_valid_path = len(path) > 1 or (len(path) == 1 and path[0].get('type') not in ['node', 'error'])
                if not is_structurally_valid_path and path:
                    first_el_info = path[0].get('name', str(path[0]))
                    self._add_error(f"Series path '{stmt.get('_path_str', 'N/A')}' is too simple (e.g., just node '{first_el_info}'). Must connect points or include a component/source.", line_num)

                for i, item in enumerate(path):
                    item_type = item.get('type')
                    if item_type == 'error':
                        self._add_error(f"Path segment '{item.get('message', 'unknown error')}' from '{stmt.get('_path_str', 'N/A')}' error.", line_num)
                        continue

                    if item_type == 'node':
                        self._check_and_register_node(item['name'], line_num, f"series path '{stmt.get('_path_str', 'N/A')}'")

                    elif item_type == 'component':
                        comp_name = item['name']
                        if comp_name not in self.declared_component_types:
                            self._add_error(f"Component '{comp_name}' in series path '{stmt.get('_path_str', 'N/A')}' not declared.", line_num)

                    elif item_type == 'source':
                        source_name = item['name']
                        if source_name not in self.declared_component_types:
                            self._add_error(f"Source '{source_name}' in path '{stmt.get('_path_str', 'N/A')}' not declared.", line_num)
                        else:
                            decl_type = self.declared_component_types[source_name]['type']
                            # Allow any declared type for a source in path, specific type checks (e.g. 'V' for voltage) can be more semantic
                            # For now, just ensure it's declared.
                            pass


                    elif item_type == 'named_current':
                        if i == 0 or i == len(path) - 1:
                            self._add_error(f"Named current '{item['direction']}{item['name']}' must be between two elements.", line_num)
                        if i > 0 and path[i-1]['type'] in ['named_current', 'error']:
                             self._add_error(f"Named current '{item['direction']}{item['name']}' preceded by invalid element '{path[i-1]['type']}'.", line_num)
                        if i < len(path) -1 and path[i+1]['type'] in ['named_current', 'error']:
                             self._add_error(f"Named current '{item['direction']}{item['name']}' followed by invalid element '{path[i+1]['type']}'.", line_num)

                    elif item_type == 'parallel_block':
                        if item.get("_empty_block"):
                            self._add_error("Parallel block `[]` is empty.", line_num)
                        elif not item['elements']:
                             self._add_error("Parallel block `[...]` parsed with no valid elements.", line_num)
                        for pel in item['elements']:
                            pel_type = pel.get('type')
                            if pel_type == 'error':
                                self._add_error(f"Parallel block element error: {pel.get('message', 'unknown')}", line_num)
                            elif pel_type not in ['component', 'controlled_source', 'noise_source']:
                                self._add_error(f"Invalid type '{pel_type}' in parallel block. Allowed: component, controlled_source, noise_source.", line_num)
                            elif pel_type == 'component':
                                if pel['name'] not in self.declared_component_types:
                                    self._add_error(f"Component '{pel['name']}' in parallel block not declared.", line_num)

            elif stmt_type == 'direct_assignment':
                src_node, tgt_node = stmt['source_node'], stmt['target_node']
                if src_node == tgt_node:
                    self._add_error(f"Direct assignment connects node '{src_node}' to itself.", line_num)

                self._check_and_register_node(src_node, line_num, f"direct assignment to ({tgt_node})")
                self._check_and_register_node(tgt_node, line_num, f"direct assignment from ({src_node})")
        return self.errors

class GraphValidator:
    def __init__(self, graph, dsu, component_db, declared_component_types):
        self.graph = graph
        self.dsu = dsu
        self.component_db = component_db
        self.declared_component_types = declared_component_types # From ASTValidator
        self.errors = []

    def _add_error(self, message, component_name=None):
        prefix = f"Graph Validation Error for component '{component_name}': " if component_name else "Graph Validation Error: "
        self.errors.append(f"{prefix}{message}")

    def validate(self):
        self.errors = []
        component_instance_nodes = [n for n, data in self.graph.nodes(data=True) if data.get('node_kind') == 'component_instance']

        for comp_name in component_instance_nodes:
            if comp_name.startswith("_internal_"): # Skip internal components like VCCS from parallel blocks
                continue

            comp_declaration_info = self.declared_component_types.get(comp_name)
            if not comp_declaration_info:
                # This should ideally be caught by ASTValidator, but as a safeguard:
                self._add_error(f"Component '{comp_name}' found in graph but has no declaration information.", comp_name)
                continue
            
            comp_type = comp_declaration_info.get("type")
            line_num = comp_declaration_info.get("line") # For error reporting context

            expected_arity = self.component_db.get_arity(comp_type)
            if expected_arity is None: # Unknown component type to the DB, already flagged by ASTValidator
                continue

            # Get actual connections from the graph
            # get_component_connectivity returns: connections_map (term -> net), raw_connections (list of dicts)
            _, raw_connections = get_component_connectivity(self.graph, comp_name)
            actual_arity = len(raw_connections)

            if actual_arity > expected_arity:
                self._add_error(f"Component '{comp_name}' (type '{comp_type}', declared L{line_num}) is connected to {actual_arity} nodes in the graph, exceeding its defined arity of {expected_arity}.", comp_name)
            
            # Future graph-specific checks can be added here:
            # - Check for components with fewer connections than expected (e.g., arity 2 component with only 1 connection)
            # - Check for floating nets or components not part of the main circuit (if desired)

        return self.errors

class CircuitValidator:
    def __init__(self, parsed_statements):
        self.parsed_statements = parsed_statements
        self.component_db = ComponentDatabase() # Shared component database

    def validate(self):
        all_errors = []

        # 1. AST Validation
        ast_validator = ASTValidator(self.parsed_statements)
        ast_errors = ast_validator.validate()
        all_errors.extend(ast_errors)

        # Proceed to graph validation only if AST is reasonably sound,
        # or collect all errors regardless. For now, let's collect all.
        # If AST errors are severe, graph construction might fail or be meaningless.
        
        # Get declared components from ASTValidator for GraphValidator
        declared_component_types = ast_validator.declared_component_types

        # 2. Graph Construction
        # We need to handle potential errors during graph construction itself, though ast_to_graph doesn't explicitly return them.
        # For now, assume ast_to_graph succeeds if AST validation passed, or that its internal prints are sufficient.
        try:
            graph, dsu = ast_to_graph(self.parsed_statements)
        except Exception as e:
            all_errors.append(f"Critical Error during graph construction: {e}. Further graph validation skipped.")
            return all_errors
            
        # 3. Graph Validation
        graph_validator = GraphValidator(graph, dsu, self.component_db, declared_component_types)
        graph_errors = graph_validator.validate()
        all_errors.extend(graph_errors)
        
        return all_errors