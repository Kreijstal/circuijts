**Circuijts Specification for Textual Circuit Description**

**1. Overview**

This document specifies a simple textual format for describing electronic circuits, primarily focusing on small-signal models, basic connections, and simple sources. The goal is to provide a human-readable way to represent circuit topology and components connecting different nodes. It is *not* intended to be a fully-featured netlist language like SPICE but serves as a clear communication tool.

**2. Syntax**

*   **Component Declarations:**
    *   Components, including sources, must be explicitly declared before use or as they are introduced.
    *   Format: `Type InstanceName`
    *   `Type`: Specifies the kind of component using standard abbreviations (e.g., `R` for Resistor, `C` for Capacitor, `L` for Inductor, `Nmos` for N-channel MOSFET, `Pmos` for P-channel MOSFET, `V` for Voltage Source, `I` for Current Source, `Opamp` for Operational Amplifier). The list of supported types is defined by the specific parser/tool implementation.
    *   `InstanceName`: A unique alphanumeric identifier for the component instance.
    *   Declarations are typically placed at the beginning of a circuit description or before the component is first used in a connection.
    *   Example:
        ```circuijts
        R R1_in        ; Declares R1_in as a Resistor
        C C_load       ; Declares C_load as a Capacitor
        Nmos M_nfet1   ; Declares M_nfet1 as an Nmos transistor
        V Vs_in      ; Declares Vs_in as a Voltage Source
        ```
*   **Nodes:**
    *   Represent abstract points or nets of equal potential.
    *   Represented by names enclosed in parentheses: `(node_name)`.
    *   Node names are typically alphanumeric strings.
    *   Device terminals can be treated as nodes using dot notation: `(Device.Terminal)`, e.g., `(M1.G)`, `(M2.S)`. These represent the specific connection point *at* that terminal. These nodes can be assigned using the `:` operator or the Component Connection Block.
    *   Special predefined node: `(GND)` represents the global ground or zero-potential reference. Other common nodes like `(VDD)` might be used by convention for supply rails.
*   **Components:**
    *   Represented by their declared `InstanceName` (e.g., `Cf`, `Cfb`, `rds1`, `CL`, `R1`, `M1`).
    *   All components must be declared using the `Type InstanceName` syntax (see Component Declarations).
    *   Component values or parameters are not typically specified directly in the connection string but assumed to be known from context, comments, or TODO: potential future extensions to the declaration syntax (e.g., `R R1 1k`).
*   **Component Connection Block (`{}`):**
    *   Provides a concise way to define multiple direct connections for a single component instance.
    *   Format: `InstanceName { Terminal1:(NodeA), Terminal2:(NodeB), ... }`
    *   It can only be written on a single line:
        ```circuijts
        InstanceName {Terminal1 : (NodeA),Terminal2 : (NodeB),Terminal3 : (NodeC)}
        ```
    *   `InstanceName`: The declared instance name of the component (e.g., `M_nfet1`, `U1A`).
    *   `{}`: Encloses the set of terminal assignments for this component instance.
    *   `TerminalX`: The name of the component's terminal (e.g., `G`, `D`, `S`, `IN+`, `OUT`).
    *   `:`: The direct assignment operator.
    *   `(NodeY)`: The node to which the terminal is connected.
    *   This syntax is a shorthand for multiple `(InstanceName.TerminalX):(NodeY)` direct assignments.
    *   Example: `M_nfet1 { G:(Vin), S:(GND), D:(Vout) }` is equivalent to writing:
        `(M_nfet1.G):(Vin)`
        `(M_nfet1.S):(GND)`
        `(M_nfet1.D):(Vout)`
*   **Sources (Independent Voltage):**
    *   Declared using `V InstanceName` (e.g., `V Vin_supply`).
    *   Represented in connection paths by their `InstanceName` followed by a polarity indicator: `SourceName (Polarity)`.
    *   `Polarity`:
        *   `(-+)`: Indicates the negative terminal is towards the element preceding it in the `--` chain, and the positive terminal is towards the element following it.
        *   `(+-)`: Indicates the positive terminal is towards the element preceding it, and the negative terminal is towards the element following it.
    *   Sources are placed within series connection paths using the `--` operator.
    *   Example: `V Vin_supply` then `(GND) -- Vin_supply (-+) -- R1`
*   **Series Connections (`--`):**
    *   The double hyphen `--` indicates a series connection *between* nodes, components, and sources.
    *   It signifies that the listed elements form a continuous path.
    *   Format: `element1 -- element2 -- element3 ...` where `element` can be a `(node)`, a declared `component_instance_name`, or a `source_instance_name (polarity)`.
    *   **A series connection path must begin with an explicit node `(node_name)` or a device terminal `(Device.Terminal)`.** A component instance name cannot be the first element in a new series path definition on a line.
        *   Correct: `(N1) -- R1 -- C1 -- (N2)`
        *   Incorrect if starting a new path: `R1 -- C1 -- (N2)` (R1 must be preceded by a node like `(N_some) -- R1...`)
    *   **Nodes between components/sources are optional.** If a node is not explicitly written between two components/sources connected by `--`, an implicit, unnamed node exists between them.
        *   `(N1) -- R1 -- C1 -- (N2)` is topologically equivalent to `(N1) -- R1 -- (internal_node1) -- C1 -- (N2)`.
    *   **Crucially, `--` builds series paths. It connects *through* components/sources or links them *to* nodes. For a direct, zero-impedance connection between two named nodes (often making them aliases), or for defining specific terminal connections for multi-terminal devices, use the `:` operator or the Component Connection Block `{}`.**
    *   Example: `(Vin_node) -- R_series -- (M1.G)` (Node Vin_node connected through declared resistor R_series to node M1.G)
    *   Example: `(Vs_node) -- C_filter -- (GND)` (Declared capacitor C_filter connected between node Vs_node and node GND)
    *   Example: `(GND) -- Vin_src (-+) -- R_path -- C_couple -- (M1.G)` (Declared source Vin_src in series with declared R_path and C_couple, between GND and M1.G).
