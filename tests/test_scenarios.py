SCENARIOS = {
    "padrao": {
        "descricao": "Teste Padrão (Altura 1.5m, Albedo 0.4)",
        "inclinacoes": [0, 15, 30, 45],
        "azimutes": [0, 180],
        "altura": 1.5,
        "albedo": 0.4
    },
    "muro_vertical": {
        "descricao": "Muro Solar (Inclinação até 90°, Azimute Norte/Sul)",
        "inclinacoes": [0, 45, 90],
        "azimutes": [0, 180],
        "altura": 2.0,
        "albedo": 0.4
    },
    "estudo_geometrico": {
        "descricao": "Sensibilidade de Altura (0.2m, 1.2m, 2.4m)",
        "inclinacoes": [15, 90],
        "azimutes": [0, 90],
        "alturas_teste": [0.2, 1.2, 2.4], 
        "albedo": 0.4
    },
    "varredura_completa": {
        "descricao": "Varredura Total (Multi-Altura e Multi-Albedo)",
        "inclinacoes": [0, 30, 60, 90],
        "azimutes": [0, 45, 90, 135, 180],
        "alturas_teste": [0.5, 1.5],
        "albedos_teste": [0.2, 0.4, 0.7]
    },
    "obstaculo_parede": {
        "descricao": "Impacto de Sombra (Parede 4m, Distância 2m)",
        "inclinacoes": [15],
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
    "validacao_sombra": {
        "descricao": "Teste de Sensibilidade de Obstrução (Sombra)",
        "lat": -5.79, "lon": -35.21, # Natal/RN
        "casos": [
            {"label": "Sem Obstáculo", "h_obs": 0, "d_obs": 2.0, "azi_obs": 0},
            {"label": "Obstáculo Baixo (0.5m)", "h_obs": 0.5, "d_obs": 2.0, "azi_obs": 0},
            {"label": "Obstáculo Médio (3.0m)", "h_obs": 3.0, "d_obs": 2.0, "azi_obs": 0},
            {"label": "Obstáculo Alto (10.0m)", "h_obs": 10.0, "d_obs": 2.0, "azi_obs": 0},
            {"label": "Distância Longa (10m)", "h_obs": 5.0, "d_obs": 10.0, "azi_obs": 0},
            {"label": "Azimute Oposto (Sul)", "h_obs": 5.0, "d_obs": 2.0, "azi_obs": 180},
            {"label": "Muro Leste (Manhã)", "h_obs": 3.0, "d_obs": 1.5, "azi_obs": 90},
            {"label": "Muro Oeste (Tarde)", "h_obs": 3.0, "d_obs": 1.5, "azi_obs": 270},
            {"label": "Objeto Estreito (Poste)", "h_obs": 8.0, "d_obs": 2.0, "azi_obs": 0, "w_obs": 0.2},
            {"label": "Objeto Largo (Edifício)", "h_obs": 10.0, "d_obs": 5.0, "azi_obs": 0, "w_obs": 50.0},
            {"label": "Retrato vs Paisagem (Sensibilidade)", "h_obs": 2.0, "d_obs": 1.0, "azi_obs": 0, "orientacao": "Retrato"},
        ],
        "inclinacoes": [15],
        "azimutes": [0]
    },
}