#!/usr/bin/env python3
"""Download and verify a NASA 3D Resources astronaut GLB for the web viewer.

NASA Z-2 is a conceptual spacesuit, not a flight-qualified Mars EVA suit.
The downloaded model is published only with original NASA attribution.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import struct
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/"assets"/"astronaut_z2.glb"
NASA_SUIT_URL=(
 "https://raw.githubusercontent.com/nasa/NASA-3D-Resources/master/"
 "3D%20Models/Z2%20Spacesuit/Z2%20Spacesuit.glb"
)
NASA_SUIT_SOURCE="https://science.nasa.gov/3d-resources/z2-spacesuit/"
NASA_BASIC_URL=(
 "https://raw.githubusercontent.com/nasa/NASA-3D-Resources/master/"
 "3D%20Models/Astronaut/Astronaut.glb"
)

def validate_glb(content:bytes)->None:
    if len(content)<100 or content[:4]!=b"glTF":
        raise ValueError("Not a binary glTF asset.")
    version,size=struct.unpack("<II",content[4:12])
    if version!=2 or size!=len(content) or len(content)>50_000_000:
        raise ValueError("Invalid glTF header or file size.")

def download_verified(url:str)->bytes:
    with urlopen(Request(url,headers={"User-Agent":"Mars-EVA-Navigator/2026"}),timeout=150) as stream:
        blob=stream.read(50_000_001)
    validate_glb(blob)
    return blob

def main()->None:
    candidates=[
      (NASA_SUIT_URL,"NASA Z-2 Spacesuit","Conceptual NASA Z-2 spacesuit, not a verified Mars exploration suit."),
      (NASA_BASIC_URL,"NASA Astronaut","NASA 3D Resources astronaut; not a certified Mars EVA suit.")
    ]
    for url,model,limitations in candidates:
        try:
            if DEST.is_file():
                payload=DEST.read_bytes()
                validate_glb(payload)
                if len(payload)<2_000_000 and model=="NASA Z-2 Spacesuit":
                    DEST.unlink()
                    payload=download_verified(url)
            else:
                payload=download_verified(url)
            DEST.parent.mkdir(parents=True,exist_ok=True)
            DEST.write_bytes(payload)
            manifest={
              "publisher":"NASA",
              "source_url":url,
              "reference_page":NASA_SUIT_SOURCE if model=="NASA Z-2 Spacesuit" else "https://science.nasa.gov/3d-resources/astronaut/",
              "model":model,"sha256":hashlib.sha256(payload).hexdigest(),
              "size_bytes":len(payload),
              "status":"Official NASA 3D Resources asset; scene integration/rendering is educational.",
              "limitations":limitations
            }
            (DEST.parent/"astronaut_manifest.json").write_text(
                json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            print(json.dumps({"model":model,"size_bytes":len(payload),"sha256":manifest["sha256"]}))
            return
        except (OSError,ValueError,TimeoutError) as exc:
            print(f"NASA suit asset unavailable ({model}): {exc}")
            DEST.unlink(missing_ok=True)
    raise OSError("Official NASA astronaut not available; procedural suit fallback remains usable.")

if __name__=="__main__":
    main()
