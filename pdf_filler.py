"""
Motor de preenchimento de PDF SINAN via sobreposição de texto (PyMuPDF).

Totalmente genérico: lê field_coords.json e config.toml da pasta da ficha.
O PDF original nunca é modificado — retorna bytes do novo PDF.
"""

from __future__ import annotations

import json
import tomllib
from datetime import date
from pathlib import Path

import fitz  # PyMuPDF

_FICHAS_DIR = Path(__file__).parent / "fichas_sinan"

_WHITE_BG_PREFIXES = ("dt_", "data_", "nu_", "co_", "id_")
_WHITE_BG_KEYWORDS = ("codigo", "ibge", "cep", "telefone", "cartao")

_UPPERCASE_FIELDS = {
    "nome_paciente", "nome_mae",
    "uf_residencia", "municipio_residencia",
    "bairro", "logradouro", "ocupacao",
}


def _load_coords(form_folder: Path) -> dict[str, tuple[int, float, float]]:
    with open(form_folder / "field_coords.json", encoding="utf-8") as f:
        raw = json.load(f)
    return {k: (v["page"], v["x"], v["y"]) for k, v in raw.items() if not v.get("skip_pdf")}


def _load_app_cfg(form_folder: Path) -> dict:
    cfg_path = form_folder / "config.toml"
    if not cfg_path.exists():
        return {}
    with open(cfg_path, "rb") as f:
        return tomllib.load(f).get("app", {})


def _find_pdf(form_folder: Path) -> Path:
    cfg_path = form_folder / "config.toml"
    if cfg_path.exists():
        with open(cfg_path, "rb") as f:
            pdf_name = tomllib.load(f).get("form", {}).get("pdf")
        if pdf_name:
            return form_folder / pdf_name
    # fallback: primeiro PDF que não seja output
    candidates = [
        p for p in form_folder.glob("*.pdf")
        if "output" not in p.stem.lower()
    ]
    if not candidates:
        raise FileNotFoundError(f"Nenhum PDF encontrado em {form_folder}")
    return sorted(candidates)[0]


def _normalize_date(value: str) -> str:
    """Normaliza string de data para dd/mm/aaaa (aceita dd/mm/aaaa ou ddmmaaaa)."""
    v = value.strip()
    if len(v) == 10 and v[2] == "/" and v[5] == "/":
        return v
    if len(v) == 8 and v.isdigit():
        return f"{v[0:2]}/{v[2:4]}/{v[4:8]}"
    return v


def _is_date_field(field_name: str) -> bool:
    fn = field_name.lower()
    return fn.startswith(("dt_", "data_")) or fn.endswith("_data")


def _needs_white_bg(field_name: str, raw_value) -> bool:
    if isinstance(raw_value, date):
        return True
    fn = field_name.lower()
    return (
        _is_date_field(fn)
        or any(fn.startswith(p) for p in _WHITE_BG_PREFIXES)
        or any(kw in fn for kw in _WHITE_BG_KEYWORDS)
    )


def _draw_white_bg(page, x: float, y: float, text: str,
                   fontname: str, fontsize: float) -> None:
    text_w = fitz.get_text_length(text, fontname=fontname, fontsize=fontsize)
    pad_x, pad_top, pad_bot = 1.0, fontsize * 0.85, fontsize * 0.15
    rect = fitz.Rect(x - pad_x, y - pad_top, x + text_w + pad_x, y + pad_bot)
    page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1), width=0)


def fill_pdf(form_data: dict, form_folder: Path) -> bytes:
    """
    Preenche o PDF da ficha com os dados e retorna bytes do arquivo gerado.

    Args:
        form_data: {nome_campo: valor} — None, False e string vazia são ignorados.
        form_folder: pasta da ficha em fichas_sinan/ (ex: fichas_sinan/Aids_adulto_v5).
    """
    cfg = _load_app_cfg(form_folder)
    font_name        = cfg.get("font_name", "helv")
    font_size        = float(cfg.get("font_size", 13))
    font_size_date   = float(cfg.get("font_size_date", 13))
    font_size_number = float(cfg.get("font_size_number", 13))
    black = (0.0, 0.0, 0.0)

    coords  = _load_coords(form_folder)
    pdf_path = _find_pdf(form_folder)
    doc = fitz.open(str(pdf_path))

    for field_name, raw_value in form_data.items():
        if raw_value is None or raw_value == "" or raw_value is False:
            continue
        if isinstance(raw_value, bool) and not raw_value:
            continue

        coord = coords.get(field_name)
        if coord is None:
            continue

        page_num, x, y = coord
        page = doc[page_num - 1]

        if isinstance(raw_value, date):
            value = raw_value.strftime("%d/%m/%Y")
            fs = font_size_date
        elif _is_date_field(field_name):
            value = _normalize_date(str(raw_value))
            fs = font_size_date
        else:
            value = str(raw_value).strip()
            if field_name in _UPPERCASE_FIELDS:
                value = value.upper()
            fs = font_size_number if _needs_white_bg(field_name, raw_value) else font_size

        if not value:
            continue

        if _needs_white_bg(field_name, raw_value):
            _draw_white_bg(page, x, y, value, font_name, fs)

        page.insert_text(
            fitz.Point(x, y),
            value,
            fontname=font_name,
            fontsize=fs,
            color=black,
        )

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# ── Teste standalone ────────────────────────────────────────────────────────
if __name__ == "__main__":
    from paciente_teste import DADOS_TESTE

    folder = _FICHAS_DIR / "Aids_adulto_v5"
    out = fill_pdf(DADOS_TESTE, folder)
    out_path = folder / "teste_output.pdf"
    out_path.write_bytes(out)
    print(f"Gerado: {out_path}")
