# Circuijts

[![CI](https://github.com/USERNAME/circuijts/actions/workflows/ci.yml/badge.svg)](https://github.com/Kreijstal/circuijts/actions/workflows/ci.yml)

A Python package for parsing and validating textual circuit descriptions, with a focus on small-signal models and basic electronic components.

## Overview

Circuijts provides a human-readable format for describing electronic circuits, making it easy to:
- Define circuit topology and components
- Specify component connections and relationships
- Model small-signal behavior
- Validate circuit descriptions

## Installation

```bash
make deps
```

## Features

- **Component Declaration**: Define components like resistors, capacitors, transistors using simple syntax
  ```
  R R1_in        ; Resistor
  C C_load       ; Capacitor
  Nmos M_nfet1   ; NMOS transistor
  ```

- **Flexible Connection Syntax**:
  - Series connections using `--`
  - Parallel connections using `[]` and `||`
  - Direct node assignments using `:`
  - Component terminal blocks using `{}`

- **Support for**:
  - Basic components (R, L, C)
  - Transistors (NMOS, PMOS)
  - Voltage/Current sources
  - Controlled sources
  - Noise sources
  - Named currents

## Usage

### Basic Example

```circuijts
; RC Filter
R R_filter
C C_filter

(Vin) -- R_filter -- (Vout) -- C_filter -- (GND)
```

### Generate Small Signal Model

```bash
make generate-ssm FILE=circuits/amp1.circuijt
```

To print the model to stdout instead of saving to a file:
```bash
make generate-ssm FILE=circuits/amp1.circuijt -- --stdout
```

### Running Tests

```bash
make test
```

## Syntax Guide

### Component Declaration
Components must be declared before use:
```circuijts
Type InstanceName  ; e.g., R R1, C C1, Nmos M1
```

### Node Representation
- Regular nodes: `(node_name)`
- Device terminals: `(Device.Terminal)` e.g., `(M1.G)`
- Special nodes: `(GND)`, `(VDD)`

### Connection Methods
1. **Series**: `(N1) -- R1 -- C1 -- (N2)`
2. **Parallel**: `(Vout) -- [ R_load || C_bypass ] -- (GND)`
3. **Direct Assignment**: `(Vin_signal):(M1.G)`
4. **Component Block**:
   ```circuijts
   M1 {
       G: (Vin),
       S: (GND),
       D: (Vout)
   }
   ```

### Advanced Features
- Controlled sources: `gm*Vgs (->)`
- Noise sources: `idn_m1 (->)`
- Named currents: `(VCC) -- ->I_supply -- R1 -- (GND)`

## Examples

### NMOS Characterization
```circuijts
; Declarations
Nmos M1
V VGS_src
V VDS_src

; Connections
M1 { S:(GND), B:(GND) }
(GND) -- VGS_src (-+) -- (M1.G)
(GND) -- VDS_src (-+) -- ->ID1 -- (M1.D)
```

### Simple Amplifier
```circuijts
; Declarations
R R_in
Nmos M_amp
R R_load
C C_load
V Vin_sig

; Connections
M_amp { D:(VDD), B:(GND), S:(Vout) }
(GND) -- Vin_sig (-+) -- R_in -- (M_amp.G)
(Vout) -- [ R_load || C_load ] -- (GND)
```

## License

This project is under the AGPLv3 License.