# Solar 3D Lab — arquitetura e validação científica (2026-11)

> **Estado**: desenvolvimento experimental, somente branch `feature/solar3d-lab`. Endpoints do HSP v2 seguem intactos. Não promover dados a produção comercial sem calibração/homologação.

## Matriz de implementação

| Etapa | Implementação | Cobertura e limite |
|:--|:--|:--|
| F1 | Editor métrico React Three Fiber | Prismas e módulos parametrizáveis; origem local |
| F2 | Posição solar com pvlib | Geolocalização, timezone IANA e efeméride diária |
| F3 | Ray casting de feixe direto | Quadratura no centro das células dos módulos; boxes opacos |
| F3.1 | Malha triangular opaca | Objetos de triângulos de duas faces, validação geométrica; **sem** terreno/horizonte/difusa |
| F4.1 | Strings, MPPTs e inversor | Topologia explícita e validação de limites elétricos nominais |
| F4.2 catálogo | Importação GreenCity OS | Diagnóstico por item; registros incompletos bloqueados até revisão |
| F4.2 curva | PVMismatch STD72 | Curva I–V/P–V de referência, **não calibrada com datasheet real** |
| F5 preliminar | Irradiância/hora e PVWatts | Estimativa independente por módulo, agregação de potencial por circuito, proxy AC |
| Relatórios | CSV/JSON/PDF | Gráfico mensal, exportação e aviso explícito de incerteza |

## Contratos e endpoints

- `POST /solar3d/solar-day`: coordenadas, dia civil, fuso e amostras.
- `POST /solar3d/shading-day`: objetos, `meshes` opcionais, mapa de células 0/1 por módulo, somente radiação direta.
- `POST /solar3d/catalog/import/greencity`: prévia de importação de um JSON explícito:
  `{"format":"greencity-os-equipment-v1","source_revision":"...","modules":[...],"inverters":[...]}`.
  Itens `review` podem ser revisados e importados; itens `blocked` não são convertidos.
- `POST /solar3d/electrical/validate`: limites preliminares; erros bloqueiam F5.
- `POST /solar3d/electrical/iv-experiment`: PVMismatch padrão genérico, sem calibração.
- `POST /solar3d/energy/simulate`: compara um ano horário via NASA POWER ou PVGIS TMY, ou intervalos fornecidos de 24h a um ano em UTC.
- `POST /solar3d/reports/pdf`: PDF rotulado experimental, a partir de resultado JSON enviado pelo navegador. O documento **não valida a autenticidade dos dados**, somente os formata.

### GreenCity OS: ausência de dados não pode ser mascarada

No repositório `SladeSouzaSantos/greencity-os`, as entidades Isar são `PvModule` e `Inverter`.
Os campos `tempCoefVoc`, `tempCoefIsc` e `tempCoefPmax` não fornecem
necessariamente `tempCoefVmp`. **Nunca** equiparar beta de Vmp ao gamma de Pmax.
Da mesma forma, `mpptCount` não é o número de entradas elétricas, e limites
globais de corrente não substituem os limites por rastreador. Exportações
sem esses valores e `stringsPerMppt` explicitamente informado são bloqueadas.
A exportação usa números em W, V, A e %/°C, sem deslocar a escala arbitrariamente.

O arquivo `solar3d/examples/greencity-staged-excerpt.json` mostra um recorte
de registros Jetion e AUXSOL no `souenergy_verified_seed.dart`; é material de
integração com atributos incompletos, **não um novo banco de dados verificado**.
Para dados reais, conferir fabricante, modelo e datasheet oficial, preencher
coeficientes e limites, exportar do GreenCity OS e importar pela aba Elétrica.
Não há leitura automática de Isar em outra aplicação nem scraping de PDFs.

## Fundamentos do F3

- X Leste, Y Elevação, Z Norte; azimute verdadeiro 0=N, 90=L, 180=S, 270=O.
- As superfícies dos módulos são amostradas em quadrícula `rows×columns`.
- Cada origem desloca EPS acima da face frontal. Raios em direção ao Sol
  intersectam boxes orientados e triângulos opacos.
- Horários noturnos/sem incidência frontal reportam `null` (diferente de 0%).
- Obstáculos de vegetação, horizontes e obstrução da componente difusa
  ainda não são representados quantitativamente.
