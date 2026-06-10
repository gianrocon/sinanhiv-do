"""
SINAN — Sistema de Informação de Agravos de Notificação
Aplicação Streamlit para preenchimento e geração de fichas em PDF.

Para rodar:
    streamlit run app.py
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import streamlit as st

from form_renderer import render_generic, get_fixed_fields, resolve_computed, apply_suppress
from pdf_filler import fill_pdf
from clipboard_import import parse_clipboard
from siclom_filler import fill_siclom
from carga_viral_filler import fill_carga_viral
from cd4_filler import fill_cd4
from baciloscopia_filler import fill_baciloscopia

_FICHAS_DIR = Path(__file__).parent / "fichas_sinan"

# Campos demográficos transferidos entre fichas na navegação cruzada
_COMMON_FIELDS = [
    "unidade_saude", "codigo_unidade_saude",
    "nome_paciente", "data_nascimento",
    "gestante", "sexo", "raca_cor", "escolaridade",
    "cartao_sus", "nome_mae",
    "municipio_residencia", "uf_residencia",
    "bairro", "logradouro", "complemento", "numero_residencia", "cep",
    "ddd_telefone",
    "ocupacao",
]

# Mapeamento de fichas irmãs: nome_pasta → [(label_botão, nome_pasta_destino)]
_SIBLING_LINKS: dict[str, list[tuple[str, str]]] = {
    "Aids_adulto_v5":     [("SINAN Tuberculose", "Tuberculose_v5"),
                           ("SINAN Sífilis", "Sifilis_adquirida")],
    "Tuberculose_v5":     [("SINAN HIV", "Aids_adulto_v5"), ("Baciloscopia", "Baciloscopia"),
                           ("SINAN Sífilis", "Sifilis_adquirida")],
    "Sifilis_adquirida":  [("SINAN HIV", "Aids_adulto_v5")],
}

_RACA_COR_LABEL: dict[str, str] = {
    "1": "Branca", "2": "Preta", "3": "Amarela",
    "4": "Parda",  "5": "Indígena", "9": "Ignorado",
}

# ── Configuração da página ───────────────────────────────────────────────────

st.set_page_config(
    page_title="SINAN",
    page_icon=":hospital:",
    layout="wide",
)

st.markdown("""
<style>
.block-container { padding-top: 0.8rem; padding-bottom: 0.5rem; }
div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] { gap: 0rem; }
h3 { margin-top: 0.6rem !important; margin-bottom: 0.1rem !important; font-size: 1rem !important; }
hr { margin: 0.8rem 0 !important; border: none !important; border-top: 2px solid #555 !important; opacity: 1 !important; }
div[data-testid="stRadio"] > label { font-size: 0.85rem; }
div[data-testid="stRadio"] { margin-bottom: 0rem; }
div[data-testid="stTextInput"] { margin-bottom: 0rem; }
div[data-testid="stSelectbox"] { margin-bottom: 0rem; }
/* Bordas visíveis — modo claro */
div[data-testid="stTextInput"] input,
div[data-testid="stSelectbox"] > div > div {
    border: 2px solid #555 !important;
    border-radius: 4px !important;
}
div[data-testid="stTextInput"] input:focus {
    border-color: #2a9d8f !important;
    box-shadow: 0 0 0 2px rgba(21, 101, 192, 0.2) !important;
}
/* Bordas visíveis — modo escuro */
@media (prefers-color-scheme: dark) {
    div[data-testid="stTextInput"] input,
    div[data-testid="stSelectbox"] > div > div {
        border: 2px solid #aaa !important;
    }
}
[data-theme="dark"] div[data-testid="stTextInput"] input,
[data-theme="dark"] div[data-testid="stSelectbox"] > div > div {
    border: 2px solid #aaa !important;
}
/* Rádios — substitui completamente o visual do Streamlit */
label[data-baseweb="radio"] > div:first-child {
    border: 3px solid #222 !important;
    background-color: #fff !important;
    box-shadow: none !important;
}
label[data-baseweb="radio"] > div:first-child > div {
    display: none !important;
}
label[data-baseweb="radio"]:has(input:checked) > div:first-child {
    box-shadow: inset 0 0 0 4px #2a9d8f !important;
}
/* Rádios — modo escuro */
@media (prefers-color-scheme: dark) {
    label[data-baseweb="radio"] > div:first-child {
        border: 3px solid #ccc !important;
        background-color: #1e1e2e !important;
    }
    label[data-baseweb="radio"]:has(input:checked) > div:first-child {
        box-shadow: inset 0 0 0 4px #4d96ff !important;
    }
}
[data-theme="dark"] label[data-baseweb="radio"] > div:first-child {
    border: 3px solid #ccc !important;
    background-color: #1e1e2e !important;
}
[data-theme="dark"] label[data-baseweb="radio"]:has(input:checked) > div:first-child {
    box-shadow: inset 0 0 0 4px #4d96ff !important;
}
div[data-testid="stDownloadButton"] button {
    background-color: #28a745 !important;
    border-color: #28a745 !important;
    color: white !important;
}
div[data-testid="stDownloadButton"] button:hover {
    background-color: #218838 !important;
    border-color: #1e7e34 !important;
}
div[data-testid="stButton"] button,
div[data-testid="stLinkButton"] a {
    background-color: #2a9d8f !important;
    border-color: #2a9d8f !important;
    color: white !important;
}
div[data-testid="stButton"] button:hover,
div[data-testid="stLinkButton"] a:hover {
    background-color: #21867a !important;
    border-color: #21867a !important;
}
</style>
""", unsafe_allow_html=True)


# ── Descoberta de fichas disponíveis ────────────────────────────────────────

def _discover_forms() -> list[Path]:
    """Retorna pastas com field_coords.json (fichas mapeadas)."""
    if not _FICHAS_DIR.exists():
        return []
    return sorted(
        d for d in _FICHAS_DIR.iterdir()
        if d.is_dir() and (d / "field_coords.json").exists()
    )


def _load_form_meta(form_folder: Path) -> dict:
    cfg_path = form_folder / "config.toml"
    if cfg_path.exists():
        with open(cfg_path, "rb") as f:
            return tomllib.load(f).get("form", {})
    return {"name": form_folder.name}


def _form_is_ready(form_folder: Path) -> bool:
    """True se a ficha tem field_coords.json e config.toml com seção [form]."""
    if not (form_folder / "field_coords.json").exists():
        return False
    cfg_path = form_folder / "config.toml"
    if not cfg_path.exists():
        return False
    with open(cfg_path, "rb") as f:
        return "form" in tomllib.load(f)


# ── Telas ────────────────────────────────────────────────────────────────────

_EXAMES_FORMS = {"Baciloscopia"}


def _render_form_cards(forms: list[Path]) -> None:
    cols = st.columns(3)
    for i, form_folder in enumerate(forms):
        meta  = _load_form_meta(form_folder)
        name  = meta.get("name", form_folder.name)
        desc  = meta.get("description", "")
        ready = _form_is_ready(form_folder)

        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"**{name}**")
                if desc:
                    st.caption(desc)
                if ready:
                    if st.button("Abrir", key=f"open_{form_folder.name}",
                                 use_container_width=True):
                        st.session_state.current_form = str(form_folder)
                        st.rerun()
                else:
                    st.caption(":orange[Aguardando configuração — crie o config.toml]")
                    st.button("Abrir", key=f"open_{form_folder.name}",
                              use_container_width=True, disabled=True)


def _show_home() -> None:
    st.title("FORMULÁRIOS")

    forms = _discover_forms()

    if not forms:
        st.info(
            "Nenhuma ficha disponível. "
            "Use a skill **sinan-coords-create** para mapear os campos de uma ficha PDF."
        )
        return

    sinan_forms = [f for f in forms if f.name not in _EXAMES_FORMS]
    exames_forms = [f for f in forms if f.name in _EXAMES_FORMS]

    if sinan_forms:
        st.markdown("#### SINAN")
        _render_form_cards(sinan_forms)

    if exames_forms:
        st.markdown("#### EXAMES")
        cols = st.columns(3)
        col_idx = 0

        # Card externo: Lacsparser
        with cols[col_idx % 3]:
            with st.container(border=True):
                st.markdown("**Lacsparser**")
                st.caption("Análise de laudos laboratoriais. Solicitação de Exames de Rotina")
                st.link_button("Abrir", "https://lacsparser.streamlit.app/",
                               use_container_width=True)
        col_idx += 1

        # Cards das fichas de exame
        for form_folder in exames_forms:
            meta  = _load_form_meta(form_folder)
            name  = meta.get("name", form_folder.name)
            desc  = meta.get("description", "")
            ready = _form_is_ready(form_folder)
            with cols[col_idx % 3]:
                with st.container(border=True):
                    st.markdown(f"**{name}**")
                    if desc:
                        st.caption(desc)
                    if ready:
                        if st.button("Abrir", key=f"open_{form_folder.name}",
                                     use_container_width=True):
                            st.session_state.current_form = str(form_folder)
                            st.rerun()
                    else:
                        st.caption(":orange[Aguardando configuração — crie o config.toml]")
                        st.button("Abrir", key=f"open_{form_folder.name}",
                                  use_container_width=True, disabled=True)
            col_idx += 1


def _collect_common(form_data: dict) -> dict:
    """Extrai os campos comuns do form_data atual para prefill da ficha destino."""
    result = {}
    for field in _COMMON_FIELDS:
        val = form_data.get(field)
        if val is None or val == "":
            continue
        result[field] = val.strftime("%d/%m/%Y") if hasattr(val, "strftime") else str(val)
    return result


def _collect_tb_to_baciloscopia(form_data: dict) -> dict:
    """Mapeia campos da ficha Tuberculose para prefill da Baciloscopia."""
    result = {}

    for field in ("nome_paciente", "data_nascimento", "cartao_sus", "nome_mae", "bairro"):
        val = form_data.get(field)
        if val is None or val == "":
            continue
        result[field] = val.strftime("%d/%m/%Y") if hasattr(val, "strftime") else str(val)

    # Endereço composto: logradouro + número + complemento
    partes = [
        str(form_data.get("logradouro") or "").strip(),
        str(form_data.get("numero_residencia") or "").strip(),
    ]
    comp = str(form_data.get("complemento") or "").strip()
    if comp:
        partes.append(comp)
    endereco = ", ".join(p for p in partes if p)
    if endereco:
        result["logradouro_complemento"] = endereco

    # Telefone (campo ddd_telefone da TB → telefone da Baciloscopia)
    tel = str(form_data.get("ddd_telefone") or "").strip()
    if tel:
        result["telefone"] = tel

    # Raça/cor: código SINAN → label texto
    raca_code = str(form_data.get("raca_cor") or "")
    if raca_code in _RACA_COR_LABEL:
        result["raca"] = _RACA_COR_LABEL[raca_code]

    return result


def _show_form(form_folder: Path) -> None:
    meta = _load_form_meta(form_folder)
    name = meta.get("name", form_folder.name)

    st.title(f"SINAN — {name}")

    if st.button("← Voltar à lista"):
        st.session_state.current_form = None
        st.session_state.pop(f"autofocused_{form_folder.name}", None)
        st.session_state.pop(f"form_came_from_{form_folder.name}", None)
        st.rerun()

    gen_key     = f"form_gen_{form_folder.name}"
    prefill_key = f"form_prefill_{form_folder.name}"
    if gen_key not in st.session_state:
        st.session_state[gen_key] = 0

    came_from = bool(st.session_state.get(f"form_came_from_{form_folder.name}"))

    # ── Importar dados do paciente (omitido quando veio de outra ficha) ──────
    if not came_from:
        _autofocus_key = f"autofocused_{form_folder.name}"
        if _autofocus_key not in st.session_state:
            st.session_state[_autofocus_key] = True
            st.html(
                "<script>"
                "(function(){"
                "  function f(){"
                "    var doc=(window.parent!==window)"
                "      ?window.parent.document:document;"
                "    var el=doc.querySelector('input[type=\"text\"]');"
                "    if(el){el.focus();}else{setTimeout(f,50);}"
                "  }"
                "  setTimeout(f,200);"
                "})();"
                "</script>"
            )

        _paste_key = f"clipboard_paste_{form_folder.name}"
        _warn_key  = f"import_warn_{form_folder.name}"

        def _do_import():
            text = st.session_state.get(_paste_key, "").strip()
            if not text:
                return
            parsed = parse_clipboard(text)
            if not parsed:
                st.session_state[_warn_key] = "Nenhum campo reconhecido no texto colado."
                return
            coords_keys = set(json.load(
                open(form_folder / "field_coords.json", encoding="utf-8")
            ).keys())
            filtered = {k: v for k, v in parsed.items() if k in coords_keys}
            if filtered:
                st.session_state[prefill_key] = filtered
                st.session_state[gen_key] += 1
                st.session_state[_paste_key] = ""
                st.session_state.pop(_warn_key, None)
            else:
                st.session_state[_warn_key] = "Nenhum campo reconhecido corresponde a esta ficha."

        st.markdown(
            "**Importar dados do paciente**&nbsp;"
            "<a href='?show_config=1' style='font-weight:normal;font-size:0.82em;"
            "color:inherit;opacity:0.5;text-decoration:none'>(configurar)</a>",
            unsafe_allow_html=True,
        )
        st.text_input(
            "Cole o texto copiado do sistema",
            placeholder="Nome: ... | SUS: ... | Nascimento: ... | Mãe: ...",
            key=_paste_key,
            label_visibility="collapsed",
            on_change=_do_import,
            autocomplete="off",
        )
        if st.button("Importar", key=f"btn_import_{form_folder.name}"):
            _do_import()
        if warn := st.session_state.get(_warn_key):
            st.warning(warn)

    prefill = st.session_state.get(prefill_key)
    form_data = render_generic(gen=st.session_state[gen_key], form_folder=form_folder,
                               prefill=prefill)

    st.divider()

    _pdf_bytes = None
    _pdf_error = None
    _is_baciloscopia = form_folder.name == "Baciloscopia"
    try:
        if _is_baciloscopia:
            _pdf_bytes = fill_baciloscopia(form_data)
        else:
            all_data = {**form_data, **get_fixed_fields(form_folder)}
            _data_diag = form_data.get("lab_triagem_data") or form_data.get("lab_rapidos_data")
            if _data_diag:
                all_data["data_diagnostico"] = _data_diag
            all_data.update(resolve_computed(form_folder, all_data))
            all_data = apply_suppress(form_folder, all_data)
            _pdf_bytes = fill_pdf(all_data, form_folder)
    except Exception as e:
        _pdf_error = e

    siblings = _SIBLING_LINKS.get(form_folder.name, [])
    _is_aids = form_folder.name == "Aids_adulto_v5"
    has_siclom       = _is_aids
    has_carga_viral  = _is_aids
    has_cd4          = _is_aids

    # Gerar SICLOM, Carga Viral e CD4 (só ficha AIDS)
    _siclom_bytes = _siclom_error = None
    _cv_bytes     = _cv_error     = None
    _cd4_bytes    = _cd4_error    = None
    if has_siclom:
        try:
            _siclom_bytes = fill_siclom(form_data)
        except Exception as e:
            _siclom_error = e
    if has_carga_viral:
        try:
            _cv_bytes = fill_carga_viral(form_data)
        except Exception as e:
            _cv_error = e
    if has_cd4:
        try:
            _cd4_bytes = fill_cd4(form_data)
        except Exception as e:
            _cd4_error = e

    # Layout: Baixar SINAN | [SICLOM] | [Carga Viral] | [CD4] | Nova Notificação | ← Voltar | [irmãs...]
    n_extra = 1 + len(siblings)  # Voltar + irmãs
    siclom_col = [1] if has_siclom else []
    cv_col     = [1] if has_carga_viral else []
    cd4_col    = [1] if has_cd4 else []
    bottom_cols = st.columns([2] + siclom_col + cv_col + cd4_col + [2] + [1] * n_extra)
    col_idx = 0

    with bottom_cols[col_idx]:
        if _pdf_bytes is not None:
            _dl_label = "Baixar Baciloscopia" if _is_baciloscopia else "Baixar SINAN"
            st.download_button(
                label=_dl_label,
                data=_pdf_bytes,
                file_name=f"notificacao_{form_folder.name.lower()}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        else:
            st.error(f"Erro ao preparar PDF: {_pdf_error}")
    col_idx += 1

    if has_siclom:
        with bottom_cols[col_idx]:
            if _siclom_bytes is not None:
                st.download_button(
                    label="Gerar SICLOM",
                    data=_siclom_bytes,
                    file_name="siclom_adulto.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key=f"siclom_{form_folder.name}",
                )
            else:
                st.error(f"SICLOM: {_siclom_error}")
        col_idx += 1

    if has_carga_viral:
        with bottom_cols[col_idx]:
            if _cv_bytes is not None:
                st.download_button(
                    label="Gerar Carga Viral",
                    data=_cv_bytes,
                    file_name="carga_viral.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key=f"cv_{form_folder.name}",
                )
            else:
                st.error(f"Carga Viral: {_cv_error}")
        col_idx += 1

    if has_cd4:
        with bottom_cols[col_idx]:
            if _cd4_bytes is not None:
                st.download_button(
                    label="Gerar CD4",
                    data=_cd4_bytes,
                    file_name="cd4.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key=f"cd4_{form_folder.name}",
                )
            else:
                st.error(f"CD4: {_cd4_error}")
        col_idx += 1

    with bottom_cols[col_idx]:
        _nova_label = "Novo Exame" if _is_baciloscopia else "Nova Notificação"
        if st.button(_nova_label, use_container_width=True):
            st.session_state[gen_key] = st.session_state.get(gen_key, 0) + 1
            st.session_state.pop(prefill_key, None)
            st.session_state.pop(f"form_came_from_{form_folder.name}", None)
            st.rerun()
    col_idx += 1

    with bottom_cols[col_idx]:
        if st.button("← Voltar", use_container_width=True, key=f"voltar_bottom_{form_folder.name}"):
            st.session_state.current_form = None
            st.session_state.pop(f"autofocused_{form_folder.name}", None)
            st.session_state.pop(f"form_came_from_{form_folder.name}", None)
            st.rerun()
    col_idx += 1

    for i, (sib_label, dest_name) in enumerate(siblings):
        dest_folder = _FICHAS_DIR / dest_name
        if not dest_folder.exists():
            continue
        with bottom_cols[col_idx + i]:
            if st.button(f"{sib_label} →", use_container_width=True,
                         key=f"nav_{dest_name}_{form_folder.name}"):
                if dest_name == "Baciloscopia" and form_folder.name == "Tuberculose_v5":
                    common = _collect_tb_to_baciloscopia(form_data)
                else:
                    common = _collect_common(form_data)
                dest_gen_key = f"form_gen_{dest_name}"
                st.session_state[f"form_prefill_{dest_name}"] = common
                st.session_state[f"form_came_from_{dest_name}"] = str(form_folder)
                st.session_state[dest_gen_key] = st.session_state.get(dest_gen_key, 0) + 1
                st.session_state.current_form = str(dest_folder)
                st.rerun()


def _show_config() -> None:
    _bookmarklet_path = Path(__file__).parent / "bookmarklet_vida" / "SCRIPT.js"
    _bookmarklet_code = _bookmarklet_path.read_text(encoding="utf-8").strip()

    st.markdown("<div style='margin-top:3rem'></div>", unsafe_allow_html=True)
    if st.button("← Voltar"):
        st.session_state.show_config = False
        st.rerun()

    st.title("Configurar importação de dados do paciente")

    st.markdown(
        "O **bookmarklet VIDA** é um favorito especial no navegador. "
        "Ao ser clicado na página do prontuário do paciente, ele copia automaticamente "
        "os dados cadastrais para a área de transferência — pronto para colar aqui no SINAN."
    )

    st.subheader("1. Copie o código abaixo")
    st.code(_bookmarklet_code, language="javascript")

    st.subheader("2. Crie um favorito no navegador")
    st.markdown(
        "- Pressione **Ctrl+Shift+O** (Chrome/Edge) para abrir o gerenciador de favoritos  \n"
        "- Clique em **Adicionar favorito** ou **Novo favorito**  \n"
        "- No campo **Nome**, escreva algo como: `VIDA - Copiar dados`  \n"
        "- No campo **URL**, cole o código copiado no passo anterior "
        "(o texto inteiro, começando com `javascript:`)  \n"
        "- Salve"
    )

    st.subheader("3. Mostre a barra de favoritos")
    st.markdown(
        "- **Chrome / Edge**: pressione **Ctrl+Shift+B** para exibir a barra  \n"
        "- O favorito **\"VIDA - Copiar dados\"** deve aparecer nela"
    )

    st.subheader("4. Como usar no dia a dia")
    st.markdown(
        "1. Abra o sistema VIDA no navegador  \n"
        "2. Navegue até a página do prontuário do paciente — a que mostra nome, "
        "cartão SUS, data de nascimento e nome da mãe  \n"
        "3. Clique no favorito **\"VIDA - Copiar dados\"** na barra de favoritos  \n"
        "4. Uma notificação verde **\"Dados copiados!\"** aparecerá brevemente na tela  \n"
        "5. Volte para esta aba do SINAN e cole o texto no campo de importação (**Ctrl+V**)"
    )


# ── Roteamento ───────────────────────────────────────────────────────────────

if "current_form" not in st.session_state:
    st.session_state.current_form = None

if st.query_params.get("show_config") == "1":
    st.query_params.clear()
    st.session_state.show_config = True
    st.rerun()

if st.session_state.get("show_config"):
    _show_config()
elif st.session_state.current_form is None:
    _show_home()
else:
    _show_form(Path(st.session_state.current_form))
