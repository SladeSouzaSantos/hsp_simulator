# Contrato v1 — recurso solar horário, sem obstáculos

Endpoint adicional para o GreenCity OS: `POST /recurso-solar/horario` (sob
o prefixo `/api` do proxy atual). As rotas `/calcular` e
`/calcular-arranjo` permanecem intactas para clientes legados.

**Exemplo de entrada:**

```json
{
  "latitude": -5.79448,
  "longitude": -35.21101,
  "inclinacao_graus": 15,
  "azimute_graus": 0,
  "albedo_solo": 0.2,
  "modelo_transposicao": "perez",
  "fonte_dados": "NASA POWER",
  "ano_utc": 2023,
  "mes_utc": 1
}
```

O servidor escolhe o ano civil UTC mais recente com todas as horas caso
`ano_utc` seja omitido. Valida o ano selecionado (8760 ou 8784 horas,
sem intervalos ausentes). Se `mes_utc` for omitido, responde com todas
as horas do ano, possivelmente um JSON grande.

**Saída:** `modelo: recurso_solar_poa_horario_sem_obstaculos_v1`,
`sem_obstaculos: true`, `sem_perdas_eletricas: true`, fonte, orientação,
período, 12 valores de `hsp_referencia_mensal_kwh_m2_dia` e
`amostras[]` de horário UTC, posição solar, GHI/DNI/DHI, POA total,
POA direto, POA céu difuso e POA refletido.

Amostras são médias por hora e a posição solar é calculada em +30 min.
Azimute solar/geográfico: 0=N, 90=L, 180=S e 270=O.
No plano horizontal a identidade `POA_total=GHI` é preservada,
inclusive para dados de provedores com pequenas inconsistências
entre componentes.

**Responsabilidades:**
- HSP Simulator: dados horários e HSP sem obstruções, corrigidos por
  inclinação/azimute.
- Editor/motor 3D GreenCity: aplicar máscaras geométricas somente sobre
  `poa_direta_w_m2`, sem descontar céu difuso e refletido por uma
  simples fração de área. Deve calcular resultados por módulo/horário.
- Dimensionamento GreenCity: determinar impactos elétricos entre
  módulos em série e strings paralelas no MPPT, usando os dados do
  catálogo Isar e perfis horários, sem inferir perdas de MPPT das
  médias mensais por módulo.

O novo endpoint **não** recebe obstáculos, placa, MPPT nem inversor.
Não converter perda de área sombreada diretamente em perda de energia
elétrica. Sombra difusa, reflexões locais e perdas elétricas são
problemas separados da POA de referência.

**Publicação:** nesta branch a rota é proposta e NÃO está disponível
até merge + deploy do backend. Não alterar a API pública de produção
sem homologação.
