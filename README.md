# ☀️ HSP Simulator — API de Irradiação Solar (branch `dev`, revisão 2.0)

API REST em **FastAPI** e dashboard em **Streamlit** para estimar a irradiação solar no plano de módulos fotovoltaicos (POA), em função de latitude, longitude, inclinação e azimute, com comparação horizontal, modelos de transposição horária e estimativa opcional da contribuição bifacial.

> **IMPORTANTE — O que esta versão realmente garante:** corrigimos a inconsistência matemática de Leste/Oeste do motor antigo, eliminamos a aplicação de um modelo horário sobre **médias mensais diárias**, normalizamos o azimute e explicitamos a origem/unidades dos dados. **A precisão dos novos números NÃO foi atestada contra o PVsyst**; é necessário executar uma validação cruzada independente antes de uso em propostas comerciais ou laudos.

## Histórico da versão e auditoria da branch `dev`

Esta revisão foi realizada a partir do projeto completo enviado em ZIP da branch `dev`, com as bases INPE/LABREN, API, dashboard e testes. **O pacote distribuído não contém `.git`, caches ou ambiente virtual**: as alterações não são publicadas automaticamente no GitHub. Preserve seu histórico Git ao copiar as alterações ou aplicar um patch; antes do commit, execute `git status` e `git diff`.

**Incidente inicial de outubro de 2026:** a execução do pytest no Windows reportou `28 failed, 33 passed`:

- **27 falhas relacionadas ao contrato do motor:** testes de estresse geográfico, arrays e Perez forneciam 12 médias mensais de irradiação diária (kWh/m²/dia) onde a transposição exige GHI, DHI e DNI **horários** (W/m²). A validação do motor **não foi desativada** para ocultar o problema.
- **1 falha de cache:** o teste do Streamlit procurava `st.session_state.cache_api_data`, estrutura substituída pelo cache `st.cache_data(ttl=3600)` indexado por localidade e fonte.

As correções anteriores introduziram `tests/fixtures/hourly_weather.py` (céu claro sintético e reproduzível), testes de rejeição de entrada mensal, regressões de obstáculos/repetibilidade, **23 cenários de estresse** com coordenadas específicas das cidades, cache coerente com o dashboard e a opção `--run-live` para isolar dependências externas. Os dados históricos SunData/CRESESB não são injetados como se fossem GHI horário.

**Execuções confirmadas no Windows antes desta consolidação:** `53 passed, 9 skipped` (`python -m pytest -q`) e `62 passed` (`python -m pytest -q --run-live`). O benchmark `engine_vs_pvlib` foi então atualizado para usar a meteorologia horária por cidade em lugar de médias SunData. A suite deve ser repetida após alterações futuras; êxito em testes funcionais **não constitui certificação de precisão física**.

**Reorganização da documentação e dos scripts:** os documentos históricos `AUDITORIA_E_LIMITACOES.md` e `GUIA_VALIDACAO_HSP.md` foram incorporados às seções de testes, protocolos e limitações deste README. Os validadores `verificar_matriz_hsp.py` e `comparar_hsp_pvgis.py` foram movidos para `benchmarks/` e agora devem ser chamados como módulos Python.

## Instalação

