# Solar 3D Lab — F1/F2/F3/F4.1 (experimental)

**This project is isolated from the existing HSP Simulator API.** Branch:
`feature/solar3d-lab`. No deployment is made to `dev` or `main`.

## Delivered in F1/F2

- Editable Three.js scene in metric units: **X = East, Y = Up, Z = North**.
- Add/select/edit/remove primitive buildings, obstacles and PV modules.
- Position (object **center**) in metres, geometry in metres, panel tilt and geographic azimuth.
- Save/load versioned JSON scene. The **project schema is now v2** (adds an
  electrical design); import of old `schema_version: 1` files remains supported.
  The converter **does not invent wiring** for legacy projects.
- Solar-day endpoint backed by **pvlib**, using geographic coordinates, civil date
  and **IANA timezone** (including historical DST transitions).
- 15-minute timeline with play/pause, daylight/night status and **visual** real-time shadows.
- Six example PV modules and a sample building and wall for UI experimentation.

## Delivered in F3 — geometry only

- `POST /solar3d/shading-day` returns **front-face direct-beam geometric shadow
  fractions** per PV module, for every solar timestamp in the local civil day.
- Deterministic ray/oriented-box intersections against buildings, wall obstacles
  and other modules in the same metric coordinate system as Three.js.
- Each panel is divided into a configurable rows × columns grid. Rays start at
  the center of each cell, offset to the outward face of the module.
- A sample is 1 when the direct sun ray is blocked by an opaque object; otherwise
  it is 0. A module fraction is the **mean of sampled blocked cells**.
- `null` indicates no direct sunlight incident on the FRONT of that module
  (e.g., at night or when the Sun is behind the tilted plane). This is **not** 0%.
- In the editor, use **Calcular sombras do dia**, move the solar timeline, select
  any module and inspect the blocked fraction and row-by-row cell grid. Module
  colors reflect the geometric shadow fraction at the selected timestamp.
- The reported day average is an **unweighted** mean only over timestamps with
  front-side direct-beam incidence. It is **not** an annual or daily energy loss.
- The backend bounds synchronous complexity with a request-size budget; large
  plants will need workers and batching.

**Not implemented in F3:** terrain/trees/true arbitrary triangle meshes,
horizon, diffuse/reflected irradiance loss, irradiance weighting, bypass,
module I–V curves, inverter efficiency, kWh/year and PVsyst-equivalent
validation. The Three.js visual shadow map is only a visualization; F3
fractions are calculated independently on the Python backend.

## Delivered in F4.1 — electrical topology and preliminary limits

The **Elétrica** tab allows you to assign an equipment model to each panel,
create multiple strings, connect/disconnect modules by clicking on the scene,
attach every string to an inverter MPPT, manage parallel strings, and edit
the inverter + MPPT nameplate parameters. During wiring mode, module colors
indicate their MPPT; outside wiring mode, colors indicate F3 geometric shading.

- Each module can belong to **at most one string** in UI operations; moving
  it into another string atomically disconnects it from its previous string.
- A string contains **ordered** module IDs (series wiring). Strings are
  assigned to MPPT IDs. Multiple strings may share an MPPT in parallel.
- A *catalog item* contains a manufacturer/model identifier, Pmax, Voc, Vmp,
  Isc, Imp and temperature coefficients. An inverter has maximum DC voltage,
  nominal AC power and per-MPPT voltage/current/parallel-string limits.
- **All factory sample equipment is fictitious and unverified.** Replace it
  with real datasheet values. Explicitly mark `verified_datasheet` only after
  checking the manufacturer's official document. The example is **not**
  a recommendation or a real-world compatible design.
- Press **Validar arranjo elétrico** to call the independent FastAPI endpoint
  `POST /solar3d/electrical/validate`. Server-side validation catches
  duplicate assignments, orphan IDs, unassigned/unknown module specs,
  mismatched models in series, incompatible MPPT assignment, and obvious
  nameplate limits. It returns typed warnings/errors and a status.
- Cold-cell Voc must stay below the absolute inverter maximum DC voltage;
  hot-cell Vmp must stay above the MPPT minimum, and cold-cell Vmp below its
  maximum. Parallel strings' **currents** add at each MPPT; their voltages do
  **not** add. Parallel strings with incompatible Vmp receive warnings/errors.
- Estimated `Imp` at high temperature uses the Isc coefficient as a
  conservative approximation. This is **not** an independently characterized
  cell current or validated thermal model.
- A preliminary connected nameplate DC power and DC/AC ratio are returned,
  **not** an energy yield. If DC > inverter nominal AC, the system warns about
  checking the manufacturer's permitted oversizing/clipping; this warning
  does not determine a valid ratio.

**Temperature fields are assumed PV CELL temperatures**, not air temperatures.
Linear calculations are first-order estimators:

```text
Voc_cold_string = N × Voc_STC × [1 + (betaVoc_%/°C / 100) × (Tcell_min - 25)]
Vmp_hot_string  = N × Vmp_STC × [1 + (betaVmp_%/°C / 100) × (Tcell_max - 25)]
Vmp_cold_string = N × Vmp_STC × [1 + (betaVmp_%/°C / 100) × (Tcell_min - 25)]
Isc_hot_string  = Isc_STC × [1 + (alphaIsc_%/°C / 100) × (Tcell_max - 25)]
```

No output from this endpoint constitutes a design approval: it **does not**
validate conductor gauge, cable voltage drop, fuses, connector ratings,
protective coordination, grounding, standards compliance, reverse currents,
module temperature estimates, spectral/irradiance effects, bypass diodes,
I–V curves, electrical mismatch, MPPT control efficiency, actual DC/AC
production or annual energy losses. These require later engineering phases.

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
  physically calculated shadow fractions. Use F3 API results for geometric
  direct-area blockage; they are still a discrete numerical approximation.
