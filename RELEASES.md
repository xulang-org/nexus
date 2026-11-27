# Nexus Engine Releases

## v0.1.1

First public tagged release of Nexus Engine (`github.com/xulang-org/nexus`), aligned with **Xu SDK v0.14.2**.

### Highlights

- **Core Architecture & Data Model**: Layered module contract (`architecture.json` + `tools/check_layers.py`) isolating pure CPU foundation (`foundation/math`, `color`, `diagnostics`, `events`, `spatial`), resource schemas/codecs (`resources/*`, `formats/*`), deterministic runtime subsystems (`scene`, `ecs`, `physics2d`, `physics3d`, `navigation`, `ai/bt`, `audio/mixer`, `networking`, `animation`, `input`, `timing`, `modeling`), and `integration/*` bridges.
- **3D & 2D Rendering**: Clustered Forward lighting, Split-Sum IBL, Meshlet Visibility Buffer (`ModernPipeline3D`), HDR Bloom/GTAO/SSR/TAA/ACES, 2D dynamic lighting & soft shadows, `Sprite3D`, GPU linear skinning, and MSL / GLSL 450 / HLSL SM 6.0 shader parity across 45 3D shaders and 7 2D shaders.
- **Developer Core Systems (Rounds 1–4)**:
  - Deterministic `Xoshiro128++` PRNG & 2D Poisson-disc sampling, 2D loose quadtree, universal Undo/Redo `CommandHistory`, `EcsCommandBuffer` & `EntityTemplate`.
  - Tiled dynamic NavMesh + portal stitching + Utility AI reasoner, budgeted DAG job queue & partition streaming scheduler, layered input context stack & replay.
  - Multi-slot save catalog with SHA-256 checksum & fallback recovery, `AudioCueBank` with round-robin/random/shuffle-no-repeat & voice stealing, pole-safe analytical springs & `MotionSequence`.
  - Authoritative RPC registry with token-bucket rate limiter & peer heartbeat tracker, 3D constraint solver (`ConstraintSolver3D`) & `NodePool`.
- **Tools & Native Bridges**:
  - Prebuilt desktop/CLI binaries per target platform (`macos-arm64`, `macos-x64`, `linux-x64`, `linux-arm64`, `windows-x64`): `nexus-project`, `nexus-project-validate`, `nexus-project-viewport`, `nexus-studio`, `xu-nexus-script`, `nexus-project-editor`, `nexus-tilemap-editor`.
  - Unified multi-platform `.xulib` bridges (`nexus_audio`, `nexus_image`, `nexus_steam`, `nexus_console`, `nexus_taptap`) bundled in `nexus-v0.1.1-native-all.tar.gz` as well as per-platform release archives.
