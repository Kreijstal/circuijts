# -*- coding: utf-8 -*-
"""Integration tests for CLI entrypoints detect_shorts.py and generate_ssm.py."""

import subprocess
import sys


def test_detect_shorts_cli(tmp_path):
    circuit_file = tmp_path / "test_circuit.circuijt"
    circuit_file.write_text("""
    R R1
    (GND) -- R1 -- (GND)
    """)

    result = subprocess.run(
        [sys.executable, "detect_shorts.py", str(circuit_file), "--debug-dump"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Component Short: 'R1'" in result.stdout


def test_generate_ssm_cli(tmp_path):
    circuit_file = tmp_path / "amp.circuijt"
    circuit_file.write_text("""
    Nmos M1
    R R1
    M1 { G:(Vin), D:(Vout), S:(GND), B:(GND) }
    (Vout) -- R1 -- (VDD)
    """)

    output_dir = tmp_path / "output_models"
    result = subprocess.run(
        [sys.executable, "generate_ssm.py", str(circuit_file), "-o", str(output_dir), "--debug-dump"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert (output_dir / "amp_ssm.circuijt").exists()
    assert (output_dir / "amp_rules.txt").exists()


def test_generate_ssm_stdout(tmp_path):
    circuit_file = tmp_path / "amp.circuijt"
    circuit_file.write_text("""
    Nmos M1
    M1 { G:(Vin), D:(Vout), S:(GND), B:(GND) }
    """)

    result = subprocess.run(
        [sys.executable, "generate_ssm.py", str(circuit_file), "-s"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Small Signal Model Generated Automatically" in result.stdout
