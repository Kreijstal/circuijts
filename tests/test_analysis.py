# -*- coding: utf-8 -*-
"""Tests for circuit short circuit analysis module."""

from circuijt.parser import ProtoCircuitParser
from circuijt.graph_utils import ast_to_graph
from circuijt.analysis import detect_short_circuits, format_short_circuit_report


def test_detect_no_shorts():
    circuit_text = """
    R R1
    C C1
    (Vin) -- R1 -- (Vout) -- C1 -- (GND)
    """
    parser = ProtoCircuitParser()
    ast, _ = parser.parse_text(circuit_text)
    graph, dsu = ast_to_graph(ast)
    shorts = detect_short_circuits(graph, dsu)
    assert len(shorts) == 0
    report = format_short_circuit_report(shorts)
    assert report == "No topological short circuits detected."


def test_detect_component_self_short():
    circuit_text = """
    R R1
    (NodeA) -- R1 -- (NodeA)
    """
    parser = ProtoCircuitParser()
    ast, _ = parser.parse_text(circuit_text)
    graph, dsu = ast_to_graph(ast)
    shorts = detect_short_circuits(graph, dsu)
    assert len(shorts) == 1
    assert shorts[0]["type"] == "component_self_short"
    assert shorts[0]["component"] == "R1"
    assert shorts[0]["net"] == "NodeA"

    report = format_short_circuit_report(shorts)
    assert "Component Short: 'R1'" in report
    assert "NodeA" in report


def test_detect_global_short():
    circuit_text = """
    (VDD) : (GND)
    """
    parser = ProtoCircuitParser()
    ast, _ = parser.parse_text(circuit_text)
    graph, dsu = ast_to_graph(ast)
    shorts = detect_short_circuits(graph, dsu)
    assert len(shorts) == 1
    assert shorts[0]["type"] == "global_short"
    assert shorts[0]["nets"] == ["GND", "VDD"]

    report = format_short_circuit_report(shorts)
    assert "Global Short: Key nets ['GND', 'VDD']" in report


def test_format_unknown_short_type():
    shorts = [{"type": "unknown_type_for_test", "info": "test"}]
    report = format_short_circuit_report(shorts)
    assert "Unknown short type" in report
