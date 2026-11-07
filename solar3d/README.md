# Solar 3D Lab — F1/F2 (experimental)

**This project is isolated from the existing HSP Simulator API.** Branch:
`feature/solar3d-lab`. No deployment is made to `dev` or `main`.

## Delivered in F1/F2

- Editable Three.js scene in metric units: **X = East, Y = Up, Z = North**.
- Add/select/edit/remove primitive buildings, obstacles and PV modules.
- Position (object **center**) in metres, geometry in metres, panel tilt and geographic azimuth.
- Save/load versioned JSON scene (`schema_version: 1`), with basic validation.
- Solar-day endpoint backed by **pvlib**, using geographic coordinates, civil date
  and **IANA timezone** (including historical DST transitions).
- 15-minute timeline with play/pause, daylight/night status and **visual** real-time shadows.
- Six example PV modules and a sample building and wall for UI experimentation.

**No annual loss, electrical mismatch, MPPT, shading-ray sampling, or validated
solar production calculation is delivered in F1/F2.** The Three.js shadow map
is visual only. Never use it as a commercial loss figure.

## Run locally

Requires Python 3.11–3.13 and Node.js 20.19+ (Node.js 24 recommended).

Terminal A, at repository root:

```bash
python -m pip install -r solar3d/backend/requirements.txt
python -m uvicorn solar3d.backend.api:app --host 127.0.0.1 --port 8001
```

Terminal B:

```bash
cd solar3d/frontend
npm install
npm run dev
```

Open **http://localhost:5173**. The Vite proxy forwards `/solar3d/*` to
`127.0.0.1:8001`. The original HSP API on port 8000 is untouched.

Tests:

```bash
python -m pytest -q tests/solar3d
cd solar3d/frontend
npm test
npm run build
```

## Optional, isolated Docker Compose

At repository root:

```bash
docker compose -f solar3d/compose.yaml up --build -d
```

Open **http://127.0.0.1:5174**. Bind is loopback-only, without host
publication of API 8001. There is no automatic remote deploy of this branch.

## Safety and limitations

- Editing geometry does **not** currently prevent panels from intersecting
  buildings or other solids; verify elevations manually.
- Coordinates are a **local metric workspace**, not automatically synchronized
  with a cadastral or satellite map. No terrain elevation model.
- The Sun direction comes from the pvlib API; if it is unavailable, the editor
  remains accessible but **does not invent solar ephemerides**.
- GPU shadow mapping uses raster approximations. Its appearance is not proof of
  physically calculated shadow fractions.
- Data are stored only in the browser session until JSON export. No database
  or remote persistence.
- Geospatial orientation uses geographic/true North and the backend solar
  azimuth. Magnetic declination is not involved.
- The 3D renderer's y-up coordinates differ from a separate ENU scientific
  vector convention. The explicit mapping is X=East, Y=Up, Z=North.

## Next increments (not implemented)

**F3:** auditable ray casting over triangulated solids and module subdivisions;
per-module direct shading fractions and sky-diffuse/horizon assumptions.

**F4:** electrical graph (modules -> strings -> MPPT -> inverter), catalog
validation, I-V/substrings/bypass modelling.

**F5:** timestamp-wise POA irradiance and generation simulations with and
without shading, annual and monthly energy results, uncertainty and PVsyst
cross-validation.

### API contract

`POST /solar3d/solar-day`

```json
{
  "latitude": -5.92520,
  "longitude": -35.20500,
  "local_date": "2026-11-07",
  "timezone": "America/Fortaleza",
  "interval_minutes": 15
}
```

Returns `samples` with `local_time`, `utc_time`, `azimuth_deg`,
`elevation_deg` and `apparent_elevation_deg`. On historical 23-hour DST days,
15-minute resolution returns 92 samples rather than erroneously forcing 96.

## Architecture

```text
solar3d/
├── backend/              FastAPI / pvlib microservice
├── frontend/             React / Vite / R3F / Three.js
│   └── src/              editor, schema, solar vector math, tests
├── compose.yaml          independent containers + local-only web binding
└── README.md             current lab contract

api.py                     original application (not modified)
```
