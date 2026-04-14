import sqlite3

conn = sqlite3.connect("pedidos.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    cnpj TEXT,
    telefone TEXT,
    cidade TEXT,
    observacao TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS pedidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_pedido TEXT,
    vendedor TEXT NOT NULL,
    cliente_id INTEGER NOT NULL,
    data_pedido TEXT,
    status TEXT,
    observacao TEXT,
    FOREIGN KEY (cliente_id) REFERENCES clientes(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS itens_pedido (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id INTEGER NOT NULL,
    material TEXT NOT NULL,
    quantidade REAL NOT NULL,
    valor_unitario REAL NOT NULL,
    FOREIGN KEY (pedido_id) REFERENCES pedidos(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS retiradas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id INTEGER NOT NULL,
    item_pedido_id INTEGER NOT NULL,
    data_retirada TEXT NOT NULL,
    quantidade_retirada REAL NOT NULL,
    numero_nota TEXT,
    observacao TEXT,
    FOREIGN KEY (pedido_id) REFERENCES pedidos(id),
    FOREIGN KEY (item_pedido_id) REFERENCES itens_pedido(id)
)
""")



conn.commit()
conn.close()

print("Banco criado com sucesso!")