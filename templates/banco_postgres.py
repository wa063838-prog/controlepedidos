import os
import psycopg

DATABASE_URL = os.environ.get("DATABASE_URL")

conn = psycopg.connect(DATABASE_URL)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS clientes (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    cnpj TEXT,
    telefone TEXT,
    cidade TEXT,
    observacao TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS pedidos (
    id SERIAL PRIMARY KEY,
    numero_pedido TEXT,
    vendedor TEXT NOT NULL,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id),
    data_pedido TEXT,
    status TEXT,
    observacao TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS itens_pedido (
    id SERIAL PRIMARY KEY,
    pedido_id INTEGER NOT NULL REFERENCES pedidos(id),
    material TEXT NOT NULL,
    quantidade DOUBLE PRECISION NOT NULL,
    valor_unitario DOUBLE PRECISION NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS retiradas (
    id SERIAL PRIMARY KEY,
    pedido_id INTEGER NOT NULL REFERENCES pedidos(id),
    item_pedido_id INTEGER NOT NULL REFERENCES itens_pedido(id),
    data_retirada TEXT NOT NULL,
    quantidade_retirada DOUBLE PRECISION NOT NULL,
    numero_nota TEXT,
    observacao TEXT
)
""")

conn.commit()
conn.close()

print("Banco PostgreSQL criado com sucesso.")