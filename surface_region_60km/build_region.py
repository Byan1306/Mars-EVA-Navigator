#!/usr/bin/env python3
"""Bundle the measured Jezero region into a portable, offline website."""
import argparse,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HERE=Path(__file__).resolve().parent
FILES=("region.html","region_world.mjs")
def build(out):
 out=Path(out).resolve()
 if not (out/"terrain_manifest.json").is_file():
  raise FileNotFoundError("No measured 60km terrain; refusing synthetic fallback")
 for name in FILES:shutil.copy2(HERE/name,out/name)
 shutil.copy2(HERE/"README.md",out/"README.md")
 (out/"index.html").write_text(
  '<!doctype html><html lang="es"><meta charset="utf-8">'
  '<meta http-equiv="refresh" content="0;url=./region.html">'
  '<title>Jezero 60 km</title><a href="./region.html">Abrir Jezero 60 km</a></html>',encoding="utf-8")
 source=ROOT/"node_modules"/"three"/"build"
 vendor=out/"vendor";vendor.mkdir(exist_ok=True)
 for name in ("three.module.js","three.core.js"):
  if not (source/name).is_file():raise FileNotFoundError("npm install required")
  shutil.copy2(source/name,vendor/name)
 (out/"scripts").mkdir(exist_ok=True)
 for path in ("prepare_region.py","verify_region.py","build_region.py"):
  shutil.copy2(HERE/path,out/"scripts"/path)
 (out/"INICIAR_JEZERO_60KM.bat").write_text(
  '@echo off\r\ncd /d "%~dp0"\r\n'
  'where py >nul 2>nul\r\nif %errorlevel%==0 (py -3 -m http.server 8765) '
  'else (python -m http.server 8765)\r\n',encoding="utf-8")
 print("READY_PORTABLE_REGION",out)
if __name__=="__main__":
 p=argparse.ArgumentParser()
 p.add_argument("output",type=Path)
 build(p.parse_args().output)
