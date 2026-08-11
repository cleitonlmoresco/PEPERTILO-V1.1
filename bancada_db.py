from __future__ import annotations
import sqlite3
from pathlib import Path
from uuid import uuid4
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "bancada.sqlite3"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = _conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS servicos (
        id TEXT PRIMARY KEY, fabricante TEXT, modelo TEXT, ano TEXT,
        modulo TEXT, part_number TEXT, hw TEXT, sw TEXT, sintoma TEXT,
        status TEXT NOT NULL, observacoes TEXT, criado_em TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS medicoes (
        id TEXT PRIMARY KEY, servico_id TEXT NOT NULL, ponto TEXT NOT NULL,
        valor REAL, unidade TEXT, esperado TEXT, instrumento TEXT,
        status TEXT NOT NULL, observacao TEXT, criado_em TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS notas (
        id TEXT PRIMARY KEY, servico_id TEXT NOT NULL, texto TEXT NOT NULL,
        criado_em TEXT NOT NULL
    );
    """)
    c.commit(); c.close()


def novo_servico(**kw):
    sid = uuid4().hex[:10]
    now = datetime.now().isoformat()
    c = _conn()
    c.execute("""INSERT INTO servicos
        (id,fabricante,modelo,ano,modulo,part_number,hw,sw,sintoma,status,observacoes,criado_em)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (
        sid, kw.get("fabricante"), kw.get("modelo"), kw.get("ano"), kw.get("modulo"),
        kw.get("part_number"), kw.get("hw"), kw.get("sw"), kw.get("sintoma"),
        kw.get("status", "aberto"), kw.get("observacoes"), now
    ))
    c.commit(); c.close()
    return sid


def listar_servicos(limit=100):
    c = _conn(); rows = c.execute("SELECT * FROM servicos ORDER BY criado_em DESC LIMIT ?", (limit,)).fetchall(); c.close()
    return [dict(r) for r in rows]


def adicionar_medicao(servico_id, **kw):
    mid = uuid4().hex[:10]
    now = datetime.now().isoformat()
    c = _conn()
    c.execute("""INSERT INTO medicoes
      (id,servico_id,ponto,valor,unidade,esperado,instrumento,status,observacao,criado_em)
      VALUES (?,?,?,?,?,?,?,?,?,?)""", (
        mid, servico_id, kw.get("ponto", ""), kw.get("valor"), kw.get("unidade"),
        kw.get("esperado"), kw.get("instrumento"), kw.get("status", "nao_avaliado"),
        kw.get("observacao"), now
    ))
    c.commit(); c.close(); return mid


def listar_medicoes(servico_id):
    c = _conn(); rows = c.execute("SELECT * FROM medicoes WHERE servico_id=? ORDER BY criado_em", (servico_id,)).fetchall(); c.close()
    return [dict(r) for r in rows]


def adicionar_nota(servico_id, texto):
    nid = uuid4().hex[:10]
    c = _conn(); c.execute("INSERT INTO notas VALUES (?,?,?,?)", (nid, servico_id, texto, datetime.now().isoformat())); c.commit(); c.close(); return nid


def listar_notas(servico_id):
    c = _conn(); rows = c.execute("SELECT * FROM notas WHERE servico_id=? ORDER BY criado_em", (servico_id,)).fetchall(); c.close(); return [dict(r) for r in rows]

init_db()
