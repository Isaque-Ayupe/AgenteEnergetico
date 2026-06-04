"""
Utilitário para criar o banco de dados PostgreSQL caso ele não exista.
Execute antes de 'manage.py migrate' em um ambiente novo:

    python energy_agent/core/db_init.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / '.env')

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def create_database_if_not_exists() -> None:
    db_name = os.getenv('DB_NAME', 'energy_agent_db')
    db_user = os.getenv('DB_USER', 'postgres')
    db_password = os.getenv('DB_PASSWORD', '')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')

    # Conecta ao banco padrão 'postgres' para verificar/criar o banco alvo
    try:
        conn = psycopg2.connect(
            dbname='postgres',
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port,
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (db_name,)
        )
        exists = cursor.fetchone()

        if not exists:
            cursor.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name))
            )
            print(f"[db_init] Banco de dados '{db_name}' criado com sucesso.")
        else:
            print(f"[db_init] Banco de dados '{db_name}' já existe. Nenhuma ação necessária.")

        cursor.close()
        conn.close()

    except psycopg2.OperationalError as e:
        print(f"[db_init] ERRO ao conectar ao PostgreSQL: {e}", file=sys.stderr)
        print(
            "[db_init] Verifique se o servidor PostgreSQL está rodando e se as "
            "variáveis DB_USER, DB_PASSWORD, DB_HOST e DB_PORT estão corretas no .env",
            file=sys.stderr
        )
        sys.exit(1)


if __name__ == '__main__':
    create_database_if_not_exists()
