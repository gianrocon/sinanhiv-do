"""
Parser de texto colado da área de transferência para pré-preenchimento de fichas SINAN.

Formato esperado (uma entrada por linha):
    Campo: Valor
"""

from __future__ import annotations

_LABEL_MAP: dict[str, str] = {
    "nome":       "nome_paciente",
    "sus":        "cartao_sus",
    "prontuário": "nu_prontuario",
    "prontuario": "nu_prontuario",
    "nascimento": "data_nascimento",
    "mãe":        "nome_mae",
    "mae":        "nome_mae",
}


def parse_clipboard(text: str) -> dict[str, str]:
    """Retorna {campo_sinan: valor} para cada campo reconhecido.

    Aceita formato de uma linha separado por ' | ' ou multi-linha (um campo por linha).
    """
    result: dict[str, str] = {}
    for part in text.replace("|", "\n").splitlines():
        if ":" not in part:
            continue
        label, _, value = part.partition(":")
        field = _LABEL_MAP.get(label.strip().lower())
        if field and value.strip():
            result[field] = value.strip()
    return result
