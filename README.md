# Mars EVA Navigator 🚀

### Every Step Matters

**NASA Space Apps Challenge 2026 | Interplanetary Survival Guide: Martian Map**

**Mars EVA Navigator** is an interactive prototype for planning exploration routes on Mars. It uses actual Martian elevation data to compare possible paths, examine slopes, and explore what could happen during an extravehicular activity (EVA).

We started with a simple question: **How do you choose the best route on a planet you've never walked on?**

We didn't want to build just another map of Mars. We wanted to use NASA's scientific data to help people understand *why* one route might be preferable to another.

## 🎥 Watch the project video

[![Watch Mars EVA Navigator on YouTube](https://img.youtube.com/vi/syIeHq7CK50/hqdefault.jpg)](https://youtu.be/syIeHq7CK50)

**[Watch our Mars EVA Navigator presentation](https://youtu.be/syIeHq7CK50)**

## What does it do?

- **Compare three route options:** green (safety-oriented), blue (balanced), and red (speed-oriented).
- **Use real elevations:** a Jezero Crater digital elevation model (DEM) supplies terrain heights to the route planner.
- **Explore the surface:** interactive maps and a 3D terrain view provide geographical context.
- **Consider emergencies:** simulate return-route planning when a mission does not go as expected.
- **Discover scientific context:** explore points of interest, Mars missions, and rover imagery.

The project is a **hackathon prototype**, not a certified system for astronaut navigation or safety.

## Why it matters

On Mars, the shortest route is not necessarily the safest or most useful. The terrain might be steep, information could be missing, or another route might make more sense for a particular mission. Our goal is to make those differences visible and help people think about the trade-offs before choosing where to go.

With further validation, the same approach could eventually help research and planning for exploration of Mars and other worlds.

## NASA resources

| Resource | Purpose |
| --- | --- |
| [HiRISE Digital Terrain Models](https://hirise.lpl.arizona.edu/dtm/) | Elevation data for Jezero terrain analysis and route planning. |
| [NASA Mars Trek](https://trek.nasa.gov/mars/) | Martian mapping and geographical context. |
| [NASA Perseverance images](https://mars.nasa.gov/mars2020/multimedia/raw-images/) | Mission imagery and context for Jezero Crater. |
| [NASA Curiosity images](https://mars.nasa.gov/msl/multimedia/raw-images/) | Additional imagery from the surface of Mars. |

Our local terrain service reads a compatible **GeoTIFF DEM** and produces elevation grids with geographic bounds, coverage, and cell-size information.

**The large GeoTIFF is not in this repository.** A compatible Jezero dataset must be obtained separately from its original source.

## Technologies

- **Frontend:** HTML, CSS, JavaScript
- **Backend:** Python, FastAPI, Uvicorn
- **Terrain processing:** Rasterio, NumPy, pyproj
- **Local catalog:** SQLite
- **HTTP:** httpx
- **Optional integration:** Meteomatics for Earth-weather analog information when configured. This is not real-time Martian weather.

Python dependencies are specified in [requirements.txt](requirements.txt).

## Run locally

### 1. Download the code and install Python dependencies

Python 3.12 or another compatible Python version is recommended.

```powershell
git clone https://github.com/Byan1306/Mars-EVA-Navigator.git
cd Mars-EVA-Navigator
python -m pip install -r requirements.txt
```

### 2. Configure a compatible Jezero DEM

Download a suitable Jezero GeoTIFF from the original data provider. In PowerShell, set the path to the file on your computer:

```powershell
$env:MARS_DEM_PATH = "C:\path\to\jezero_hirise_dtm.tif"
```

Alternatively, place the compatible GeoTIFF alongside `mars_dem_server.py`. Providing `MARS_DEM_PATH` is more reliable if the file lives elsewhere.

### 3. Start the server

```powershell
python mars_dem_server.py
```

### 4. Open Mars EVA Navigator

Open **http://127.0.0.1:8000/** in your browser. Keep PowerShell running while using the application.

You can also check:

- [Server status](http://127.0.0.1:8000/api/status)
- [Processed elevation grid](http://127.0.0.1:8000/api/dem/jezero?size=40)

A successful status check only shows that a file was detected; a successful elevation request confirms that the server processed terrain data.

## Repository files

| File | Description |
| --- | --- |
| `mars_eva_navigator_guia_de_supervivencia_interplanetaria_nasa_space_apps_2026.html` | Main interactive app |
| `mars_dem_server.py` | Backend server and terrain API |
| `catalog_store.py` | Local mission-evidence catalog logic |
| `catalog.sqlite` | Included local catalog database |
| `requirements.txt` | Python packages needed to run the backend |

The local catalog database is included. If that database is removed, the server may require a separate `catalog_seed.json` file to rebuild the catalog; that seed file is not currently published in this repository.

## Scientific limitations

Our planner works with real topography, but the routes are **not guaranteed safe**. A high-resolution DEM can be resampled to a much coarser planning grid, leaving smaller hazards unresolved. Missing coverage, environmental risks, and operational constraints also need more testing. The three colors represent experimental route priorities, not certified safety levels.

## Team and responsible AI use

Built by **Ronald López and Brayan Barrera** for **NASA Space Apps Challenge 2026**.

We used ChatGPT as a development assistant for coding, debugging, interface improvements, research, and documentation. Our team directed the project, connected the terrain data, and tested the prototype. AI assistance does not substitute for scientific verification.

## Acknowledgments

Thanks to NASA and the teams behind HiRISE, Mars Trek, Perseverance, and Curiosity for making planetary science information accessible. External data, images, and software remain subject to their original terms and licenses.

---

**We don't just want to see Mars. We want to understand how to explore it.**
