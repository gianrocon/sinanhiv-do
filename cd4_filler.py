"""
Preenchedor do Formulário de Solicitação de CD4 (Contagem de Linfócitos T-CD4+).

Baseado em cd4_filler.py — mesmos campos 1-28 da Carga Viral com micro-ajustes
de posicionamento derivados da comparação das posições dos rótulos entre os dois PDFs.
Campo 29 omitido (lógica a definir).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import fitz  # PyMuPDF

_CD4_PDF = Path(__file__).parent / "forms_externos" / "cd4" / "cd4 impressao.pdf"
_FONT  = "helv"
_BLACK = (0.0, 0.0, 0.0)
_WHITE = (1.0, 1.0, 1.0)
_FS    = 1.2

# (chave_em_form_data, x, y, font_size_base)
# Coordenadas derivadas da Carga Viral com delta y por seção:
#   campos 1-4  → +2 a +3 pts
#   campo  6    → +1.7 pts
#   campos 8-9  → -0.9 pts
#   campos 15-17→ -1.8 pts
#   campo  23   → -8.2 pts
#   campo  24   → -10.9 pts
#   campos 25-28→ -13.4 pts
_FIELDS = [
    # 1 — Instituição solicitante
    ("unidade_saude",        22.9,  69.0, 8.0),
    # 2 — CNES
    ("codigo_unidade_saude", 480.9, 69.8, 8.0),
    # 3 — CPF do paciente
    ("cpf",                   22.1, 112.9, 8.0),
    # 4 — CNS do paciente
    ("cartao_sus",           309.1, 112.9, 8.0),
    # 6 — Nome civil
    ("nome_paciente",         26.2, 141.5, 9.0),
    # 8 — Data de nascimento  (fundo branco)
    ("data_nascimento",       20.9, 199.1, 9.0),
    # 9 — Sexo  (M / F / I)
    ("sexo",                 116.7, 197.0, 9.0),
    # 15 — Raça/Cor
    ("raca_cor",              20.4, 252.2, 9.0),
    # 16 — Escolaridade  (código CV 1-7, convertido de SINAN)
    ("_escolaridade",        210.0, 251.9, 9.0),
    # 17 — Gestante  → S ou N
    ("_gestante",            382.2, 251.9, 9.0),
    # 23 — Nome da mãe
    ("nome_mae",             172.3, 310.5, 9.0),
    # 24 — Endereço  (logradouro + nº + complemento, maiúsculas)
    ("_endereco",             35.3, 336.3, 9.0),
    # 25 — Bairro  (maiúsculas)
    ("bairro",                31.3, 370.3, 9.0),
    # 26 — CEP
    ("cep",                  214.2, 368.7, 8.0),
    # 27 — Município de residência
    ("municipio_residencia", 294.8, 370.3, 9.0),
    # 28 — UF de residência
    ("uf_residencia",        563.2, 368.4, 9.0),
]

# Checkbox "Avaliação inicial" (item 29) — retângulo preenchido
_CHECKBOX_AVALIACAO = fitz.Rect(25.51, 413.85, 31.18, 420.09)

_UPPERCASE_FIELDS = {"_endereco", "bairro"}
_WHITE_BG_FIELDS  = {"data_nascimento"}

_GESTANTE_S = {"1", "2", "3", "4"}
_GESTANTE_N = {"5", "6", "9"}

_ESCOLARIDADE_MAP = {
    "0":  "1",
    "1":  "2",
    "2":  "3",
    "3":  "3",
    "4":  "4",
    "5":  "4",
    "6":  "4",
    "7":  "5",
    "8":  "5",
    "9":  "7",
    "10": "6",
}


def _fmt(value) -> str:
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return str(value).strip()


def _draw_white_bg(page, x: float, y: float, text: str, fontname: str, fontsize: float) -> None:
    text_w = fitz.get_text_length(text, fontname=fontname, fontsize=fontsize)
    pad_x, pad_top, pad_bot = 1.0, fontsize * 0.85, fontsize * 0.15
    rect = fitz.Rect(x - pad_x, y - pad_top, x + text_w + pad_x, y + pad_bot)
    page.draw_rect(rect, color=_WHITE, fill=_WHITE, width=0)


def _build_data(form_data: dict) -> dict:
    partes = [_fmt(form_data.get("logradouro", "")),
              _fmt(form_data.get("numero_residencia", ""))]
    comp = _fmt(form_data.get("complemento", ""))
    if comp:
        partes.append(comp)
    endereco = ", ".join(p for p in partes if p).upper()

    gest_raw = str(form_data.get("gestante", "")).strip()
    if gest_raw in _GESTANTE_S:
        gestante = "S"
    elif gest_raw in _GESTANTE_N:
        gestante = "N"
    else:
        gestante = ""

    escol_raw = str(form_data.get("escolaridade", "")).strip()
    escolaridade = _ESCOLARIDADE_MAP.get(escol_raw, "")

    return {
        **form_data,
        "_endereco":     endereco,
        "_gestante":     gestante,
        "_escolaridade": escolaridade,
    }


def fill_cd4(form_data: dict) -> bytes:
    """
    Preenche o formulário de CD4 com os dados do paciente.

    Args:
        form_data: dict com campos da ficha AIDS.

    Returns:
        Bytes do PDF preenchido.
    """
    if not _CD4_PDF.exists():
        raise FileNotFoundError(f"PDF CD4 não encontrado: {_CD4_PDF}")

    data = _build_data(form_data)
    doc  = fitz.open(str(_CD4_PDF))
    page = doc[0]

    # Marca checkbox "Avaliação inicial" (item 29)
    page.draw_rect(_CHECKBOX_AVALIACAO, color=_BLACK, fill=_BLACK, width=0)

    for field, x, y, fs in _FIELDS:
        raw = data.get(field)
        if raw is None or raw == "" or raw is False:
            continue
        text = _fmt(raw)
        if not text:
            continue
        if field in _UPPERCASE_FIELDS:
            text = text.upper()
        fontsize = round(fs * _FS, 1)
        if field in _WHITE_BG_FIELDS:
            _draw_white_bg(page, x, y, text, _FONT, fontsize)
        page.insert_text(
            fitz.Point(x, y), text,
            fontname=_FONT, fontsize=fontsize, color=_BLACK,
        )

    doc.select([0])
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
