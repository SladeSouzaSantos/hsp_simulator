# Referência Técnica de Fatores de Bifacialidade por Tecnologia
# Valores baseados em padrões de mercado para simulações de engenharia
CELL_TECHNOLOGY_REFERENCE = {
    "AL_BSF": {
        "nome_comum": "p-Poly (Standard)",
        "fator_conservador": 0.60,
        "fator_laboratorio": 0.70
    },
    "PERC": {
        "nome_comum": "p-Mono PERC",
        "fator_conservador": 0.70,
        "fator_laboratorio": 0.75
    },
    "TOPCON": {
        "nome_comum": "n-Mono TOPCon", # Tecnologia do seu Astronergy 
        "fator_conservador": 0.80,
        "fator_laboratorio": 0.85
    },
    "HJT": {
        "nome_comum": "Heterojunção (n-type)",
        "fator_conservador": 0.90,
        "fator_laboratorio": 0.95
    }
}

# Referências de Albedo (Fonte: ASHRAE / IEEE)
ALBEDO_REFERENCE = {
    "Grama/Gramado": 0.20,
    "Solo Arenoso": 0.25,
    "Concreto Novo": 0.35,
    "Concreto Velho": 0.22,
    "Asfalto": 0.12,
    "Cascalho Branco": 0.50,
    "Pintura Branca (Telhado)": 0.75,
    "Solo Desértico": 0.30,
    "Neve (Fresta)": 0.80,
    "Vegetação Densa": 0.18
}