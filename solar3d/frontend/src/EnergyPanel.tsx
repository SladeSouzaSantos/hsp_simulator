import { useEffect, useRef, useState } from "react";
import type { ElectricalDesign } from "./electrical";
import type { SceneObject } from "./model";
import type { MeshObstacle } from "./meshModel";

type Monthly = {
  month_utc: number; hours: number;
  dc_reference_potential_w_kwh: number; dc_shaded_potential_w_kwh: number;
  ac_reference_proxy_w_kwh: number; ac_shaded_proxy_w_kwh: number;
};
export type EnergyResult = {
  model: string;
  validated_electrical_yield: false;
  full_year: boolean;
  period: { start_utc: string; end_utc: string; hours: number };
  weather: { source: string; years: number[]; sample_count: number; full_utc_calendar_year: boolean };
  assumptions: string[];
  modules: Array<{ id: string; model_id: string;
    reference_independent_dc_potential_kwh: number;
    shaded_independent_dc_potential_kwh: number;
    direct_area_blocked_mean_daylight: number }>;
  strings: Array<{ id: string; mppt_id: string;
    unconstrained_dc_reference_kwh: number; unconstrained_dc_shaded_kwh: number }>;
  mppts: Array<{ id: string;
    unconstrained_dc_reference_kwh: number; unconstrained_dc_shaded_kwh: number }>;
  summary: { reference_ac_proxy_kwh: number; shaded_ac_proxy_kwh: number;
    proxy_difference_percent: number; reference_dc_potential_kwh: number;
    shaded_dc_potential_kwh: number };
  monthly: Monthly[];
};

