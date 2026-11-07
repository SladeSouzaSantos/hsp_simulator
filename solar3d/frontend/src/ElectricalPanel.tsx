import { useEffect, useRef, useState } from "react";
import { CatalogImporter } from "./CatalogImporter";
import type { SceneObject } from "./model";
import type { ElectricalDesign, ElectricalResult, ElectricalString, InverterSpec,
  ModuleSpec, MpptSpec } from "./electrical";

type Props = {
  objects: SceneObject[];
  design: ElectricalDesign;
  onChange: (next: ElectricalDesign) => void;
  selectedId: string | null;
  activeStringId: string | null;
  onActiveString: (id: string | null) => void;
  wiringEnabled: boolean;
  onWiring: (value: boolean) => void;
};

const F = ({ label, value, onChange, step = 0.1, min, max }: {
  label: string; value: number; onChange: (value: number) => void;
  step?: number; min?: number; max?: number;
}) => (
  <label className="field">
    <span>{label}</span>
    <input type="number" value={value} step={step} min={min} max={max}
      onChange={(event) => {
        const value = Number(event.target.value);
        if (Number.isFinite(value)) onChange(value);
      }}/>
  </label>
);

const T = ({ label, value, onChange }: {
  label: string; value: string; onChange: (value: string) => void;
}) => (
  <label className="field">
    <span>{label}</span>
    <input value={value} maxLength={120}
      onChange={(event) => onChange(event.target.value)} />
  </label>
);

