"""
Renderer genérico para qualquer ficha SINAN.

Lê field_coords.json e config.toml da pasta da ficha e gera widgets
automaticamente com base nos prefixos dos nomes dos campos (convenção SINAN):

  dt_*          → campo de data (dd/mm/aaaa)
  nm_*, no_*    → texto livre (nome)
  sg_uf_*, *_uf → texto curto (sigla UF, 2 chars)
  nu_*          → texto (número/código)
  co_*, id_*    → texto (código/ID)
  st_*          → Sim / Não / Ignorado (radio)
  cs_*, tp_*    → opções definidas em [fields.<campo>] ou texto livre

Campos em [fixed] e [hidden] são omitidos do formulário.
Valores padrão vêm de [defaults].
Campos em [form] sni_fields recebem radio Sim/Não/Ignorado automaticamente,
independente do prefixo.

Opções em [fields.<campo>]:
  options       → lista de rótulos exibidos
  values        → lista de valores retornados (1:1 com options); se ausente, retorna o rótulo
  widget        → "selectbox" (padrão) ou "radio"
  default_index → índice selecionado por padrão (padrão: 0)
  horizontal    → true (padrão) ou false; só para widget="radio"
  allow_none    → true para radio sem seleção padrão (retorna "" se nada selecionado)
"""

from __future__ import annotations

import json
import tomllib
from datetime import date, datetime
from pathlib import Path

import streamlit as st

_GEN: int = 0

_SNI_OPTIONS = ["Sim (1)", "Não (2)", "Ignorado (9)"]
_SNI_VALUES  = ["1", "2", "9"]


def _k(key: str) -> str:
    return f"{key}_{_GEN}"


def _load_cfg(form_folder: Path) -> dict:
    cfg_path = form_folder / "config.toml"
    if not cfg_path.exists():
        return {}
    with open(cfg_path, "rb") as f:
        return tomllib.load(f)


def _load_coords_raw(form_folder: Path) -> dict:
    with open(form_folder / "field_coords.json", encoding="utf-8") as f:
        return json.load(f)


def apply_suppress(form_folder: Path, all_data: dict) -> dict:
    """Zera campos cujo valor coincide com [suppress_if] do config.toml.

    Exemplo:
        [suppress_if]
        classificacao_final = "2"   # não escreve "2" no PDF
    """
    cfg = _load_cfg(form_folder)
    result = dict(all_data)
    for field, suppress_val in cfg.get("suppress_if", {}).items():
        if str(result.get(field, "")) == str(suppress_val):
            result[field] = ""
    return result


def resolve_computed(form_folder: Path, all_data: dict) -> dict:
    """Resolve campos [computed] do config.toml usando os dados já montados.

    Exemplo no config.toml:
        [computed]
        investigador_municipio_unidade = "{municipio_notificacao} / {unidade_saude}"
    """
    cfg = _load_cfg(form_folder)
    result = {}
    for field, template in cfg.get("computed", {}).items():
        try:
            result[field] = template.format_map(all_data)
        except KeyError:
            pass
    return result


def get_fixed_fields(form_folder: Path) -> dict:
    """Retorna campos ocultos: [fixed] com valores fixos + [hidden] como vazios."""
    cfg = _load_cfg(form_folder)
    fixed: dict = dict(cfg.get("fixed", {}))

    # Resolve sentinel "today" → data atual
    for k, v in list(fixed.items()):
        if v == "today":
            fixed[k] = date.today()

    if "data_notificacao" in _load_coords_raw(form_folder):
        fixed.setdefault("data_notificacao", date.today())

    for field in cfg.get("hidden", {}).get("campos", []):
        fixed.setdefault(field, "")

    return fixed


# ---------------------------------------------------------------------------
# Widgets auxiliares
# ---------------------------------------------------------------------------

