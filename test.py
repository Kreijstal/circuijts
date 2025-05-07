# -*- coding: utf-8 -*-
"""Tests for circuit parser/validator/graph utilities."""

from circuijt.parser import ProtoCircuitParser
from circuijt.validator import CircuitValidator # Updated import
from circuijt.ast_utils import summarize_circuit_elements, generate_proto_from_ast
from circuijt.graph_utils import ast_to_graph, graph_to_structured_ast, DSU # DSU might be needed by graph_to_structured_ast if not implicitly handled

def test_validator(parsed_statements):
    print("\n--- Testing Validator ---")
    validator = CircuitValidator(parsed_statements) # Use the new general validator
    validation_errors = validator.validate()
    
    if validation_errors:
        print("Validation Errors:")
        for error in validation_errors:
            print(error)
    else:
        print("Validation successful, no errors.")

def test_ast_utils(parsed_statements):
    print("\n--- Testing AST Utilities ---")
    summary = summarize_circuit_elements(parsed_statements)
    print("Circuit Summary:")
    print(f"Total Nodes: {summary['num_total_nodes']}")
    print(f"Components: {summary['num_total_components']}")
    print(f"Explicit Nodes: {summary['details']['explicit_nodes']}")
    print(f"Implicit Nodes: {summary['details']['implicit_nodes']}")

    reconstructed = generate_proto_from_ast(parsed_statements)
    print("\nReconstructed Circuit:")
    print(reconstructed)

def test_graph_utils(parsed_statements):
    print("\n--- Testing Graph Utilities ---")
    graph, dsu = ast_to_graph(parsed_statements)
    print(f"Graph nodes: {len(graph.nodes())}")
    print(f"Graph edges: {len(graph.edges())}")
    
    reconstructed_ast = graph_to_structured_ast(graph, dsu)
    print("\nReconstructed AST from graph:")
    print(f"Statements: {len(reconstructed_ast)}")
    
    reconstructed_code = generate_proto_from_ast(reconstructed_ast)
    print("\nReconstructed Code from graph:")
    print(reconstructed_code)

def transform_and_validate_loop(initial_code: str):
    """
    Performs a loop of transformations and validations:
    code -> ast1 -> validate ast1 -> graph1 -> ast2 -> validate ast2 -> code_final
    """
    print("\n--- Starting Transformation and Validation Loop ---")

    # --- Step 1: Code to AST_1 (Parse) ---
    print("\n1. Parsing initial code to AST_1...")
    parser = ProtoCircuitParser()
    ast_1, parser_errors = parser.parse_text(initial_code)
    
    if parser_errors:
        print("Parser Errors for AST_1:")
        for error in parser_errors:
            print(error)
    if not ast_1 and parser_errors: # Critical parsing failure if ast_1 is empty and there were errors
        print("Parsing failed critically. Aborting loop.")
        return None, None, None, None
    elif not ast_1 and not parser_errors: # Empty input perhaps
        print("Parsing resulted in an empty AST (no errors reported). Continuing cautiously.")
    else:
        print("Parsing to AST_1 successful.")
    
    assert ast_1 is not None, "AST_1 should not be None after parsing."
    if not ast_1 and not parser_errors: # Empty input perhaps
        print("Warning: AST_1 is empty but no parser errors reported.")
    elif not ast_1 and parser_errors:
        print("Critical: AST_1 is empty and parser errors were reported.")


    print("AST_1 (Initial):")
    for stmt_idx, stmt in enumerate(ast_1): print(f"  AST_1 Stmt {stmt_idx}: {stmt}")

    # --- Step 2: Validate AST_1 ---
    print("\n2. Validating AST_1...")
    validator_ast1 = CircuitValidator(ast_1)
    validation_errors_ast1 = validator_ast1.validate()
    if validation_errors_ast1:
        print("Validation Errors for AST_1:")
        for error in validation_errors_ast1:
            print(error)
    else:
        print("AST_1 validation successful.")

    # --- Step 3: AST_1 to Graph_1 ---
    print("\n3. Converting AST_1 to Graph_1...")
    graph_1 = None
    dsu_1 = None
    try:
        graph_1, dsu_1 = ast_to_graph(ast_1)
        print(f"Graph_1 created with {len(graph_1.nodes())} nodes and {len(graph_1.edges())} edges.")
        assert graph_1 is not None, "Graph_1 should not be None after ast_to_graph."
        assert len(graph_1.nodes()) > 0 if ast_1 else True, "Graph_1 should have nodes if AST_1 was not empty."
    except Exception as e:
        print(f"Error during AST_1 to Graph_1 conversion: {e}")
        print("Aborting loop due to graph conversion failure.")
        return ast_1, None, None, None
    
    print("Graph_1 nodes:", list(graph_1.nodes(data=True)))
    print("DSU_1 structure (first 5 items):", dict(list(dsu_1.parent.items())[:5]) if dsu_1 else "No DSU object")


    # --- Step 4: Graph_1 to AST_2 ---
    print("\n4. Converting Graph_1 to AST_2...")
    ast_2 = None
    try:
        # Note: The provided graph_to_structured_ast may have limitations
        # in fully reconstructing all original statement types (e.g., series paths).
        ast_2 = graph_to_structured_ast(graph_1, dsu_1)
        print(f"AST_2 reconstructed with {len(ast_2)} statements.")
        assert ast_2 is not None, "AST_2 should not be None after graph_to_structured_ast."
        # It's possible ast_2 is empty if graph_to_structured_ast doesn't reconstruct anything,
        # so an assertion for non-emptiness might be too strong without knowing expected behavior.
    except Exception as e:
        print(f"Error during Graph_1 to AST_2 conversion: {e}")
        # Continue to allow validation of whatever ast_2 might be, or if it's None
        print("Continuing loop despite AST reconstruction error to allow further steps if possible.")
        
    # print("AST_2 (Reconstructed from graph):") # Uncomment to see the full AST
    # if ast_2:
    #     for stmt in ast_2: print(stmt)
    # else:
    #     print("AST_2 is None or empty.")
    print("AST_2 (Reconstructed from graph):")
    if ast_2:
        for stmt_idx, stmt in enumerate(ast_2): print(f"  AST_2 Stmt {stmt_idx}: {stmt}")
    else:
        print("  AST_2 is None or empty.")


    # --- Step 5: Validate AST_2 ---
    print("\n5. Validating AST_2...")
    if not ast_2:
        print("AST_2 is empty or None, skipping validation.")
    else:
        validator_ast2 = CircuitValidator(ast_2)
        validation_errors_ast2 = validator_ast2.validate()
        if validation_errors_ast2:
            print("Validation Errors for AST_2:")
            for error in validation_errors_ast2:
                print(error)
        else:
            print("AST_2 validation successful.")

    # --- Step 6: AST_2 to Code_final ---
    print("\n6. Generating final code from AST_2...")
    code_final = ""
    if not ast_2:
        print("AST_2 is empty or None, cannot generate code.")
        code_final = "; AST_2 was empty or None, no code generated."
    else:
        try:
            code_final = generate_proto_from_ast(ast_2)
            print("Final Code (from AST_2):")
            print(code_final)
        except Exception as e:
            print(f"Error generating code from AST_2: {e}")
            code_final = f"; Error during code generation from AST_2: {e}"

    print("\n--- Transformation and Validation Loop Finished ---")
    return ast_1, graph_1, ast_2, code_final

