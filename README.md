# SINAN — Preenchimento de Fichas em PDF

Aplicação Streamlit para preencher fichas do Sistema de Informação de Agravos de Notificação (SINAN) e formulários de exames em PDF, com importação de dados cadastrais direto do sistema VIDA.

Disponível em: **[sinanhiv.streamlit.app](https://sinanhiv.streamlit.app)**

## Funcionalidades

- Preenchimento das fichas **SINAN AIDS Adulto**, **SINAN Tuberculose** e **SINAN Sífilis Adquirida**
- Formulário de **Baciloscopia do Escarro** (solicitação de exame, standalone)
- Geração de PDFs preenchidos para download (SINAN, SICLOM, Carga Viral, CD4, Baciloscopia)
- Importação de dados do paciente via bookmarklet do sistema VIDA (nome, cartão SUS, data de nascimento, nome da mãe, prontuário)
- Navegação cruzada entre fichas com transferência automática dos campos em comum (dados demográficos, residência, ocupação)
- Botão **Baciloscopia** na ficha Tuberculose: abre o formulário de Baciloscopia já com os dados do paciente preenchidos
- Link externo para o **[Lacsparser](https://lacsparser.streamlit.app/)** (análise de laudos laboratoriais e solicitação de exames de rotina)

## Tela inicial

A home page está organizada em duas seções:

| Seção | Conteúdo |
|---|---|
| **SINAN** | Fichas de notificação (AIDS Adulto, Tuberculose, Sífilis Adquirida) |
| **EXAMES** | Lacsparser (link externo) + Baciloscopia |

## Baciloscopia

Formulário standalone de solicitação de baciloscopia do escarro. Comportamentos automáticos:

- **Data do atendimento**: sempre hoje (oculta do formulário)
- **Tipo de material (Escarro)**: sempre marcado (oculto do formulário)
- **TRM-TB**: Sim por padrão; Não automaticamente para amostras de Controle
- **Diag. 1ª amostra**: usa PDF duplo — preenche dois formulários na mesma folha (1ª à esquerda, 2ª à direita com offset de 420.7 pt); a 2ª amostra gerada automaticamente sempre terá Cultura = Não e sem data de coleta

## Importação via bookmarklet VIDA

O link **(configurar)** no topo de qualquer ficha exibe o passo a passo para instalar o bookmarklet no navegador. Após instalado:

1. Abra o prontuário do paciente no sistema VIDA
2. Clique no favorito **"VIDA - Copiar dados"** na barra de favoritos
3. Volte para esta aba e cole o texto no campo de importação (Ctrl+V)

Os campos reconhecidos são preenchidos automaticamente no formulário.

## Rodando localmente

```bash
streamlit run app.py
```

Requer Python 3.14+ e as dependências em `requirements.txt`.

## Estrutura

```
fichas_sinan/
  Aids_adulto_v5/      # Ficha AIDS: PDF, config.toml, field_coords.json
  Tuberculose_v5/      # Ficha TB:   PDF, config.toml, field_coords.json
  Baciloscopia/        # Formulário de baciloscopia: PDFs (simples e duplo), config.toml, field_coords.json
  Sifilis_adquirida/   # Ficha Sífilis Adquirida: PDF, config.toml, field_coords.json
bookmarklet_vida/
  SCRIPT.js            # Código do bookmarklet (extrai dados do DOM do VIDA)
app.py                 # Roteamento, home page e orquestração Streamlit
form_renderer.py       # Renderização genérica de formulários
pdf_filler.py          # Preenchimento de PDF com coordenadas (fichas SINAN)
baciloscopia_filler.py # Preenchimento customizado do formulário de Baciloscopia
clipboard_import.py    # Parser do texto copiado pelo bookmarklet
carga_viral_filler.py  # Preenchimento do formulário de Carga Viral
cd4_filler.py          # Preenchimento do formulário de CD4
siclom_filler.py       # Preenchimento do formulário SICLOM
```
