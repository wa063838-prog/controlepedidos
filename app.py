import os
import psycopg
from flask import (
    Flask, render_template, request, redirect,
    url_for, make_response, session
)
from functools import wraps

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "troque-isso-em-producao")
DATABASE_URL = os.environ.get("DATABASE_URL")

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "123456")


def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL não configurada.")
    return psycopg.connect(DATABASE_URL)


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("logado"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped_view


@app.route("/teste")
def teste():
    return "ROTA TESTE OK"


@app.route("/login", methods=["GET", "POST"])
def login():
    erro = None

    if request.method == "POST":
        usuario = request.form["usuario"].strip()
        senha = request.form["senha"].strip()

        if usuario == ADMIN_USER and senha == ADMIN_PASSWORD:
            session["logado"] = True
            return redirect(url_for("inicio"))
        else:
            erro = "Usuário ou senha inválidos"

    return render_template("login.html", erro=erro)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# Página inicial
@app.route("/")
@login_required
def inicio():
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM pedidos")
    total_pedidos = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT COALESCE(SUM(ip.quantidade), 0)
        FROM itens_pedido ip
        JOIN pedidos p ON ip.pedido_id = p.id
        WHERE p.status != 'Cancelado'
    """)
    total_pedido = float(cursor.fetchone()[0] or 0)

    cursor.execute("""
        SELECT COALESCE(SUM(r.quantidade_retirada), 0)
        FROM retiradas r
        JOIN pedidos p ON r.pedido_id = p.id
        WHERE p.status != 'Cancelado'
    """)
    total_retirado = float(cursor.fetchone()[0] or 0)

    conn.close()

    saldo = total_pedido - total_retirado

    return render_template(
        "index.html",
        total_pedidos=total_pedidos,
        total_pedido=total_pedido,
        total_retirado=total_retirado,
        saldo=saldo
    )


# LISTAR CLIENTES
@app.route("/clientes")
@login_required
def clientes():
    busca = request.args.get("busca", "").strip()

    conn = get_conn()
    cursor = conn.cursor()

    if busca:
        cursor.execute("""
            SELECT id, nome, cnpj, telefone, cidade
            FROM clientes
            WHERE nome ILIKE %s
               OR cnpj ILIKE %s
               OR telefone ILIKE %s
               OR cidade ILIKE %s
            ORDER BY nome ASC
        """, (f"%{busca}%", f"%{busca}%", f"%{busca}%", f"%{busca}%"))
    else:
        cursor.execute("""
            SELECT id, nome, cnpj, telefone, cidade
            FROM clientes
            ORDER BY nome ASC
        """)

    dados = cursor.fetchall()
    conn.close()

    clientes_lista = []

    for c in dados:
        clientes_lista.append({
            "id": c[0],
            "nome": c[1],
            "cnpj": c[2],
            "telefone": c[3],
            "cidade": c[4]
        })

    return render_template("clientes.html", clientes=clientes_lista)


# CADASTRAR CLIENTE
@app.route("/cadastrar_cliente", methods=["GET", "POST"])
@login_required
def cadastrar_cliente():
    if request.method == "POST":
        nome = request.form["nome"].strip()
        cnpj = request.form["cnpj"].strip()
        telefone = request.form["telefone"].strip()
        cidade = request.form["cidade"].strip()
        obs = request.form["obs"].strip()

        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO clientes (nome, cnpj, telefone, cidade, observacao)
            VALUES (%s, %s, %s, %s, %s)
        """, (nome, cnpj, telefone, cidade, obs))

        conn.commit()
        conn.close()

        return redirect(url_for("clientes"))

    return render_template("cadastrar_cliente.html")


