"""
Preenchedor do Formulário de Solicitação de Medicamentos SICLOM (Adulto/Adolescente/Gestante).

Recebe dados do paciente (vindos da ficha SINAN AIDS) e retorna bytes do PDF preenchido.
Usa PyMuPDF para sobrepor marcações e texto no PDF original sem modificá-lo.
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

_SICLOM_PDF = Path(__file__).parent / "forms_externos" / "siclom" / "SICLOM_adulto.pdf"

# ── Radio buttons ────────────────────────────────────────────────────────────
# Cada entrada: centro (cx, cy) e raio do ponto preenchido
# Valores calibrados via extração de drawings do PDF (page 1)

_RADIOS_PAGINA_1 = [
    # Item 1 — Categoria: HIV/AIDS - Adulto
    (134.9, 41.4, 2.5),
    # Item 2 — Serviço: CTA
    (302.7, 58.8, 2.5),
    # Item 3 — Origem: Público
    (227.2, 75.2, 2.5),
    # Item 9 — Início de tratamento: Sim
    (54.3, 188.4, 3.0),
    # Item 19 — Esquema preferencial: Tenofovir/Lamivudina "2 em 1" + Dolutegravir
    (248.0, 388.3, 3.5),
]

# ── Campos de texto ──────────────────────────────────────────────────────────
# (chave_no_form_data, x, y, font_size)

_TEXT_FIELDS_P1 = [
    ("nome_paciente", 22.0, 104.0, 10.4),
]

_BLACK = (0.0, 0.0, 0.0)


def fill_siclom(form_data: dict) -> bytes:
    """
    Preenche o formulário SICLOM com os dados fornecidos.

    Args:
        form_data: dict com campos do paciente (ex: {'nome_paciente': 'FULANO DE TAL'})

    Returns:
        Bytes do PDF preenchido.

    Raises:
        FileNotFoundError: se o PDF base não for encontrado.
    """
    if not _SICLOM_PDF.exists():
        raise FileNotFoundError(f"PDF SICLOM não encontrado: {_SICLOM_PDF}")

    doc = fitz.open(str(_SICLOM_PDF))
    page = doc[0]

    # Marcar radio buttons com ponto preenchido
    for cx, cy, r in _RADIOS_PAGINA_1:
        page.draw_circle(fitz.Point(cx, cy), r, color=_BLACK, fill=_BLACK, width=0)

    # Inserir campos de texto
    for field, x, y, fs in _TEXT_FIELDS_P1:
        raw = form_data.get(field, "")
        if not raw:
            continue
        value = str(raw).upper().strip()
        page.insert_text(fitz.Point(x, y), value, fontname="helv", fontsize=fs, color=_BLACK)

    doc.select([0])   # página 1 apenas
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