*   **Direct Node Assignment (`:`):**
    *   The colon `:` indicates a direct, zero-impedance assignment.
    *   Used within Component Connection Blocks or for:
        *   Connecting a device terminal to a named node: `(Device.Terminal):(NodeName)` or vice-versa.
        *   Aliasing two named nodes: `(NodeA):(NodeB)`.
    *   Example: `(Vin_signal):(M1.G)`
    *   Example: `(M1.D):(VDD)`
*   **Parallel Connections (`[]` with `||`):**
    *   Declared components connected in parallel *between* two points are enclosed in `[]` and separated by `||`.
    *   Format: `point_A -- [ Inst1 || Inst2 || ... ] -- point_B`
    *   Example: `(Vout) -- [ R_load || C_bypass ] -- (GND)`
    *   Example: `(M1.D) -- [ rds_m1 || Cgd_m1 ] -- (M1.G)` (assuming rds_m1, Cgd_m1 are declared components like `R rds_m1`, `C Cgd_m1`)
*   **Controlled Sources (within Parallel Blocks `[]`):**
    *   Format: `gain*control_variable (->)` or `gain*control_variable (<-)`
    *   These are not components that are separately declared with `Type InstanceName` but are behavioral elements defined in place.
    *   Example: `(Vd) -- [ gm_val*Vgs (->) || gds_res ] -- (Vs)` (gds_res would be a declared `R` instance)
*   **Noise Sources (within Parallel Blocks `[]`):**
    *   Format: `noise_id (->)` or `noise_id (<-)`
    *   These are behavioral elements defined in place.
    *   Example: `(M1.D) -- [ gm1*vgs1 (->) || rds1 || idn_m1 (->) ] -- (M1.S)` (rds1 is a declared `R` instance)
*   **Named Currents on Paths:**
    *   Format: `element1 -- ->CurrentName -- element2` or `element1 -- <-CurrentName -- element2`
    *   Example: `(VCC) -- ->I_supply -- R_limit -- (NodeX)`
*   **Comments:**
    *   Lines starting with a semicolon `;` are treated as comments.

**3. Semantics**

*   Components must be declared with `Type InstanceName` (using standard abbreviations for `Type`) before being used in connections.
*   Nodes `( )` represent points (nets) of equal potential.
*   The Component Connection Block `InstanceName { ... }` defines direct connections for a component's terminals.
*   The `--` operator describes a series path, which must start with a node or an already-connected device terminal.
*   The `:` operator establishes a direct, zero-impedance connection or alias.
*   The `[]` block aggregates parallel elements.

**4. Examples**

*   **RC Filter:**
    ```circuijts
    ; Declarations
    R R_filter
    C C_filter

    ; Connections
    (Vin) -- R_filter -- (Vout) -- C_filter -- (GND)
    ```
*   **NMOS Characterization Circuit:**
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
*   **Amplifier with Input Source:**
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
*   **Feedback Circuit (assuming gm1, rds1, rds2 are behavioral or abstract parameters, Cl is a capacitor):**
    ```circuijts
    ; Declarations
    C Cf_fb
    C Cfb_path
    C Cl_load
    R Rds1_m  ; Assuming rds1, rds2 are represented by resistor components
    R Rds2_m

    ; Connections
    (Vin) -- Cf_fb -- (Vx)
    (Vx) -- Cfb_path -- (Vout)
    (Vout) -- [ gm1*Vx (->) || Rds1_m || Rds2_m || Cl_load ] -- (GND)
    ; Note: Vx is defined by the connection point between Cf_fb and Cfb_path
    ; gm1*Vx is a behavioral VCCS
    ```
*   **Cascode Amplifier Small-Signal Model:**
    ```circuijts
    ; Declarations
    Nmos M1
    Nmos M2
    V vin_src
    R rds1_m1  ; Output resistance of M1 (as a resistor model)
    R rds2_m2  ; Output resistance of M2 (as a resistor model)
    C CL_out   ; Load capacitance

    ; M1 Connections
    M1 { S:(GND) }
    (GND) -- vin_src (-+) -- (M1.G)
    (M1.D) -- [ gm1*vgs1 (->) || rds1_m1 || idn1 (->) ] -- (M1.S)

    ; M2 Connections
    M2 { G:(GND), S:(M1.D), D:(vout) }
    (M2.D) -- [ gm2*vgs2 (->) || rds2_m2 || idn2 (->) ] -- (M2.S)

    ; Load Connection
    (vout) -- CL_out -- (GND)

    ; Control voltage definitions (comments)
    ; vgs1 = (M1.G) - (M1.S)
    ; vgs2 = (M2.G) - (M2.S)
    ```
