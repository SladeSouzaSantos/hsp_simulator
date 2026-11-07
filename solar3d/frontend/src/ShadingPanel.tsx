import { useEffect, useRef, useState } from "react";
import type { SceneObject, SolarSample } from "./model";
import type { MeshObstacle } from "./meshModel";
import { activeShading } from "./shadingModel";
import type { ShadingDayResult } from "./shadingModel";

export function ShadingPanel({
  latitude, longitude, timezone, date, objects, meshes, selectedId, sample, sampleIndex,
  result, onResult,
}: {
  latitude: number;
  longitude: number;
  timezone: string;
  date: string;
  objects: SceneObject[];
  meshes: MeshObstacle[];
  selectedId: string | null;
  sample: SolarSample | null;
  sampleIndex: number;
  result: ShadingDayResult | null;
  onResult: (value: ShadingDayResult | null) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [rows, setRows] = useState(6);
  const [columns, setColumns] = useState(4);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    // Geometry edits or new solar coordinates make past shadow fractions invalid.
    controllerRef.current?.abort();
    controllerRef.current = null;
    setLoading(false);
    setError("");
    onResult(null);
    return () => controllerRef.current?.abort();
  }, [latitude, longitude, timezone, date, objects, meshes, rows, columns, onResult]);

  async function analyzeDay() {
    if (!objects.some((obj) => obj.kind === "panel")) {
      setError("Adicione ao menos um módulo antes de analisar.");
      return;
    }
    const controller = new AbortController();
    controllerRef.current?.abort();
    controllerRef.current = controller;
    setError("");
    onResult(null);
    setLoading(true);
    try {
      const response = await fetch("/solar3d/shading-day", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          schema_version: 1,
          latitude, longitude, local_date: date, timezone,
          interval_minutes: 15,
          sample_rows: rows, sample_columns: columns,
          objects, meshes,
        }),
        signal: controller.signal,
      });
      if (!response.ok) {
        let reason = "HTTP " + response.status;
        if (response.status === 422) {
          reason += ": cenário inválido ou amostragem acima do orçamento do laboratório.";
        }
        throw new Error(reason);
      }
      const body = (await response.json()) as ShadingDayResult;
      if (!controller.signal.aborted) {
        if (!body.geometry_only || body.schema_version !== 1) {
          throw new Error("Contrato de sombreamento inesperado.");
        }
        onResult(body);
      }
    } catch (cause: unknown) {
      if (!controller.signal.aborted) {
        setError(cause instanceof Error ? cause.message : "Erro no cálculo geométrico.");
      }
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }

  const selected = selectedId
    ? result?.modules.find((mod) => mod.id === selectedId) ?? null
    : null;
  const selectedFrame = selected && selectedId
    ? activeShading(result, sample, sampleIndex, selectedId)
    : null;
  const pct = (value: number | null) => value === null ? "Sem incidência direta"
    : (value * 100).toFixed(1) + "%";

  return (
    <section className="shading-panel" aria-label="Análise geométrica de sombreamento">
      <div className="panel-heading section-heading">
        <h2>Sombreamento 3D</h2>
        <span>F3 · experimental</span>
      </div>
      <p className="hint">
        Fração da área frontal bloqueada ao longo de um dia, calculada por raios 3D
        para objetos opacos. <strong>Não representa perdas de kWh.</strong>
      </p>
      <div className="field-grid">
        <label className="field">
          <span>Linhas de amostragem</span>
          <select value={rows} onChange={(event) => setRows(Number(event.target.value))}>
            <option value={4}>4</option>
            <option value={6}>6</option>
            <option value={8}>8</option>
          </select>
        </label>
        <label className="field">
          <span>Colunas de amostragem</span>
          <select value={columns} onChange={(event) => setColumns(Number(event.target.value))}>
            <option value={4}>4</option>
            <option value={6}>6</option>
            <option value={8}>8</option>
          </select>
        </label>
      </div>
      <button type="button" className="play-button"
        onClick={analyzeDay} disabled={loading}>
        {loading ? "Calculando sombreamento…" : "Calcular sombras do dia"}
      </button>
      {error && <p role="alert" className="error-message">{error}</p>}
      {result && (
        <>
          <p className="hint">
            Média geométrica somente nos intervalos em que a face recebe radiação direta.
            Sem ponderação por irradiância; não é perda energética.
          </p>
          <div className="shade-summary-list">
            {result.modules.map((mod) => {
              const frame = activeShading(result, sample, sampleIndex, mod.id);
              return (
                <div key={mod.id} className={"shade-result " + (mod.id === selectedId ? "active" : "")}>
                  <div className="shade-result-top">
                    <strong>{mod.name}</strong>
                    <span>{frame ? pct(frame.blocked_fraction) : "—"}</span>
                  </div>
                  <div className="shade-bar">
                    <div style={{ width: ((frame?.blocked_fraction ?? 0) * 100) + "%" }} />
                  </div>
                  <small>
                    Média diurna geométrica: {pct(mod.mean_blocked_fraction_direct_eligible)}
                  </small>
                </div>
              );
            })}
          </div>
          {selected && selectedFrame?.blocked_cells && (
            <div className="shade-grid-wrapper">
              <strong>Mapa de células de amostragem — {selected.name}</strong>
              <div className="shade-grid"
                style={{ gridTemplateColumns: `repeat(${result.sampling.columns}, minmax(0,1fr))` }}>
                {selectedFrame.blocked_cells.map((blocked, index) => (
                  <div key={index} className={blocked ? "shade-cell blocked" : "shade-cell clear"}
                    title={blocked ? "Raio bloqueado" : "Raio livre"} />
                ))}
              </div>
              <div className="shade-legend">
                <span>■ livre</span><span>■ bloqueado</span>
              </div>
            </div>
          )}
          {selected && selectedFrame?.blocked_fraction === null && (
            <p className="hint">Neste horário, o módulo selecionado não recebe feixe direto frontal.</p>
          )}
          <p className="shade-disclaimer">
            O sombreamento inclui obstáculos e outros painéis; usa caixas orientadas
            com amostragem discreta. Ainda não modela difusa, horizonte, árvores
            translúcidas, strings, MPPT ou potência AC.
          </p>
        </>
      )}
    </section>
  );
}