const monthName = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
const csvLine = (values: (number | string)[]) => values.map((v) =>
  '"' + String(v).replace(/"/g, '""') + '"').join(",");

function download(content: string, name: string, mime: string) {
  const url = URL.createObjectURL(new Blob([content], { type: mime }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function EnergyPanel({
  latitude, longitude, objects, meshes, design,
}: {
  latitude: number;
  longitude: number;
  objects: SceneObject[];
  meshes: MeshObstacle[];
  design: ElectricalDesign;
}) {
  const [source, setSource] = useState<"nasa-power" | "pvgis-tmy">("nasa-power");
  const [year, setYear] = useState(2023);
  const [model, setModel] = useState<"isotropic" | "haydavies" | "perez">("haydavies");
  const [allowUnverified, setAllowUnverified] = useState(false);
  const [result, setResult] = useState<EnergyResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const reqRef = useRef<AbortController | null>(null);

  useEffect(() => {
    reqRef.current?.abort();
    setResult(null);
    setBusy(false);
    setError("");
    return () => reqRef.current?.abort();
  }, [latitude, longitude, objects, meshes, design, source, year, model, allowUnverified]);

  async function simulate() {
    reqRef.current?.abort();
    const controller = new AbortController();
    reqRef.current = controller;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const response = await fetch("/solar3d/energy/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          schema_version: 1,
          latitude, longitude, source,
          weather_year: year, objects, meshes, design,
          model, sample_rows: 2, sample_columns: 2,
          allow_unverified_for_research: allowUnverified,
        }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null) as { detail?: unknown } | null;
        const detail = typeof body?.detail === "string" ? body.detail : "Verifique os dados do cenário e da fonte.";
        throw new Error("HTTP " + response.status + " — " + detail);
      }
      const body = await response.json() as EnergyResult;
      if (body.validated_electrical_yield !== false || body.model !== "F5_PVWATTS_MODULE_POTENTIAL_V1")
        throw new Error("Contrato inesperado da simulação.");
      if (!controller.signal.aborted) setResult(body);
    } catch (err: unknown) {
      if (!controller.signal.aborted) setError(
        err instanceof Error ? err.message : "Não foi possível simular.");
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  function exportMonthly() {
    if (!result) return;
    const rows = [
      ["mes_utc", "horas", "referencia_dc_potencial_kwh", "com_sombra_dc_potencial_kwh",
        "referencia_ac_proxy_kwh", "com_sombra_ac_proxy_kwh"],
      ...result.monthly.map((m) => [
        m.month_utc, m.hours, m.dc_reference_potential_w_kwh,
        m.dc_shaded_potential_w_kwh, m.ac_reference_proxy_w_kwh, m.ac_shaded_proxy_w_kwh,
      ]),
    ];
    download(rows.map(csvLine).join("\n") + "\n", "solar3d-simulacao-mensal.csv", "text/csv;charset=utf-8");
  }

  const maxBar = Math.max(1, ...(result?.monthly.map((m) => m.ac_reference_proxy_w_kwh) ?? []));
  return (
    <section className="energy-panel" aria-label="Simulação de irradiância e energia potencial">
      <div className="panel-heading"><h2>Simulação temporal</h2><span>F5 · prévia</span></div>
      <p className="hint">
        Compara módulos sem e com obstrução externa usando dados horários de
        NASA POWER ou PVGIS e PVWatts. <strong>Estimativa experimental não calibrada
        de circuitos/MPPTs</strong> — não equivale a energia AC validada.
      </p>
      <label className="field"><span>Fonte meteorológica gratuita</span>
        <select value={source} onChange={(e) =>
          setSource(e.target.value as "nasa-power" | "pvgis-tmy")}>
          <option value="nasa-power">NASA POWER — ano histórico</option>
          <option value="pvgis-tmy">PVGIS — ano meteorológico típico</option>
        </select>
      </label>
      {source === "nasa-power" && <label className="field">
        <span>Ano UTC</span>
        <select value={year} onChange={(e) => setYear(Number(e.target.value))}>
          {[2022, 2023, 2024].map((i) => <option key={i} value={i}>{i}</option>)}
        </select>
      </label>}
      <label className="field"><span>Modelo POA</span>
        <select value={model} onChange={(e) =>
          setModel(e.target.value as "isotropic" | "haydavies" | "perez")}>
          <option value="haydavies">Hay–Davies</option>
          <option value="isotropic">Isotrópico</option>
          <option value="perez">Perez</option>
        </select>
      </label>
      <label className="verify-check">
        <input type="checkbox" checked={allowUnverified}
          onChange={(e) => setAllowUnverified(e.target.checked)} />
        Autorizar cenário apenas exploratório com equipamentos não verificados
      </label>
      <button type="button" className="play-button"
        disabled={busy} onClick={simulate}>
        {busy ? "Consultando meteorologia e calculando…" : "Simular série horária"}
      </button>
      {busy && <button type="button" className="secondary"
        onClick={() => reqRef.current?.abort()}>Cancelar consulta</button>}
      {error && <p className="error-message" role="alert">{error}</p>}
      {result && <div className="energy-report">
        <div className="energy-report-header">
          <strong>Solar 3D · Relatório experimental</strong>
          <span>{result.full_year ? "Ano UTC completo" : "Amostra parcial — NÃO anual"}</span>
        </div>
        <p className="hint">
          {result.weather.source} · {result.period.hours} horas ·
          {result.period.start_utc} — {result.period.end_utc}
        </p>
        <div className="electrical-metrics">
          <div><span>AC referência (proxy)</span><b>{result.summary.reference_ac_proxy_kwh.toFixed(1)} kWh</b></div>
          <div><span>AC com sombras (proxy)</span><b>{result.summary.shaded_ac_proxy_kwh.toFixed(1)} kWh</b></div>
          <div><span>Diferença do proxy</span><b>{result.summary.proxy_difference_percent.toFixed(2)}%</b></div>
          <div><span>DC potencial sombreado</span><b>{result.summary.shaded_dc_potential_kwh.toFixed(1)} kWh</b></div>
        </div>
        <p className="shade-disclaimer">
          Os valores por módulo são potenciais independentes; a soma de uma string
          não considera limitação de corrente, bypass nem busca global do MPPT.
          Os números AC são um proxy PVWatts, não um projeto bancável.
        </p>
        <h3>Comparação mensal — proxy AC</h3>
        <div className="energy-bars" role="img" aria-label="Gráfico mensal de energia AC indicativa">
          {result.monthly.map((m) =>
            <div key={m.month_utc} className="energy-month">
              <span>{monthName[m.month_utc - 1]}</span>
              <div className="energy-bar-track">
                <div className="energy-bar-ref" style={{ width: 100 * m.ac_reference_proxy_w_kwh / maxBar + "%" }} />
                <div className="energy-bar-shaded" style={{ width: 100 * m.ac_shaded_proxy_w_kwh / maxBar + "%" }} />
              </div>
              <small>{m.ac_shaded_proxy_w_kwh.toFixed(0)} kWh</small>
            </div>)}
        </div>
        <h3>Potencial individual dos módulos</h3>
        <div className="energy-tabular">
          {result.modules.map((m) => <div key={m.id}>
            <strong>{m.id}</strong>
            <span>{m.shaded_independent_dc_potential_kwh.toFixed(1)} / {m.reference_independent_dc_potential_kwh.toFixed(1)} kWh DC</span>
          </div>)}
        </div>
        <h3>Strings e MPPTs (potencial não limitado)</h3>
        <div className="energy-tabular">
          {result.strings.map((str) => <div key={str.id}>
            <strong>{str.id} / {str.mppt_id}</strong>
            <span>{str.unconstrained_dc_shaded_kwh.toFixed(1)} kWh DC</span>
          </div>)}
          {result.mppts.map((mppt) => <div key={mppt.id}>
            <strong>{mppt.id}</strong>
            <span>{mppt.unconstrained_dc_shaded_kwh.toFixed(1)} kWh DC</span>
          </div>)}
        </div>
        <div className="energy-export no-print">
          <button type="button" onClick={exportMonthly}>Exportar CSV mensal</button>
          <button type="button" className="secondary" onClick={() =>
            download(JSON.stringify(result, null, 2), "solar3d-relatorio.json", "application/json")}>
            Exportar JSON
          </button>
          <button type="button" className="secondary" onClick={() => window.print()}>
            Imprimir / salvar PDF
          </button>
        </div>
        <div className="energy-report-note">
          {result.assumptions.join(" · ")}
        </div>
      </div>}
    </section>
  );
}
