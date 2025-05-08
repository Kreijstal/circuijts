# -*- coding: utf-8 -*-
"""Circuit parser implementation."""

import re


class ProtoCircuitParser:
    def __init__(self):
        self.parsed_statements = []
        self.errors = []

        # Regex patterns
        self.COMMENT_RE = re.compile(r";.*$")
        self.DECLARATION_RE = re.compile(
            r"^[ \t]*([a-zA-Z_][a-zA-Z0-9_]*)[ \t]+([a-zA-Z_][a-zA-Z0-9_]*)[ \t]*$"
        )  # Type InstanceName
        self.NODE_RE = re.compile(r"^\(([a-zA-Z0-9_.]+)\)$")  # Allows dot for Dev.Term
        self.COMPONENT_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")  # For instance names, type names, terminal names
        self.SOURCE_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*)[ \t]*\((\-\+|\+-)\)$")  # InstanceName (Polarity)
        self.NAMED_CURRENT_RE = re.compile(r"^(->|<\-)([a-zA-Z_][a-zA-Z0-9_]*)$")
        self.CONTROLLED_SOURCE_RE = re.compile(r"^(.*?)\s*\((->|<\-)\)$")
        self.COMPONENT_BLOCK_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*{\s*(.*?)\s*}$", re.DOTALL)
        self.COMPONENT_BLOCK_ASSIGN_RE = re.compile(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*\(([a-zA-Z0-9_.]+)\)")
        self.DIRECT_ASSIGN_RE = re.compile(r"^\s*\(([a-zA-Z0-9_.]+)\)\s*:\s*\(([a-zA-Z0-9_.]+)\)")

    def _validate_node_name(self, node_name, line_num, element_str):
        valid_node = re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?", node_name)
        if not valid_node:
            self.errors.append(
                f"L{line_num}: Invalid node name format '{node_name}' in '{element_str}'. "
                f"Expected (name) or (Device.Terminal)."
            )
            return False
        return True

    def _parse_node_element(self, match, line_num, element_str):
        node_name = match.group(1)
        if not self._validate_node_name(node_name, line_num, element_str):
            return {"type": "error", "message": f"Invalid node name format: {node_name}"}
        return {"type": "node", "name": node_name}

    def _parse_source_element(self, match, line_num):
        name, polarity = match.groups()
        if not self.COMPONENT_NAME_RE.fullmatch(name):
            self.errors.append(
                f"L{line_num}: Invalid source instance name format '{name}'. "
                f"Must be alphanumeric, starting with letter/underscore."
            )
            return {"type": "error", "message": f"Invalid source instance name format: {name}"}
        return {"type": "source", "name": name, "polarity": polarity}

    def _parse_named_current_element(self, match, line_num):
        direction, name = match.groups()
        if not self.COMPONENT_NAME_RE.fullmatch(name):
            self.errors.append(
                f"L{line_num}: Invalid current identifier '{name}'. " f"Must be alphanumeric, starting with letter/underscore."
            )
            return {"type": "error", "message": f"Invalid current identifier: {name}"}
        return {"type": "named_current", "direction": direction, "name": name}

    def _parse_controlled_or_noise_source_element(self, match, line_num, element_str):
        expr_id = match.group(1).strip()
        direction = match.group(2)
        if not expr_id:
            self.errors.append(
                f"L{line_num}: Empty expression/id for controlled/noise source in parallel block: '{element_str}'"
            )
            return {"type": "error", "message": "Empty expression/id for source"}
        if "*" in expr_id:  # Assume VCCS if '*' is present
            return {"type": "controlled_source", "expression": expr_id, "direction": direction}
        else:  # Assume noise_id
            if not self.COMPONENT_NAME_RE.fullmatch(expr_id):
                self.errors.append(
                    f"L{line_num}: Invalid noise source identifier '{expr_id}'. "
                    f"Must be alphanumeric, starting with letter/underscore."
                )
                return {"type": "error", "message": f"Invalid noise source id: {expr_id}"}
            return {"type": "noise_source", "id": expr_id, "direction": direction}

    def _parse_element(self, element_str, line_num, context="series"):
        # Strip any inline comments first
        element_str = self.COMMENT_RE.sub("", element_str).strip()

        match_node = self.NODE_RE.match(element_str)
        if match_node:
            return self._parse_node_element(match_node, line_num, element_str)

        match_source = self.SOURCE_RE.match(element_str)
        if match_source:
            return self._parse_source_element(match_source, line_num)

        if context == "series":
            match_current = self.NAMED_CURRENT_RE.match(element_str)
            if match_current:
                return self._parse_named_current_element(match_current, line_num)

        if context == "parallel":
            match_cs = self.CONTROLLED_SOURCE_RE.match(element_str)
            if match_cs:
                return self._parse_controlled_or_noise_source_element(match_cs, line_num, element_str)

        # Default to component instance name if nothing else matches
        if self.COMPONENT_NAME_RE.fullmatch(element_str):  # Check if it's a valid identifier
            return {"type": "component", "name": element_str}  # Name is instance name

        self.errors.append(f"L{line_num}: Unrecognized or malformed element '{element_str}' in {context} context.")
        return {"type": "error", "message": f"Unrecognized element: {element_str}"}

    def _parse_parallel_block_content(self, content_str, line_num):
        elements_str_raw = content_str.split("||")
        parsed_elements = []
        if not any(s.strip() for s in elements_str_raw) and content_str:
            self.errors.append(
                f"L{line_num}: Parallel block `[{content_str}]` appears to have malformed separators or empty elements."
            )

        for i, el_str_raw in enumerate(elements_str_raw):
            el_str = el_str_raw.strip()
            if not el_str:
                if len(elements_str_raw) > 1 and i < len(elements_str_raw) - 1:
                    self.errors.append(
                        f"L{line_num}: Empty element due to '|| ||' or trailing '||' in parallel block: `[{content_str}]`."
                    )
                elif len(elements_str_raw) == 1:
                    self.errors.append(f"L{line_num}: Parallel block `[{content_str}]` is empty or contains only whitespace.")
                continue
            parsed_el = self._parse_element(el_str, line_num, context="parallel")
            parsed_elements.append(parsed_el)
        return parsed_elements

    def _parse_declaration(self, line, line_num):
        match_decl = self.DECLARATION_RE.fullmatch(line)
        if not match_decl:
            return False
        comp_type, inst_name = match_decl.groups()
        if not self.COMPONENT_NAME_RE.fullmatch(comp_type):
            self.errors.append(
                f"L{line_num}: Invalid component type format '{comp_type}'. "
                f"Must be alphanumeric, starting with letter/underscore."
            )
        if not self.COMPONENT_NAME_RE.fullmatch(inst_name):
            self.errors.append(
                f"L{line_num}: Invalid component instance name format '{inst_name}'. "
                f"Must be alphanumeric, starting with letter/underscore."
            )
        self.parsed_statements.append(
            {
                "type": "declaration",
                "line": line_num,
                "component_type": comp_type,
                "instance_name": inst_name,
            }
        )
        return True

    def _parse_component_connection_block(self, line, line_num):
        match_comp_block = self.COMPONENT_BLOCK_RE.fullmatch(line)
        if not match_comp_block:
            return False
        comp_name, assignments_str = match_comp_block.groups()
        if not self.COMPONENT_NAME_RE.fullmatch(comp_name):
            self.errors.append(f"L{line_num}: Invalid component instance name '{comp_name}' for connection block.")
        connections = []
        valid_assignments_found_in_block = False
        raw_assignments = assignments_str.split(",")
        for assign_part_raw in raw_assignments:
            assign_part = assign_part_raw.strip()
            if not assign_part:
                continue
            assign_match = self.COMPONENT_BLOCK_ASSIGN_RE.fullmatch(assign_part)
            if assign_match:
                term, node = assign_match.groups()
                if not self.COMPONENT_NAME_RE.fullmatch(term):
                    self.errors.append(f"L{line_num}: Invalid terminal name '{term}' in block for '{comp_name}'.")
                    continue
                if not self._validate_node_name(node, line_num, f"block for {comp_name}"):
                    continue
                connections.append({"terminal": term, "node": node})
                valid_assignments_found_in_block = True
            else:
                self.errors.append(
                    f"L{line_num}: Malformed assignment '{assign_part}' in "
                    f"component block for '{comp_name}'. Expected 'Terminal:(NodeName)'."
                )
        if assignments_str.strip() and not valid_assignments_found_in_block:
            self.errors.append(
                f"L{line_num}: Component block for '{comp_name}' "
                f"('{assignments_str.strip()}') had no valid 'Terminal:(NodeName)' assignments."
            )
        self.parsed_statements.append(
            {
                "type": "component_connection_block",
                "line": line_num,
                "component_name": comp_name,
                "connections": connections,
                "_original_assignments_str": assignments_str,
            }
        )
        return True

    def _split_series_path(self, line):
        parts_str = []
        current_segment = ""
        bracket_level = 0
        for char_idx, char in enumerate(line):
            current_segment += char
            if char == "[":
                bracket_level += 1
            elif char == "]":
                bracket_level -= 1
            elif char == "-" and len(current_segment) > 1 and current_segment[-2] == "-" and bracket_level == 0:
                parts_str.append(current_segment[:-2].strip())
                current_segment = ""
        if (
            current_segment.strip() or not parts_str
        ):  # Add last segment or if line is just e.g. "(N1)" which is not a series path
            parts_str.append(current_segment.strip())
        return [p for p in parts_str if p]  # Filter out empty strings

    def _parse_series_connection(self, line, line_num):
        if "--" not in line:
            return False

        parts_str = self._split_series_path(line)

        if not parts_str and line.strip():
            self.errors.append(f"L{line_num}: Series path line '{line}' could not be segmented. Check structure.")
            self.parsed_statements.append(
                {
                    "type": "series_connection",
                    "line": line_num,
                    "path": [{"type": "error", "message": "Path segmentation failed"}],
                    "_invalid_start": True,
                }
            )
            return True

        path = []
        if not parts_str:  # Should not happen if line.strip() is true due to above check, but as a safeguard
            self.parsed_statements.append(
                {
                    "type": "series_connection",
                    "line": line_num,
                    "path": path,
                    "_path_str": line,
                }
            )
            return True

        first_element_str = parts_str[0].strip()
        first_part_parsed = self._parse_element(first_element_str, line_num, context="series")

        if first_part_parsed.get("type") != "node":
            self.errors.append(
                f"L{line_num}: Series path must start with a node. "
                f"Found '{first_element_str}' (parsed as type "
                f"'{first_part_parsed.get('type', 'unknown')}')."
            )
            self.parsed_statements.append(
                {
                    "type": "series_connection",
                    "line": line_num,
                    "path": [first_part_parsed],
                    "_invalid_start": True,
                    "_path_str": line,
                }
            )
            return True
        else:
            path.append(first_part_parsed)

        for part_str_orig in parts_str[1:]:
            part_str = part_str_orig.strip()
            if not part_str:  # Should be filtered by _split_series_path
                continue

            if part_str.startswith("[") and part_str.endswith("]"):
                content = part_str[1:-1].strip()
                if not content:
                    self.errors.append(f"L{line_num}: Empty parallel block `[]` in series path.")
                    path.append({"type": "parallel_block", "elements": [], "_empty_block": True})
                    continue
                parallel_elements = self._parse_parallel_block_content(content, line_num)
                path.append({"type": "parallel_block", "elements": parallel_elements})
            else:
                path.append(self._parse_element(part_str, line_num, context="series"))

        self.parsed_statements.append(
            {
                "type": "series_connection",
                "line": line_num,
                "path": path,
                "_path_str": line,
            }
        )
        return True

    def _parse_direct_assignment(self, line, line_num):
        match_direct_assign = self.DIRECT_ASSIGN_RE.fullmatch(line)
        if not match_direct_assign:
            return False
        src, tgt = match_direct_assign.groups()
        valid_src = self._validate_node_name(src, line_num, f"direct assignment source: {line}")
        valid_tgt = self._validate_node_name(tgt, line_num, f"direct assignment target: {line}")

        if valid_src and valid_tgt:
            self.parsed_statements.append(
                {
                    "type": "direct_assignment",
                    "line": line_num,
                    "source_node": src,
                    "target_node": tgt,
                }
            )
        return True

    def parse_line(self, line_text, line_num):
        line = self.COMMENT_RE.sub("", line_text).strip()
        if not line:
            return

        if self._parse_declaration(line, line_num):
            return

        if self._parse_component_connection_block(line, line_num):
            return

        if self._parse_series_connection(line, line_num):
            return

        if self._parse_direct_assignment(line, line_num):
            return

        self.errors.append(f"L{line_num}: Unrecognized line format or syntax error: '{line}'")

    def parse_text(self, text_content):
        self.parsed_statements = []
        self.errors = []
        lines = text_content.splitlines()
        for i, line_text in enumerate(lines):
            self.parse_line(line_text, i + 1)
        return self.parsed_statements, self.errors
