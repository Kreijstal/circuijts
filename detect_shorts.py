#!/usr/bin/env python3
"""
CLI tool to detect topological short circuits in .circuijt files.
"""
import argparse
import os
import sys
import pprint  # Added for debug dumping
from circuijt.analysis import detect_short_circuits, format_short_circuit_report
from circuijt.graph_utils import ast_to_graph
from circuijt.parser import ProtoCircuitParser
from circuijt.validator import ASTValidator

# Adjust path to import from circuijt module if script is in root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Detect topological short circuits in .circuijt files."
    )
    parser.add_argument("circuit_file", help="Input .circuijt file to process")
    parser.add_argument(
        "--debug-dump",
        action="store_true",
        help="Dump intermediate AST and graph structures for debugging",
    )
    return parser.parse_args()

def read_and_parse_circuit(args):
    circuit_parser = ProtoCircuitParser()
    try:
        with open(args.circuit_file, "r", encoding="utf-8") as f:
            circuit_text = f.read()
    except FileNotFoundError:
        print(f"Error: Circuit file '{args.circuit_file}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file '{args.circuit_file}': {e}")
        sys.exit(1)

    ast, parser_errors = circuit_parser.parse_text(circuit_text)

    if args.debug_dump:
        print("\n--- DEBUG DUMP: Initial AST (from parser) ---")
        pprint.pprint(ast)
        if parser_errors:
            print("\n--- DEBUG DUMP: Parser Errors ---")
            pprint.pprint(parser_errors)

    if parser_errors:
        print(f"Parser errors found in '{args.circuit_file}':")
        for error in parser_errors:
            print(f"  {error}")

    if not ast and parser_errors:
        print("Critical parsing errors prevented AST generation. Cannot perform analysis.")
        sys.exit(1)
    if not ast and not parser_errors:
        print(f"No circuit statements found in '{args.circuit_file}'.")

    return ast, parser_errors


def validate_circuit(ast, args):
    validator = ASTValidator(ast)
    validation_errors, _ = validator.validate()
    if validation_errors:
        print(f"\nStandard validation errors found in '{args.circuit_file}':")
        for error in validation_errors:
            print(f"  {error}")
        print("Proceeding with short circuit detection despite these validation errors...")

def convert_to_graph(ast, args):
    try:
        graph, dsu = ast_to_graph(ast)
    except Exception as e:
        print(f"\nError during graph construction for '{args.circuit_file}': {e}")
        print("This may be due to severe issues in the circuit description not caught by the parser.")
        if args.debug_dump:
            print("\n--- DEBUG DUMP: AST before failing ast_to_graph call ---")
            pprint.pprint(ast)
        sys.exit(1)

    if args.debug_dump:
        print("\n--- DEBUG DUMP: Graph Structure ---")
        print("Nodes:")
        pprint.pprint(list(graph.nodes(data=True)))
        print("Edges:")
        pprint.pprint(list(graph.edges(data=True)))
        print("DSU Parent Map:")
        pprint.pprint(dsu.parent)

    return graph, dsu


def detect_and_report_shorts(graph, dsu, args):
    shorts = detect_short_circuits(graph, dsu)
    report = format_short_circuit_report(shorts)
    print(f"\n--- Short Circuit Report for {args.circuit_file} ---")
    print(report)


def main():
    args = parse_arguments()
    ast, parser_errors = read_and_parse_circuit(args)
    if ast:
        validate_circuit(ast, args)
        graph, dsu = convert_to_graph(ast, args)
        detect_and_report_shorts(graph, dsu, args)

if __name__ == "__main__":
    main()


