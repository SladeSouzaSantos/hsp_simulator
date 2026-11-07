import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent } from "react";
import { INITIAL_OBJECTS, makeObject, parseProject } from "./model";
import type { Position, SceneKind, SceneObject, SolarDay, SolarSample } from "./model";
import { sunVector } from "./solarMath";
import { BufferGeometry, DoubleSide, Float32BufferAttribute } from "three";
import { sampleRoof } from "./meshModel";
import type { MeshObstacle } from "./meshModel";
import { ShadingPanel } from "./ShadingPanel";
import type { ShadingDayResult } from "./shadingModel";
import { activeShading } from "./shadingModel";
import { ElectricalPanel } from "./ElectricalPanel";
import { assignPanelToString, defaultElectricalDesign,
  deleteModuleFromDesign, registerModule } from "./electrical";
import type { ElectricalDesign } from "./electrical";

const degrees = (value: number) => value * Math.PI / 180;
const todayFortaleza = () => new Date().toLocaleDateString("sv-SE", { timeZone: "America/Fortaleza" });
const showDegrees = (value: number) => value.toFixed(1) + "°";

function SceneShape({ object, selected, onSelect, blockedFraction, wireColor }: {
  object: SceneObject;
  selected: boolean;
  onSelect: (id: string) => void;
  blockedFraction: number | null;
  wireColor: string | null;
}) {
  const isPanel = object.kind === "panel";
  const color = isPanel ? (selected ? "#22cfc7" : wireColor !== null ? wireColor :
    blockedFraction === null ? "#215f95" :
    blockedFraction >= 0.75 ? "#d65c4e" :
    blockedFraction >= 0.35 ? "#d3a352" :
    blockedFraction > 0 ? "#5c9b8a" : "#215f95") :
    object.kind === "building" ? (selected ? "#8daec5" : "#6b7f8d") :
    (selected ? "#ffc173" : "#bc966e");
  return (
    <group position={[object.position.east, object.position.elevation, object.position.north]}
      rotation={[0, degrees(object.azimuth), 0]}>
      <mesh
        castShadow receiveShadow
        rotation={[isPanel ? degrees(object.tilt) : 0, 0, 0]}
        onClick={(event) => { event.stopPropagation(); onSelect(object.id); }}>
        <boxGeometry args={[object.width, object.height, object.depth]} />
        <meshStandardMaterial color={color} metalness={isPanel ? 0.35 : 0.05} roughness={0.72} />
      </mesh>
      {selected && (
        <mesh rotation={[isPanel ? degrees(object.tilt) : 0, 0, 0]}>
          <boxGeometry args={[object.width + 0.07, object.height + 0.07, object.depth + 0.07]} />
          <meshBasicMaterial color="#61f1d5" wireframe transparent opacity={0.8} depthTest={false} />
        </mesh>
      )}
    </group>
  );
}

