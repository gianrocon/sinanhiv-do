"""Preenchimento do formulário de Baciloscopia do Escarro (PDF paisagem)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import fitz  # PyMuPDF

_PDF       = Path(__file__).parent / "fichas_sinan" / "Baciloscopia" / "baciloscopia.pdf"
_PDF_DUPLO = Path(__file__).parent / "fichas_sinan" / "Baciloscopia" / "baciloscopia_duplo.pdf"
_DUPLO_OFFSET = 420.7  # distância horizontal entre os dois formulários no PDF duplo
_FONT = "helv"
_FS   = 9    # tamanho de fonte para campos de texto
_BOX  = 4.0  # lado do quadrado preenchido (pt) para checkboxes/radio

# Cor de fundo dos campos de data (cinza claro conforme formulário)
_DATE_BG = (0.92, 0.92, 0.92)

# Campos de texto não-data: chave → (x, y)
_TEXT_FIELDS: dict[str, tuple[float, float]] = {
    "unidade_saude":          (23,  127),
    "nome_paciente":          (23,  156),
    "cartao_sus":             (273, 185),   # +20 x
    "nome_mae":               (23,  214),
    "logradouro_complemento": (82,  240),
    "bairro":                 (23,  280),
    "cidade":                 (151, 280),
    "estado":                 (310, 280),
    "telefone":               (23,  309),
    "raca":                   (310, 309),
    "solicitante":            (23,  338),
    "conselho":               (310, 338),
    "vulneravel_qual":        (180, 365),   # -1 y
}

# Campos de data: chave → (x, y)
_DATE_FIELDS: dict[str, tuple[float, float]] = {
    "data_nascimento": (331, 156),   # +3 x
    "data_coleta":     (167, 474),   # +7 x  (+5 anterior +2 novo)
}

# Grupos de radio: chave → {valor → (x, y)}
_RADIO_BOXES: dict[str, dict[str, tuple[float, float]]] = {
    "sexo":               {"M": (232, 304), "F":   (258, 304)},
    "caso":               {"Novo": (26.2, 361.5), "Retratamento": (26.5, 370.5)},
    "vulneravel":         {"Sim": (132, 361.7), "Não": (132, 370)},
    "encaminhar_cultura": {"Sim": (27,  469), "Não": (75.2, 469)},
    "trm_tb":             {"Sim": (258, 469), "Não": (301, 469)},  # SIM bem posicionado — mantido
}

# Posição do checkbox de cada amostra (seleção única): valor → (x, y)
# Linha 1 (y≈402): bac_ctrl_1 bem posicionado — mantidos
# Linha 2 (y≈410): todos corrigidos +1,+1
_AMOSTRA_POS: dict[str, tuple[float, float]] = {
    "bac_diag_1": (24.5, 402),
    "bac_diag_2": (25,  411),
    "bac_ctrl_1": (119, 402),
    "bac_ctrl_2": (119,   411),
    "bac_ctrl_3": (175,   402),
    "bac_ctrl_4": (175,   411),
    "bac_ctrl_5": (231,   402),
    "bac_ctrl_6": (231,   411),
}

# Escarro (tipo de material) — sempre marcado
_ESCARRO_POS = (26.5, 441.5)

_BLACK = (0.0, 0.0, 0.0)


def _draw_box(page, x: float, y: float) -> None:
    page.draw_rect(
        fitz.Rect(x, y, x + _BOX, y + _BOX),
        color=_BLACK, fill=_BLACK, width=0,
    )


def _draw_date_bg(page, x: float, y: float, text: str) -> None:
    """Desenha fundo colorido cobrindo o campo de data."""
    w = fitz.get_text_length(text, fontname=_FONT, fontsize=_FS)
    pad_x, pad_top, pad_bot = 1.0, _FS * 0.85, _FS * 0.15
    rect = fitz.Rect(x - pad_x, y - pad_top, x + w + pad_x, y + pad_bot)
    page.draw_rect(rect, color=_DATE_BG, fill=_DATE_BG, width=0)


def _fill_page(page, form_data: dict, dx: float = 0.0,
               amostra_override: str | None = None,
               field_overrides: dict | None = None) -> None:
    """Escreve todos os campos em `page` com deslocamento horizontal `dx`.
    `amostra_override` substitui o valor do campo amostra se fornecido.
    `field_overrides` sobrepõe valores pontuais de form_data sem mutá-lo.
    """
    data = form_data if not field_overrides else {**form_data, **field_overrides}

    # Data do atendimento: sempre hoje
    today_str = date.today().strftime("%d/%m/%Y")
    _draw_date_bg(page, 331 + dx, 127, today_str)
    page.insert_text(fitz.Point(331 + dx, 127), today_str,
                     fontname=_FONT, fontsize=_FS, color=_BLACK)

    # Campos de texto (sem data) — MAIÚSCULAS
    for field, (x, y) in _TEXT_FIELDS.items():
        val = data.get(field)
        if not val:
            continue
        text = str(val).strip().upper()
        if not text:
            continue
        page.insert_text(fitz.Point(x + dx, y), text,
                         fontname=_FONT, fontsize=_FS, color=_BLACK)

    # Campos de data — fundo colorido
    for field, (x, y) in _DATE_FIELDS.items():
        val = data.get(field)
        if not val:
            continue
        text = val.strftime("%d/%m/%Y") if hasattr(val, "strftime") else str(val).strip().upper()
        if not text:
            continue
        _draw_date_bg(page, x + dx, y, text)
        page.insert_text(fitz.Point(x + dx, y), text,
                         fontname=_FONT, fontsize=_FS, color=_BLACK)

    # Radio buttons
    for field, options in _RADIO_BOXES.items():
        val = data.get(field)
        if val and val in options:
            ox, oy = options[val]
            _draw_box(page, ox + dx, oy)

    # Amostra (seleção única)
    amostra = amostra_override if amostra_override is not None else data.get("amostra")
    if amostra and amostra in _AMOSTRA_POS:
        ax, ay = _AMOSTRA_POS[amostra]
        _draw_box(page, ax + dx, ay)

    # Escarro: sempre marcado
    _draw_box(page, _ESCARRO_POS[0] + dx, _ESCARRO_POS[1])


def fill_baciloscopia(form_data: dict) -> bytes:
    """Preenche o PDF de Baciloscopia e retorna os bytes do arquivo gerado.

    Quando a amostra for Diag. 1ª, usa o PDF duplo e preenche dois formulários:
    esquerdo com Diag. 1ª e direito (offset 420.7 pt) com Diag. 2ª.
    """
    amostra = form_data.get("amostra")

    # TRM-TB: Não apenas para amostras de controle, Sim em todos os outros casos
    is_controle = amostra in ("bac_ctrl_1", "bac_ctrl_2", "bac_ctrl_3",
                              "bac_ctrl_4", "bac_ctrl_5", "bac_ctrl_6")
    effective = {**form_data, "trm_tb": "Não" if is_controle else "Sim"}

    if amostra == "bac_diag_1":
        doc  = fitz.open(str(_PDF_DUPLO))
        page = doc[0]
        _fill_page(page, effective, dx=0.0, amostra_override="bac_diag_1")
        # 2ª amostra gerada automaticamente: cultura sempre Não, sem data de coleta
        _fill_page(page, effective, dx=_DUPLO_OFFSET, amostra_override="bac_diag_2",
                   field_overrides={"encaminhar_cultura": "Não", "data_coleta": None})
    else:
        doc  = fitz.open(str(_PDF))
        page = doc[0]
        _fill_page(page, effective, dx=0.0)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
