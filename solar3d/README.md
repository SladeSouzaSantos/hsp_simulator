# Solar 3D Lab — F1/F2/F3/F3.1/F4.1/F4.2/F5 preliminar (experimental)

**This project is isolated from the existing HSP Simulator API.** Branch:
`feature/solar3d-lab`. No deployment is made to `dev` or `main`.

**Documentação técnica atualizada:** [Modelos, contratos e limitações](docs/MODELOS_E_VALIDACAO.md).
Esta branch oferece um caminho de pesquisa ponta a ponta; o cálculo de potência
real da string/MPPT e a validação de rendimento com PVsyst ainda precisam
de calibração por datasheet e medições.

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

## F5.2 — perdas mensais por string e MPPT (aproximação elétrica)

**Objetivo funcional:** responder qual a perda energética mensal por MPPT
decorrente de obstáculos 3D e permitir comparar a reorganização das strings.

No painel **Energia → Perdas por MPPT**, selecione NASA POWER ou PVGIS,
confirme a utilização experimental de dados eventualmente não verificados
e aceite explicitamente a hipótese de **três substrings genéricas**.
Clique em **Calcular perdas mensais por MPPT**. Abra cada MPPT para
consultar perdas mensais em kWh DC e %, e cada string para examinar
seu MPP hipotético individual. Os relatórios podem ser exportados
como CSV, JSON e PDF (documentos não certificados).

### Contrato API

`POST /solar3d/losses/monthly` utiliza os mesmos campos de
`POST /solar3d/energy/simulate`, com alterações importantes:

- `sample_rows: 3 | 6` (cada terço do comprimento modela uma substring
  hipotética); `sample_columns: 2 | 4`;
- `assume_generic_three_substrings: true` é uma confirmação **obrigatória**;
- `allow_unverified_for_research` deve ser habilitado se os equipamentos
  não estiverem individualmente conferidos nos datasheets;
- `objects`, `meshes` e `design` são os mesmos do projeto 3D;
- `source` usa `nasa-power`, `pvgis-tmy`, ou `uploaded` com `weather`
  horário, ordenado e contínuo.

A resposta contém `model: F5_2_MONTHLY_STRING_MPPT_PIECEWISE_IV_V1`,
`calibrated: false`, `validated_electrical_yield: false`,
`summary`, `monthly[]`, `strings[].monthly[]` e
`mppts[].monthly[]`, todos com:

```json
{
  "month_utc": 1,
  "hours": 744,
  "reference_kwh": 104.2,
  "shaded_kwh": 95.6,
  "loss_kwh": 8.6,
  "loss_percent": 8.2534
}
```

**Atenção:** os valores acima ilustram somente a estrutura JSON; não
foram obtidos de uma simulação. A soma mensal é a integração horária
`Σ(P_W × 1h)/1000`. O percentual é `100 × (E_ref-E_sombra)/E_ref`,
calculado a partir das **energias do mesmo mês**, não de uma média
de porcentagens de sombra. Meses ausentes não são preenchidos como zero,
e séries parciais não são anualizadas.

### Modelo elétrico e limitações

- Cada módulo possui três substrings genéricas iguais de 1/3 do comprimento.
  A localização de diodos/células **não** corresponde necessariamente a
  módulos half-cut, TOPCon, HJT ou outros datasheets reais.
- Para cada substring, usa-se curva I–V **aproximada e ancorada em
  Voc/Vmp/Isc/Imp**, com correções térmicas e aproximação logarítmica
  de tensão sob irradiância baixa; a tensão em bypass é limitada
  por hipótese a -0,55 V. **Não** equivale a um ajuste físico por diodo.
- Um módulo divide sua curva por 3 substrings em série; os módulos
  de uma string compartilham corrente, enquanto strings em paralelo
  no mesmo MPPT compartilham tensão. Para cada instante, procura-se
  o máximo aproximado de P(V) sobre uma malha de tensões permitida.
- O limite de corrente do MPPT é uma aproximação de saturação ideal;
  não resolve tensão de partida, energia de arranque, curva de eficiência
  real, limites por entrada física, clipping do inversor nem histerese
  do algoritmo MPPT.
- A perda por string apresentada refere-se ao **MPP individual hipotético**
  da string desconectada das demais. Sua energia não é uma partição
  da energia efetiva do MPPT quando existem strings paralelas.
- **A perda por MPPT** é obtida do ponto de operação comum calculado
  para todas as strings nele conectadas.
- Os resultados são de **energia DC estimada**, não de energia AC certificada.
  A redução de área sombreada não foi confundida com redução linear
  da potência elétrica: o motor utiliza curvas/ligação, ainda que
  aproximadas.
- Os resultados precisam de **calibração por fabricante, topologia
  física das células, análise de convergência e comparação com dados
  medidos/PVsyst** antes de servir a decisões comerciais.

### Comparação de estratégias

Na mesma aba, execute uma análise, clique em **Salvar como cenário A**,
edite as ligações em **Elétrica** e execute novamente. A comparação
é apresentada somente quando localização, fonte, ano e período
meteorológico permanecem alinhados. A diferença em kWh indica se
a alternativa reduziu ou aumentou a perda DC estimada.

`POST /solar3d/losses/report/pdf` transforma o retorno em um relatório
de MPPTs e strings, com declaração explícita de não calibração e
de que os dados enviados do navegador não são autenticados no servidor.
Não é laudo ou memorial de cálculo executivo.

**Próxima condição de aceite:** implementar a topologia
física de diodos/substrings do modelo real e comparar curvas
medidas/fornecidas pelo fabricante, antes de rotular os fatores
como perdas elétricas validadas.

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

**F4.2 refinements:** integração do catálogo com revisão manual, experimento
PVMismatch genérico e curva I–V estão presentes. Ainda é necessário calibrar
o circuito de células/substrings com dados reais, ligar a sombra 3D às
substrings físicas e integrar a solução elétrica completa por MPPT.

**F5 preliminar:** simulação temporal de irradiância/energia potencial,
comparação sombra/sem sombra, agregações mensais e PDF/CSV/JSON foram criados.
Ainda **não** há perdas elétricas rigorosas por string/MPPT, validação
PVsyst/campo nem quantificação de incerteza. Consulte a matriz técnica.

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

O editor exporta agora `schema_version: 3`, com `meshes` triangulares; projetos
v1 e v2 são importados sem criar malhas ou ligações elétricas fictícias.
A etapa F3.1 aceita malhas opacas triangulares com coordenadas absolutas
de cena (X Leste/Y altura/Z Norte). Para testar, adicione uma cobertura
triangular na aba de geometria. O ray casting utiliza os mesmos triângulos
em Python e no renderizador 3D.

### F4.2 / F5 preliminar / Relatórios

Na aba **Elétrica**, o catálogo GreenCity OS pode ser carregado via
**Selecionar exportação JSON** (ver
`examples/greencity-staged-excerpt.json`). Campos indispensáveis faltantes
geram bloqueios por item. O laboratório de PVMismatch exibe curvas I–V/P–V
de módulos **STD72 genéricos**, não calibrados por fabricante.

Na aba **Energia**, selecione NASA POWER (ano histórico) ou PVGIS TMY,
modelo POA e confirme o modo experimental somente quando a procedência dos
dados assim exigir. O resultado inclui potências/energias **potenciais**
independentes, agregação indicativa por string/MPPT, proxy AC, comparativo
mensal, CSV, JSON e PDF com advertências explícitas. O gráfico não
representa energia elétrica validada de strings reais. Sem internet
no container, a busca NASA/PVGIS pode falhar; para ensaios offline, use
testes Python com série horária fornecida.

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
