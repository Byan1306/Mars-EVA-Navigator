# Mars EVA Navigator — Motion Genesis V5

## Scope and provenance

This module continues the astronaut locomotion work that was interrupted in
another temporary workspace. The uncommitted temporary workspace files could
not be recovered from GitHub. Instead, this change extends the verified
206-bone NASA Z-2 educational suit in the project's open feature branch.

**Scientific data are unchanged**: observed USGS/NASA Jezero DEM values,
their NoData mask and the scientific route planner are not rewritten.
Synthetic or illustrative rocks, sky and lighting must never enter the route
planner's terrain samples.

### What changed

- The independently authored NASA Z-2 visual rig still contains **206 adult
  anatomical joints** (80 axial, 126 appendicular). Only major surface
  deformation/animation groups are weighted; this is not a medical scan.
- New testable analytic **two-link IK** solves the actual femur and tibia
  angles and folds the knee in its intended forward direction.
- The gait phase advances with the **metres walked**, not just with elapsed
  time. Stopped characters do not deliberately run in place.
- Each planted foot has a **world-coordinate contact anchor**, followed by a
  raised swing arc to the next grounded contact.
- Swing-end prediction follows actual velocity including backward and
  lateral walking, not the character's hardcoded forward axis.
- Boot pitch and roll are bounded by **four measured DEM height samples**
  around the contact point, where all measurements exist.
- At NoData positions, the IK skips contact instead of assigning an invented
  elevation. The app's existing safe-ground restrictions remain independent.
- IK is throttled to **20/30/60 Hz** (low/balanced/high), and is skipped when
  the suit is hidden from camera in first person.
- A small browser HUD shows motion state, measured speed, observed FPS, IK
  update budget and foot-reach correction count. The FPS number is sampled
  from the render loop, not a promise of 60 FPS on every computer.
- The original anatomical overlay remains available using **K**.

### Known limits (important)

- This is an educational low-cost procedural hybrid of glTF animation and
  two-bone IK, not motion capture or NASA-certified EVA biomechanics.
- The NASA outer spacesuit mesh does not contain individual internal bones,
  separate glove fingers or surveyed anatomical weights.
- The world lock only holds within a leg's maximum reach; emergency
  corrections are counted in the HUD and can cause limited sliding.
- CTX data at ~20 m spacing do not reveal individual pebbles; do not
  infer unseen local foot obstacles from the DEM.
- A 206-bone glTF skeleton does not mean 206 independently simulated rigid
  bodies or 206 actively animated channels.
- Browser FPS/IK update rates must be measured on the user's machine before
  describing performance as verified for their RTX 4050.
- Automated browser tests prove software integration and frame rendering;
  they cannot by themselves certify natural human movement quality.

### Tests

```bash
node --test tests/motion-genesis.test.mjs
node --check astronaut_motion/motor.mjs
# Existing science and browser suite (CI):
python -m unittest discover -s tests -v
node --test tests/curiosity*.test.cjs tests/dem-routing.test.cjs tests/open-world-core.test.cjs
node tests/unified-browser.test.cjs
```

### Architecture

- `astronaut_motion/motor.mjs`: animate 206-bone glTF with foot anchors,
  two-link IK, quality gate, measured torso turns and telemetry.
- `astronaut_motion/math.mjs`: pure IK, slope normal, swing trajectory and
  distance-driven gait phase.
- `astronaut_motion/terrain_adapter.mjs`: read-only measured height sampler
  with explicit NoData handling.
- `astronaut_motion/quality.mjs`: conservative IK budgets for laptop GPUs.
- `astronaut_motion/metrics.mjs`: 1-second counters for debug and profiling.
- `tests/motion-genesis.test.mjs`: isolated deterministic mathematical tests.

V5 makes no assertion that Astra's four interrupted agents committed any of
these files; this module is an independent continuation using the current repo.
