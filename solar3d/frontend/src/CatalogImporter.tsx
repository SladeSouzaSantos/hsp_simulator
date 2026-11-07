import { useRef, useState } from "react";
import type { ChangeEvent } from "react";
import type { ElectricalDesign, ModuleSpec, InverterSpec } from "./electrical";

type Entry = {
  kind: "module" | "inverter";
  status: "blocked" | "review";
  name: string;
  problems: string[];
  data: ModuleSpec | InverterSpec | null;
  source?: string | null;
};
type CatalogPreview = {
  format: "solar3d-staged-catalog-v1";
  source: "greencity-os-equipment-v1";
  source_revision: string;
  totals: { entries: number; reviewable: number; blocked: number };
  entries: Entry[];
  warnings: string[];
};

const identity = (brand: string, model: string) =>
  (brand + "::" + model).trim().replace(/\s+/g, " ").toLocaleLowerCase();

export function CatalogImporter({ design, onChange }: {
  design: ElectricalDesign;
  onChange: (design: ElectricalDesign) => void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [data, setData] = useState<CatalogPreview | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setBusy(true); setError(""); setNotice(""); setData(null);
    try {
      if (file.size > 1024 * 1024) throw new Error("Arquivo maior que 1 MiB; exporte em lotes menores.");
      const raw = JSON.parse(await file.text()) as unknown;
      const response = await fetch("/solar3d/catalog/import/greencity", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(raw),
      });
      if (!response.ok) throw new Error("Falha na validação da exportação GreenCity OS (HTTP " + response.status + ").");
      const body = await response.json() as CatalogPreview;
      if (body.format !== "solar3d-staged-catalog-v1" || !Array.isArray(body.entries))
        throw new Error("Resposta de catálogo incompatível.");
      setData(body);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "Não foi possível importar o arquivo.");
    } finally { setBusy(false); }
  }

  function accept(item: Entry) {
    if (item.status !== "review" || !item.data) return;
    setNotice("");
    if (item.kind === "module") {
      const module = item.data as ModuleSpec;
      const exists = design.module_catalog.some((m) =>
        identity(m.manufacturer, m.model) === identity(module.manufacturer, module.model));
      if (exists) return setNotice("Este fabricante/modelo de módulo já existe; importação ignorada.");
      onChange({ ...design, module_catalog: [...design.module_catalog, {
        ...module, verified_datasheet: false,
      }] });
      return setNotice("Módulo adicionado para revisão. Confirme os valores no datasheet.");
    }
    const inverter = item.data as InverterSpec;
    if (!window.confirm(
      "Substituir o inversor atual? Todas as strings existentes serão apagadas " +
      "porque a distribuição de MPPTs pode ser diferente. A geometria dos módulos será preservada."
    )) return;
    onChange({ ...design, strings: [], inverter: { ...inverter, verified_datasheet: false } });
    setNotice("Inversor substituído. Reconecte cada string e confira o datasheet.");
  }

  return (
    <div className="catalog-import">
      <strong>Importação GreenCity OS (JSON)</strong>
      <p className="hint">
        Aceita exportação `greencity-os-equipment-v1` de registros Isar em JSON.
        O importador identifica campos faltantes; não inventa coeficientes ou
        limites elétricos.
      </p>
      <input ref={fileRef} hidden type="file" accept=".json,application/json" onChange={upload} />
      <button type="button" className="secondary" disabled={busy}
        onClick={() => fileRef.current?.click()}>
        {busy ? "Conferindo exportação…" : "Selecionar exportação JSON"}
      </button>
      {error && <p className="error-message" role="alert">{error}</p>}
      {notice && <p className="wiring-tip">{notice}</p>}
      {data && <>
        <p className="hint">
          Origem {data.source_revision || "(revisão não informada)"}:
          {" "}{data.totals.reviewable} revisáveis, {data.totals.blocked} bloqueados.
        </p>
        <div className="catalog-import-entries">
          {data.entries.map((item, index) => (
            <div key={index} className="electrical-block">
              <strong>{item.kind === "module" ? "Módulo" : "Inversor"}: {item.name || "(sem identificação)"}</strong>
              <p className={item.status === "blocked" ? "issue-error" : "issue-warning"}>
                {item.status === "blocked" ? "Bloqueado" : "Pendente de conferência"}:
                {" "}{item.problems.join("; ")}
              </p>
              {item.source && <a href={item.source} target="_blank" rel="noreferrer">Fonte informada</a>}
              {item.status === "review" && <button type="button" onClick={() => accept(item)}
                className="secondary" style={{ marginTop: 8 }}>
                {item.kind === "module" ? "Adicionar módulo ao catálogo" : "Selecionar inversor"}
              </button>}
            </div>
          ))}
        </div>
      </>}
    </div>
  );
}
