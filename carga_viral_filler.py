"""
Preenchedor do Formulário de Solicitação de Carga Viral HIV.

Recebe dados do paciente (vindos da ficha SINAN AIDS) e retorna bytes do PDF preenchido.
Usa PyMuPDF para sobrepor texto no PDF original sem modificá-lo.

Coordenadas em espaço fitz (origem topo-esquerdo, y cresce para baixo).
Derivadas de carga_viral_fields.json (ReportLab, A4 h=841.89):
    fitz_x = x1 + 2
    fitz_y = 841.89 - (y1 + y2) / 2 + font_size * 0.3

Campos 29, 30, 32, 34, 35 omitidos (sem dados para preencher).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import fitz  # PyMuPDF

_CV_PDF = Path(__file__).parent / "forms_externos" / "carga viral" / "carga viral impressao.pdf"
_FONT   = "helv"
_BLACK  = (0.0, 0.0, 0.0)
_WHITE  = (1.0, 1.0, 1.0)
_FS     = 1.2   # fator de escala de fonte

# Radio buttons padrão — (cx, cy, raio) em coordenadas fitz
_RADIOS = [
    (28.3, 443.6, 3.0),   # 28.2 Diagnóstico — centro exato extraído das anotações do PDF
]

# (chave_em_form_data, x, y, font_size_base)
# Fonte final = font_size_base * _FS
_FIELDS = [
    # 1 — Instituição solicitante  (+2 y)
    ("unidade_saude",        22.9,  67.0, 8.0),
    # 2 — CNES  (+2 y)
    ("codigo_unidade_saude", 480.9, 67.0, 8.0),
    # 3 — CPF do paciente
    ("cpf",                   22.1, 110.4, 8.0),
    # 4 — CNS do paciente
    ("cartao_sus",           309.1, 110.4, 8.0),
    # 6 — Nome civil  (+2 y)
    ("nome_paciente",         26.2, 139.8, 9.0),
    # 8 — Data de nascimento  (date → dd/mm/aaaa; fundo branco)  (+2 y)
    ("data_nascimento",       20.9, 200.0, 9.0),
    # 9 — Sexo  (M / F / I)
    ("sexo",                 116.7, 197.9, 9.0),
    # 15 — Raça/Cor  (código 1-5, 9)
    ("raca_cor",              20.4, 253.9, 9.0),
    # 16 — Escolaridade  (código CV 1-7, convertido de SINAN)
    ("_escolaridade",        210.0, 253.9, 9.0),
    # 17 — Gestante  → S (1-4) ou N (5, 6, 9)
    ("_gestante",            382.2, 253.9, 9.0),
    # 23 — Nome da mãe  (+2 y)
    ("nome_mae",             172.3, 318.7, 9.0),
    # 24 — Endereço  (logradouro + nº + complemento, maiúsculas)
    ("_endereco",             35.3, 347.2, 9.0),
    # 25 — Bairro  (maiúsculas)  (+2 y)
    ("bairro",                31.3, 383.8, 9.0),
    # 26 — CEP
    ("cep",                  214.2, 382.0, 8.0),
    # 27 — Município de residência  (+2 y)
    ("municipio_residencia", 294.8, 383.8, 9.0),
    # 28 — UF de residência
    ("uf_residencia",        563.2, 382.3, 9.0),
]

_UPPERCASE_FIELDS  = {"_endereco", "bairro"}
_WHITE_BG_FIELDS   = {"data_nascimento"}

_GESTANTE_S = {"1", "2", "3", "4"}
_GESTANTE_N = {"5", "6", "9"}

# Conversão escolaridade SINAN → Carga Viral
# SINAN: 0=Analfabeto 1=1ª-4ª incompleto 2=4ª completo 3=5ª-8ª incompleto
#        4=EF completo 5=EM incompleto 6=EM completo 7=Sup incompleto
#        8=Sup completo 9=Ignorado 10=Não se aplica
# CV:    1=Nenhuma 2=De 1 a 3 3=De 4 a 7 4=De 8 a 11 5=De 12 e mais
#        6=Não informado 7=Ignorado
_ESCOLARIDADE_MAP = {
    "0":  "1",  # Analfabeto          → Nenhuma
    "1":  "2",  # 1ª-4ª incompleto    → De 1 a 3
    "2":  "3",  # 4ª completa         → De 4 a 7
    "3":  "3",  # 5ª-8ª incompleto    → De 4 a 7
    "4":  "4",  # EF completo         → De 8 a 11
    "5":  "4",  # EM incompleto       → De 8 a 11
    "6":  "4",  # EM completo         → De 8 a 11
    "7":  "5",  # Superior incompleto → De 12 e mais
    "8":  "5",  # Superior completo   → De 12 e mais
    "9":  "7",  # Ignorado            → Ignorado
    "10": "6",  # Não se aplica       → Não informado
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
    """Deriva campos calculados a partir de form_data."""
    # Endereço: logradouro + número + complemento (quando houver), maiúsculas
    partes = [_fmt(form_data.get("logradouro", "")),
              _fmt(form_data.get("numero_residencia", ""))]
    comp = _fmt(form_data.get("complemento", ""))
    if comp:
        partes.append(comp)
    endereco = ", ".join(p for p in partes if p).upper()

    # Gestante: S se grávida (1-4), N caso contrário (5, 6, 9)
    gest_raw = str(form_data.get("gestante", "")).strip()
    if gest_raw in _GESTANTE_S:
        gestante = "S"
    elif gest_raw in _GESTANTE_N:
        gestante = "N"
    else:
        gestante = ""

    # Escolaridade: converter código SINAN → código Carga Viral
    escol_raw = str(form_data.get("escolaridade", "")).strip()
    escolaridade = _ESCOLARIDADE_MAP.get(escol_raw, "")

    return {
        **form_data,
        "_endereco":    endereco,
        "_gestante":    gestante,
        "_escolaridade": escolaridade,
    }


def fill_carga_viral(form_data: dict) -> bytes:
    """
    Preenche o formulário de Carga Viral com os dados do paciente.

    Args:
        form_data: dict com campos da ficha AIDS (ex: {'nome_paciente': 'FULANO'}).

    Returns:
        Bytes do PDF preenchido.
    """
    if not _CV_PDF.exists():
        raise FileNotFoundError(f"PDF Carga Viral não encontrado: {_CV_PDF}")

    data = _build_data(form_data)
    doc  = fitz.open(str(_CV_PDF))
    page = doc[0]

    for cx, cy, r in _RADIOS:
        page.draw_circle(fitz.Point(cx, cy), r, color=_BLACK, fill=_BLACK, width=0)

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

    doc.select([0])   # página 1 apenas
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
