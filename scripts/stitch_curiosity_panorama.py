#!/usr/bin/env python3
"""Create an experimental photographic panorama from genuinely overlapping rover frames.

This is not 3D photogrammetry. It does not invent images between rover positions,
does not interpolate missing terrain, and does not guarantee a 360-degree view.
For scientific traceability, preserve the original NASA files and their URLs.
"""
import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def find_images(directory: Path, maximum: int) -> list[Path]:
    if not directory.is_dir():
        raise ValueError(f"El directorio de imágenes no existe: {directory}")
    paths = sorted(
        x for x in directory.iterdir()
        if x.is_file() and x.suffix.lower() in IMAGE_SUFFIXES
    )
    if len(paths) < 3:
        raise ValueError("Se necesitan tres o más imágenes NASA originales que se solapen.")
    if len(paths) > maximum:
        raise ValueError(f"Hay {len(paths)} fotografías; el máximo configurado es {maximum}. "
                         "Selecciona un conjunto más pequeño de imágenes de una sola estación.")
    return paths


def resize_image(image, cv2, max_side: int):
    height, width = image.shape[:2]
    if width <= max_side and height <= max_side:
        return image
    ratio = max_side / max(width, height)
    return cv2.resize(image, (max(1, round(width * ratio)), max(1, round(height * ratio))),
                      interpolation=cv2.INTER_AREA)


def sha256_file(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def make_manifest(source_paths: list[Path], output: Path, sol: int, shape: tuple):
    return {
        "kind": "experimental-photographic-stitch",
        "mission": "NASA Mars Science Laboratory / Curiosity",
        "sol": sol,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "output_file": output.name,
        "width_px": int(shape[1]),
        "height_px": int(shape[0]),
        "method": "OpenCV Stitcher PANORAMA",
        "coverage_360_degrees": "NOT VERIFIED",
        "camera_georeference": "NOT VERIFIED",
        "native_3d_depth": False,
        "review_required": True,
        "notice": (
            "The imagery originates from user-selected source files; no invented terrain "
            "was added, but automatic feature stitching can introduce errors and the "
            "result is not a certified panorama, 3D model or full 360-degree capture."
        ),
        "sources": [
            {
                "filename": file.name,
                "sha256": sha256_file(file),
                "official_source_url": "Add the original NASA URL and camera ID here before publication",
            }
            for file in source_paths
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True,
                        help="Folder of overlapping NASA raw photos from the same stationary site")
    parser.add_argument("--sol", type=int, required=True,
                        help="NASA mission sol documented for this frame sequence")
    parser.add_argument("--output", type=Path, default=Path("curiosity_panorama_experimental.jpg"))
    parser.add_argument("--max-side", type=int, default=1920,
                        help="Maximum input image dimension (prevents memory overload)")
    parser.add_argument("--max-photos", type=int, default=30)
    args = parser.parse_args()
    if not 0 <= args.sol <= 10000:
        parser.error("--sol must be between 0 and 10000")
    if not 640 <= args.max_side <= 6000:
        parser.error("--max-side must be between 640 and 6000")
    if not 3 <= args.max_photos <= 100:
        parser.error("--max-photos must be between 3 and 100")
    if args.output.suffix.lower() not in (".jpg", ".jpeg", ".png"):
        parser.error("Use JPEG or PNG for the result")
    try:
        import cv2
    except ImportError as error:
        raise SystemExit("Falta OpenCV. Instala: python -m pip install opencv-python-headless") from error

    sources = find_images(args.input_dir, args.max_photos)
    images = []
    for item in sources:
        picture = cv2.imread(str(item), cv2.IMREAD_COLOR)
        if picture is None:
            raise SystemExit(f"No se puede leer {item.name}. Verifica el archivo.")
        images.append(resize_image(picture, cv2, args.max_side))
    print(f"Intentando unir {len(images)} fotografías solapadas del Sol {args.sol}…")
    status, mosaic = cv2.Stitcher_create(cv2.Stitcher_PANORAMA).stitch(images)
    if status != cv2.Stitcher_OK or mosaic is None:
        raise SystemExit(
            f"OpenCV no pudo unir estas imágenes (estado {status}). "
            "Esto suele indicar superposición insuficiente, cámaras/perspectivas incompatibles, "
            "movimiento del rover entre tomas o falta de rasgos visuales compartidos. "
            "No se inventará un panorama de relleno."
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(args.output), mosaic):
        raise SystemExit("No fue posible escribir el panorama al disco.")
    manifest = make_manifest(sources, args.output, args.sol, mosaic.shape)
    meta_path = args.output.with_name(args.output.stem + ".provenance.json")
    meta_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Panorama construido: {args.output} ({mosaic.shape[1]} × {mosaic.shape[0]} píxeles)")
    print(f"Procedencia: {meta_path}")
    print("ATENCIÓN: mosaico experimental; cobertura 360° y orientación no verificadas.")


if __name__ == "__main__":
    main()