# EDITAR CLIENTE
@app.route("/editar_cliente/<int:id>", methods=["GET", "POST"])
@login_required
def editar_cliente(id):
    conn = get_conn()
    cursor = conn.cursor()

    if request.method == "POST":
        nome = request.form["nome"].strip()
        cnpj = request.form["cnpj"].strip()
        telefone = request.form["telefone"].strip()
        cidade = request.form["cidade"].strip()
        obs = request.form["obs"].strip()

        cursor.execute("""
            UPDATE clientes
            SET nome = %s, cnpj = %s, telefone = %s, cidade = %s, observacao = %s
            WHERE id = %s
        """, (nome, cnpj, telefone, cidade, obs, id))

        conn.commit()
        conn.close()

        return redirect(url_for("clientes"))

    cursor.execute("""
        SELECT id, nome, cnpj, telefone, cidade, observacao
        FROM clientes
        WHERE id = %s
    """, (id,))
    cliente = cursor.fetchone()
    conn.close()

    if not cliente:
        return "Cliente não encontrado"

    cliente_dados = {
        "id": cliente[0],
        "nome": cliente[1],
        "cnpj": cliente[2],
        "telefone": cliente[3],
        "cidade": cliente[4],
        "obs": cliente[5]
    }

    return render_template("editar_cliente.html", cliente=cliente_dados)


