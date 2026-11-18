"""Seleção explícita de análise 3D no dashboard; a API nunca usa este toggle."""


def optional_shading_scene(enabled, scene_builder, *args, **kwargs):
    """Não monta nem calcula a cena 3D quando o usuário deixa opção desligada."""
    if not enabled:
        return None
    return scene_builder(*args, **kwargs)