Recomendado: Python 3.11 a 3.13 (com `pip` e acesso à internet para instalar dependências e consultar NASA/PVGIS). No Windows, execute os comandos sempre com `python -m` para utilizar o mesmo interpretador/ambiente virtual.

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
# Opcional: inclui testes que requisitam NASA POWER/PVGIS via internet
python -m pytest -q --run-live
```

API (URL local http://localhost:8000/docs):

```bash
python -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload
```

Dashboard (URL local http://localhost:8501):

```bash
python -m streamlit run dashboard.py
```

Docker Compose (desenvolvimento/ambiente único; **não** é um deployment stack Swarm com imagens publicadas):

```bash
docker compose -f docker-stack.yml up --build -d
```

**Antes de publicar no domínio atual**, revise seu Nginx/Traefik, volume de dados, HTTPS, políticas de cache e estratégia de atualização. O ZIP não replica automaticamente as credenciais e a infraestrutura do servidor original.

## Principais alterações técnicas

| Área | Antes | Agora |
| --- | --- | --- |
| Perez legacy | Integração `Rb` assimétrica em azimutes e difusa parametrizada sem coeficientes de Perez | `PerezEngine` mantém a assinatura mas chama transposição horária com pvlib |
| Perez pvlib | Média **diária mensal** (kWh/m²/d) tratada como **instantânea** (W/m²) no dia 21 às 12h | Série horária GHI/DHI/DNI em W/m², posição solar por intervalo; integração posterior |
| Azimute | Conversão `(360 - az)` invertia Leste/Oeste | Convenção **geográfica 0° Norte, 90° Leste, 180° Sul, 270° Oeste** em toda a API |
| NASA POWER | Endpoint climatológico mensal; HSP calculada por `W/m² × 0.024` (válido apenas para média diária) | Endpoint `/temporal/hourly/point`, timestamps UTC, W/m² sem `0.024` por amostra |
| PVGIS | TMY horário reduzido prematuramente a médias mensais | TMY horário preservado até o cálculo POA |
| INPE/LABREN | Atlas mensal usado no motor horário | **Somente referência horizontal mensal**; não inventamos irradiância horária |
| Bifacial | Fator artificial de altura podia inflar irradiação da traseira | Traseira de **plano isolado exposto** × bifacialidade, apresentada separadamente |
| Obstáculos | Janela angular aproximada e projeção horizontal incapazes de distinguir poste e muro | Interseção analítica da sombra de uma tela vertical finita com o retângulo inclinado do módulo; bloqueio horário apenas da irradiância direta |
| Comparação | Padrão 0°/0° podia incluir ganho bifacial | Base horizontal **monofacial GHI**. Para `tilt=0`, identidade `POA=GHI` |
| Média anual | Média aritmética dos 12 meses | Média de todos os dias completos observados (ponderação por dias) |

## Fonte de dados e precisão

### NASA POWER — padrão preferencial

`NasaPowerProvider` requisita GHI (`ALLSKY_SFC_SW_DWN`), DHI (`ALLSKY_SFC_SW_DIFF`), DNI (`ALLSKY_SFC_SW_DNI`), temperatura e vento da **API horária** em UTC. Por padrão, consulta 2022–2024 (3 anos históricos), com cache simples em memória por processo; essa janela **não é uma normal climatológica de 20–30 anos**. Para alterar:

```bash
export NASA_START_YEAR=2019
export NASA_END_YEAR=2024
# Windows PowerShell: $env:NASA_START_YEAR='2019'
```

Aceita anos de 2001 a 2025 com até 10 anos por solicitação. A execução verifica ausências e limites de irradiância; dados indisponíveis não são substituídos silenciosamente por zero. Longos intervalos podem sofrer timeout ou limite de serviço da NASA.

### PVGIS — fallback horário, onde houver cobertura

Utiliza um **Typical Meteorological Year (TMY)** de 8760 observações via `pvlib.iotools.get_pvgis_tmy()`, com seus próprios dados meteorológicos. Um TMY **não é** uma observação do ano 2023, mesmo quando as datas são normalizadas para 2023 para fins de cálculo astronômico. A API tenta PVGIS quando NASA falha, e registra `detalhes.fonte` e `detalhes.qualidade`.

### INPE/LABREN — climatologia horizontal mensal

O Atlas não fornece por si só todos os pares de GHI/DHI/DNI em cada hora. Por isso uma chamada com `fonte_dados="INPE/LABREN Atlas 2017"` retorna **422** na API `/calcular` (não há transposição válida sem série temporal); no dashboard apenas as médias horizontais são apresentadas. **Não é erro de instalação.** Use-o para referência/benchmark horizontal independente, não para fingir cálculo Perez horário.

### Bases INPE/LABREN e catálogo de localidades

**Nesta entrega**, foram preservados os arquivos presentes no ZIP enviado:
`data/inpe_labren/global_horizontal_means.csv`, `direct_normal_means.csv`,
`diffuse_means.csv`, `atlas_brasil_consolidado.parquet` e
`atlas_solar_2017_metadados.pdf`. `data/localidades.json` mantém o catálogo recebido com **27 UFs e 634 localidades**. As coordenadas de algumas entradas representam pontos de uma grade meteorológica, e não necessariamente os centros urbanos. O seletor não limita o cálculo por latitude/longitude informadas manualmente. Para recuperar a lista original e reprocessar os CSVs, se necessário:

```bash
python scripts/restore_original_data.py --overwrite
```

O script consulta exclusivamente URLs de uma **revisão imutável** do repositório original, faz download dos CSVs, PDF/fixture e localidades, e valida se os grids coincidem. Necessita rede e `pyarrow`. Sem `--overwrite`, preserva os arquivos de dados preexistentes.

## Contrato da API

### `POST /calcular`

```json
{
  "latitude": -5.79448,
  "longitude": -35.21101,
  "inclinacao_graus": 15,
  "azimute_graus": 0,
  "is_bifacial": false,
  "tecnologia_celula": "TOPCON",
  "albedo_solo": 0.20,
  "distancia_centro_modulo_chao": 0.20,
  "comprimento_modulo": 2.278,
  "largura_modulo": 1.134,
  "orientacao": "Retrato",
  "modelo_transposicao": "perez",
  "fonte_dados": "auto"
}
```

`fonte_dados`: `auto`, `NASA POWER`, `PVGIS` ou `INPE/LABREN Atlas 2017`. `modelo_transposicao`: `perez`, `haydavies`, `isotropic`. Convenção azimutal global **0=N, 90=L, 180=S, 270=O**; o PVsyst pode apresentar a orientação de referência conforme o hemisfério e a versão/configuração do projeto. **Não aplique um deslocamento fixo de 180° sem verificar a rosa dos ventos e a convenção da instalação no PVsyst**.

Resposta mantém o contrato original em `clima`, `kWh/m²/dia.real`, `kWh/m²/dia.referencia`, `perda_sombreamento_estimada` e acrescenta `detalhes` com modelo, origem, componente frontal, equivalente traseiro e HSP horizontal. Em instalação bifacial, a chave `real` é **irradiância efetiva equivalente** (não exclusivamente frontal): prefira usar `detalhes.hsp_frontal` para HSP POA e `detalhes.hsp_traseira_equivalente` para ganho estimado separado.

### `POST /calcular-arranjo`

```json
{
  "latitude": -5.79448,
  "longitude": -35.21101,
  "itens": [
    {"id_placa":"Norte","inclinacao_graus":15,"azimute_graus":0},
    {"id_placa":"Leste","inclinacao_graus":15,"azimute_graus":90}
  ]
}
```

Os itens de um lote compartilham a fonte meteorológica; configurações distintas de fonte recebem HTTP 422. O mesmo conjunto horário é baixado apenas uma vez por lote. Limite: 500 itens, mas 500 simulações Perez completas podem exceder a capacidade do servidor; recomenda-se processamento assíncrono para lotes volumosos.

`GET /health` responde estado básico da aplicação. **Ele não é um monitor da disponibilidade externa da NASA/PVGIS.**

## Fórmula e grandezas

A irradiância no plano (`POA`, W/m²) é transposta para **cada hora**, resultando em três componentes: feixe direto + céu difuso + solo refletido. Em seguida:

\[
HSP_{dia} = \frac{\sum_{h=1}^{24} POA_h \; \Delta t_h}{1000\;\mathrm{W/m^2}},\quad \Delta t_h=1\;\mathrm{h}
\]

Uma média mensal é calculada a partir dos valores diários completos, e a média geral pondera corretamente o número de dias representados. Os dias são agrupados **em UTC**; para um relatório baseado no calendário civil local, acrescente uma etapa explícita de conversão para IANA timezone e ajuste de dias parciais.

A análise bifacial usa face oposta `tilt_rear = 180° − tilt_front` e `azi_rear = (azi_front+180)%360`, aplicando um fator de bifacialidade **estimado** por tecnologia. Este modelo representa um plano isolado sem bloqueio por fileiras nem perdas por mismatch ou IAM; altura do módulo não é usada para criar ganhos fictícios. **Não é uma simulação bifacial comercial completa**. Para fileiras, é preciso altura, pitch, GCR, geometria e um modelo próprio (ex.: `pvlib.bifacial.infinite_sheds`) com validação específica.

### Fase 1 — sombreamento geométrico frontal (22/10/2026)

O algoritmo de `core/perez_engines/shadow_engine.py` usa **uma tela retangular vertical de largura e altura finitas** (muro, fachada aproximada ou poste plano), orientada perpendicularmente à direção radial `referencia_azimutal_obstaculo`. Para cada timestamp solar horário, projeta os raios do Sol para os pontos da superfície inclinada do módulo e calcula **analiticamente** a interseção da região bloqueada com o seu retângulo. Assim, um poste estreito não equivale a um muro largo. O procedimento trabalha em coordenadas locais do módulo e não exige dados GIS nem imagem de drone.

Os quatro campos existentes de `config_obstaculo` permanecem com a mesma grafia:

```json
"config_obstaculo": {
  "altura_obstaculo": 3.5,
  "distancia_obstaculo": 2.0,
  "largura_obstaculo": 0.4,
  "referencia_azimutal_obstaculo": 0
}
```

- **Altura** é a cota do topo da tela sobre o solo (m); sua base está no nível 0.
- **Distância** é medida horizontalmente desde a **borda mais próxima do retângulo do módulo** até o plano da tela (m). Não é a distância inclinada nem a distância até o centro. Alterar essa referência em relação ao motor antigo modifica as estimativas, intencionalmente.
- **Largura** (m) é medida no eixo tangencial à direção indicada; a tela é centrada nesse eixo, sem deslocamento lateral opcional nesta fase.
- **Azimute do obstáculo** é a posição geográfica da tela em relação ao centro do módulo: **0° Norte, 90° Leste, 180° Sul, 270° Oeste**. O motor respeita independentemente o azimute e a inclinação do módulo.
- **Geometria do módulo** usa `comprimento_modulo`, `largura_modulo` e `orientacao` (Retrato/Paisagem); sua inclinação determina a altura de cada ponto. Um item de `/calcular-arranjo` é calculado como painel isolado, pois a API ainda **não** recebe a posição 3D de cada módulo.
- **Centro baixo demais:** a configuração antiga permite `distancia_centro_modulo_chao=0.20` com módulo de 2,278 m e inclinação 15°, colocando a borda inferior abaixo do solo. Somente durante o cálculo de sombra, o motor usa `altura_centro_utilizada=max(altura_centro_informada, comprimento_na_rampa*sin(inclinação)/2)`. Isso **altera a altura física efetiva** e é explicitado em `detalhes.sombra_geometria.altura_ajustada_para_evitar_solo`. Recomenda-se informar uma altura central realista para evitar essa correção de compatibilidade.

**O que é calculado:** fração da **área** bloqueada para o feixe direto a cada hora, aplicada exclusivamente a `poa_direct`. `poa_sky_diffuse` e `poa_ground_diffuse` permanecem sem desconto; no modo bifacial, a irradiância equivalente traseira permanece sem sombra. O sistema **não calcula** fator de vista do céu, sombra por árvores com copa volumétrica, sobreposição de vários obstáculos, perfil de horizonte, fileiras, IAM, ou perdas elétricas por substrings/bypass. Os resultados são **perdas de irradiância**, não necessariamente perdas de energia elétrica do sistema.

**Resultados preservados e novas métricas aditivas:** `kWh/m²/dia.real` continua sendo a série efetiva com sombra e `kWh/m²/dia.referencia` continua sendo a série equivalente sem sombra; `perda_sombreamento_estimada` mantém o formato de percentual anual. Agora `detalhes` inclui `hsp_frontal_mensal_sem_sombra` (12 valores), `perda_sombreamento_mensal_pct` (12 percentuais sobre a POA frontal de referência) e `sombra_geometria` (hipóteses e altura ajustada). Nenhum campo antigo da API foi renomeado/removido. No dashboard é possível visualizar e exportar ambas as curvas mensais e o percentual de perda.

A sombra anual não é a média simples dos 12 percentuais: é a razão entre as energias anuais perdidas e a POA frontal anual sem sombra. Um dado mensal, por sua vez, usa as integrações horárias de cada mês; as duas curvas são derivadas da **mesma meteorologia**. A interface antiga de rastro solar foi removida, pois não sincronizava longitude/tempo solar corretamente.

**Testes analíticos locais:** `python -m benchmarks.validar_sombra_geometrica` cria `benchmarks/documents/VALIDACAO_SOMBRA_GEOMETRICA.csv`, incluindo um painel horizontal 2×2 m com 25% de sombra por muro, 5% por obstáculo de 40 cm, 0,125% por obstáculo de 1 cm e casos verticais. Esses gabaritos validam a **geometria idealizada**: ainda falta confronto de irradiância com medições e software especializado.


## Validação automatizada e critérios de auditoria

A suíte diferencia testes unitários determinísticos de testes que acessam dados externos. **Execute os comandos na raiz do repositório**, que contém `api.py`, `dashboard.py` e o pacote `benchmarks/`:

```powershell
python -m pytest -q                 # offline: sem consultar provedores externos
python -m pytest -q --run-live      # inclui testes marcados live com NASA/PVGIS
python -m compileall -q core services tests benchmarks api.py dashboard.py
```

- `tests/fixtures/hourly_weather.py` constrói séries **sintéticas** consistentes com posição solar para ensaios reprodutíveis; não representa dados de campo.
- `tests/integration/test_geographical_stress.py` testa inclinações e latitudes com coordenadas próprias de cada localidade; os registros do SunData delimitam os cenários, **não** fornecem GHI horário.
- O motor rejeita `hsp_global`/`hsp_diffuse` mensais sem `hourly`, porque a transposição Perez exige irradiâncias em **W/m²** e seus timestamps.
- O cache Streamlit usa `st.cache_data(ttl=3600)`; os testes não dependem de chave obsoleta de `session_state`.
- Testes marcados com `@pytest.mark.live` exigem acesso aos provedores e podem falhar por rede, indisponibilidade ou alteração no serviço. São executados somente com `--run-live`.
- Na auditoria da Fase 1 (22/10/2026), a suíte local resultou em **39 testes aprovados, 16 ignorados e nenhuma falha**, incluindo 14 novos cenários de geometria e integração mensal. Os ignorados precisam ser repetidos num ambiente com `pvlib`/Streamlit e, quando aplicável, rede. Na primeira auditoria local, o ambiente restrito sem `pvlib`, Streamlit e `pyarrow` reportou `18 passed, 15 skipped`; após a atualização do benchmark, `21 passed, 16 skipped`; após a reorganização dos scripts e quatro novos testes de regressão, `25 passed, 16 skipped`. Esses resultados refletem dependências não instaladas e **não substituem** os resultados completos do Windows.

**Verificações de auditoria:** recusar entrada meteorológica inválida; conservar a fonte e as unidades; assegurar série UTC contínua e dias completos; garantir identidade horizontal e equivalência 0°/360°; comparar a implementação com a referência direta do pvlib; por fim confrontar fontes independentes e PVsyst sob condições meteorológicas equivalentes. Resultados de diferentes bases não devem ser tratados automaticamente como erros do motor.

### Estrutura dos validadores

```text
benchmarks/
├── __init__.py
├── auditor.py
├── run_benchmarks.py                 # sombra, comparação SunData e provedores
├── validar_sombra_geometrica.py      # testes analíticos de área e saída CSV
├── engine_vs_pvlib.py                # benchmark horário do motor versus pvlib direto
├── validate_matrix.py                # grade configurável por coordenadas
├── verificar_matriz_hsp.py           # 40 orientações fixas para Natal
├── comparar_hsp_pvgis.py             # comparação independente com PVGIS horário
└── documents/
    ├── MATRIZ_HSP_AZIMUTE_NATAL.csv
    └── ... (outros relatórios CSV gerados)
