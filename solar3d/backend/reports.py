"""Experimentally labeled Solar3D energy report PDF (ReportLab, open source).

The input is a client-supplied simulation result. Never certify the values
or imply server verification of authenticity. Footer/watermark explicit.
"""
from __future__ import annotations
from io import BytesIO
from typing import Literal

from pydantic import BaseModel, Field

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas


class MonthRow(BaseModel):
    month_utc: int = Field(ge=1, le=12)
    hours: int = Field(ge=1, le=8784)
    dc_reference_potential_w_kwh: float = Field(ge=0, le=1e9, allow_inf_nan=False)
    dc_shaded_potential_w_kwh: float = Field(ge=0, le=1e9, allow_inf_nan=False)
    ac_reference_proxy_w_kwh: float = Field(ge=0, le=1e9, allow_inf_nan=False)
    ac_shaded_proxy_w_kwh: float = Field(ge=0, le=1e9, allow_inf_nan=False)


class ReportSummary(BaseModel):
    reference_ac_proxy_kwh: float = Field(ge=0, le=1e9, allow_inf_nan=False)
    shaded_ac_proxy_kwh: float = Field(ge=0, le=1e9, allow_inf_nan=False)
    proxy_difference_percent: float = Field(ge=-100, le=100, allow_inf_nan=False)
    reference_dc_potential_kwh: float = Field(ge=0, le=1e9, allow_inf_nan=False)
    shaded_dc_potential_kwh: float = Field(ge=0, le=1e9, allow_inf_nan=False)


class Period(BaseModel):
    start_utc: str = Field(min_length=1, max_length=100)
    end_utc: str = Field(min_length=1, max_length=100)
    hours: int = Field(ge=24, le=8784)


class WeatherMeta(BaseModel):
    source: str = Field(min_length=1, max_length=80)


class ReportRequest(BaseModel):
    model: Literal["F5_PVWATTS_MODULE_POTENTIAL_V1"]
    validated_electrical_yield: Literal[False]
    full_year: bool
    period: Period
    weather: WeatherMeta
    summary: ReportSummary
    monthly: list[MonthRow] = Field(min_length=1, max_length=12)


def render_pdf(report: ReportRequest) -> bytes:
    stream = BytesIO()
    canvas = Canvas(stream, pagesize=A4, pageCompression=1)
    width, height = A4
    y = height - 53

    def line(text: str, size=9, bold=False, gap=20):
        nonlocal y
        canvas.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        # ReportLab core fonts are Latin-1. Encode user strings defensively.
        safe = text.encode("latin-1", errors="replace").decode("latin-1")
        canvas.drawString(48, y, safe[:125])
        y -= gap

    canvas.setFillColorRGB(0.08, 0.19, 0.25)
    canvas.rect(0, height - 122, width, 122, stroke=0, fill=1)
    canvas.setFillColorRGB(1, 1, 1)
    canvas.setFont("Helvetica-Bold", 18)
    canvas.drawString(48, height - 69, "SOLAR 3D LAB")
    canvas.setFont("Helvetica", 10)
    canvas.drawString(48, height - 92, "RELATORIO EXPERIMENTAL - NAO CERTIFICADO")
    canvas.setFillColorRGB(0.06, 0.13, 0.17)
    y = height - 146
    line("Modelo: PVWatts potencial independente / proxy DC-AC", bold=True)
    line(f"Fonte: {report.weather.source}")
    line(f"Periodo: {report.period.start_utc[:19]} a {report.period.end_utc[:19]} UTC")
    line(f"Duracao: {report.period.hours} horas | Ano UTC completo: {'sim' if report.full_year else 'nao'}")
    y -= 9
    s = report.summary
    line("RESULTADOS COMPARATIVOS (NAO VALIDOS PARA DIMENSIONAMENTO)", size=11, bold=True, gap=24)
    line(f"Referencia AC aproximada: {s.reference_ac_proxy_kwh:.2f} kWh", bold=True)
    line(f"Com sombra AC aproximada: {s.shaded_ac_proxy_kwh:.2f} kWh", bold=True)
    line(f"Diferenca do proxy: {s.proxy_difference_percent:.2f}%")
    line(f"Potencial DC referencia: {s.reference_dc_potential_kwh:.2f} kWh")
    line(f"Potencial DC sombreado: {s.shaded_dc_potential_kwh:.2f} kWh")
    y -= 12
    line("RESUMO MENSAL (MES CIVIL UTC)", size=11, bold=True, gap=25)
    line("Mes     Ref AC (kWh)       Sombra AC (kWh)       DC sombra (kWh)", bold=True)
    for month in sorted(report.monthly, key=lambda m: m.month_utc):
        line(f"{month.month_utc:02d}        {month.ac_reference_proxy_w_kwh:10.2f}           "
             f"{month.ac_shaded_proxy_w_kwh:10.2f}                "
             f"{month.dc_shaded_potential_w_kwh:10.2f}", size=9, gap=18)
    y -= 17
    line("LIMITACOES E RASTREABILIDADE", size=10, bold=True)
    for msg in [
        "Valores informados pelo navegador; nao sao verificados/assinados pelo servidor.",
        "Areas bloqueadas em malhas discretas, sem obstrucao da irradiacao difusa.",
        "Potencia DC por modulo independente: nao modela mismatch/string/MPPT.",
        "Inversor PVWatts como proxy; sem validacao de campo ou PVsyst.",
        "Fontes NASA/PVGIS sao dados modelados, nao medicao no local.",
        "Nao utilizar como laudo, ART, projeto executivo ou garantia de rendimento.",
    ]:
        line("- " + msg, size=8, gap=15)
    canvas.setStrokeColorRGB(0.55, 0.32, 0.18)
    canvas.line(48, 64, width - 48, 64)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColorRGB(0.52, 0.25, 0.12)
    canvas.drawString(48, 49, "PREVIA DE PESQUISA - NAO CONSTITUI PROJETO ELETRICO OU PRODUCAO AC CERTIFICADA")
    canvas.save()
    return stream.getvalue()
