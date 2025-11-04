## Copilot / Contributor Note: how the `domain` package works

This file explains the execution-chain and CNC state model for quick reference when making edits or generating code (for Copilot or contributors).

### High-level overview

- The domain implements a small Chain-of-Responsibility for interpreting NC/G-code nodes. Each link implements `handle(node, state)` and either processes the node or delegates to the `next_handler`.
- Handlers return a tuple: `(points_list | None, duration_seconds | None)`. If `points_list` is not None the control collects it as part of the tool path.
- `CNCState` is the canonical domain model for machine state (axes, offsets, modal groups, feed, etc.). Handlers mutate `CNCState` directly when appropriate.

### Key files to inspect / edit

- `src/ncplot7py/domain/exec_chain.py` — base `Handler` class and delegation contract.
- `src/ncplot7py/domain/cnc_state.py` — `CNCState` dataclass; use `resolve_target`, `update_axes`, `get_modal`, and `compute_distance` when writing handlers.
- `src/ncplot7py/shared/state_protocol.py` — minimal typing contract used by non-domain code to avoid importing full `CNCState`.
- `src/ncplot7py/domain/handlers/gcode_group0.py` — example handler for G50/G28/G4 that mutates `node.command_parameter` and `state`.
- `src/ncplot7py/domain/handlers/motion.py` — motion interpolation (G00/G01/G02/G03) and the place where `state.feed_rate` and `state.update_axes` are used.
- `src/ncplot7py/infrastructure/machines/stateful_iso_turn_control.py` — wiring: `GCodeGroup0ExecChainLink(next_handler=MotionHandler())` per canal, and how `run_nc_code_list` consumes handler outputs and builds `_tool_path`.

### Contract / guidance for Copilot edits

- When creating or editing handlers:
  - Implement `handle(node, state)` and either return `(points, duration)` or call `super().handle(node, state)` to delegate.
  - Prefer returning `None, None` only when no action is required.
  - Do not change the return shape — other parts of the system expect `(list, float)` or `(None, None)`.
  - Use `StateProtocol` when writing code outside the domain package for typing (avoid importing `CNCState` from non-domain modules).

- About `CNCState` mutation:
  - Handlers may mutate `state` (modal groups, axes, offsets, etc.). If an operation must be transactional (reversible on error), use `state.clone()` and restore if needed.
  - Use `resolve_target(target_spec, absolute)` to get absolute coordinates (it handles both absolute and relative delta modes).
  - Use `update_axes` to set final axis positions after motion handlers compute endpoints.

- NC command nodes (`NCCommandNode`):
  - Parameters are strings; handlers should convert using `float()` safely (current code uses try/except and falls back to 0.0). Prefer explicit validation if behaviour should change.
  - Handlers sometimes mutate `node.command_parameter` (e.g., G28 remapping UVW -> XYZ). This is intentional to let downstream handlers see corrected values.

### Important edge cases to keep in mind

- `feed_rate` units: current code treats `state.feed_rate` as units per minute (converted to mm/s in motion handler). Be explicit in comments or doc changes when altering behavior.
- Missing feed or zero feed: motion code falls back to `feed_rate = 1.0` when None. Consider adding clearer defaults or raising if feed is required.
- Arc interpolation: only XY-plane arcs are implemented; if you add multilane arcs, implement Z or plane-selection logic and add tests.
- Parameter parsing: silent fallbacks to 0.0 can hide malformed input — adding warnings/logging is recommended for maintainability.

### Tests and verification

- When changing domain behavior, add unit tests under `tests/unit` or `tests/integration` that exercise the handler chain and `CNCState` updates.
- Useful small tests:
  - G28 UVW->XYZ remapping and offset correction
  - Linear interpolation duration computation for known `feed_rate`
  - Arc interpolation using I/J vs R

### Quick checklist for Copilot when proposing changes

- Preserve the `Handler.handle(node, state) -> (points, duration)` contract.
- Prefer using domain utilities (`resolve_target`, `compute_distance`, `update_axes`) rather than direct dict math when possible.
- Add or update unit tests for behaviour changes.
- If adding new State fields accessed outside domain, update `shared/state_protocol.py` to include the minimal contract.

---

If you'd like, I can also add one or two example unit tests that follow this guidance (e.g., a test for G28 remapping).