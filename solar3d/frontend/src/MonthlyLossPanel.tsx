import { useEffect, useRef, useState } from "react";
import type { ElectricalDesign } from "./electrical";
import type { SceneObject } from "./model";
import type { MeshObstacle } from "./meshModel";

type MonthlyRow = { month_utc: number; hours: number; reference_kwh: number;
  shaded_kwh: number; loss_kwh: number; loss_percent: number | null };
type Circuit = { id: string; mppt_id?: string; string_ids?: string[];
  monthly: MonthlyRow[] };
type Result = { model: string; calibrated: false; validated_electrical_yield: false;
  period: { start_utc: string; end_utc: string; hours: number; full_year: boolean };
  weather: { source: string };
  summary: { dc_reference_kwh: number; dc_shaded_kwh: number;
    dc_loss_kwh: number; dc_loss_percent: number | null };
  monthly: MonthlyRow[]; strings: Circuit[]; mppts: Circuit[]; warnings: string[] };
const MONTHS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
const pct = (n: number | null) => n === null ? "Sem referência" : n.toFixed(2) + "%";
function download(data: string, filename: string, mime: string) {
  const url = URL.createObjectURL(new Blob([data], { type: mime }));
  const a = document.createElement("a"); a.href = url; a.download = filename; a.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function MonthlyCircuit({ title, items }: {title: string; items: Circuit[]}) {
  return <div className="monthly-circuits"><h3>{title}</h3>
    {items.map(c => <details className="monthly-circuit" key={c.id}>
      <summary><strong>{c.id}</strong> · {c.string_ids ? c.string_ids.join(", ") : c.mppt_id}</summary>
      <table><thead><tr><th>Mês</th><th>Base</th><th>Sombra</th><th>Perda</th></tr></thead>
        <tbody>{c.monthly.map(m => <tr key={m.month_utc}>
          <td>{MONTHS[m.month_utc - 1]}</td><td>{m.reference_kwh.toFixed(1)}</td>
          <td>{m.shaded_kwh.toFixed(1)}</td><td>{pct(m.loss_percent)}</td>
        </tr>)}</tbody>
      </table>
      <small>Valores de energia DC em kWh; sem perdas de inversor.</small>
    </details>)}
  </div>;
}
export function MonthlyLossPanel({
  latitude, longitude, objects, meshes, design, source, year, model, allowUnverified,
}: {
  latitude: number; longitude: number; objects: SceneObject[];
  meshes: MeshObstacle[]; design: ElectricalDesign;
  source: "nasa-power" | "pvgis-tmy"; year: number;
  model: "isotropic" | "haydavies" | "perez"; allowUnverified: boolean;
}) {
  const [accepted, setAccepted] = useState(false);
  const [rows, setRows] = useState<3 | 6>(3);
  const [result, setResult] = useState<Result | null>(null);
  const [baseline, setBaseline] = useState<{ result: Result; key: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const abort = useRef<AbortController | null>(null);
  const comparisonKey = JSON.stringify({latitude, longitude, source, year, model});
  useEffect(() => {
    abort.current?.abort(); setResult(null); setBusy(false); setError("");
    return () => abort.current?.abort();
  }, [latitude, longitude, objects, meshes, design, source, year, model, allowUnverified, accepted, rows]);
  async function run() {
    abort.current?.abort();
    const controller = new AbortController(); abort.current = controller;
    setBusy(true); setError(""); setResult(null);
    try {
      const response = await fetch("/solar3d/losses/monthly", {
        method: "POST", headers: {"Content-Type":"application/json"},
        signal: controller.signal,
        body: JSON.stringify({
          schema_version: 1, latitude, longitude, objects, meshes, design,
          source, weather_year: year, model, sample_rows: rows, sample_columns: 4,
          assume_generic_three_substrings: accepted,
          allow_unverified_for_research: allowUnverified,
        }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null) as {detail?: unknown} | null;
        throw new Error("HTTP " + response.status + ": " +
          (typeof body?.detail === "string" ? body.detail : "Revise equipamentos, clima e MPPTs."));
      }
      const data = await response.json() as Result;
      if (data.model !== "F5_2_MONTHLY_STRING_MPPT_PIECEWISE_IV_V1" ||
          data.calibrated !== false || data.validated_electrical_yield !== false)
        throw new Error("Versão incompatível do motor de perdas.");
      if (!controller.signal.aborted) setResult(data);
    } catch (e: unknown) {
      if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Erro na simulação.");
    } finally { if (!controller.signal.aborted) setBusy(false); }
  }
  function exportCsv() {
    if (!result) return;
    const records: (string | number | null)[][] = [[
      "tipo","id","mppt","mes_utc","horas","sem_sombra_kwh",
      "com_sombra_kwh","perda_kwh","perda_pct"
    ]];
    for (const kind of ["mppts", "strings"] as const)
      for (const c of result[kind])
        for (const m of c.monthly)
          records.push([kind,c.id,c.mppt_id ?? c.id,m.month_utc,m.hours,
            m.reference_kwh,m.shaded_kwh,m.loss_kwh,m.loss_percent]);
    download(records.map(row => row.map(value => '"' +
      String(value ?? "").replace(/"/g,'""') + '"').join(",")).join("\n") + "\n",
      "solar3d-perdas-mensais-mppt.csv", "text/csv;charset=utf-8");
  }
  const comparable = !!(baseline && result && baseline.key === comparisonKey &&
    baseline.result.period.start_utc === result.period.start_utc &&
    baseline.result.period.hours === result.period.hours);
  return <section className="monthly-loss-panel">
    <div className="panel-heading"><h2>Perdas por MPPT</h2><span>F5.2 · Experimental</span></div>
    <p className="hint">Perda mensal DC de strings e MPPTs com tensão comum de strings
      paralelas. Não representa produção AC certificada.</p>
    <label className="verify-check"><input type="checkbox" checked={accepted}
      onChange={e=>setAccepted(e.target.checked)}/>
      Admitir temporariamente três substrings genéricas e curvas I–V aproximadas.
    </label>
    <label className="field"><span>Resolução de sombra por módulo</span>
      <select value={rows} onChange={e=>setRows(Number(e.target.value) as 3|6)}>
        <option value={3}>3 linhas (rápido)</option><option value={6}>6 linhas (detalhado)</option>
      </select>
    </label>
    <button type="button" className="play-button" disabled={busy || !accepted} onClick={run}>
      {busy ? "Calculando perdas…" : "Calcular perdas mensais por MPPT"}
    </button>
    {busy && <button type="button" className="secondary" onClick={() => abort.current?.abort()}>
      Cancelar
    </button>}
    {error && <p role="alert" className="error-message">{error}</p>}
    {result && <div className="monthly-loss-results">
      <p className="hint">{result.weather.source} · {result.period.hours} horas ·
        {result.period.full_year ? "Ano UTC completo" : "Período parcial (não anualizado)"}</p>
      <div className="electrical-metrics">
        <div><span>DC sem sombra</span><b>{result.summary.dc_reference_kwh.toFixed(1)} kWh</b></div>
        <div><span>DC com sombra</span><b>{result.summary.dc_shaded_kwh.toFixed(1)} kWh</b></div>
        <div><span>Perda de energia DC</span><b>{result.summary.dc_loss_kwh.toFixed(1)} kWh</b></div>
        <div><span>Perda percentual DC</span><b>{pct(result.summary.dc_loss_percent)}</b></div>
      </div>
      <h3>Perdas totais por mês</h3>
      <div className="monthly-loss-months">
        {result.monthly.map(m => <div key={m.month_utc} className="monthly-loss-month">
          <span>{MONTHS[m.month_utc - 1]}</span>
          <div className="monthly-loss-bar"><div style={{width:
            (m.reference_kwh>0 ? Math.max(0,Math.min(100,100*m.shaded_kwh/m.reference_kwh)) : 0)+"%"}}/></div>
          <strong>{pct(m.loss_percent)}</strong>
        </div>)}
      </div>
      <MonthlyCircuit title="MPPTs (ponto de operação comum)" items={result.mppts}/>
      <MonthlyCircuit title="Strings (MPP independente hipotético)" items={result.strings}/>
      <h3>Comparar estratégias de instalação</h3>
      <p className="hint">Salve o cenário A, reorganize as strings no editor,
        volte aqui e simule novamente para comparar as perdas.</p>
      <button type="button" className="secondary"
        onClick={()=>setBaseline({result,key:comparisonKey})}>Salvar como cenário A</button>
      {comparable && baseline && <div className="electrical-block">
        <strong>Cenário A × atual</strong>
        <p className="hint">A: {baseline.result.summary.dc_loss_kwh.toFixed(2)} kWh ·
          Atual: {result.summary.dc_loss_kwh.toFixed(2)} kWh ·
          Diferença: {(result.summary.dc_loss_kwh - baseline.result.summary.dc_loss_kwh).toFixed(2)} kWh
          (negativo indica menor perda no cenário atual).</p>
      </div>}
      {baseline && !comparable && <p className="hint">
        Para comparar, mantenha localização, fonte meteorológica, ano e período iguais.
      </p>}
      <div className="energy-export">
        <button type="button" className="secondary" onClick={async () => {
          try {
            const response = await fetch("/solar3d/losses/report/pdf", {
              method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify(result),
            });
            if (!response.ok) throw new Error("Falha ao gerar PDF mensal (HTTP " + response.status + ")");
            const url = URL.createObjectURL(await response.blob());
            const anchor = document.createElement("a");
            anchor.href = url; anchor.download = "solar3d-perdas-mensais-mppt.pdf";
            anchor.click();
            window.setTimeout(() => URL.revokeObjectURL(url), 1000);
          } catch (cause: unknown) {
            setError(cause instanceof Error ? cause.message : "Não foi possível gerar o relatório PDF.");
          }
        }}>PDF mensal por MPPT</button>
        <button type="button" onClick={exportCsv}>CSV de perdas mensais</button>
        <button type="button" className="secondary" onClick={()=>download(
          JSON.stringify(result,null,2),"solar3d-perdas-mensais.json","application/json")}>JSON técnico</button>
      </div>
      <p className="shade-disclaimer">
        Limitações: substrings genéricas, diodos/bypass e curvas aproximados,
        sem correspondência automática com células reais, MPPT dinâmico ou produção AC.
        Validação por datasheet/PVsyst ainda pendente.
      </p>
    </div>}
  </section>;
}
