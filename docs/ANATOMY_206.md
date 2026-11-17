# Mars EVA Navigator — Astronaut anatomical 206 (educational)

NASA's Z-2 visual spacesuit previously had no supplied skeletal armature. This
module creates **206 named adult anatomical bones**: **80 axial + 126
appendicular**, in an acyclic bone hierarchy. The rig is designed to support
efficient third-person walking in Three.js, **not** to reconstruct an actual
astronaut's internal skeleton from a medical scan.

## Anatomy and optimized motion

- Axial: 8 cranial + 14 facial + 6 auditory ossicles + 1 hyoid +
  26 spinal + 25 thoracic = **80**.
- Appendicular: 4 pectoral girdle + 60 arm/hand + 2 pelvic girdle +
  60 leg/foot = **126**.
- 206 genuine glTF skin joints, named consistently; no duplicates or cycles.
- **23 animated bones** move the body visibly (hip/femur, tibia, talus,
  humerus, forearm, hands, spine, head and a few fingers).
- The surface of NASA's visual Z-2 suit only has skin weights on about
  **21 visible deformation groups**, because bones like ribs, the tiny
  auditory ossicles and finger phalanges cannot deform independently if
  their own meshes are missing.
- Four GPU influences per vertex; gait clips idle, walk, fast_walk;
  2-bone analytic IK with CTX DEM contact.
- Press **K** inside the 3D world to view/hide the **conceptual 206-joint
  skeleton overlay**. The overlay is only instantiated when requested.
- The original visual NASA Z-2 mesh geometry and textures are preserved.

**This is not 206 distinct rigid-body dynamics simulations.** The adult
skeletal count and educational pivot locations should not be mistaken for
biomechanical measurements or a NASA-approved Mars EVA motion model.

## Regeneration

1. Install the repository's pinned Python and npm packages.
2. `python scripts/prepare_astronaut.py`
3. `node scripts/decode_nasa_z2.cjs assets/astronaut_z2.glb node_modules/three/examples/jsm/libs/draco/draco_decoder.js _motion_raw`
4. `python scripts/build_motion_asset.py assets/astronaut_z2.glb _motion_raw assets/astronaut_z2_anatomical_206.glb`
5. `python scripts/verify_anatomy206.py assets/astronaut_z2_anatomical_206.glb`

The NASA Z-2 original source SHA-256 is pinned in the builder. Original
USGS Mars topography and Astra's verified science planner remain unchanged.
See [PR #12](https://github.com/Byan1306/Mars-EVA-Navigator/pull/12).