function MeshShape({ shape }: { shape: MeshObstacle }) {
  const geometry = useMemo(() => {
    const geo = new BufferGeometry();
    const points = shape.triangles.flatMap((face) =>
      face.flatMap((index) => shape.vertices[index]));
    geo.setAttribute("position", new Float32BufferAttribute(points, 3));
    geo.computeVertexNormals();
    return geo;
  }, [shape]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  return (
    <mesh geometry={geometry} castShadow receiveShadow>
      <meshStandardMaterial color="#ad9582" metalness={0.08} roughness={0.85}
        side={DoubleSide} />
    </mesh>
  );
}

function SolarScene({ objects, meshes, selectedId, onSelect, sun, shadingResult, sampleIndex,
  electrical, wiringEnabled }: {
  objects: SceneObject[];
  meshes: MeshObstacle[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  sun: SolarSample | null;
  shadingResult: ShadingDayResult | null;
  sampleIndex: number;
  electrical: ElectricalDesign;
  wiringEnabled: boolean;
}) {
  const daylight = sun !== null && sun.apparent_elevation_deg > 0;
  const sunPosition: [number, number, number] = sun
    ? sunVector(sun.azimuth_deg, sun.apparent_elevation_deg, 38)
    : [0, -38, 0];
  return (
    <Canvas shadows camera={{ position: [15, 13, 19], fov: 47, near: 0.1, far: 300 }}
      onPointerMissed={() => onSelect(null)}>
      <color attach="background" args={["#132a36"]} />
      <ambientLight intensity={daylight ? 0.65 : 0.28} />
      {daylight && (
        <directionalLight
          position={sunPosition} intensity={3.2} castShadow
          shadow-mapSize={[2048, 2048]}
          shadow-camera-left={-28} shadow-camera-right={28}
          shadow-camera-top={28} shadow-camera-bottom={-28}
          shadow-camera-near={0.5} shadow-camera-far={110}
          shadow-bias={-0.00008}
        />
      )}
      {sun && daylight && (
        <mesh position={sunPosition}>
          <sphereGeometry args={[0.52, 20, 12]} />
          <meshBasicMaterial color="#ffe2a3" />
        </mesh>
      )}
      <mesh position={[0, -0.10, 0]} receiveShadow>
        <boxGeometry args={[80, 0.2, 80]} />
        <meshStandardMaterial color="#29434c" roughness={0.97} />
      </mesh>
      <gridHelper args={[80, 80, "#466c72", "#36545f"]} position={[0, 0.009, 0]} />
      {meshes.map((shape) => <MeshShape key={shape.id} shape={shape} />)}
      {objects.map((object) => {
        const string = electrical.strings.find((entry) => entry.module_ids.includes(object.id));
        const mpptIndex = electrical.inverter.mppts.findIndex((entry) => entry.id === string?.mppt_id);
        const mpptPalette = ["#249f94", "#768fd3", "#b18acb", "#d49b55"];
        return (
          <SceneShape key={object.id} object={object}
            selected={selectedId === object.id}
            blockedFraction={activeShading(shadingResult, sun, sampleIndex, object.id)?.blocked_fraction ?? null}
            wireColor={wiringEnabled && object.kind === "panel"
              ? mpptIndex >= 0 ? mpptPalette[mpptIndex % mpptPalette.length] : "#60707b"
              : null}
            onSelect={onSelect} />
        );
      })}
      <OrbitControls makeDefault enableDamping minDistance={3} maxDistance={105}
        maxPolarAngle={Math.PI / 2 - 0.02} />
    </Canvas>
  );
}

function NumberField({ title, value, step = 0.1, min, max, onChange }: {
  title: string;
  value: number;
  step?: number;
  min?: number;
  max?: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="field">
      <span>{title}</span>
      <input type="number" value={value} step={step} min={min} max={max}
        onChange={(event) => {
          const numeric = Number(event.target.value);
          if (Number.isFinite(numeric)) onChange(numeric);
        }} />
    </label>
  );
}

const kindTitle: Record<SceneKind, string> = {
  building: "Edificação", obstacle: "Obstáculo", panel: "Módulo FV",
};

export function App() {
  const [latitude, setLatitude] = useState(-5.92520);
  const [longitude, setLongitude] = useState(-35.20500);
  const [timezone, setTimezone] = useState("America/Fortaleza");
  const [date, setDate] = useState(todayFortaleza);
  const [objects, setObjects] = useState<SceneObject[]>(INITIAL_OBJECTS);
  const [meshes, setMeshes] = useState<MeshObstacle[]>([]);
  const [electrical, setElectrical] = useState<ElectricalDesign>(
    () => defaultElectricalDesign(INITIAL_OBJECTS, true));
  const [activeStringId, setActiveStringId] = useState<string | null>("S1");
  const [wiringEnabled, setWiringEnabled] = useState(false);
  const [rightTab, setRightTab] = useState<"solar" | "electrical">("solar");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [solarDay, setSolarDay] = useState<SolarDay | null>(null);
  const [shadingData, setShadingData] = useState<ShadingDayResult | null>(null);
  const [sampleIndex, setSampleIndex] = useState(36);
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const uploadRef = useRef<HTMLInputElement>(null);

  const selected = objects.find((obj) => obj.id === selectedId) ?? null;
  const samples = solarDay?.samples ?? [];
  const activeSample = samples.length ? samples[Math.min(sampleIndex, samples.length - 1)] : null;
  const panels = objects.filter((obj) => obj.kind === "panel").length;

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError("");
      fetch("/solar3d/solar-day", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          latitude, longitude, local_date: date,
          timezone, interval_minutes: 15,
        }),
        signal: controller.signal,
      })
        .then(async (response) => {
          if (!response.ok) throw new Error("API de posição solar indisponível ou parâmetros inválidos (" + response.status + ").");
          return (await response.json()) as SolarDay;
        })
        .then((result) => {
          if (!controller.signal.aborted) {
            setSolarDay(result);
            setSampleIndex((i) => Math.min(i, Math.max(0, result.samples.length - 1)));
          }
        })
        .catch((cause: unknown) => {
          if (!controller.signal.aborted) {
            setSolarDay(null);
            setPlaying(false);
            setError(cause instanceof Error ? cause.message : "Falha ao consultar o motor solar.");
          }
        })
        .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    }, 350);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [latitude, longitude, date, timezone]);

  useEffect(() => {
    if (!playing || samples.length < 2) return;
    const timer = window.setInterval(() => setSampleIndex((i) => (i + 1) % samples.length), 180);
    return () => window.clearInterval(timer);
  }, [playing, samples.length]);

  function handleSceneSelect(id: string | null) {
    setSelectedId(id);
    if (wiringEnabled && id && activeStringId) {
      setElectrical((previous) =>
        assignPanelToString(previous, activeStringId, id, objects));
    }
  }

  function updateObject(changes: Partial<SceneObject>) {
    if (!selectedId) return;
    setObjects((current) => current.map((obj) =>
      obj.id === selectedId ? { ...obj, ...changes } : obj));
  }

  function updatePosition(axis: keyof Position, value: number) {
    if (!selected || Math.abs(value) > 10000) return;
    updateObject({ position: { ...selected.position, [axis]: value } });
  }

  function updateSize(field: "width" | "depth" | "height", value: number) {
    if (value > 0 && value <= 1000) updateObject({ [field]: value });
  }

  function addObject(kind: SceneKind) {
    if (objects.length >= 250) {
      window.alert("O laboratório permite no máximo 250 objetos por cena.");
      return;
    }
    const obj = makeObject(kind, objects.length + 1);
    setObjects((current) => [...current, obj]);
    if (kind === "panel") setElectrical((current) => registerModule(current, obj.id));
    setSelectedId(obj.id);
  }

  function removeSelected() {
    if (!selectedId) return;
    const removedId = selectedId;
    setObjects((current) => current.filter((obj) => obj.id !== removedId));
    setElectrical((current) => deleteModuleFromDesign(current, removedId));
    setSelectedId(null);
  }

  function exportProject() {
    const project = { schema_version: 3, latitude, longitude, timezone, objects, meshes, electrical };
    const blob = new Blob([JSON.stringify(project, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "hsp-solar3d-projeto.json";
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function importProject(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const project = parseProject(JSON.parse(await file.text()) as unknown);
      setLatitude(project.latitude);
      setLongitude(project.longitude);
      setTimezone(project.timezone);
      setObjects(project.objects);
      setMeshes(project.meshes);
      setElectrical(project.electrical);
      setActiveStringId(project.electrical.strings[0]?.id ?? null);
      setWiringEnabled(false);
      setSelectedId(null);
    } catch (cause: unknown) {
      window.alert(cause instanceof Error ? cause.message : "Não foi possível importar o projeto.");
    } finally {
      event.target.value = "";
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-icon" aria-hidden="true">☀</span>
          <div><strong>HSP Simulator</strong><small>Solar 3D Lab · F1–F4 experimental</small></div>
        </div>
        <div className="topbar-actions">
          <span className="stage-tag">EXPERIMENTAL</span>
          <button type="button" className="secondary" onClick={() => uploadRef.current?.click()}>Importar JSON</button>
          <button type="button" onClick={exportProject}>Exportar projeto</button>
          <input ref={uploadRef} type="file" accept=".json,application/json"
            className="visually-hidden" onChange={importProject} />
        </div>
      </header>

      <main className="workspace">
        <aside className="side-panel left-panel">
          <div className="panel-heading"><h2>Localização</h2><span>Geodésia</span></div>
          <div className="field-grid">
            <NumberField title="Latitude (°)" value={latitude} step={0.00001}
              min={-90} max={90} onChange={(value) => { if (Math.abs(value) <= 90) setLatitude(value); }} />
            <NumberField title="Longitude (°)" value={longitude} step={0.00001}
              min={-180} max={180} onChange={(value) => { if (Math.abs(value) <= 180) setLongitude(value); }} />
          </div>
          <label className="field">
            <span>Fuso horário IANA</span>
            <input value={timezone} onChange={(event) => setTimezone(event.target.value)} />
          </label>
          <p className="hint">Referencial local: X = Leste, Z = Norte, Y = altura. Todas as distâncias em metros.</p>

          <div className="panel-heading section-heading"><h2>Cena</h2><span>{objects.length} objetos</span></div>
          <div className="add-buttons">
            <button type="button" className="secondary" onClick={() => addObject("building")}>+ Edificação</button>
            <button type="button" className="secondary" onClick={() => addObject("obstacle")}>+ Obstáculo</button>
            <button type="button" className="secondary" onClick={() => addObject("panel")}>+ Módulo FV</button>
            <button type="button" className="secondary" onClick={() =>
              setMeshes((current) => current.length < 20 ? [...current, sampleRoof()] : current)}>
              + Cobertura triangular
            </button>
          </div>
          {meshes.length > 0 && <div className="mesh-list">
            {meshes.map((shape) => (
              <div className="mesh-row" key={shape.id}>
                <span title={shape.id}>{shape.name} · {shape.triangles.length} faces</span>
                <button type="button" className="danger" onClick={() =>
                  setMeshes((current) => current.filter((m) => m.id !== shape.id))}>
                  Excluir
                </button>
              </div>
            ))}
          </div>}
          <div className="object-list">
            {objects.map((obj) => (
              <button key={obj.id} type="button"
                className={"object-item " + (selectedId === obj.id ? "selected" : "")}
                onClick={() => handleSceneSelect(obj.id)}>
                <span className={"object-dot " + obj.kind} />
                <span>{obj.name}</span>
                <small>{kindTitle[obj.kind]}</small>
              </button>
            ))}
          </div>
          <button type="button" className="ghost"
            onClick={() => {
              setObjects(INITIAL_OBJECTS);
              setMeshes([]);
              setElectrical(defaultElectricalDesign(INITIAL_OBJECTS, true));
              setActiveStringId("S1");
              setWiringEnabled(false);
              setSelectedId(null);
            }}>
            Restaurar cena de exemplo
          </button>
        </aside>

        <section className="canvas-pane" aria-label="Visualização tridimensional">
          <div className="canvas-badge"><span className="status-dot" /> Editor 3D em metros</div>
          <SolarScene objects={objects} meshes={meshes} selectedId={selectedId}
            onSelect={handleSceneSelect} sun={activeSample}
            shadingResult={shadingData} sampleIndex={sampleIndex}
            electrical={electrical} wiringEnabled={wiringEnabled} />
          <div className="compass">
            <span>N ↑</span><span>E →</span>
          </div>
          <div className="canvas-hint">Arraste para girar · roda para aproximar · clique para selecionar</div>
          <div className="visual-notice">{wiringEnabled
            ? "F4: clique nos módulos para atribuir à string ativa. Cores indicam MPPTs."
            : "F3: a cor dos módulos indica a fração geométrica bloqueada, quando calculada. Ainda sem perdas de energia."}</div>
        </section>

        <aside className="side-panel right-panel">
          <div className="workspace-tabs" role="group" aria-label="Painel de ferramentas">
            <button type="button" className={rightTab === "solar" ? "tab-active" : ""}
              onClick={() => { setRightTab("solar"); setWiringEnabled(false); }}>
              Sol e sombra
            </button>
            <button type="button" className={rightTab === "electrical" ? "tab-active" : ""}
              onClick={() => setRightTab("electrical")}>
              Elétrica
            </button>
          </div>
          {rightTab === "solar" ? <>
          <div className="panel-heading"><h2>Trajetória solar</h2><span>pvlib</span></div>
          <label className="field">
            <span>Dia local</span>
            <input type="date" value={date} onChange={(event) => setDate(event.target.value)} />
          </label>
          <div className="solar-readouts">
            <div><small>Elevação</small><strong>{activeSample ? showDegrees(activeSample.apparent_elevation_deg) : "—"}</strong></div>
            <div><small>Azimute</small><strong>{activeSample ? showDegrees(activeSample.azimuth_deg) : "—"}</strong></div>
          </div>
          <div className="time-header">
            <span>Horário local</span>
            <strong>{activeSample ? activeSample.local_time.slice(11, 16) : "--:--"}</strong>
          </div>
          <input aria-label="Horário solar" className="time-slider" type="range"
            min={0} max={Math.max(0, samples.length - 1)} step={1}
            value={Math.min(sampleIndex, Math.max(0, samples.length - 1))}
            disabled={!samples.length} onChange={(event) => setSampleIndex(Number(event.target.value))} />
          <div className="timeline-endpoints"><span>00:00</span><span>Fim do dia</span></div>
          <button type="button" className="play-button" disabled={!samples.length}
            onClick={() => setPlaying((value) => !value)}>
            {playing ? "❚❚ Pausar sol" : "▶ Animar dia"}
          </button>
          {loading && <p className="loading-message">Calculando posição solar…</p>}
          {error && <p className="error-message" role="alert">{error} Inicie o backend local para habilitar o sol.</p>}
          {!error && activeSample && (
            <p className="hint">{activeSample.apparent_elevation_deg > 0 ?
              "Sol acima do horizonte: sombras renderizadas." :
              "Sol abaixo do horizonte: iluminação solar desativada."}</p>
          )}

          <div className="panel-heading section-heading"><h2>Propriedades</h2><span>Editar medidas</span></div>
          {selected ? (
            <div className="properties">
              <label className="field">
                <span>Nome</span>
                <input value={selected.name} maxLength={120}
                  onChange={(event) => updateObject({ name: event.target.value })} />
              </label>
              <div className="field-grid">
                <NumberField title="Leste X (m)" value={selected.position.east}
                  onChange={(value) => updatePosition("east", value)} />
                <NumberField title="Norte Z (m)" value={selected.position.north}
                  onChange={(value) => updatePosition("north", value)} />
              </div>
              <NumberField title="Centro / cota Y (m)" value={selected.position.elevation}
                onChange={(value) => updatePosition("elevation", value)} />
              <div className="field-grid">
                <NumberField title="Largura X (m)" value={selected.width}
                  min={0.001} onChange={(value) => updateSize("width", value)} />
                <NumberField title="Profundidade Z (m)" value={selected.depth}
                  min={0.001} onChange={(value) => updateSize("depth", value)} />
              </div>
              <NumberField title={selected.kind === "panel" ? "Espessura (m)" : "Altura (m)"}
                value={selected.height} min={0.001} step={0.01}
                onChange={(value) => updateSize("height", value)} />
              <div className="field-grid">
                <NumberField title="Azimute (°)" value={selected.azimuth} step={1} min={0} max={359.999}
                  onChange={(value) => { if (value >= 0 && value < 360) updateObject({ azimuth: value }); }} />
                {selected.kind === "panel" && (
                  <NumberField title="Inclinação (°)" value={selected.tilt} step={1} min={0} max={90}
                    onChange={(value) => { if (value >= 0 && value <= 90) updateObject({ tilt: value }); }} />
                )}
              </div>
              <p className="hint">A posição é o centro do objeto. Para módulos, a inclinação gira o plano em torno desse centro; ajuste a cota para evitar cruzar a laje.</p>
              <button type="button" className="danger" onClick={removeSelected}>Excluir objeto</button>
            </div>
          ) : (
            <p className="empty-state">Selecione um objeto na cena 3D ou na lista à esquerda para editar posição, dimensões e orientação.</p>
          )}
          <div className="scene-stats">
            <span>Módulos na cena</span><strong>{panels}</strong>
          </div>
          <ShadingPanel latitude={latitude} longitude={longitude}
            timezone={timezone} date={date} objects={objects} meshes={meshes}
            selectedId={selectedId} sample={activeSample} sampleIndex={sampleIndex}
            result={shadingData} onResult={setShadingData} />
          </> : <ElectricalPanel objects={objects} design={electrical}
            onChange={setElectrical} selectedId={selectedId}
            activeStringId={activeStringId} onActiveString={setActiveStringId}
            wiringEnabled={wiringEnabled} onWiring={setWiringEnabled} />}
        </aside>
      </main>
      <footer className="footer">Solar 3D Lab · F1 cena métrica · F2 sol via pvlib · F3 sombra geométrica · F4 topologia elétrica preliminar · Sem simulação kWh</footer>
    </div>
  );
}
