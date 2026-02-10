SCENARIOS = {
    "padrao": {
        "descricao": "Teste Padrão (Altura 1.5m, Albedo 0.4)",
        "inclinações": [0, 15, 30, 45],
        "azimutes": [0, 180],
        "altura": 1.5,
        "albedo": 0.4
    },
    "muro_vertical": {
        "descricao": "Muro Solar (Inclinação até 90°, Azimute Norte/Sul)",
        "inclinações": [0, 45, 90],
        "azimutes": [0, 180],
        "altura": 2.0,
        "albedo": 0.4
    },
    "estudo_geometrico": {
        "descricao": "Sensibilidade de Altura (0.2m, 1.2m, 2.4m)",
        "inclinações": [15, 90],
        "azimutes": [0, 90],
        "alturas_teste": [0.2, 1.2, 2.4], 
        "albedo": 0.4
    },
    "varredura_completa": {
        "descricao": "Varredura Total (Multi-Altura e Multi-Albedo)",
        "inclinações": [0, 30, 60, 90],
        "azimutes": [0, 45, 90, 135, 180],
        "alturas_teste": [0.5, 1.5],
        "albedos_teste": [0.2, 0.4, 0.7]
    },
    "obstaculo_parede": {
        "descricao": "Impacto de Sombra (Parede 4m, Distância 2m)",
        "inclinações": [15],
        "azimutes": [0],
        "altura": 1.5,
        "albedo": 0.2,
        "obstacle_config": {
            "altura": 4.0,
            "distancia": 2.0,
            "az_parede": 45.0, # Nordeste
            "largura": 10.0
        }
    },
}