test_circuit_description = """
; Component Declarations
V Vin_src     ; Input Voltage Source
R R1          ; Resistor 1
Nmos M1       ; NMOS Transistor M1
R R2          ; Resistor 2
C Cgd         ; Gate-Drain Capacitance of M1
C Cgb         ; Gate-Bulk Capacitance of M1 (the small one in the diagram)
C Cgs         ; Gate-Source Capacitance of M1
C Cdb         ; Drain-Bulk Capacitance of M1
C Csb         ; Source-Bulk Capacitance of M1
C CL          ; Load Capacitance

; Connections for the main transistor M1
; We'll use node names (node_gate), (Vout) and rely on M1's block definition
; to connect its terminals to these and other primary nodes like (VDD) and (GND).
M1 { G:(node_gate), D:(VDD), S:(Vout), B:(GND) }

; Input Path
(GND) -- Vin_src (-+) -- (node_vin_pos) -- R1 -- (node_gate)

; Parasitic Capacitances connected to the Gate of M1
(node_gate) -- Cgd -- (VDD)  ; Cgd between Gate (node_gate/M1.G) and Drain (VDD/M1.D)
(node_gate) -- Cgb -- (GND)  ; Cgb between Gate (node_gate/M1.G) and Bulk (GND/M1.B)
(node_gate) -- Cgs -- (Vout) ; Cgs between Gate (node_gate/M1.G) and Source (Vout/M1.S)

; Parasitic Capacitance connected to the Drain of M1 (besides Cgd)
(VDD) -- Cdb -- (GND)        ; Cdb between Drain (VDD/M1.D) and Bulk (GND/M1.B)

; Parasitic Capacitance connected to the Source of M1 (besides Cgs)
(Vout) -- Csb -- (GND)       ; Csb between Source (Vout/M1.S) and Bulk (GND/M1.B)

; Output Path Components
; R2 and CL are effectively in parallel from Vout to GND.
(Vout) -- [ R2 || CL ] -- (GND)

; Node Aliases/Definitions (Implicit from M1 block and Vout usage)
; (M1.G) : (node_gate)
; (M1.D) : (VDD)
; (M1.S) : (Vout)
; (M1.B) : (GND)
; (Vout_pin) : (Vout) ; Assuming Vout label in schematic is this node
"""
transform_and_validate_loop(test_circuit_description)