```

Execute **`python -m benchmarks.nome_do_modulo`**, e não `python benchmarks/nome_do_modulo.py`, para que os imports de `core`, `services` e outros pacotes sejam resolvidos de maneira consistente, sem ajustar manualmente `PYTHONPATH`. Os CSVs e o cache usam caminhos resolvidos a partir do diretório raiz do projeto.

### Comandos rápidos

```powershell
# Auditoria histórica: sombra, SunData/CRESESB e provedores
python -m benchmarks.run_benchmarks

# Fase 1: verificar seis resultados analíticos da geometria de sombra
python -m benchmarks.validar_sombra_geometrica

# Comparativo horário e 40 orientações usando o motor e o pvlib direto
python -m benchmarks.engine_vs_pvlib --city Natal
python -m benchmarks.engine_vs_pvlib --city Natal --grid

# Grade adicional de orientações para coordenadas arbitrárias
python -m benchmarks.validate_matrix --latitude -5.79448 --longitude -35.21101 --source "NASA POWER"

# Matriz fixa Natal: 5 inclinações x 8 azimutes, com NASA POWER horário
python -m benchmarks.verificar_matriz_hsp

# Comparação externa PVGIS: primeiro uma amostra, depois tudo
python -m benchmarks.comparar_hsp_pvgis --max-new-calls 3
python -m benchmarks.comparar_hsp_pvgis
```

### Relatórios CSV e interpretação

| Arquivo em `benchmarks/documents/` | Produzido por | O que demonstra / limitação |
| --- | --- | --- |
| `MATRIZ_HSP_AZIMUTE_NATAL.csv` | `verificar_matriz_hsp` | Invariância horizontal, azimutes e HSP por orientação no mesmo clima NASA |
| `COMPARATIVO_HSP_PVGIS_NATAL.csv` | `comparar_hsp_pvgis` | Comparação de HSP e fator de transposição com PVGIS; bases/períodos podem diferir |
| `BENCHMARK_ENGINE_VS_PVLIB.csv` | `engine_vs_pvlib` | Integração com algoritmo pvlib em mesma meteorologia; **não** é referência científica independente |
| `BENCHMARK_ORIENTACOES_ENGINE_VS_PVLIB.csv` | `engine_vs_pvlib --grid` | Verificação da mesma grade com implementação interna e pvlib |
| `BENCHMARK_SOMBRA_FINAL.csv` | `run_benchmarks` | Sensibilidade do obstáculo retangular, deve ser **regenerado** após a Fase 1; CSVs preexistentes são históricos |
| `VALIDACAO_SOMBRA_GEOMETRICA.csv` | `validar_sombra_geometrica` | Gabaritos analíticos para a fração da área bloqueada da face frontal |
| `VALIDACAO_CRESESB_ATTESTED.csv` | `run_benchmarks` | Comparação indireta normalizada com amostragem SunData; **o nome histórico não significa validação atestada** |
| `COMPARATIVO_PROVIDERS.csv` | `run_benchmarks` | Diferenças de GHI entre INPE, NASA e PVGIS (fontes/períodos distintos) |
| `COMPARATIVO_LEGACY_VS_PVLIB_NASA.csv` | Histórico, não atualizado | Referência antiga de implementação obsoleta; **não utilizar para aprovar o motor atual** |

Os scripts `verificar_matriz_hsp` e `comparar_hsp_pvgis` usam caminhos fixos de Natal; use `validate_matrix` ou `engine_vs_pvlib` para outras cidades. Consulte também os parâmetros de cada benchmark com `python -m benchmarks.engine_vs_pvlib --help` ou `python -m benchmarks.comparar_hsp_pvgis --help`.

## Benchmark `engine_vs_pvlib` — entrada horária corrigida (22/10/2026)

A versão antiga de `benchmarks/engine_vs_pvlib.py` montava `dados_clima`
com `hsp_global` e `hsp_diffuse` **mensais** extraídos do SunData, usando
uma parcela difusa arbitrária de 30%, e passava essas médias como se fossem
irradiâncias instantâneas em W/m². Essa entrada é **inválida** para Perez
horário, e a exceção `Transposição Perez requer GHI, DHI e DNI em série
horária (W/m²)` é a proteção correta do motor.

O benchmark atualizado **busca a série horária uma única vez por cidade**
no NASA POWER (ou PVGIS, se escolhido explicitamente). Conserva os dados
GHI/DHI/DNI em W/m² e os timestamps UTC; calcula a POA sem sombra e
monofacial com albedo 0,20 e azimute geográfico 0° (Norte). Compara os
resultados de `PerezEngine` com uma **chamada direta ao `pvlib`**, usando
a mesma geometria, o mesmo modelo Perez, os mesmos timestamps e a mesma
base meteorológica. A referência SunData aparece separadamente, com
indicadores de diferença bruta e diferença do fator de transposição
após normalização pela GHI horizontal do SunData.

**Executar no PowerShell, a partir da raiz do projeto:**

```powershell
# Comparar todas as cidades presentes na amostragem SunData com NASA POWER:
python -m benchmarks.engine_vs_pvlib

