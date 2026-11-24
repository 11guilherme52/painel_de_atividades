"""Meu Dia — servidor local com banco SQLite.

A interface pode ser aberta de dois jeitos, e os dois gravam no mesmo banco
(meu_dia.db) aqui no seu computador:
    - pelo GitHub Pages: https://11guilherme52.github.io/painel_de_atividades/
    - direto pelo servidor: http://localhost:8000

Uso:
    python app.py                  # abre a página do GitHub Pages
    python app.py --local          # abre http://localhost:8000
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
STATIC = BASE / "docs"
PAGES_URL = "https://11guilherme52.github.io/painel_de_atividades/"
# Sites que podem ler e gravar no banco. O navegador bloqueia qualquer outro.
ORIGENS = {"https://11guilherme52.github.io"}
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
    def _origem_ok(self):
        """Sem cabeçalho Origin (curl, navegação direta) ou origem permitida."""
        origem = self.headers.get("Origin")
        if not origem:
            return True
        host, porta = self.server.server_address[:2]
        locais = {f"http://localhost:{porta}", f"http://127.0.0.1:{porta}"}
        return origem in ORIGENS or origem in locais

    def _cors(self):
        origem = self.headers.get("Origin")
        if origem and origem in ORIGENS:
            self.send_header("Access-Control-Allow-Origin", origem)
            self.send_header("Vary", "Origin")

    def _json(self, status, obj):
        corpo = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._cors()
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
    def do_OPTIONS(self):
        # pré-verificação do navegador antes de PUT/DELETE vindos do GitHub Pages
        if not self.path.startswith("/api/") or not self._origem_ok():
            self.send_response(HTTPStatus.FORBIDDEN)
            self.end_headers()
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        # Chrome pede isto quando um site público acessa o localhost
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def _bloqueado(self):
        if self.path.startswith("/api/") and not self._origem_ok():
            self._json(HTTPStatus.FORBIDDEN, {"erro": "origem não permitida"})
            return True
        return False

    def do_GET(self):
        if self._bloqueado():
            return
        if self.path.split("?")[0] == "/api/dias":
            with conectar(self.db_path) as con:
                return self._json(HTTPStatus.OK, {"dias": ler_dias(con)})
        if self.path.startswith("/api/"):
            return self._json(HTTPStatus.NOT_FOUND, {"erro": "rota não encontrada"})
        return super().do_GET()

    def do_PUT(self):
        if self._bloqueado():
            return
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
        if self._bloqueado():
            return
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
    p.add_argument("--local", action="store_true", help="abrir http://localhost em vez do GitHub Pages")
    p.add_argument("--sem-navegador", action="store_true", help="não abrir o navegador")
    p.add_argument("--origem", action="append", default=[],
                   help="outro site autorizado a usar o banco (ex.: https://usuario.github.io)")
    args = p.parse_args()

    ORIGENS.update(o.rstrip("/") for o in args.origem)
    iniciar_banco(args.db)
    Handler.db_path = args.db
    srv = ThreadingHTTPServer(("127.0.0.1", args.porta), Handler)
    local = f"http://localhost:{args.porta}"
    pages = PAGES_URL if args.porta == 8000 else f"{PAGES_URL}?servidor={local}"
    print(f"Meu Dia: servidor ligado, gravando em {args.db}")
    print(f"  GitHub Pages: {pages}")
    print(f"  Local:        {local}")
    print("Deixe esta janela aberta enquanto usa. Ctrl+C para desligar.")
    if not args.sem_navegador:
        webbrowser.open(local if args.local else pages)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nAté logo!")


if __name__ == "__main__":
    main()
