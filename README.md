# Meu Dia

Sistema simples para controlar as atividades do dia: lista de tarefas com categoria e horário, cronômetro por atividade, progresso da semana, tempo por categoria e anotações diárias.

Roda no seu computador e guarda tudo num banco **SQLite** local (`meu_dia.db`). Só usa a biblioteca padrão do Python, então não há nada para instalar.

## Como funciona

A página fica publicada no **GitHub Pages** e os dados ficam num banco **SQLite** (`meu_dia.db`) no seu computador. Para isso, um servidor pequeno (`app.py`) roda na sua máquina e a página conversa com ele.

```
GitHub Pages (a página)  ──►  http://localhost:8000 (app.py)  ──►  meu_dia.db
```

- Endereço da página: https://11guilherme52.github.io/painel_de_atividades/
- O servidor só aceita conexões do próprio computador e só responde à página acima (ou a ele mesmo em `localhost`).
- Com o servidor desligado, a página mostra um aviso e tenta reconectar sozinha a cada 5 segundos. Mudanças feitas enquanto ele estava fora do ar são enviadas quando ele volta.

## Como usar

Requisito: Python 3.9 ou mais novo. Não há nada para instalar.

1. Baixe o projeto (uma vez só):

   ```bash
   git clone https://github.com/11guilherme52/painel_de_atividades.git
   ```

2. Ligue o servidor. No Windows, dê dois cliques em **`iniciar.bat`**. Em outro sistema:

   ```bash
   cd painel_de_atividades && python app.py
   ```

   A página do GitHub Pages abre no navegador. Deixe a janela do servidor aberta enquanto usa.

3. Na primeira vez, o Chrome/Edge pergunta se o site pode **acessar a rede local** (ou "outros dispositivos"). Clique em **Permitir**: é assim que a página alcança o servidor no seu computador.

Opções do servidor:

```bash
python app.py --local               # abre http://localhost:8000 em vez do GitHub Pages
python app.py --porta 9000          # outra porta
python app.py --db ~/dados/dia.db   # outro arquivo de banco
python app.py --sem-navegador       # não abre o navegador
```

Funciona no Chrome, Edge e Firefox. O Safari pode bloquear o acesso de um site `https` ao `localhost`; nele, use `python app.py --local`.

### Publicar no GitHub Pages (uma vez)

No repositório: **Settings → Pages → Build and deployment**, em *Source* escolha **Deploy from a branch**, branch **`main`**, pasta **`/docs`**, e salve. Em um ou dois minutos a página fica no ar.

## Banco de dados

O arquivo `meu_dia.db` é criado na primeira execução e fica fora do Git (`.gitignore`). Tabelas:

| Tabela       | O que guarda |
|--------------|--------------|
| `atividades` | uma linha por atividade: `dia`, `titulo`, `categoria`, `horario`, `feita`, `segundos` cronometrados, `iniciado_em` (cronômetro rodando), `concluido_em`, `veio_de` |
| `notas`      | a anotação de cada dia |

Para consultar direto:

```bash
sqlite3 meu_dia.db "SELECT dia, categoria, ROUND(SUM(segundos)/3600.0, 1) AS horas FROM atividades GROUP BY dia, categoria;"
```

Para fazer backup, copie o arquivo `meu_dia.db` com o servidor parado.

## API

| Método   | Rota                    | Descrição |
|----------|-------------------------|-----------|
| `GET`    | `/api/dias`             | todos os dias: `{"dias": {"2026-11-24": {"items": [...], "note": "..."}}}` |
| `PUT`    | `/api/dias/AAAA-MM-DD`  | substitui as atividades e a anotação do dia |
| `DELETE` | `/api/dias/AAAA-MM-DD`  | apaga o dia |

## Estrutura

```
app.py           servidor local: API + banco SQLite
docs/index.html  a página (publicada pelo GitHub Pages)
iniciar.bat      atalho para Windows: liga o servidor e abre a página
```

## Atalhos

`←` / `→` trocam de dia, `N` vai para o campo de nova atividade.
