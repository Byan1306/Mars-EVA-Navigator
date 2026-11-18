#!/usr/bin/env python3
"""Publish only public application assets and the validated real Jezero DEM.

Never publish a local database, .env file, raw GeoTIFF, or repo internals.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil

try:
    from .verify_static_dem import verify
except ImportError:  # direct invocation: python scripts/build_static_site.py
    from verify_static_dem import verify

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FILES = (
    "index.html",
    "mars_eva_navigator_guia_de_supervivencia_interplanetaria_nasa_space_apps_2026.html",
    "curiosity_explorer.js",
    "curiosity_explorer.css",
    "curiosity_pro.css",
    "curiosity_360_renderer.js",
    "open_world.html",
    "open_world.css",
    "open_world.mjs",
    "open_world_visuals.mjs",
    "astronaut_motion.mjs",
    "open_world_core.js",
)


def build(output: Path, dem: Path) -> None:
    source = dem.resolve()
    metadata = verify(source)
    output = output.resolve()
    if output == ROOT or ROOT in output.parents and output == source.parent:
        raise ValueError("Output must be a dedicated publish directory, never the repository root")
    output.mkdir(parents=True, exist_ok=True)
    for name in PUBLIC_FILES:
        path = ROOT / name
        if not path.is_file():
            raise FileNotFoundError(f"Missing public asset: {name}")
        shutil.copy2(path, output / name)
    # Explicit, auditable Motion Genesis submodule allowlist only.
    motion_dir = output / "astronaut_motion"
    motion_dir.mkdir(exist_ok=True)
    for name in ("motor.mjs", "math.mjs", "quality.mjs", "terrain_adapter.mjs", "metrics.mjs"):
        origin = ROOT / "astronaut_motion" / name
        if not origin.is_file():
            raise FileNotFoundError(f"Missing verified motion source: {name}")
        shutil.copy2(origin, motion_dir / name)
    # Only the converted, provenance-pinned walking clip is public. The
    # original CMU BVH ZIP remains in source control for independent audit.
    mocap = ROOT / 'mocap' / 'cmu_walk_human_v6.json'
    if mocap.is_file():
        directory = output / 'mocap'
        directory.mkdir(exist_ok=True)
        shutil.copy2(mocap, directory / mocap.name)
    # Bundle Three.js locally: no CDN is needed at runtime.
    three = ROOT / "node_modules" / "three" / "build" / "three.module.js"
    if not three.is_file():
        raise FileNotFoundError("Three.js is missing. Run npm install before building.")
    (output / "vendor").mkdir(exist_ok=True)
    shutil.copy2(three, output / "vendor" / "three.module.js")
    three_core = ROOT / "node_modules" / "three" / "build" / "three.core.js"
    if not three_core.is_file():
        raise FileNotFoundError("Three.js core module missing. Run npm install.")
    shutil.copy2(three_core, output / "vendor" / "three.core.js")
    extras = ROOT / "node_modules" / "three" / "examples" / "jsm"
    for relative in ("loaders/GLTFLoader.js", "loaders/DRACOLoader.js", "utils/BufferGeometryUtils.js"):
        source_mod = extras / relative
        if not source_mod.is_file():
            raise FileNotFoundError(f"Three.js addon not installed: {relative}")
        out_file = output / "vendor" / relative
        out_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_mod, out_file)
    # Official NASA Z-2 glTF uses KHR_draco_mesh_compression.
    # Ship the WASM decoder locally so the web demo works fully offline.
    decoder_dir = output / "vendor" / "draco"
    decoder_dir.mkdir(parents=True, exist_ok=True)
    for name in ("draco_wasm_wrapper.js", "draco_decoder.wasm", "draco_decoder.js"):
        decoder_file = extras / "libs" / "draco" / name
        if not decoder_file.is_file():
            raise FileNotFoundError(f"Local Draco decoder missing: {name}")
        shutil.copy2(decoder_file, decoder_dir / name)
    astronaut = ROOT / "assets" / "astronaut_z2.glb"
    animated_suit = ROOT / "assets" / "astronaut_z2_anatomical_206.glb"
    astronaut_meta = ROOT / "assets" / "astronaut_manifest.json"
    if astronaut.is_file() and astronaut_meta.is_file():
        (output / "assets").mkdir(exist_ok=True)
        shutil.copy2(astronaut, output / "assets" / astronaut.name)
        if not animated_suit.is_file():
            raise FileNotFoundError("Motion Genesis requires a 206-bone NASA Z-2 educational rig. Run scripts/build_motion_asset.py.")
        shutil.copy2(animated_suit, output / "assets" / animated_suit.name)
        shutil.copy2(astronaut_meta, output / "assets" / astronaut_meta.name)
    # Optional USGS-registered CTX texture; never ship unverified arbitrary imagery.
    texture = ROOT / "jezero_ortho.jpg"
    texture_meta = ROOT / "jezero_ortho_meta.json"
    if texture.exists() and texture_meta.exists():
        shutil.copy2(texture, output / texture.name)
        shutil.copy2(texture_meta, output / texture_meta.name)
    shutil.copy2(source, output / "jezero_dem_precomputed.json")
    print(f"Static NASA science build ready: {output} ({metadata['valid_fraction']:.1%} valid cells)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dem", required=True, type=Path, help="Validated JSON generated from USGS")
    parser.add_argument("--output", default=ROOT / "_site", type=Path)
    args = parser.parse_args()
    build(args.output, args.dem)


if __name__ == "__main__":
    main()