# REGISTRAR PEDIDO
@app.route("/novo_pedido", methods=["GET", "POST"])
@login_required
def novo_pedido():
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT id, nome FROM clientes ORDER BY nome ASC")
    clientes = cursor.fetchall()

    if request.method == "POST":
        try:
            numero_pedido = request.form["numero_pedido"].strip()
            vendedor = request.form["vendedor"].strip()
            cliente_id = int(request.form["cliente"])
            data_pedido = request.form["data_pedido"].strip()
            status = request.form["status"].strip()
            obs = request.form["obs"].strip()

            materiais = request.form.getlist("material[]")
            quantidades = request.form.getlist("quantidade[]")
            valores_unitarios = request.form.getlist("valor_unitario[]")

            cursor.execute("""
                INSERT INTO pedidos
                (numero_pedido, vendedor, cliente_id, data_pedido, status, observacao)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (numero_pedido, vendedor, cliente_id, data_pedido, status, obs))

            pedido_id = cursor.fetchone()[0]

            for material, quantidade, valor_unitario in zip(materiais, quantidades, valores_unitarios):
                material = material.strip()
                quantidade = quantidade.strip()
                valor_unitario = valor_unitario.strip()

                if material and quantidade and valor_unitario:
                    cursor.execute("""
                        INSERT INTO itens_pedido (pedido_id, material, quantidade, valor_unitario)
                        VALUES (%s, %s, %s, %s)
                    """, (
                        pedido_id,
                        material,
                        float(quantidade),
                        float(valor_unitario)
                    ))

            conn.commit()
            conn.close()
            return redirect(url_for("pedidos"))

        except Exception as e:
            conn.rollback()
            conn.close()
            return f"Erro ao salvar pedido: {e}"

    conn.close()
    return render_template("novo_pedido.html", clientes=clientes)


# LISTAR PEDIDOS
@app.route("/pedidos")
@login_required
def pedidos():
    busca = request.args.get("busca", "").strip()

    conn = get_conn()
    cursor = conn.cursor()

    if busca:
        cursor.execute("""
            SELECT
                pedidos.id,
                pedidos.numero_pedido,
                pedidos.vendedor,
                clientes.nome,
                pedidos.data_pedido,
                pedidos.status,
                pedidos.observacao
            FROM pedidos
            JOIN clientes ON pedidos.cliente_id = clientes.id
            WHERE pedidos.numero_pedido ILIKE %s
               OR clientes.nome ILIKE %s
               OR pedidos.vendedor ILIKE %s
            ORDER BY pedidos.id DESC
        """, (f"%{busca}%", f"%{busca}%", f"%{busca}%"))
    else:
        cursor.execute("""
            SELECT
                pedidos.id,
                pedidos.numero_pedido,
                pedidos.vendedor,
                clientes.nome,
                pedidos.data_pedido,
                pedidos.status,
                pedidos.observacao
            FROM pedidos
            JOIN clientes ON pedidos.cliente_id = clientes.id
            ORDER BY pedidos.id DESC
        """)

    dados = cursor.fetchall()

    pedidos_lista = []

    for p in dados:
        pedido_id = p[0]

        cursor.execute("""
            SELECT material, quantidade
            FROM itens_pedido
            WHERE pedido_id = %s
        """, (pedido_id,))
        itens_db = cursor.fetchall()

        itens = []
        total_quantidade = 0

        for item in itens_db:
            itens.append(f"{item[0]} ({item[1]} t)")
            total_quantidade += float(item[1])

        pedidos_lista.append({
            "id": p[0],
            "numero_pedido": p[1],
            "vendedor": p[2],
            "cliente": p[3],
            "data_pedido": p[4],
            "status": p[5],
            "obs": p[6],
            "itens": itens,
            "total_quantidade": total_quantidade
        })

    conn.close()
    return render_template("pedidos.html", pedidos=pedidos_lista)


# PEDIDOS DE UM CLIENTE
@app.route("/cliente/<int:id>/pedidos")
@login_required
def pedidos_do_cliente(id):
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT nome FROM clientes WHERE id = %s", (id,))
    cliente = cursor.fetchone()

    if not cliente:
        conn.close()
        return "Cliente não encontrado"

    nome_cliente = cliente[0]

    cursor.execute("""
        SELECT
            pedidos.id,
            pedidos.numero_pedido,
            pedidos.vendedor,
            pedidos.data_pedido,
            pedidos.status,
            pedidos.observacao
        FROM pedidos
        WHERE pedidos.cliente_id = %s
        ORDER BY pedidos.id DESC
    """, (id,))

    dados = cursor.fetchall()

    pedidos_lista = []

    for p in dados:
        pedido_id = p[0]

        cursor.execute("""
            SELECT material, quantidade
            FROM itens_pedido
            WHERE pedido_id = %s
        """, (pedido_id,))
        itens_db = cursor.fetchall()

        itens = []
        total = 0

        for item in itens_db:
            itens.append(f"{item[0]} ({item[1]} t)")
            total += float(item[1])

        pedidos_lista.append({
            "id": p[0],
            "numero_pedido": p[1],
            "vendedor": p[2],
            "data_pedido": p[3],
            "status": p[4],
            "obs": p[5],
            "itens": itens,
            "quantidade": total
        })

    cursor.execute("""
        SELECT
            ip.material,
            SUM(ip.quantidade) AS total_pedido,
            COALESCE(SUM(r.quantidade_retirada), 0) AS total_retirado
        FROM pedidos p
        JOIN itens_pedido ip ON ip.pedido_id = p.id
        LEFT JOIN retiradas r ON r.item_pedido_id = ip.id
        WHERE p.cliente_id = %s
        AND p.status != 'Cancelado'
        GROUP BY ip.material
        ORDER BY ip.material ASC
    """, (id,))

    resumo_db = cursor.fetchall()
    conn.close()

    resumo_materiais = []

    for r in resumo_db:
        material = r[0]
        total_pedido = float(r[1] or 0)
        total_retirado = float(r[2] or 0)
        falta = total_pedido - total_retirado

        resumo_materiais.append({
            "material": material,
            "total_pedido": total_pedido,
            "total_retirado": total_retirado,
            "falta": falta
        })

    return render_template(
        "pedidos_cliente.html",
        pedidos=pedidos_lista,
        nome_cliente=nome_cliente,
        resumo_materiais=resumo_materiais
    )


# DETALHE DO PEDIDO + RETIRADAS
@app.route("/pedido/<int:id>", methods=["GET", "POST"])
@login_required
def detalhe_pedido(id):
    conn = get_conn()
    cursor = conn.cursor()

    if request.method == "POST":
        item_pedido_id = request.form["item_pedido"]
        data_retirada = request.form["data_retirada"]
        quantidade_retirada = request.form["quantidade_retirada"]
        numero_nota = request.form["numero_nota"]
        observacao = request.form["observacao"]

        cursor.execute("""
            INSERT INTO retiradas (
                pedido_id,
                item_pedido_id,
                data_retirada,
                quantidade_retirada,
                numero_nota,
                observacao
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (id, item_pedido_id, data_retirada, quantidade_retirada, numero_nota, observacao))

        conn.commit()
        conn.close()
        return redirect(url_for("detalhe_pedido", id=id))

    cursor.execute("""
        SELECT
            pedidos.id,
            pedidos.numero_pedido,
            pedidos.vendedor,
            clientes.nome,
            pedidos.data_pedido,
            pedidos.status,
            pedidos.observacao
        FROM pedidos
        JOIN clientes ON pedidos.cliente_id = clientes.id
        WHERE pedidos.id = %s
    """, (id,))

    pedido = cursor.fetchone()

    if not pedido:
        conn.close()
        return "Pedido não encontrado"

    pedido_dados = {
        "id": pedido[0],
        "numero_pedido": pedido[1],
        "vendedor": pedido[2],
        "cliente": pedido[3],
        "data_pedido": pedido[4],
        "status": pedido[5],
        "obs": pedido[6]
    }

    cursor.execute("""
        SELECT id, material, quantidade
        FROM itens_pedido
        WHERE pedido_id = %s
    """, (id,))
    itens_db = cursor.fetchall()

    itens_pedido = []
    total_pedido = 0

    for item in itens_db:
        itens_pedido.append({
            "id": item[0],
            "material": item[1],
            "quantidade": item[2]
        })
        total_pedido += float(item[2])

    resumo_materiais = []

    for item in itens_pedido:
        cursor.execute("""
            SELECT COALESCE(SUM(quantidade_retirada), 0)
            FROM retiradas
            WHERE item_pedido_id = %s
        """, (item["id"],))

        total_retirado_item = cursor.fetchone()[0] or 0
        total_retirado_item = float(total_retirado_item)

        saldo_item = float(item["quantidade"]) - total_retirado_item

        resumo_materiais.append({
            "material": item["material"],
            "quantidade_pedida": float(item["quantidade"]),
            "quantidade_retirada": total_retirado_item,
            "saldo": saldo_item
        })

    cursor.execute("""
        SELECT
            retiradas.id,
            itens_pedido.material,
            retiradas.data_retirada,
            retiradas.quantidade_retirada,
            retiradas.numero_nota,
            retiradas.observacao
        FROM retiradas
        JOIN itens_pedido ON retiradas.item_pedido_id = itens_pedido.id
        WHERE retiradas.pedido_id = %s
        ORDER BY retiradas.id DESC
    """, (id,))

    retiradas_db = cursor.fetchall()
    conn.close()

    retiradas = []
    total_retirado = 0

    for r in retiradas_db:
        retiradas.append({
            "id": r[0],
            "material": r[1],
            "data_retirada": r[2],
            "quantidade": r[3],
            "numero_nota": r[4],
            "obs": r[5]
        })
        total_retirado += float(r[3])

    saldo = total_pedido - total_retirado

    return render_template(
        "detalhe_pedido.html",
        pedido=pedido_dados,
        itens_pedido=itens_pedido,
        total_pedido=total_pedido,
        retiradas=retiradas,
        total_retirado=total_retirado,
        saldo=saldo,
        resumo_materiais=resumo_materiais
    )


# ATUALIZAR STATUS
@app.route("/atualizar_status/<int:id>", methods=["POST"])
@login_required
def atualizar_status(id):
    novo_status = request.form["status"]

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE pedidos
        SET status = %s
        WHERE id = %s
    """, (novo_status, id))

    conn.commit()
    conn.close()

    return redirect(request.referrer or url_for("pedidos"))


@app.route("/relatorios")
@login_required
def relatorios():
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT id, nome FROM clientes ORDER BY nome ASC")
    clientes = cursor.fetchall()

    conn.close()
    return render_template("relatorios.html", clientes=clientes)


@app.route("/relatorios/pdf")
@login_required
def relatorio_pdf():
    cliente_id = request.args.get("cliente")

    conn = get_conn()
    cursor = conn.cursor()

    nome_cliente = "Todos os clientes"

    if cliente_id:
        cursor.execute("SELECT nome FROM clientes WHERE id = %s", (cliente_id,))
        cliente_db = cursor.fetchone()
        if cliente_db:
            nome_cliente = cliente_db[0]

        cursor.execute("""
            SELECT
                p.numero_pedido,
                p.data_pedido,
                ip.material,
                ip.quantidade,
                COALESCE(SUM(r.quantidade_retirada), 0) AS retirado
            FROM pedidos p
            JOIN itens_pedido ip ON ip.pedido_id = p.id
            LEFT JOIN retiradas r ON r.item_pedido_id = ip.id
            WHERE p.cliente_id = %s
            GROUP BY p.id, ip.id
            ORDER BY p.id DESC, ip.material ASC
        """, (cliente_id,))
    else:
        cursor.execute("""
            SELECT
                c.nome,
                p.numero_pedido,
                p.data_pedido,
                ip.material,
                ip.quantidade,
                COALESCE(SUM(r.quantidade_retirada), 0) AS retirado
            FROM pedidos p
            JOIN clientes c ON c.id = p.cliente_id
            JOIN itens_pedido ip ON ip.pedido_id = p.id
            LEFT JOIN retiradas r ON r.item_pedido_id = ip.id
            GROUP BY p.id, ip.id, c.nome
            ORDER BY c.nome ASC, p.id DESC, ip.material ASC
        """)

    dados = cursor.fetchall()
    conn.close()

    response = make_response()
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=relatorio_pedidos.pdf"

    pdf = canvas.Canvas(response.stream, pagesize=A4)
    largura, altura = A4

    y = altura - 40

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(40, y, "Relatório de Pedidos")
    y -= 30

    pdf.setFont("Helvetica", 11)
    pdf.drawString(40, y, f"Cliente: {nome_cliente}")
    y -= 25

    if cliente_id:
        cabecalho = ["Pedido", "Data", "Material", "Pedido (t)", "Retirado (t)", "Saldo (t)"]
        colunas_x = [40, 100, 170, 330, 410, 500]
    else:
        cabecalho = ["Cliente", "Pedido", "Data", "Material", "Pedido (t)", "Retirado (t)", "Saldo (t)"]
        colunas_x = [40, 130, 200, 270, 390, 460, 530]

    pdf.setFont("Helvetica-Bold", 9)
    for i, titulo in enumerate(cabecalho):
        pdf.drawString(colunas_x[i], y, titulo)

    y -= 20
    pdf.line(40, y, largura - 40, y)
    y -= 15

    total_pedido = 0
    total_retirado = 0

    pdf.setFont("Helvetica", 9)

    for linha in dados:
        if cliente_id:
            numero_pedido, data_pedido, material, quantidade, retirado = linha
            saldo = float(quantidade) - float(retirado)

            valores = [
                str(numero_pedido or ""),
                str(data_pedido or ""),
                str(material or ""),
                f"{float(quantidade):.2f}",
                f"{float(retirado):.2f}",
                f"{saldo:.2f}"
            ]
        else:
            cliente_nome, numero_pedido, data_pedido, material, quantidade, retirado = linha
            saldo = float(quantidade) - float(retirado)

            valores = [
                str(cliente_nome or ""),
                str(numero_pedido or ""),
                str(data_pedido or ""),
                str(material or ""),
                f"{float(quantidade):.2f}",
                f"{float(retirado):.2f}",
                f"{saldo:.2f}"
            ]

        total_pedido += float(quantidade)
        total_retirado += float(retirado)

        for i, valor in enumerate(valores):
            texto_quebrado = simpleSplit(valor, "Helvetica", 8, 80)
            texto = texto_quebrado[0] if texto_quebrado else ""
            pdf.drawString(colunas_x[i], y, texto[:25])

        y -= 18

        if y < 60:
            pdf.showPage()
            y = altura - 40
            pdf.setFont("Helvetica", 9)

    saldo_total = total_pedido - total_retirado

    y -= 10
    pdf.line(40, y, largura - 40, y)
    y -= 20

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(40, y, f"Total Pedido: {total_pedido:.2f} t")
    y -= 18
    pdf.drawString(40, y, f"Total Retirado: {total_retirado:.2f} t")
    y -= 18
    pdf.drawString(40, y, f"Saldo Total: {saldo_total:.2f} t")

    pdf.save()
    return response

@app.route("/apagar_pedido/<int:id>", methods=["POST"])
@login_required
def apagar_pedido(id):
    conn = get_conn()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM retiradas WHERE pedido_id = %s", (id,))
        cursor.execute("DELETE FROM itens_pedido WHERE pedido_id = %s", (id,))
        cursor.execute("DELETE FROM pedidos WHERE id = %s", (id,))

        conn.commit()
    except Exception as e:
        conn.rollback()
        return f"Erro ao apagar pedido: {e}"
    finally:
        conn.close()

    return redirect(url_for("pedidos"))


if __name__ == "__main__":
    app.run(debug=True)