# Executar apenas Natal para conferir primeiro o resultado:
python -m benchmarks.engine_vs_pvlib --city Natal

# Selecionar dados horários PVGIS explicitamente:
python -m benchmarks.engine_vs_pvlib --city Natal --source PVGIS

# Teste adicional das 40 orientações em Natal, com o mesmo dataset horário:
python -m benchmarks.engine_vs_pvlib --city Natal --grid

# Ensaio offline/determinístico: céu claro sintético, NÃO é validação de precisão:
python -m benchmarks.engine_vs_pvlib --city Natal --synthetic
```

**Saídas:**

- `benchmarks/documents/BENCHMARK_ENGINE_VS_PVLIB.csv`: cidades,
  inclinações SunData, HSP SunData, HSP do motor, HSP do `pvlib` direto,
  diferença entre cálculos, origem meteorológica e diferença normalizada.
- `benchmarks/documents/BENCHMARK_ORIENTACOES_ENGINE_VS_PVLIB.csv`:
  somente com `--grid`, as cinco inclinações × oito azimutes (40 casos).
- A antiga saída `COMPARATIVO_LEGACY_VS_PVLIB_NASA.csv` **não é mais
  atualizada**: seus números históricos referem-se à implementação anterior.
  Não utilize esse CSV para avaliar o motor corrigido.

**Interpretação crítica:** `PerezEngine` e `PerezEnginePVLib` são hoje
**o mesmo motor**, pois `perez_legacy` foi mantido apenas como alias de
compatibilidade. Logo, diferenças próximas de zero entre o motor e a
chamada direta ao pvlib são esperadas e demonstram a consistência da
integração, **não constituem validação científica independente**.

Os valores SunData/CRESESB e NASA POWER ou PVGIS podem ser diferentes
por resolução, climatologia histórica e método de transposição. O
benchmark `run_benchmarks` existente também normaliza o fator de
transposição pela GHI horizontal do SunData — seus desvios **não atestam
precisão contra observações de campo**. Para validar numericamente a
transposição, compare `GlobInc` do PVsyst com POA frontal usando a **mesma
série meteorológica horária**, o mesmo albedo e orientações equivalentes.

O código **não fabrica DNI horário** a partir de HSP mensal nem remove
a validação de dados do motor. Para impedir mudanças silenciosas de
provedor, o benchmark força a fonte solicitada e indica sua origem no CSV.

## Protocolo reproduzível de validação física — Natal/RN

### Configuração e resultados de referência interna

A configuração de controle reportada é Natal/RN (**latitude −5,79448; longitude −35,21101**), NASA POWER horário **2022–2024**, Perez, módulo **monofacial**, sem sombras, sem IAM ou perdas elétricas e albedo **0,20**. As inclinações são **0°, 15°, 20°, 45° e 90°** e os azimutes geográficos **0°, 45°, 90°, 135°, 180°, 225°, 270° e 360°**.

Matriz registrada no Windows em outubro de 2026, em **kWh/m²/dia**:

| Inclinação | 0° N | 45° NE | 90° L | 135° SE | 180° S | 225° SO | 270° O | 360° N |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0° | 5,796 | 5,796 | 5,796 | 5,796 | 5,796 | 5,796 | 5,796 | 5,796 |
| 15° | 5,473 | 5,451 | 5,399 | 5,328 | 5,298 | 5,331 | 5,402 | 5,473 |
| 20° | 5,406 | 5,385 | 5,327 | 5,224 | 5,174 | 5,228 | 5,331 | 5,406 |
| 45° | 4,607 | 4,690 | 4,689 | 4,374 | 4,134 | 4,387 | 4,700 | 4,607 |
| 90° | 2,289 | 2,728 | 3,025 | 2,477 | 1,951 | 2,496 | 3,034 | 2,289 |

**Propriedades que passaram:** (1) na inclinação 0°, `POA = GHI` em todos os azimutes; (2) para cada inclinação, azimutes 0° e 360° geram a mesma HSP. A referência GHI horizontal foi **5,796 kWh/m²/dia**. Há ainda o teste independente de orientação solar com AOI: em 21/06/2024 (15h UTC) o AOI da face Norte foi 17,6° e o da Sul 74,7°; em 21/12/2024, Norte 63,4° e Sul 28,5°. Logo, **0° significa Norte geográfico**, e **180° significa Sul**, independentemente do hemisfério, no contrato da API/pvlib.

O valor de HSP inclinado ficar abaixo da GHI horizontal — inclusive 15° Norte, **5,473 versus 5,796** — deve ser investigado com referências independentes, mas **não autoriza concluir isoladamente** que há erro; é preciso analisar a climatologia e as componentes do modelo.

### Camada 1 — propriedades numéricas e orientação

```powershell
python -m pytest -q --run-live
python -m benchmarks.verificar_matriz_hsp
python -m benchmarks.engine_vs_pvlib --city Natal --grid
```

Defina tolerância de comparação de **0,001 kWh/m²/dia** para valores arredondados na identidade horizontal e equivalência 0°/360°. Registre a fonte meteorológica, os anos consultados, o modelo, a unidade e os resultados antes de comparar. Isso testa coerência interna, **não precisão absoluta**.

### Camada 2 — referência externa PVGIS (29 geometrias únicas)

```powershell
# O CSV da matriz deve existir antes da comparação
python -m benchmarks.verificar_matriz_hsp

