# CLAUDE.md — Projeto SINAN

## Idioma
Responda sempre em **português brasileiro**. Mensagens de commit, comentários de código e toda comunicação devem estar em pt-BR.

## Ambiente Python
- Interpretador: sempre usar `.venv\Scripts\python.exe` (nunca `python`, `python3` ou `py`)
- Versão: **Python 3.14.5**
- O venv já existe na raiz do projeto; não recriar sem motivo explícito

## Plataforma de deploy
- O app é servido via **Streamlit Community Cloud** em `sinanhiv.streamlit.app`
- Ao fazer alterações, considerar compatibilidade com o Streamlit Cloud:
  - Arquivos de configuração ficam em `fichas_sinan/<nome_ficha>/config.toml`
  - PDFs da ficha ficam em `fichas_sinan/<nome_ficha>/`
  - Dependências declaradas em `requirements.txt` na raiz
- Para testar localmente: `streamlit run app.py`

## Encoding — regras obrigatórias
- **PowerShell 5.1** (padrão no Windows) não suporta `-Encoding utf8NoBOM`; usar `.NET`:
  ```powershell
  [System.IO.File]::WriteAllText("caminho.json", $conteudo, [System.Text.UTF8Encoding]::new($false))
  ```
- Definir `$env:PYTHONIOENCODING = "utf-8"` antes de rodar scripts Python que imprimem JSON no terminal
- Scripts Python que imprimem para stdout devem incluir no topo quando necessário:
  ```python
  import sys, io
  sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
  ```
- Ler JSONs com `encoding="utf-8-sig"` para tolerar BOM acidental
- Salvar JSONs via Python com `open(path, "w", encoding="utf-8")`
- **Nunca** usar `Out-File` sem especificar encoding; preferir `[System.IO.File]::WriteAllText`

## Convenções de campo — field_coords.json

- Campos UI-only (aparecem no formulário Streamlit mas **não** devem ser escritos no PDF SINAN) recebem `"skip_pdf": true` no `field_coords.json`.
- `pdf_filler._load_coords` filtra automaticamente entradas com `skip_pdf: true`.
- Exemplo: campo `cpf` da ficha AIDS — presente no formulário e nos PDFs de CV/CD4, ausente no PDF SINAN.

## Formulários de exames laboratoriais

- `carga_viral_filler.py` e `cd4_filler.py` preenchem PDFs em `forms_externos/`.
- Ambos recebem o mesmo `form_data` da ficha AIDS (incluindo campos comuns como `cpf`).
- Novas versões desses formulários devem seguir o mesmo padrão: `_FIELDS` com `(chave, x, y, font_size_base)`, `_FS = 1.2` como multiplicador.

## Roteamento de páginas (app.py)

O app tem três telas controladas por `st.session_state`:

| Estado | Tela exibida |
|---|---|
| `current_form = None` | Home (lista de fichas) |
| `current_form = "<caminho>"` | Formulário da ficha |
| `show_config = True` | Página de configuração do bookmarklet |

O link `(configurar)` usa `<a href='?show_config=1'>` (HTML inline no `st.markdown`). O roteamento detecta o query param, limpa-o e seta `show_config = True` antes de qualquer render. Não usar `st.button` para esse link — o query param é necessário para ficar inline com o texto do label.

## Home page — seções SINAN e EXAMES

A home exibe duas seções separadas:

- **SINAN**: fichas cujo `form_folder.name` **não** esteja em `_EXAMES_FORMS` (set definido em `app.py`)
- **EXAMES**: fichas em `_EXAMES_FORMS` + cards externos (ex: Lacsparser via `st.link_button`)

Para mover uma ficha para a seção EXAMES, adicionar seu `folder.name` ao set `_EXAMES_FORMS`.

## Formulário de Baciloscopia

- Filler customizado: `baciloscopia_filler.py` (não usa `pdf_filler.py`)
- PDFs: `fichas_sinan/Baciloscopia/baciloscopia.pdf` (simples) e `baciloscopia_duplo.pdf` (dois formulários lado a lado, offset 420.7 pt)
- Quando `amostra == "bac_diag_1"`: usa o PDF duplo, preenche lado esquerdo com Diag. 1ª e lado direito com Diag. 2ª; a 2ª amostra sempre recebe `encaminhar_cultura = "Não"` e `data_coleta = None`
- `_fill_page(page, form_data, dx, amostra_override, field_overrides)` — `field_overrides` sobrepõe valores pontuais sem mutar o dict original
- Campos automáticos (ocultos do UI via `[hidden]` no config.toml): `data_atendimento` (sempre hoje), `tipo_escarro` (sempre marcado), `trm_tb` (Sim por padrão, Não para amostras de controle)

