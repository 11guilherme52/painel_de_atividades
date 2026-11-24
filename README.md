# Meu Dia

Sistema simples para controlar as atividades do dia: lista de tarefas com categoria e horário, cronômetro por atividade, progresso da semana, tempo por categoria e anotações diárias.

Roda no seu computador e guarda tudo num banco **SQLite** local (`meu_dia.db`). Só usa a biblioteca padrão do Python, então não há nada para instalar.

## Como rodar

Requisito: Python 3.9 ou mais novo.

```bash
git clone https://github.com/11guilherme52/painel_de_atividades.git
cd painel_de_atividades
python app.py
```

O navegador abre em http://localhost:8000. Opções:

```bash
python app.py --porta 9000          # outra porta
python app.py --db ~/dados/dia.db   # outro arquivo de banco
python app.py --sem-navegador       # não abre o navegador
```

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

O servidor escuta só em `127.0.0.1`, então não fica acessível por outras máquinas da rede.

## Estrutura

```
app.py             servidor HTTP + SQLite
static/index.html  interface (HTML/CSS/JS, sem dependências)
```

## Atalhos

`←` / `→` trocam de dia, `N` vai para o campo de nova atividade.