def _date_input(label: str, key: str, default: str = "") -> date | None:
    raw = st.text_input(label, value=default, placeholder="dd/mm/aaaa", key=_k(key), autocomplete="off")
    if not raw:
        return None
    for fmt in ("%d/%m/%Y", "%d%m%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    st.error("Data inválida: use dd/mm/aaaa ou ddmmaaaa")
    return None


def _radio_sni(label: str, key: str, default_index: int = 1) -> str:
    """Radio padrão Sim/Não/Ignorado."""
    choice = st.radio(label, _SNI_OPTIONS, index=default_index,
                      horizontal=True, key=_k(key))
    return _SNI_VALUES[_SNI_OPTIONS.index(choice)]


def _resolve_value(choice, opts: list, values: list | None) -> str:
    """Retorna o código correspondente à opção selecionada."""
    if choice is None:
        return ""
    if values is None:
        return choice
    try:
        return values[opts.index(choice)]
    except (ValueError, IndexError):
        return choice


def _widget_for(field: str, label: str, default: str,
                cfg_field: dict, sni_set: set) -> str | date | None:
    """Escolhe o widget adequado para o campo."""
    prefix = field.split("_")[0]

    # Campos listados explicitamente em [form] sni_fields → Sim/Não/Ignorado
    if field in sni_set:
        sni_default = int(cfg_field.get("default_index", 1))
        if default in _SNI_VALUES:
            sni_default = _SNI_VALUES.index(default)
        return _radio_sni(label, field, default_index=sni_default)

    # Opções customizadas em [fields.<campo>]
    if "options" in cfg_field:
        opts          = cfg_field["options"]
        values        = cfg_field.get("values")
        widget        = cfg_field.get("widget", "selectbox")
        default_index = int(cfg_field.get("default_index", 0))
        horizontal    = bool(cfg_field.get("horizontal", True))
        allow_none    = bool(cfg_field.get("allow_none", False))

        # Resolve índice a partir do valor de prefill
        if default:
            lookup = values if values else opts
            if default in lookup:
                default_index = lookup.index(default)

        if widget == "radio":
            if default and default in (values if values else opts):
                idx = (values if values else opts).index(default)
            else:
                idx = None if allow_none else default_index
            choice = st.radio(label, opts, index=idx,
                              horizontal=horizontal, key=_k(field))
            return _resolve_value(choice, opts, values)
        else:
            choice = st.selectbox(label, opts, index=default_index,
                                  key=_k(field))
            return _resolve_value(choice, opts, values)

    # Checkbox
    if cfg_field.get("widget") == "checkbox":
        checked = str(default).lower() in ("true", "1")
        return st.checkbox(label, value=checked, key=_k(field))

    # Data
    if prefix in ("dt", "data") or field.endswith("_data"):
        return _date_input(label, field, default=default)

    # Booleano SINAN por prefixo (st_*)
    if prefix == "st":
        return _radio_sni(label, field)

    # UF (2 chars)
    if "uf" in field and prefix in ("sg", "co", "id", ""):
        return st.text_input(label, value=default, max_chars=2, key=_k(field), autocomplete="off")

    # Texto livre para o restante
    max_chars = cfg_field.get("max_chars") or None
    return st.text_input(label, value=default, max_chars=max_chars, key=_k(field), autocomplete="off")


# ---------------------------------------------------------------------------
# Layout em colunas
# ---------------------------------------------------------------------------

_MAX_SPAN = 4
_NARROW_KEYWORDS = ("cep", "ddd", "ibge", "complemento", "codigo", "cartao", "cnpj", "cpf",
                    "municipio", "logradouro", "numero")


def _col_span(field: str, cfg_field: dict, sni_set: set) -> int:
    """Largura relativa do campo para layout em colunas (1 = estreito … 4 = toda a largura)."""
    if "col_span" in cfg_field:
        return int(cfg_field["col_span"])

    fn     = field.lower()
    prefix = fn.split("_")[0]

    # Datas
    if prefix in ("dt", "data") or fn.endswith("_data"):
        return 1

    # UF (2 chars)
    if prefix == "uf" or (prefix in ("sg", "co", "id") and "uf" in fn):
        return 1

    # Códigos e números padrão
    if prefix in ("nu", "co", "id", "sg"):
        return 1

    # Palavras-chave de campos curtos (sem prefixo padrão)
    if any(kw in fn for kw in _NARROW_KEYWORDS):
        return 1

    # Checkbox individual
    if cfg_field.get("widget") == "checkbox":
        return 1

    # SNI radio (Sim/Não/Ignorado)
    if field in sni_set:
        return 2

    # Opções customizadas
    if "options" in cfg_field:
        opts       = cfg_field["options"]
        horizontal = bool(cfg_field.get("horizontal", True))
        widget     = cfg_field.get("widget", "selectbox")
        if widget == "radio":
            if (not horizontal
                    or len(opts) > 5
                    or sum(len(o) for o in opts) > 80):
                return 4
            return 1 if len(opts) <= 3 else 2
        return 1  # selectbox → dropdown compacto

    # st_ sem opções customizadas → renderiza como SNI
    if prefix == "st":
        return 2

    return 2


# ---------------------------------------------------------------------------
# Renderer principal
# ---------------------------------------------------------------------------

def render_generic(gen: int = 0, form_folder: Path | None = None,
                   prefill: dict | None = None) -> dict:
    """
    Renderiza o formulário a partir do field_coords.json e config.toml da ficha.
    Retorna {campo: valor} com os dados preenchidos pelo usuário.

    prefill: valores importados (ex: área de transferência) que sobrepõem os
             defaults do config.toml; aplicados apenas na criação dos widgets
             (chave nova), portanto não sobrescrevem edições posteriores.
    """
    global _GEN
    _GEN = gen

    if form_folder is None:
        raise ValueError("form_folder é obrigatório para o renderer genérico")

    cfg        = _load_cfg(form_folder)
    coords_raw = _load_coords_raw(form_folder)

    _prefill   = prefill or {}
    defaults   = {**cfg.get("defaults", {}), **_prefill}  # prefill sobrepõe defaults
    fixed_keys    = set(cfg.get("fixed", {}).keys())
    hidden_keys   = set(cfg.get("hidden", {}).get("campos", []))
    fields_cfg    = cfg.get("fields", {})
    sni_fields    = set(cfg.get("form", {}).get("sni_fields", []))
    divider_after = set(cfg.get("dividers", {}).get("apos", []))
    skip_keys     = fixed_keys | hidden_keys
    if "data_notificacao" in coords_raw:
        skip_keys.add("data_notificacao")

    by_page: dict[int, list[tuple[float, str, dict]]] = {}
    for field, meta in coords_raw.items():
        if field in skip_keys:
            continue
        p = meta["page"]
        sort_key = meta.get("display_order", meta["y"])
        by_page.setdefault(p, []).append((sort_key, field, meta))

    data: dict = {}

    for page_num in sorted(by_page.keys()):
        st.subheader(f"Página {page_num}")
        fields_on_page = sorted(by_page[page_num], key=lambda t: t[0])

        # Agrupar campos em linhas de até _MAX_SPAN colunas
        rows: list[list] = []
        cur_row: list    = []
        cur_total        = 0
        for item in fields_on_page:
            _, field, _ = item
            span = _col_span(field, fields_cfg.get(field, {}), sni_fields)
            if cur_total + span > _MAX_SPAN and cur_row:
                rows.append(cur_row)
                cur_row   = [(item, span)]
                cur_total = span
            else:
                cur_row.append((item, span))
                cur_total += span
        if cur_row:
            rows.append(cur_row)

        # Renderizar linhas
        for row_items in rows:
            spans = [s for _, s in row_items]

            if len(row_items) == 1:
                item, _ = row_items[0]
                _, field, meta = item
                label   = meta.get("label", field)
                default = str(defaults.get(field, ""))
                if default == "today":
                    default = date.today().strftime("%d/%m/%Y")
                data[field] = _widget_for(field, label, default,
                                          fields_cfg.get(field, {}), sni_fields)
            else:
                cols = st.columns(spans)
                for col, (item, _) in zip(cols, row_items):
                    _, field, meta = item
                    label   = meta.get("label", field)
                    default = str(defaults.get(field, ""))
                    if default == "today":
                        default = date.today().strftime("%d/%m/%Y")
                    with col:
                        data[field] = _widget_for(field, label, default,
                                                   fields_cfg.get(field, {}), sni_fields)

            # Divisor após a linha se algum campo da linha estiver em divider_after
            row_fields = {f for (_, f, _), _ in row_items}
            if divider_after & row_fields:
                st.divider()

    return data