export function ElectricalPanel({ objects, design, onChange, selectedId,
  activeStringId, onActiveString, wiringEnabled, onWiring }: Props) {
  const [catalogId, setCatalogId] = useState(design.module_catalog[0]?.id ?? "");
  const [result, setResult] = useState<ElectricalResult | null>(null);
  const [error, setError] = useState("");
  const [validating, setValidating] = useState(false);
  const [showSpecs, setShowSpecs] = useState(false);
  const abort = useRef<AbortController | null>(null);

  const panels = objects.filter((obj) => obj.kind === "panel");
  const active = design.strings.find((str) => str.id === activeStringId) ?? null;
  const catalog = design.module_catalog.find((mod) => mod.id === catalogId)
    ?? design.module_catalog[0];
  const selectedPanel = panels.find((panel) => panel.id === selectedId);
  const assignment = design.strings.find((str) => str.module_ids.includes(selectedId ?? ""));
  const selectedModelId = selectedId ? design.module_model_ids[selectedId] : undefined;

  useEffect(() => {
    abort.current?.abort();
    abort.current = null;
    setValidating(false);
    setError("");
    setResult(null); // Never show old electrical checks after edits/import/deletion.
    return () => abort.current?.abort();
  }, [design, objects]);

  const patch = (values: Partial<ElectricalDesign>) => onChange({ ...design, ...values });
  const patchInverter = (values: Partial<InverterSpec>) =>
    patch({ inverter: { ...design.inverter, ...values } });
  const patchModel = (id: string, values: Partial<ModuleSpec>) => patch({
    module_catalog: design.module_catalog.map((mod) =>
      mod.id === id ? { ...mod, ...values } : mod),
  });
  const patchMppt = (id: string, values: Partial<MpptSpec>) =>
    patchInverter({ mppts: design.inverter.mppts.map((mppt) =>
      mppt.id === id ? { ...mppt, ...values } : mppt) });
  const patchString = (id: string, values: Partial<ElectricalString>) =>
    patch({ strings: design.strings.map((str) =>
      str.id === id ? { ...str, ...values } : str) });

  function addString() {
    if (design.strings.length >= 64) {
      setError("Limite de 64 strings atingido.");
      return;
    }
    const mpptId = active?.mppt_id ?? design.inverter.mppts[0]?.id;
    if (!mpptId) return;
    let counter = 1;
    while (design.strings.some((str) => str.id === "S" + counter)) counter++;
    const id = "S" + counter;
    patch({ strings: [...design.strings, { id, mppt_id: mpptId, module_ids: [] }] });
    onActiveString(id);
    onWiring(true);
  }

  function removeString() {
    if (!active) return;
    patch({ strings: design.strings.filter((str) => str.id !== active.id) });
    onActiveString(design.strings.find((str) => str.id !== active.id)?.id ?? null);
    onWiring(false);
  }

  function addMppt() {
    if (design.inverter.mppts.length >= 8) return;
    let n = 1;
    while (design.inverter.mppts.some((m) => m.id === "MPPT" + n)) n++;
    const base = design.inverter.mppts[0];
    patchInverter({ mppts: [...design.inverter.mppts,
      { ...base, id: "MPPT" + n }] });
  }

  function removeMppt(mpptId: string) {
    if (design.inverter.mppts.length <= 1) return;
    if (design.strings.some((str) => str.mppt_id === mpptId)) {
      setError("Desconecte ou mova as strings deste MPPT antes de excluí-lo.");
      return;
    }
    patchInverter({ mppts: design.inverter.mppts.filter((mppt) => mppt.id !== mpptId) });
  }

  function addModuleModel() {
    if (design.module_catalog.length >= 50) return;
    let n = 1;
    while (design.module_catalog.some((mod) => mod.id === "MOD-" + n)) n++;
    const id = "MOD-" + n;
    // Values are explicitly COPIED from an unverified example, not real parts.
    const base = design.module_catalog[0];
    patch({ module_catalog: [...design.module_catalog, {
      ...base, id, manufacturer: "PREENCHER FABRICANTE",
      model: "Novo modelo — substituir todos os parâmetros",
      verified_datasheet: false,
    }] });
    setCatalogId(id);
    setShowSpecs(true);
  }

  async function validate() {
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    setResult(null);
    setError("");
    setValidating(true);
    try {
      const response = await fetch("/solar3d/electrical/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          panel_ids: panels.map((panel) => panel.id),
          design,
        }),
        signal: controller.signal,
      });
      if (!response.ok) {
        throw new Error(response.status === 422
          ? "Parâmetros inválidos. Verifique datasheets, dimensões e faixas permitidas (HTTP 422)."
          : "Serviço de validação indisponível (HTTP " + response.status + ").");
      }
      const payload = (await response.json()) as ElectricalResult;
      if (payload.electrical_only !== true || payload.ready_for_energy_simulation !== false) {
        throw new Error("Contrato inesperado da API elétrica.");
      }
      if (!controller.signal.aborted) setResult(payload);
    } catch (cause: unknown) {
      if (!controller.signal.aborted) {
        setError(cause instanceof Error ? cause.message : "Erro desconhecido.");
      }
    } finally {
      if (!controller.signal.aborted) setValidating(false);
    }
  }

  return (
    <section className="electrical-panel" aria-label="Topologia elétrica do arranjo">
      <div className="panel-heading">
        <h2>Arranjo elétrico</h2><span>F4 · Topologia</span>
      </div>
      <p className="hint">
        Configure módulos, strings, MPPTs e inversor. Valores iniciais são
        <strong> exemplos fictícios</strong>, não equipamentos reais.
      </p>

      <div className="electrical-heading">Conectar módulos</div>
      <div className="string-toolbar">
        <button type="button" onClick={addString}>+ Criar string</button>
        <button type="button" className="secondary" disabled={!active}
          onClick={() => onWiring(!wiringEnabled)}>
          {wiringEnabled ? "✓ Selecionando módulos" : "Selecionar no 3D"}
        </button>
      </div>
      {wiringEnabled && (
        <p className="wiring-tip">
          Clique nas placas na cena 3D ou na lista à esquerda para
          adicionar/remover da string ativa. Módulos movidos de outra string
          são automaticamente desconectados da anterior.
        </p>
      )}
      <div className="string-items">
        {design.strings.map((str) => (
          <button key={str.id} type="button"
            className={"string-item " + (str.id === activeStringId ? "active" : "")}
            onClick={() => onActiveString(str.id)}>
            <strong>{str.id}</strong>
            <small>{str.mppt_id} · {str.module_ids.length} módulos</small>
          </button>
        ))}
      </div>
      {active ? (
        <div className="electrical-block">
          <div className="string-toolbar">
            <strong>{active.id}</strong>
            <button type="button" className="danger" onClick={removeString}>Excluir string</button>
          </div>
          <label className="field">
            <span>Entrada MPPT desta string</span>
            <select value={active.mppt_id} onChange={(e) => patchString(active.id, { mppt_id: e.target.value })}>
              {design.inverter.mppts.map((m) =>
                <option key={m.id} value={m.id}>{m.id}</option>)}
            </select>
          </label>
          <p className="hint">
            Ordem da ligação em série: {active.module_ids.length
              ? active.module_ids.join(" → ") : "nenhum módulo selecionado"}.
          </p>
          {active.module_ids.length > 1 && (
            <button type="button" className="secondary"
              onClick={() => patchString(active.id, { module_ids: [...active.module_ids].reverse() })}>
              Inverter ordem da string
            </button>
          )}
        </div>
      ) : <p className="empty-state">Crie uma string para iniciar a ligação dos módulos.</p>}

      <div className="electrical-heading">Equipamento do módulo selecionado</div>
      {selectedPanel ? (
        <div className="electrical-block">
          <strong>{selectedPanel.name}</strong>
          <label className="field">
            <span>Modelo do catálogo</span>
            <select value={selectedModelId ?? ""} onChange={(e) =>
              patch({ module_model_ids: { ...design.module_model_ids,
                [selectedPanel.id]: e.target.value } })}>
              <option value="" disabled>Selecionar modelo</option>
              {design.module_catalog.map((mod) => (
                <option key={mod.id} value={mod.id}>{mod.manufacturer} · {mod.model}</option>
              ))}
            </select>
          </label>
          <p className="hint">
            {assignment
              ? "Ligado na string " + assignment.id + " / " + assignment.mppt_id
              : "Módulo ainda não conectado a uma string."}
          </p>
        </div>
      ) : <p className="hint">Selecione uma placa para associar seu modelo elétrico.</p>}

      <CatalogImporter design={design} onChange={onChange} />
      <button type="button" className="ghost"
        onClick={() => setShowSpecs((value) => !value)}>
        {showSpecs ? "Ocultar parâmetros dos equipamentos" : "Editar catálogo e inversor"}
      </button>

      {showSpecs && <>
        <div className="electrical-heading">Catálogo de módulos</div>
        <label className="field">
          <span>Modelo para editar</span>
          <select value={catalog?.id ?? ""} onChange={(e) => setCatalogId(e.target.value)}>
            {design.module_catalog.map((mod) =>
              <option key={mod.id} value={mod.id}>{mod.id} · {mod.model}</option>)}
          </select>
        </label>
        <button type="button" className="secondary" onClick={addModuleModel}
          disabled={design.module_catalog.length >= 50}>+ Adicionar modelo (copiar exemplo)</button>
        {catalog && <div className="electrical-block">
          <T label="Fabricante" value={catalog.manufacturer}
            onChange={(value) => patchModel(catalog.id, { manufacturer: value })}/>
          <T label="Modelo" value={catalog.model}
            onChange={(value) => patchModel(catalog.id, { model: value })}/>
          <div className="field-grid">
            {([
              ["pmax_w", "Pmax (W)"], ["voc_v", "Voc (V)"],
              ["vmp_v", "Vmp (V)"], ["isc_a", "Isc (A)"],
              ["imp_a", "Imp (A)"], ["beta_voc_pct_c", "β Voc (%/°C)"],
              ["beta_vmp_pct_c", "β Vmp (%/°C)"], ["alpha_isc_pct_c", "α Isc (%/°C)"],
            ] as const).map(([key, label]) =>
              <F key={key} label={label} value={catalog[key]} step={0.01}
                onChange={(value) => patchModel(catalog.id, { [key]: value })}/>)}
          </div>
          <label className="verify-check">
            <input type="checkbox" checked={catalog.verified_datasheet}
              onChange={(e) => patchModel(catalog.id, { verified_datasheet: e.target.checked })}/>
            Conferi pessoalmente os valores no datasheet oficial
          </label>
        </div>}

        <div className="electrical-heading">Inversor</div>
        <div className="electrical-block">
          <T label="Fabricante" value={design.inverter.manufacturer}
            onChange={(value) => patchInverter({ manufacturer: value })}/>
          <T label="Modelo" value={design.inverter.model}
            onChange={(value) => patchInverter({ model: value })}/>
          <div className="field-grid">
            <F label="Tensão DC absoluta máx. (V)" value={design.inverter.max_dc_voltage_v}
              onChange={(value) => patchInverter({ max_dc_voltage_v: value })}/>
            <F label="Potência AC nominal (W)" value={design.inverter.rated_ac_power_w} step={100}
              onChange={(value) => patchInverter({ rated_ac_power_w: value })}/>
          </div>
          <label className="verify-check">
            <input type="checkbox" checked={design.inverter.verified_datasheet}
              onChange={(e) => patchInverter({ verified_datasheet: e.target.checked })}/>
            Conferi pessoalmente os valores no datasheet oficial
          </label>
        </div>
        <div className="string-toolbar">
          <strong>Entradas MPPT</strong>
          <button type="button" className="secondary"
            disabled={design.inverter.mppts.length >= 8} onClick={addMppt}>+ MPPT</button>
        </div>
        {design.inverter.mppts.map((mppt) =>
          <div className="electrical-block" key={mppt.id}>
            <div className="string-toolbar">
              <strong>{mppt.id}</strong>
              <button type="button" className="danger" onClick={() => removeMppt(mppt.id)}
                disabled={design.inverter.mppts.length <= 1}>Excluir MPPT</button>
            </div>
            <div className="field-grid">
              {([
                ["min_voltage_v", "Vmp mínimo (V)"],
                ["max_voltage_v", "Vmp máximo (V)"],
                ["max_input_current_a", "Corrente entrada (A)"],
                ["max_short_circuit_current_a", "Isc máx. (A)"],
                ["max_parallel_strings", "Máx. strings"],
              ] as const).map(([key, label]) =>
                <F key={key} label={label} value={mppt[key]}
                  step={key === "max_parallel_strings" ? 1 : 0.1}
                  onChange={(value) => patchMppt(mppt.id, { [key]: value })}/>)}
            </div>
          </div>)}
        <p className="hint">
          Confira separadamente os limites reais de cada MPPT e entrada física
          no manual do inversor; não basta conferir a quantidade de MPPTs.
        </p>
      </>}

      <div className="electrical-heading">Condições extremas</div>
      <div className="field-grid">
        <F label="Temperatura mínima da célula (°C)"
          value={design.min_cell_temp_c}
          step={1} onChange={(value) => patch({ min_cell_temp_c: value })}/>
        <F label="Temperatura máxima da célula (°C)"
          value={design.max_cell_temp_c}
          step={1} onChange={(value) => patch({ max_cell_temp_c: value })}/>
      </div>
      <p className="hint">Temperaturas de <strong>célula FV</strong>, não ar ambiente. Valores são hipóteses do cenário.</p>

      <button type="button" className="play-button" disabled={validating}
        onClick={validate}>
        {validating ? "Validando conexões…" : "Validar arranjo elétrico"}
      </button>
      {error && <p className="error-message" role="alert">{error}</p>}
      {result && <div className="electrical-result">
        <strong className={result.status === "invalid" ? "electrical-invalid" : "electrical-warning"}>
          {result.status === "invalid" ? "Configuração incompatível" :
            result.status === "review_required" ? "Requer revisão de dados" :
              "Sem incompatibilidades detectadas nesta checagem"}
        </strong>
        <div className="electrical-metrics">
          <div><span>Conectados</span><b>{result.summary.connected_panel_count}/{result.summary.panel_count}</b></div>
          <div><span>Potência nominal DC</span><b>{result.summary.nameplate_connected_dc_w.toFixed(0)} Wp</b></div>
          <div><span>Razão DC/AC</span><b>{result.summary.dc_ac_ratio.toFixed(2)}</b></div>
        </div>
        {result.strings.map((str) =>
          <div className="electrical-block" key={str.id}>
            <strong>{str.id} · {str.mppt_id} · {str.module_count} módulos</strong>
            <p className="hint">
              Voc frio: {str.voc_cold_v.toFixed(1)} V
              {" · "}Vmp quente: {str.vmp_hot_v.toFixed(1)} V
            </p>
          </div>)}
        {result.issues.map((issue, index) =>
          <p key={issue.code + issue.scope + index}
            className={issue.severity === "error" ? "issue-error" : "issue-warning"}>
            {issue.severity === "error" ? "Erro" : "Revisão"}: {issue.message}
          </p>)}
        <p className="shade-disclaimer">
          Checagem preliminar de limites nominais/temperaturas e topologia.
          Não simula corrente I–V, bypass, perdas em kWh, proteções nem conformidade normativa.
          Nunca interpretar como projeto elétrico aprovado.
        </p>
      </div>}
    </section>
  );
}