# Baixa no máximo 3 consultas novas para testar acesso ao PVGIS
python -m benchmarks.comparar_hsp_pvgis --max-new-calls 3

# Continua o benchmark, reaproveitando cache de respostas válidas
python -m benchmarks.comparar_hsp_pvgis

# Exemplo explícito de ano e banco (verifique cobertura)
python -m benchmarks.comparar_hsp_pvgis --year 2020 --database PVGIS-ERA5
```

O script utiliza `pvlib.iotools.get_pvgis_hourly()`, endpoint **PVGIS 5.3**, `components=False`, `usehorizon=False` e `poa_global` horário em **W/m²**, agregado em **kWh/m²/dia**. O padrão é ano **2020**, diferente da meteorologia NASA **2022–2024**: por isso a comparação **não mede somente diferenças do algoritmo de transposição**.

O script deduplica geometrias: a face horizontal (8 azimutes equivalentes) e os pares 0°=360° dos planos inclinados deixam **29 configurações efetivas**, embora gere **40 linhas** no CSV. As consultas bem-sucedidas ficam em `benchmarks/documents/cache_pvgis_validacao/`. Durante a execução parcial (por exemplo `--max-new-calls 3`) o programa gera resultados marcados como `PENDENTE` e encerra com **código de saída 2**; isto sinaliza matriz incompleta, não necessariamente defeito. Erros HTTP, timeout ou ausência de amostras válidas não viram valores artificiais.

O parâmetro `surface_azimuth` passado ao **wrapper pvlib** segue a convenção geográfica do simulador; **não subtraia 180° manualmente ao chamar o wrapper**. O próprio pvlib converte para `aspect` da API PVGIS.

Analise o fator de transposição `FT = HSP_inclinada / HSP_horizontal` para ambas as fontes e o campo `desvio_relativo_ft_pct`. Compare tendências de N/S e L/O, mas interprete diferenças de FT como **sinais para investigação**, pois dados meteorológicos diferentes afetam até o fator de transposição. A HSP absoluta e o FT, sozinhos, não certificam o motor.

### Camada 3 — PVsyst com a mesma meteorologia

Para isolar a transposição, configure **a mesma série horária** de GHI/DHI/DNI e período histórico em ambos os programas. Em PVsyst, revise a conversão do formato meteorológico, amostras por hora e fuso/horário de verão antes de analisar diferenças.

1. Fixe Natal e as mesmas inclinações, albedo 0,20, orientação, modelo de transposição (Perez inicialmente), geometria sem sombra, sem IAM/soiling e sem perdas elétricas. Certifique-se de comparar grandezas anteriores às perdas.
2. Sempre que tecnicamente viável, importe a mesma série NASA horária; confirme a interpretação dos timestamps como início/meio/fim do intervalo, UTC ou hora local, e o fechamento do balanço de irradiância.
3. Exporte as grandezas **`GlobHor`** (GHI), **`DiffHor`** (DHI), **`BeamInc`**, **`DiffSInc`**, **`AlbInc`**, **`GlobInc`** e **`FTransp`**, preferencialmente horárias e mensais.
4. Compare o **`GlobInc`** do PVsyst com a **POA frontal** do HSP Simulator para o mesmo intervalo; **não** use `GlobEff` ou `E_Grid` para aferir a irradiância incidente. Converta totais mensais kWh/m² em médias kWh/m²/dia dividindo pelo número de dias do mês.
5. Avalie desvio mensal, viés, erro absoluto médio, componentes e ângulo de incidência em períodos representativos; repita outras orientações e modelos (ex.: Hay-Davies) somente após isolar o caso base.

#### Convenções de azimute: Natal, hemisfério Sul

**A referência do simulador/pvlib é geográfica:** 0° = Norte, 90° = Leste, 180° = Sul, 270° = Oeste. A API PVGIS adota orientação relativa ao Sul e pode receber o `aspect` mostrado abaixo. No PVsyst a referência indicada ao usuário depende do hemisfério e da forma de exibição; **confira a orientação visual da rosa dos ventos e as definições da versão instalada**.

| Direção | Simulador/pvlib | PVsyst (convenção Norte = 0° no hemisfério Sul) | PVGIS `aspect` |
| --- | ---: | ---: | ---: |
| Norte | 0° | 0° | −180° / +180° |
| Nordeste | 45° | −45° | −135° |
| Leste | 90° | −90° | −90° |
| Sudeste | 135° | −135° | −45° |
| Sul | 180° | ±180° | 0° |
| Sudoeste | 225° | +135° | +45° |
| Oeste | 270° | +90° | +90° |
| Norte | 360° | 0° | −180° / +180° |

**Não use uma conversão fixa Norte↔Sul na API HSP Simulator**, nem associe `0°` a Sul só porque uma ferramenta externa usa essa convenção. O azimute da API HSP é sempre geográfico.

### Critérios de aceitação e pendências

- **Invariantes geométricas:** igualdade horizontal e 0°/360° dentro da precisão do relatório (±0,001 kWh/m²/dia em saídas de três casas decimais).
- **Mesmo modelo/mesmo dataset:** a implementação interna e uma chamada direta ao pvlib devem coincidir numericamente; isso valida o encadeamento de dados, **não** o modelo físico do próprio pvlib.
- **PVGIS e NASA diferentes:** não existe limiar universal para diferenças absolutas ou FT de climatologias diferentes. Registre períodos, bancos, orientação, unidade e fonte; investigue diferenças sistemáticas.
- **PVsyst com meteorologia equivalente:** verificar primeiro qualidade temporal e GHI/DHI/DNI; depois estabelecer uma meta preliminar de engenharia (por exemplo, desvios mensais relativos de **2%–5%**, conforme hipótese e nível de arredondamento). Esse intervalo é **indicativo, não normativo nem garantia de precisão**.
- **Bifacial e sombra:** o novo motor idealiza uma única tela vertical frontal e calcula a fração geométrica exata para essa idealização; continuam pendentes altura detalhada do local, múltiplos obstáculos, céu difuso, pitch, GCR, fator elétrico de sombra parcial e validação com PVsyst/levantamento em campo.

### Fontes técnicas do protocolo

- [PVGIS API não interativa — JRC](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/api-non-interactive-service_en).
- [pvlib — `get_pvgis_hourly`](https://pvlib-python.readthedocs.io/en/v0.14.0/reference/generated/pvlib.iotools.get_pvgis_hourly.html).
- [PVsyst — azimute do plano](https://www.pvsyst.com/help/glossary/solar-geometry/plane-azimuth.html).
- [PVsyst — variáveis de irradiação](https://www.pvsyst.com/help/project-design/results/simulation-variables-meteo-and-irradiations.html).

## Limitações conhecidas e próximos passos

- O modelo horário pressupõe que timestamp identifica início do intervalo para avaliação solar +30 min. Proveniência temporal do TMY PVGIS deve ser verificada para melhor concordância sub-horária.
- NASA vs PVGIS variam em resolução espacial, períodos e modelos; resultados diferentes podem ser **dados**, não falhas da fórmula.
- Os modelos não incorporam inclinação real sobre horizonte local, altitude exata de cada instalação, sujeira, IAM, perdas de temperatura/inversor ou degradação.
- Em `tilt=0` monofacial, a identidade POA=GHI é imposta mesmo quando os três produtos satelitais tenham pequeno resíduo de fechamento energético.
- O projeto está preparado para validação, mas **ainda não possui estudo atestado em campo/PVsyst**.

## Licença e fontes

[MIT](LICENSE). Fonte inicial: [hsp_simulator](https://github.com/SladeSouzaSantos/hsp_simulator). Modelos científicos/serviços: [pvlib-python](https://pvlib-python.readthedocs.io/), [NASA POWER Hourly](https://power.larc.nasa.gov/docs/services/api/temporal/hourly/), [PVGIS](https://re.jrc.ec.europa.eu/pvg_tools/). Os dados de terceiros seguem suas respectivas condições de acesso.

Os protocolos de validação, o histórico de auditoria e as limitações estão consolidados neste `README.md`; não há dependência dos antigos arquivos de documentação separados.