- Grade discreta pode não capturar sombra estreita menor que a célula.
  Para estudos sérios, fazer refinamento/convergência do grid.

## Fundamentos do F4.2

O experimento `iv-experiment` usa a biblioteca livre PVMismatch 4.1
(BSD 3-clause) e `STD72`. Ele permite modificar irradiância relativa
de células selecionadas em um único módulo genérico de uma string de série
e mostrar os traços de curvas I–V/P–V; modela diodos de bypass da topologia
padrão da biblioteca. **Não** recebe nem calibra os parâmetros STC de
um produto GreenCity OS, não representa automaticamente half-cut,
TOPCon, HJT, bifacialidade ou divisão física das substrings do produto.
Não associar a redução de Pmp genérica a um painel real ou à porcentagem
anual de energia.

## F5 — fórmula e limites

1. Fonte horário UTC de `GHI`, `DNI`, `DHI`, temperatura do ar e vento.
   NASA POWER: anos históricos disponíveis no provedor configurado
   (por padrão 2022–2024; análise por um ano isolado); PVGIS: TMY,
   não sequência histórica de produção.
2. Posição solar calculada no **meio** da hora representada pelo provedor.
3. POA por `pvlib.irradiance.get_total_irradiance`, com modelo Hay–Davies,
   Perez ou isotrópico. Albedo escalar.
4. Feixe direto removido conforme fração geométrica F3; componentes difusa
   e refletida preservadas, **sem** obstrução de céu/horizonte.
5. Temperatura de célula pelo modelo genérico Faiman; potência por módulo
   via PVWatts DC: `Pdc = Pstc × POAef / 1000 × (1+gamma(Tcell-25))`.
6. Soma de potências de módulos independentes fornece um **limite/proxy**
   de potencial para strings e MPPTs. Um circuito em série real impõe
   corrente comum: não tratar essa soma como potência real da string.
7. O inversor PVWatts é aplicado somente à soma de potenciais para criar
   um **proxy AC ilustrativo**, ignorando a busca do MPPT e limites
   elétricos dinâmicos. É uma aproximação informativa, não modelagem
   validada da produção efetiva.
8. Energia integra valores de W observados em passos de 1h:
   `Σ(P_h[W] × 1h)/1000 = kWh`. Meses definidos por UTC.
9. Apenas 8760/8784 horas contínuas com início em 1/jan 00h UTC e
   fim em 31/dez 23h UTC são rotuladas **ano completo**.
   Conjuntos parciais não são anualizados.
10. Materiais não verificados exigem opt-in `allow_unverified_for_research`,
    e configuração elétrica incompatível é recusada.

## Lacunas para um sistema elétrico PVsyst-comparável

- [ ] Calibrar modelos de células/curvas I–V com STC e dados de módulo real.
- [ ] Mapear espacialmente máscara da F3 ao circuito real de células e diodos
  (incluindo half-cut, substrings, bipartições e bypass).
- [ ] Integrar as curvas de strings concorrentes por MPPT e buscar máximos globais.
- [ ] Calcular potência AC confiável com limites dinâmicos, clipping e temperatura.
- [ ] Modelar geometria de terreno, árvores/translucidez, horizonte e céu difuso.
- [ ] Implementar validação cruzada contra PVsyst e medições, incerteza dos
  dados meteorológicos e sensibilidade da resolução temporal.
- [ ] Escalar processamento com worker/filas assíncronas para dezenas/centenas
  de módulos e anos multianuais; atual API é síncrona e orçada.

**Conclusão:** F5 gera comparações explícitas de potência/energia potencial
por cenário. O percentual de diferença de proxy AC **não** é um percentual
de perda fotovoltaica comercialmente validado. Engenharia de ligação,
proteções e normas aplicáveis requerem avaliação profissional.

## Testes

```bash
python -m pip install -r solar3d/backend/requirements.txt pytest httpx
python -m pytest -q tests/solar3d
cd solar3d/frontend
npm install
npm test
npm run build
```

Os testes incluem exemplos geométricos (módulo sem sombra, obstáculo total,
meia sombra, triângulos), limites elétricos, importação bloqueada, curvas
PVMismatch, serie meteorológica de 24h, coerência da energia de referência
e exportação PDF. Faltam ensaios de campo de equipamentos reais.
