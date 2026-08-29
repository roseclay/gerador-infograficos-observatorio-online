from __future__ import annotations


def recommended_max_per_page(metric_count: int) -> int:
    if metric_count <= 0:
        return 9
    if metric_count <= 9:
        return 9
    return 9


def layout_reason(metric_count: int, section_count: int) -> str:
    if metric_count <= 2:
        return "poucos indicadores; cards grandes no layout existente"
    if metric_count <= 4:
        return "até quatro indicadores; grade compacta"
    if metric_count <= 6:
        return "cinco ou seis indicadores; seções intermediárias"
    if metric_count <= 9:
        return "sete a nove indicadores; estrutura completa em uma página"
    return f"{metric_count} indicadores; recomendação de múltiplas páginas"
