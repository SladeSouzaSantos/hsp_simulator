import { useState } from "react";
type Curve = { v_v: number[]; i_a: number[]; p_w: number[]; pmp_w: number; };
type Result = {
  model: string; experimental: true; model_calibrated_to_equipment: false;
  reference: Curve; shaded: Curve; difference_pct: number; limitations: string[];
};
function Trace({ a, b, keyValue }: { a: Curve; b: Curve; keyValue: "i_a" | "p_w" }) {
  const maxV = Math.max(1, ...a.v_v, ...b.v_v);
  const maxY = Math.max(1, ...a[keyValue], ...b[keyValue]);
  const points = (c: Curve) => c.v_v.map((v,i) =>
    (16 + 250 * v / maxV).toFixed(1) + "," +
    (110 - 96 * (c[keyValue][i] ?? 0) / maxY).toFixed(1)).join(" ");
  return <div className="iv-plot">
    <strong>{keyValue === "p_w" ? "Curva P–V" : "Curva I–V"}</strong>
    <svg viewBox="0 0 284 130" width="100%" role="img"
      aria-label={keyValue === "p_w" ? "Potência versus tensão" : "Corrente versus tensão"}>
      <polyline points={points(a)} fill="none" stroke="#71bbef" strokeWidth={2.2}/>
      <polyline points={points(b)} fill="none" stroke="#efba6b" strokeWidth={2.2}/>
    </svg>
  </div>;
}
export function IvExperimentPanel() {
  const [modules, setModules] = useState(3);
  const [cells, setCells] = useState(20);
  const [suns, setSuns] = useState(0.2);
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function run() {
    setBusy(true); setError(""); setResult(null);
    try {
      const response = await fetch("/solar3d/electrical/iv-experiment", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          modules_in_series: modules, shaded_module_index: 0,
          blocked_cell_indices: Array.from({ length: cells }, (_, i) => i),
          clear_irradiance_suns: 1.0, blocked_irradiance_suns: suns,
          cell_temperature_c: 25,
        }),
      });
      if (!response.ok) throw new Error("Não foi possível calcular (HTTP " + response.status + ")");
      const payload = await response.json() as Result;
      if (payload.model_calibrated_to_equipment !== false || payload.experimental !== true)
        throw new Error("Resposta não corresponde ao modelo demonstrativo.");
      setResult(payload);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Falha I–V.");
    } finally { setBusy(false); }
  }
  return <section className="iv-experiment">
    <div className="electrical-heading">Ensaio de curvas I–V e bypass</div>
    <p className="hint">PVMismatch · topologia genérica STD72, três bypass.
      <strong> Não calibrado com dados de fabricante.</strong></p>
    <div className="field-grid">
      <label className="field"><span>Módulos em série</span>
        <select value={modules} onChange={e => setModules(Number(e.target.value))}>
          {[1,2,3,4,5,6,7,8].map(n=><option key={n}>{n}</option>)}
        </select>
      </label>
      <label className="field"><span>Células sombreadas</span>
        <select value={cells} onChange={e => setCells(Number(e.target.value))}>
          {[0,4,12,20,30,48,72].map(n=><option key={n}>{n}</option>)}
        </select>
      </label>
    </div>
    <label className="field"><span>Irradiância relativa nas células sombreadas</span>
      <input type="number" value={suns} min={0} max={1} step={0.05}
        onChange={e => { const n=Number(e.target.value); if(Number.isFinite(n))setSuns(Math.max(0,Math.min(1,n))); }} />
    </label>
    <button type="button" className="secondary" disabled={busy} onClick={run}>
      {busy ? "Calculando curvas…" : "Comparar curvas I–V / P–V"}
    </button>
    {error && <p role="alert" className="error-message">{error}</p>}
    {result && <>
      <div className="electrical-metrics">
        <div><span>Pmp referência</span><b>{result.reference.pmp_w.toFixed(1)} W</b></div>
        <div><span>Pmp sombreado</span><b>{result.shaded.pmp_w.toFixed(1)} W</b></div>
        <div><span>Diferença</span><b>{result.difference_pct.toFixed(1)}%</b></div>
      </div>
      <p className="hint">Azul: sem sombra. Laranja: sombreado.</p>
      <Trace a={result.reference} b={result.shaded} keyValue="i_a"/>
      <Trace a={result.reference} b={result.shaded} keyValue="p_w"/>
      <p className="shade-disclaimer">
        Ensaio genérico sem calibração por datasheet, sem relação com o MPPT
        escolhido, nem kWh anual ou validação de um projeto elétrico.
      </p>
    </>}
  </section>;
}