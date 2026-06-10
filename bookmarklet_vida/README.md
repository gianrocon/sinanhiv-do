# Bookmarklet — Importar dados do paciente (sistema VIDA)

## O que é

`SCRIPT.js` é um bookmarklet que extrai dados do paciente da página do sistema VIDA e copia uma string formatada para a área de transferência.

## Formato copiado

```text
Nome: ANTONIO DO CARMO CABRAL | SUS: 706301724891171 | Prontuário: 07093 | Nascimento: 11/10/1967 | Mãe: AMERICA DO CARMO SANTANA CABRAL
```

## Como usar no browser

1. Crie um novo favorito no browser.
2. No campo URL, cole o conteúdo de `SCRIPT.js` (começando com `javascript:`).
3. Na página do paciente no VIDA, clique no favorito.
4. A string é copiada automaticamente; uma notificação verde confirma.

## Integração com o app SINAN

Cole o texto no campo **"Importar dados do paciente"** do app. O módulo `clipboard_import.py` interpreta os rótulos e preenche os campos:

| Rótulo | Campo SINAN |
|---|---|
| `Nome` | `nome_paciente` |
| `SUS` | `cartao_sus` |
| `Prontuário` | `nu_prontuario` |
| `Nascimento` | `data_nascimento` |
| `Mãe` | `nome_mae` |

## Adicionar um novo campo

1. Adicionar a extração em `SCRIPT.js` (leitura do DOM da página VIDA).
2. Adicionar o mapeamento em `clipboard_import.py` → `_LABEL_MAP`.

## Arquivo de exemplo

`pagina vida.html` — snapshot de uma página real do VIDA, usada para testar o bookmarklet sem precisar do sistema.
