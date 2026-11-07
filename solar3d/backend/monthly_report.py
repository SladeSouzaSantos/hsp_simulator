"""PDF disclosure for computed F5.2 monthly DC losses by string/MPPT.

Input is a client-supplied result. This formatter does NOT independently verify
calibration, weather, source provenance, geometry, circuit or numerical values.
"""
from __future__ import annotations
from io import BytesIO
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen.canvas import Canvas


class LossMonth(BaseModel):
    month_utc: int = Field(ge=1, le=12)
    hours: int = Field(ge=1, le=8784)
    reference_kwh: float = Field(ge=0, le=1e9, allow_inf_nan=False)
    shaded_kwh: float = Field(ge=0, le=1e9, allow_inf_nan=False)
    loss_kwh: float = Field(ge=-1e9, le=1e9, allow_inf_nan=False)
    loss_percent: float | None = Field(default=None, ge=-1000, le=1000, allow_inf_nan=False)


class LossCircuit(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    mppt_id: str | None = None
    string_ids: list[str] | None = None
    monthly: list[LossMonth] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def validate_month_ids(self):
        months = [x.month_utc for x in self.monthly]
        if len(set(months)) != len(months):
            raise ValueError("Meses duplicados")
        return self


class LossSummary(BaseModel):
    dc_reference_kwh: float = Field(ge=0, le=1e9, allow_inf_nan=False)
    dc_shaded_kwh: float = Field(ge=0, le=1e9, allow_inf_nan=False)
    dc_loss_kwh: float = Field(ge=-1e9, le=1e9, allow_inf_nan=False)
    dc_loss_percent: float | None = Field(ge=-1000, le=1000, allow_inf_nan=False)


class LossPeriod(BaseModel):
    start_utc: str = Field(min_length=5, max_length=80)
    end_utc: str = Field(min_length=5, max_length=80)
    hours: int = Field(ge=24, le=8784)
    full_year: bool


class LossWeather(BaseModel):
    source: str = Field(min_length=1, max_length=80)


class MonthlyLossReport(BaseModel):
    model: Literal["F5_2_MONTHLY_STRING_MPPT_PIECEWISE_IV_V1"]
    calibrated: Literal[False]
    validated_electrical_yield: Literal[False]
    period: LossPeriod
    weather: LossWeather
    summary: LossSummary
    monthly: list[LossMonth] = Field(min_length=1, max_length=12)
    strings: list[LossCircuit] = Field(max_length=64)
    mppts: list[LossCircuit] = Field(max_length=8)

    @model_validator(mode="after")
    def month_match(self):
        expected = {m.month_utc for m in self.monthly}
        for circuit in [*self.strings, *self.mppts]:
            if {m.month_utc for m in circuit.monthly} != expected:
                raise ValueError("Meses de circuitos devem coincidir com resumo")
        return self


def render_monthly_loss_report(result: MonthlyLossReport) -> bytes:
    stream = BytesIO()
    width, height = landscape(A4)
    page = Canvas(stream, pagesize=(width, height), pageCompression=1)
    page_number = 0
    y = 0

    def page_header():
        nonlocal y, page_number
        if page_number:
            page.showPage()
        page_number += 1
        page.setFillColorRGB(0.08, 0.18, 0.22)
        page.rect(0, height-76, width, 76, stroke=0, fill=1)
        page.setFillColorRGB(1, 1, 1)
        page.setFont("Helvetica-Bold", 17)
        page.drawString(38, height-35, "SOLAR 3D LAB — ESTIMATIVA MENSAL DC")
        page.setFont("Helvetica", 10)
        page.drawString(38, height-55, "Strings / MPPTs — RESULTADO EXPERIMENTAL NAO CALIBRADO")
        page.setFillColorRGB(0.13, 0.2, 0.22)
        page.setFont("Helvetica-Bold", 8)
        page.drawString(38, 33,
            "NAO E LAUDO, PROJETO EXECUTIVO, GARANTIA DE PRODUCAO OU PREVISAO AC CERTIFICADA")
        page.setFont("Helvetica", 8)
        page.drawRightString(width-38, 33, f"Pagina {page_number}")
        y = height - 103

    def line(text, bold=False, size=10, step=17):
        nonlocal y
        if y < 71:
            page_header()
        page.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        safe = str(text).encode("latin-1", "replace").decode("latin-1")
        page.drawString(40, y, safe[:145])
        y -= step

    def block(name, months):
        line(name, bold=True, size=11, step=21)
        line("MES UTC       REFERENCIA [kWh DC]      COM SOMBRA [kWh DC]      PERDA [kWh DC]      PERDA [%]",
             bold=True, size=9, step=19)
        for row in sorted(months, key=lambda x: x.month_utc):
            pct = "s/ ref." if row.loss_percent is None else f"{row.loss_percent:8.2f}"
            line(f"{row.month_utc:02d}             {row.reference_kwh:12.2f}                    "
                 f"{row.shaded_kwh:12.2f}                 {row.loss_kwh:11.2f}          {pct}",
                 size=9, step=16)
        line(" ", step=9)

    page_header()
    line(f"Fonte meteorologica: {result.weather.source} | "
         f"Duracao: {result.period.hours} horas | "
         f"Ano completo: {'SIM' if result.period.full_year else 'NAO'}")
    line(f"UTC: {result.period.start_utc[:25]} ate {result.period.end_utc[:25]}")
    s = result.summary
    line(f"TOTAL CC: referencia {s.dc_reference_kwh:.2f} kWh | "
         f"sombreado {s.dc_shaded_kwh:.2f} kWh | perda {s.dc_loss_kwh:.2f} kWh | "
         f"perda {s.dc_loss_percent if s.dc_loss_percent is not None else 0:.2f}%", bold=True)
    line("Hipotese: 3 substrings genericas, bypass idealizado, curvas I-V aproximadas.", size=9)
    line("Importante: formulario recebido do navegador; PDF nao verifica autenticidade nem fontes.", size=9)
    line(" ", step=10)
    block("PERDA DC TOTAL — ESTIMATIVA GEOMETRICA + ELETRICA", result.monthly)
    for circuit in result.mppts:
        block(f"MPPT {circuit.id} (strings: {', '.join(circuit.string_ids or [])})",
              circuit.monthly)
    for circuit in result.strings:
        block(f"STRING {circuit.id} | MPPT {circuit.mppt_id} — MPP PROPRIO HIPOTETICO",
              circuit.monthly)
    line("LIMITES: MPPT ideal aproximado; sem calibração real de celulas, bypass, inversor AC, horizonte/difusa.",
         size=8)
    line("Nao comparar perdas DC desta tabela com um percentual de perda AC medido sem modelagem do inversor.",
         size=8)
    page.save()
    return stream.getvalue()
