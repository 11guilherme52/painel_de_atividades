"""Meu Dia — servidor local com banco SQLite.

Uso:
    python app.py              # abre em http://localhost:8000
    python app.py --porta 9000
    python app.py --db outro.db

Só usa a biblioteca padrão do Python (3.9+). Nada para instalar.
"""

import argparse
import json
import re
import sqlite3
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).resolve().parent
STATIC = BASE / "static"
DATA_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CATEGORIAS = {"trabalho", "pessoal", "saude", "estudo", "casa"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS atividades (
    id            TEXT PRIMARY KEY,
    dia           TEXT NOT NULL,              -- AAAA-MM-DD
    titulo        TEXT NOT NULL,
    categoria     TEXT NOT NULL,
    horario       TEXT NOT NULL DEFAULT '',   -- HH:MM ou vazio
    feita         INTEGER NOT NULL DEFAULT 0, -- 0/1
    segundos      REAL NOT NULL DEFAULT 0,    -- tempo cronometrado acumulado
    iniciado_em   INTEGER,                    -- ms desde epoch, se o cronômetro está rodando
    criado_em     INTEGER,
    concluido_em  INTEGER,
    veio_de       TEXT,                       -- dia de origem, se foi trazida de outro dia
    ordem         INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_atividades_dia ON atividades(dia);

CREATE TABLE IF NOT EXISTS notas (
    dia   TEXT PRIMARY KEY,
    texto TEXT NOT NULL DEFAULT ''
);
"""


def conectar(caminho):
    con = sqlite3.connect(caminho)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def iniciar_banco(caminho):
    with conectar(caminho) as con:
        con.executescript(SCHEMA)


def item_para_json(r):
    return {
        "id": r["id"],
        "t": r["titulo"],
        "cat": r["categoria"],
        "at": r["horario"],
        "done": bool(r["feita"]),
        "sec": r["segundos"],
        "run": r["iniciado_em"],
        "created": r["criado_em"],
        "doneAt": r["concluido_em"],
        "from": r["veio_de"],
    }


def ler_dias(con):
    dias = {}
    for r in con.execute("SELECT * FROM atividades ORDER BY dia, ordem"):
        dias.setdefault(r["dia"], {"items": [], "note": ""})["items"].append(item_para_json(r))
    for r in con.execute("SELECT dia, texto FROM notas"):
        dias.setdefault(r["dia"], {"items": [], "note": ""})["note"] = r["texto"]
    return dias


def salvar_dia(con, dia, corpo):
    itens = corpo.get("items") or []
    nota = str(corpo.get("note") or "")
    if not isinstance(itens, list):
        raise ValueError("'items' precisa ser uma lista")
    linhas = []
    for i, it in enumerate(itens):
        titulo = str(it.get("t", "")).strip()[:140]
        if not titulo or not it.get("id"):
            raise ValueError("cada atividade precisa de 'id' e 't'")
        cat = it.get("cat") if it.get("cat") in CATEGORIAS else "pessoal"
        linhas.append((
            str(it["id"]), dia, titulo, cat, str(it.get("at") or ""),
            1 if it.get("done") else 0, float(it.get("sec") or 0),
            it.get("run"), it.get("created"), it.get("doneAt"), it.get("from"), i,
        ))
    with con:
        con.execute("DELETE FROM atividades WHERE dia = ?", (dia,))
        con.executemany(
            "INSERT OR REPLACE INTO atividades (id, dia, titulo, categoria, horario, feita, segundos,"
            " iniciado_em, criado_em, concluido_em, veio_de, ordem) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            linhas,
        )
        if nota:
            con.execute("INSERT INTO notas (dia, texto) VALUES (?, ?) "
                        "ON CONFLICT(dia) DO UPDATE SET texto = excluded.texto", (dia, nota))
        else:
            con.execute("DELETE FROM notas WHERE dia = ?", (dia,))


def apagar_dia(con, dia):
    with con:
        con.execute("DELETE FROM atividades WHERE dia = ?", (dia,))
        con.execute("DELETE FROM notas WHERE dia = ?", (dia,))


class Handler(SimpleHTTPRequestHandler):
    db_path = "meu_dia.db"

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(STATIC), **kw)

    # --- utilidades ---
    def _json(self, status, obj):
        corpo = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _dia_da_rota(self):
        m = re.fullmatch(r"/api/dias/([^/]+)", self.path.split("?")[0])
        if not m or not DATA_RE.match(m.group(1)):
            return None
        return m.group(1)

    # --- rotas ---
    def do_GET(self):
        if self.path.split("?")[0] == "/api/dias":
            with conectar(self.db_path) as con:
                return self._json(HTTPStatus.OK, {"dias": ler_dias(con)})
        if self.path.startswith("/api/"):
            return self._json(HTTPStatus.NOT_FOUND, {"erro": "rota não encontrada"})
        return super().do_GET()

    def do_PUT(self):
        dia = self._dia_da_rota()
        if not dia:
            return self._json(HTTPStatus.NOT_FOUND, {"erro": "use /api/dias/AAAA-MM-DD"})
        try:
            tamanho = int(self.headers.get("Content-Length", 0))
            if tamanho > 1_000_000:
                return self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"erro": "corpo grande demais"})
            corpo = json.loads(self.rfile.read(tamanho) or b"{}")
            with conectar(self.db_path) as con:
                salvar_dia(con, dia, corpo)
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            return self._json(HTTPStatus.BAD_REQUEST, {"erro": str(e)})
        return self._json(HTTPStatus.OK, {"ok": True})

    def do_DELETE(self):
        dia = self._dia_da_rota()
        if not dia:
            return self._json(HTTPStatus.NOT_FOUND, {"erro": "use /api/dias/AAAA-MM-DD"})
        with conectar(self.db_path) as con:
            apagar_dia(con, dia)
        return self._json(HTTPStatus.OK, {"ok": True})

    def log_message(self, fmt, *args):
        if self.path.startswith("/api/") and self.command != "GET":
            super().log_message(fmt, *args)


def main():
    p = argparse.ArgumentParser(description="Meu Dia — controle de atividades diárias")
    p.add_argument("--porta", type=int, default=8000)
    p.add_argument("--db", default=str(BASE / "meu_dia.db"), help="arquivo do banco SQLite")
    p.add_argument("--sem-navegador", action="store_true", help="não abrir o navegador")
    args = p.parse_args()

    iniciar_banco(args.db)
    Handler.db_path = args.db
    srv = ThreadingHTTPServer(("127.0.0.1", args.porta), Handler)
    url = f"http://localhost:{args.porta}"
    print(f"Meu Dia rodando em {url}  (banco: {args.db})  — Ctrl+C para sair")
    if not args.sem_navegador:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nAté logo!")


if __name__ == "__main__":
    main()
