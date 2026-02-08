from core.app import calcular_projeto_solar

print("--- CALCULADORA SOLAR BIFACIAL ---")

# Inputs simulando uma entrada de formulário ou banco de dados
inputs = {
    "lat": -7.562,
    "lon": -37.688,
    "inclinacao": 15,
    "azimute": 0,
    "albedo": 0.20,
    "altura": 1.0,
    "tecnologia": "TOPCON"
}

relatorio = calcular_projeto_solar(**inputs)

print(f"\nResultados para Lat: {inputs['lat']} | Lon: {inputs['lon']}")
print(f"Configuração: Inc {inputs['inclinacao']}°, Azi {inputs['azimute']}°, Altura {inputs['altura']}m")
print("-" * 40)

meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
for i, hsp in enumerate(relatorio["mensal"]):
    print(f"{meses[i]}: {hsp:.3f} HSP")

print("-" * 40)
print(f"MÉDIA ANUAL: {relatorio['media']:.3f} HSP/dia")