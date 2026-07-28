# AXIOM System Architecture

## Overview

AXIOM v5.3.0 is structured as a **Sovereign AI Operating System Layer**. It moves beyond the "AI application" paradigm into a persistent system service that manages hardware, filesystems, and network nodes as first-class citizens in an autonomous reasoning loop.

---

## 🗺️ System Architecture Diagram

```mermaid
graph TD
    %% Global Styles
    classDef kernel fill:#f1c40f,stroke:#f39c12,stroke-width:2px,color:#000
    classDef interface fill:#3498db,stroke:#2980b9,stroke-width:2px,color:#fff
    classDef security fill:#e74c3c,stroke:#c0392b,stroke-width:2px,color:#fff
    classDef memory fill:#9b59b6,stroke:#8e44ad,stroke-width:2px,color:#fff
    classDef network fill:#2ecc71,stroke:#27ae60,stroke-width:2px,color:#fff

    %% Components
    HUD([Wayland Multimodal HUD]):::interface
    CLI([AXIOM CLI]):::interface
    IDE([Cursor/VSCode/Neovim]):::interface

    subgraph Kernel_Supervisor [AXIOM Sovereign Kernel]
        Master[Kernel Master Daemon]:::kernel
        EventBus[High-Speed IPC EventBus]:::kernel
        SelfPatcher[Self-Patching Registry]:::kernel
    end

    subgraph Security_Layer [Isolation & Execution]
        Bwrap[Bubblewrap Sandbox]:::security
        QEMU[KVM Micro-VMs]:::security
        Verifier[SHA256 Release Verifier]:::security
    end

    subgraph Semantic_Storage [AxiomFS & Memory]
        FUSE[AxiomFS FUSE Mount]:::memory
        GraphRAG[GraphRAG / Vector DB]:::memory
        SQLite[Persistence Layer]:::memory
    end

    subgraph Federation_Swarm [Networking & LLMs]
        P2P[LAN P2P Mesh]:::network
        Consensus[Swarm Consensus Engine]:::network
        MCPServer[MCP Server]:::network
        LLMs[Hybrid LLM Router: Ollama / Claude]:::network
    end

    %% Interactions
    HUD <--> Master
    CLI <--> Master
    IDE <--> MCPServer
    MCPServer <--> Master

    Master <--> EventBus
    EventBus <--> SelfPatcher

    Master -->|Orchestrate| Bwrap
    Master -->|Orchestrate| QEMU
    QEMU --> Verifier

    Master <--> FUSE
    FUSE <--> GraphRAG
    GraphRAG <--> SQLite

    Master <--> Consensus
    Consensus <--> P2P
    Consensus <--> LLMs
```

---

## 🔧 Subsystem Deep-Dives

### 1. **Sovereign Kernel & Self-Patcher** (`axiom.kernel`)
The Kernel is a persistent `systemd` or `launchd` service that acts as the supervisor for all other components. It maintains an atomic component registry. The **Self-Patcher** allows the kernel to download, verify, and "hot-swap" its own Python modules without losing state, enabling live evolution of agent logic.

### 2. **Hardware Isolation: Bwrap & QEMU** (`axiom.security`)
To prevent "hallucination-driven system damage," all tool execution is sandboxed:
- **Bubblewrap (`bwrap`)**: Rootless, unprivileged containers for standard file/shell operations.
- **QEMU/KVM**: Fully isolated micro-VMs for high-risk operations or complex software builds, featuring snapshotting and state-rollback.

### 3. **AxiomFS: Semantic Filesystem** (`axiom.fs`)
AxiomFS mounts your agent's long-term memory as a standard Linux directory. 
- `/mnt/axiom/memories/` - Dynamic folders based on GraphRAG clusters.
- `/mnt/axiom/scratch/` - Volatile memory for active task reasoning.
- `/mnt/axiom/vault/` - Encrypted long-term secrets.

### 4. **Swarm Consensus Engine** (`axiom.swarm`)
When complex tasks are initiated, AXIOM triggers a **Swarm Loop**:
1. **Delegation**: The task is broadcasted to the local P2P Mesh.
2. **Specialization**: Nodes (local or LAN) bid based on their capabilities (e.g., "Node A has an H100 for heavy lifting," "Node B has local file access").
3. **Reasoning**: Multiple agents generate candidate solutions.
4. **Consensus**: A majority-vote or "Judicial Agent" validates the plan before execution in a sandbox.

### 5. **Multimodal HUD** (`axiom.gui`)
A floating Wayland overlay built with PySide6. It provides:
- **Low-Latency Voice**: GPU-accelerated STT (Whisper) for hands-free control.
- **Ambient Awareness**: Visual indicators of kernel health, memory usage, and swarm activity.
- **Direct Interaction**: Context-aware tooltips that appear over other windows via Wayland protocol extensions.

---

## 🔄 Autonomous Swarm Consensus Lifecycle

The following sequence diagram outlines how the Swarm resolves a high-complexity directive (e.g., "Implement a new feature and verify its security").

```mermaid
sequenceDiagram
    participant U as User / HUD
    participant K as Kernel Master
    participant S as Swarm Consensus
    participant G as Generalist Agent
    participant C as Coder Agent
    participant T as Test/Audit Agent
    participant V as Sandbox (Bwrap/QEMU)

    U->>K: Directive: "Build secure IPC bridge"
    K->>S: Initiate Swarm Loop
    S->>G: Analyze & Decompose Directive
    G->>C: Generate Code Implementation
    C->>V: Execute & Build in Sandbox
    V-->>C: Build Results
    C->>T: Handover for Auditing
    T->>V: Run Fuzzing & Security Tests
    V-->>T: Pass/Fail Report
    T-->>S: Audit Consensus (Approved/Rejected)
    S-->>K: Final Verified Artifact
    K-->>U: HUD Notification: Task Complete
```

---

## 🚀 Future Roadmap: v6.0 and Beyond
- **Hardware Brain-Bridge**: Direct kernel modules for FPGA-accelerated inference.
- **Global Mesh**: Encrypted WireGuard-based federation across public networks.
- **Neural IPC**: Binary event stream optimization for zero-copy memory sharing between local nodes.