- The F3 backend accepts **opaque boxes** (buildings/walls) and tilted module
  boxes, not arbitrary imported meshes. Non-panel shapes use yaw; any tilt
  assigned to other shapes is ignored.
- Module shading is sampled on grid-cell centers. Small poles, narrow shadows
  and near-boundary shadows can be missed at coarse resolution. Test convergence
  at finer grids before drawing conclusions.
- The shadowed-area average excludes ineligible night/back-facing timestamps.
  It is not weighted by extraterrestrial radiation, GHI, DNI, or POA.
- A building intersecting a panel is an invalid physical installation; the
  editor does not yet prevent collisions.
- Data are stored only in the browser session until JSON export. No database
  or remote persistence. F4 assignments are saved in project schema version 2.
- The new electrical endpoint is **stateless** and does not persist customer
  datasheets, topology or PV site geometry.
- Geospatial orientation uses geographic/true North and the backend solar
  azimuth. Magnetic declination is not involved.
- The 3D renderer's y-up coordinates differ from a separate ENU scientific
  vector convention. The explicit mapping is X=East, Y=Up, Z=North.

## Next increments (not implemented)

**F3.1 refinements:** triangulated-mesh imports, spatial acceleration, adaptive
subdivision and benchmark suite for non-rectangular obstacles; sky-view and
horizon treatment should be added separately from direct-beam shadow casting.

**F4.2 refinements:** datasheet-driven equipment catalog integration (GreenCity
OS only after schema validation), manufacturer-specific MPPT input rules,
substrings/bypass modelling and physical I–V/mismatch simulation. F4.1 covers
topology and preliminary nameplate checks only.

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

`POST /solar3d/shading-day` accepts these solar fields plus:
```json
{
  "schema_version": 1,
  "latitude": -5.92520,
  "longitude": -35.20500,
  "local_date": "2026-11-07",
  "timezone": "America/Fortaleza",
  "interval_minutes": 15,
  "sample_rows": 6,
  "sample_columns": 4,
  "objects": [
    {
      "id": "M01",
      "name": "PV module 01",
      "kind": "panel",
      "position": {"east": 0, "north": 0, "elevation": 3.48},
      "width": 1.134,
      "depth": 2.278,
      "height": 0.045,
      "azimuth": 0,
      "tilt": 12
    }
  ]
}
```

Response structure:
- `solar_samples_utc`: exactly aligned with solar day samples (same 15-min time grid).
- `modules[].frames[].blocked_fraction`: value 0–1, or null when no
  front-side direct-beam incidence.
- `modules[].frames[].blocked_cells`: row-major 0/1 grid or null.
- `mean_blocked_fraction_direct_eligible`: unweighted geometric mean.
- `geometry_only: true` and `limitations`: explicit fidelity disclosure.

The F3 parser rejects invalid dimensions, duplicate IDs, scenes without modules
and requests that exceed the synchronous computation budget with HTTP 422.
Objects in the scene **are not** a cadastral/GPS georegistered model:
`position` is a local metric offset (X=East, Y=Up, Z=North) from an arbitrary
local origin, and `elevation` is the object's center height in metres.

### F4 electrical validation API

`POST /solar3d/electrical/validate` accepts:

```json
{
  "panel_ids": ["M01", "M02", "M03"],
  "design": {
    "module_catalog": [{
      "id": "DEMO-550", "manufacturer": "EXEMPLO (não real)",
      "model": "Módulo ilustrativo 550 W", "pmax_w": 550,
      "voc_v": 49, "vmp_v": 41, "isc_a": 14.2, "imp_a": 13.42,
      "beta_voc_pct_c": -0.28, "beta_vmp_pct_c": -0.35,
      "alpha_isc_pct_c": 0.04, "verified_datasheet": false
    }],
    "module_model_ids": {
      "M01": "DEMO-550", "M02": "DEMO-550", "M03": "DEMO-550"
    },
    "inverter": {
      "id": "DEMO-INV", "manufacturer": "EXEMPLO (não real)",
      "model": "Inversor ilustrativo 5 kW",
      "max_dc_voltage_v": 600, "rated_ac_power_w": 5000,
      "verified_datasheet": false,
      "mppts": [{
        "id": "MPPT1", "min_voltage_v": 100, "max_voltage_v": 550,
        "max_input_current_a": 20,
        "max_short_circuit_current_a": 25,
        "max_parallel_strings": 2
      }]
    },
    "strings": [{
      "id": "S1", "mppt_id": "MPPT1",
      "module_ids": ["M01", "M02", "M03"]
    }],
    "min_cell_temp_c": 0, "max_cell_temp_c": 65
  }
}
```

The response includes `status` (`invalid`, `review_required`,
`preliminary_pass`), `issues`, `summary`, per-string cold/hot voltages,
and per-MPPT aggregate currents. `electrical_only=true` and
`ready_for_energy_simulation=false` always clarify the current scope.

### Project JSON schema v2

```json
{
  "schema_version": 2,
  "latitude": -5.9252,
  "longitude": -35.205,
  "timezone": "America/Fortaleza",
  "objects": [],
  "electrical": {
    "...": "same design structure as above"
  }
}
```

The empty objects array above only illustrates the envelope; actual scenes
require real geometry. Version 1 imports preserve geometry and create
**unconnected** default wiring with clearly labeled illustrative equipment.

## Architecture

```text
solar3d/
├── backend/              FastAPI / pvlib + shading + F4 electrical checks
├── frontend/             React / Vite / R3F / Three.js
│   └── src/              scene editor, shading UI, wiring/catalog UI & tests
├── compose.yaml          independent containers + local-only web binding
└── README.md             current lab contract

api.py                     original application (not modified)
```