## Ficha Sífilis Adquirida

- Pasta: `fichas_sinan/Sifilis_adquirida/`
- PDF: `sifilis_adquirida.pdf` (2 páginas)
- Coordenadas originadas de `widgets_sifilis_adquirida.json` (exportado de ferramenta externa com origem **top-left**)
- Conversão top-left → baseline para `pdf_filler`: `x_fill = x + 2`, `y_fill = y + 10` (h≥12) ou `y + 8` (h≤11)
- Campos específicos (31–42): `antecedente_sifilis`, `tratamento_realizado`, `comportamento_sexual`, `resultado_nao_treponemico`, `titulo_nao_treponemico`, `data_nao_treponemico`, `resultado_treponemico`, `classificacao_clinica`, `classificacao_final`, `esquema_tratamento`, `data_inicio_tratamento`
- `classificacao_final` (campo 42): se o usuário marcar "2 - Não", o campo **não é escrito no PDF** (via `[suppress_if]`) — espaço reservado para assinatura manual

## Convenções de config.toml — funcionalidades genéricas

Funcionalidades disponíveis para qualquer ficha:

| Seção | Comportamento |
|---|---|
| `[fixed]` com valor `"today"` | Campo escrito no PDF com `date.today()`, oculto do formulário |
| `[computed]` | Campo calculado via template `{campo}` a partir dos dados montados — ex: `investigador_municipio_unidade = "{municipio_notificacao} / {unidade_saude}"` |
| `[suppress_if]` | Zera o campo antes do PDF se o valor coincidir — ex: `classificacao_final = "2"` |
| `[fields.<campo>] max_chars` | Limita caracteres no `st.text_input` |

Funções correspondentes em `form_renderer.py`: `get_fixed_fields` (resolve `"today"`), `resolve_computed`, `apply_suppress`.

## _COMMON_FIELDS — campos transferidos na navegação cruzada

Lista em `app.py`. Inclui: `unidade_saude`, `codigo_unidade_saude`, `nome_paciente`, `data_nascimento`, `gestante`, `sexo`, `raca_cor`, `escolaridade`, `cartao_sus`, `nome_mae`, `municipio_residencia`, `uf_residencia`, `bairro`, `logradouro`, `complemento`, `numero_residencia`, `cep`, `ddd_telefone`, `ocupacao`. **Não inclui** `data_diagnostico` (cada ficha preenche com sua própria lógica).

## Navegação cruzada TB → Baciloscopia

- `_SIBLING_LINKS["Tuberculose_v5"]` inclui `("Baciloscopia", "Baciloscopia")`
- A função `_collect_tb_to_baciloscopia(form_data)` faz o mapeamento:
  - Campos diretos: `nome_paciente`, `data_nascimento`, `cartao_sus`, `nome_mae`, `bairro`
  - Endereço composto: `logradouro + numero_residencia + complemento` → `logradouro_complemento`
  - Raça: código SINAN (`"4"`) → label texto (`"Parda"`) via `_RACA_COR_LABEL`
  - Telefone: `ddd_telefone` → `telefone` (só transfere se disponível)

## Navegação cruzada com Sífilis

- `_SIBLING_LINKS["Aids_adulto_v5"]` inclui `("SINAN Sífilis", "Sifilis_adquirida")`
- `_SIBLING_LINKS["Tuberculose_v5"]` inclui `("SINAN Sífilis", "Sifilis_adquirida")`
- `_SIBLING_LINKS["Sifilis_adquirida"]` = `[("SINAN HIV", "Aids_adulto_v5")]`
- Transferência usa `_collect_common` (campos até `ocupacao`, sem `data_diagnostico`)

## Integrações externas

- `bookmarklet_vida/SCRIPT.js` — código do bookmarklet que extrai dados do DOM do sistema VIDA e copia no formato `Nome: X | SUS: Y | Prontuário: Z | Nascimento: W | Mãe: V`. A página de configuração (`_show_config()` em `app.py`) exibe esse código e as instruções de instalação.
- **Lacsparser** — app externo em `https://lacsparser.streamlit.app/`, exibido como card na seção EXAMES da home.

## Shell
- Ambiente: Windows 11, PowerShell 5.1
- Operadores `&&` e `||` **não existem** no PS 5.1 — usar `; if ($?) { }` para encadear com verificação
- Usar `$env:VAR` para variáveis de ambiente (não `export`)
