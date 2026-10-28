"""Acceso a PostgreSQL (Supabase en producción, PostgreSQL local en pruebas) con un pequeño pool de conexiones.
La cadena de conexión viene de DATABASE_URL (variable de entorno o st.secrets). Nunca se imprime."""
from __future__ import annotations

import os
import threading
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb  # noqa: F401  (se reexporta)
from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None
_url_pool: str | None = None
_lock = threading.Lock()


def url() -> str:
    u = os.environ.get("DATABASE_URL", "")
    if not u:
        try:  # Streamlit Community Cloud: st.secrets
            import streamlit as st
            u = str(st.secrets.get("DATABASE_URL", ""))
        except Exception:
            u = ""
    if not u:
        raise RuntimeError("Falta DATABASE_URL (variable de entorno o secreto de Streamlit).")
    return u


def pool() -> ConnectionPool:
    global _pool, _url_pool
    u = url()
    with _lock:
        if _pool is None or _url_pool != u:
            if _pool is not None:
                _pool.close()
            _pool = ConnectionPool(u, min_size=1, max_size=int(os.environ.get("PMS_POOL_MAX", "6")),
                                   kwargs={"row_factory": dict_row, "prepare_threshold": None, "connect_timeout": 15},
                                   check=ConnectionPool.check_connection, open=True, timeout=30)
            _url_pool = u
    return _pool


def cerrar_pool():
    global _pool
    with _lock:
        if _pool is not None:
            _pool.close()
            _pool = None


@contextmanager
def tx():
    """Una transacción: confirma al salir bien y deshace todo si hay un error."""
    with pool().connection() as cx:
        yield cx


def todos(sql: str, params=None) -> list[dict]:
    with tx() as cx:
        return cx.execute(sql, params or ()).fetchall()


def uno(sql: str, params=None) -> dict | None:
    with tx() as cx:
        return cx.execute(sql, params or ()).fetchone()


def conectar_directo():
    """Conexión suelta (scripts de mantenimiento)."""
    return psycopg.connect(url(), row_factory=dict_row, prepare_threshold=None)
