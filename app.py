# app.py
import os
import io
import base64
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, Response
from sqlalchemy import func, extract
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message

# Bibliotecas para o PDF e Gráficos
from weasyprint import HTML
import matplotlib
matplotlib.use('Agg') # Usa um backend não-interativo para o Matplotlib
import matplotlib.pyplot as plt

# Importações locais
from database import db
from models import Usuario, Veiculo, Funcionario, Abastecimento, Manutencao, DespesaGeral, Receita

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
# CONFIGURAÇÕES
app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-dificil-de-adivinhar'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'scala.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# CONFIGURAÇÕES PARA E-MAIL
app.config['MAIL_SERVER'] = 'smtp.googlemail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')

# Inicializa as extensões com o app
db.init_app(app)
mail = Mail(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Por favor, faça o login para acessar esta página."
login_manager.login_message_category = "info"

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))

# --- FUNÇÕES AUXILIARES PARA GRÁFICOS ---
def gerar_grafico_pizza(labels, data, titulo):
    if not data: return None
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.pie(data, labels=labels, autopct='%1.1f%%', startangle=90, colors=plt.cm.Paired.colors)
    ax.axis('equal')
    ax.set_title(titulo)
    
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    return img_base64

def gerar_grafico_barras(labels, data, titulo):
    if not data or all(v == 0 for v in data): return None
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = ['#28a745', '#dc3545'] # Verde para receita, vermelho para despesa
    ax.bar(labels, data, color=colors)
    ax.set_ylabel('Valor (R$)')
    ax.set_title(titulo)

    for i, v in enumerate(data):
        ax.text(i, v, f'R$ {v:.2f}', ha='center', va='bottom')

    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)

    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    return img_base64

# --- DECORADOR DE ADMIN ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Você não tem permissão para acessar esta página.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# --- ROTAS DE AUTENTICAÇÃO ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        user = Usuario.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('Usuário ou senha inválidos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você foi desconectado com sucesso.', 'success')
    return redirect(url_for('login'))

# --- ROTAS PRINCIPAIS ---
@app.route('/')
@login_required
def home():
    ano_atual = datetime.now().year
    mes_atual = datetime.now().month
    gastos_por_categoria = {}
    total_combustivel = db.session.query(func.sum(Abastecimento.valor_total)).filter(extract('year', Abastecimento.data) == ano_atual, extract('month', Abastecimento.data) == mes_atual).scalar() or 0.0
    if total_combustivel > 0: gastos_por_categoria['Combustível'] = round(total_combustivel, 2)
    total_manutencao = db.session.query(func.sum(Manutencao.custo)).filter(extract('year', Manutencao.data) == ano_atual, extract('month', Manutencao.data) == mes_atual).scalar() or 0.0
    if total_manutencao > 0: gastos_por_categoria['Manutenção'] = round(total_manutencao, 2)
    despesas_agrupadas = db.session.query(DespesaGeral.categoria, func.sum(DespesaGeral.valor)).filter(extract('year', DespesaGeral.data) == ano_atual, extract('month', DespesaGeral.data) == mes_atual).group_by(DespesaGeral.categoria).all()
    for categoria, total in despesas_agrupadas:
        if total and total > 0: gastos_por_categoria[categoria] = round(gastos_por_categoria.get(categoria, 0) + total, 2)
    total_gastos_mes = sum(gastos_por_categoria.values())
    total_receitas_mes = db.session.query(func.sum(Receita.valor)).filter(extract('year', Receita.data) == ano_atual, extract('month', Receita.data) == mes_atual).scalar() or 0.0
    saldo_mes = round(total_receitas_mes - total_gastos_mes, 2)
    chart_labels = list(gastos_por_categoria.keys())
    chart_data = list(gastos_por_categoria.values())
    return render_template('index.html', total_veiculos=Veiculo.query.count(), total_funcionarios=Funcionario.query.filter_by(ativo=True).count(), total_gastos_mes=round(total_gastos_mes, 2), total_receitas_mes=round(total_receitas_mes, 2), saldo_mes=saldo_mes, chart_labels=chart_labels, chart_data=chart_data)

# --- ROTAS DE RELATÓRIOS (NOVO SISTEMA) ---
@app.route('/relatorios', methods=['GET', 'POST'])
@login_required
def relatorios():
    if request.method == 'POST':
        try:
            data_inicio_str = request.form['data_inicio']
            data_fim_str = request.form['data_fim']
            
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()

            # --- COLETA DE DADOS ---
            # 1. Resumo Geral
            total_receitas = db.session.query(func.sum(Receita.valor)).filter(Receita.data.between(data_inicio, data_fim)).scalar() or 0.0
            total_combustivel = db.session.query(func.sum(Abastecimento.valor_total)).filter(Abastecimento.data.between(data_inicio, data_fim)).scalar() or 0.0
            total_manutencao = db.session.query(func.sum(Manutencao.custo)).filter(Manutencao.data.between(data_inicio, data_fim)).scalar() or 0.0
            total_despesas_gerais = db.session.query(func.sum(DespesaGeral.valor)).filter(DespesaGeral.data.between(data_inicio, data_fim)).scalar() or 0.0
            total_despesas = total_combustivel + total_manutencao + total_despesas_gerais
            
            resumo_financeiro = {
                "total_receitas": total_receitas,
                "total_despesas": total_despesas,
                "saldo": total_receitas - total_despesas
            }

            # 2. Dados para Gráficos
            gastos_por_categoria = {}
            if total_combustivel > 0: gastos_por_categoria['Combustível'] = total_combustivel
            if total_manutencao > 0: gastos_por_categoria['Manutenção'] = total_manutencao
            despesas_gerais_agrupadas = db.session.query(DespesaGeral.categoria, func.sum(DespesaGeral.valor)).filter(DespesaGeral.data.between(data_inicio, data_fim)).group_by(DespesaGeral.categoria).all()
            for categoria, total in despesas_gerais_agrupadas:
                if total and total > 0: gastos_por_categoria[categoria] = gastos_por_categoria.get(categoria, 0) + total
            
            # 3. Detalhamento de Despesas e Receitas
            despesas_combustivel_detalhe = Abastecimento.query.filter(Abastecimento.data.between(data_inicio, data_fim)).all()
            despesas_manutencao_detalhe = Manutencao.query.filter(Manutencao.data.between(data_inicio, data_fim)).all()
            despesas_gerais_detalhe = DespesaGeral.query.filter(DespesaGeral.data.between(data_inicio, data_fim)).all()
            
            lista_despesas_unificada = []
            for item in despesas_combustivel_detalhe:
                lista_despesas_unificada.append({'data': item.data, 'tipo': 'Combustível', 'descricao': f"{item.litros:.2f}L", 'veiculo_placa': item.veiculo.placa, 'valor': item.valor_total})
            for item in despesas_manutencao_detalhe:
                 lista_despesas_unificada.append({'data': item.data, 'tipo': 'Manutenção', 'descricao': item.descricao_servico, 'veiculo_placa': item.veiculo.placa, 'valor': item.custo})
            for item in despesas_gerais_detalhe:
                 lista_despesas_unificada.append({'data': item.data, 'tipo': item.categoria, 'descricao': item.descricao, 'veiculo_placa': None, 'valor': item.valor})
            lista_despesas_unificada.sort(key=lambda x: x['data'])
            receitas_detalhe = Receita.query.filter(Receita.data.between(data_inicio, data_fim)).order_by(Receita.data).all()
            detalhamento_geral = { "despesas": lista_despesas_unificada, "receitas": receitas_detalhe }

            # 4. Detalhamento por Veículo
            todos_veiculos = Veiculo.query.all()
            detalhamento_por_veiculo = []
            for veiculo in todos_veiculos:
                v_abastecimentos = Abastecimento.query.filter(Abastecimento.id_veiculo == veiculo.id, Abastecimento.data.between(data_inicio, data_fim)).all()
                v_manutencoes = Manutencao.query.filter(Manutencao.id_veiculo == veiculo.id, Manutencao.data.between(data_inicio, data_fim)).all()
                v_receitas = Receita.query.filter(Receita.id_veiculo == veiculo.id, Receita.data.between(data_inicio, data_fim)).all()

                if v_abastecimentos or v_manutencoes or v_receitas:
                    detalhamento_por_veiculo.append({
                        "placa": veiculo.placa, "modelo": veiculo.modelo,
                        "total_combustivel": sum(a.valor_total for a in v_abastecimentos),
                        "total_manutencao": sum(m.custo for m in v_manutencoes),
                        "total_receita": sum(r.valor for r in v_receitas),
                        "abastecimentos": v_abastecimentos, "manutencoes": v_manutencoes
                    })

            # --- GERAÇÃO DOS GRÁFICOS ---
            grafico_gastos = gerar_grafico_pizza(labels=list(gastos_por_categoria.keys()), data=list(gastos_por_categoria.values()), titulo='Distribuição de Gastos por Categoria')
            grafico_receita_despesa = gerar_grafico_barras(labels=['Receitas', 'Despesas'], data=[resumo_financeiro['total_receitas'], resumo_financeiro['total_despesas']], titulo='Comparativo: Receitas vs. Despesas')

            # --- RENDERIZAÇÃO DO HTML PARA O PDF ---
            html_renderizado = render_template('relatorio_pdf.html',
                data_inicio=data_inicio.strftime('%d/%m/%Y'), data_fim=data_fim.strftime('%d/%m/%Y'),
                data_emissao=datetime.now().strftime('%d/%m/%Y'), resumo=resumo_financeiro,
                detalhamento=detalhamento_geral, detalhamento_veiculos=detalhamento_por_veiculo,
                grafico_gastos_categoria=grafico_gastos, grafico_receita_despesa=grafico_receita_despesa)
            
            pdf = HTML(string=html_renderizado).write_pdf()
            return Response(pdf, mimetype='application/pdf', headers={'Content-Disposition': 'attachment;filename=relatorio_scala_gestao.pdf'})

        except Exception as e:
            print(f"--- ERRO AO GERAR RELATÓRIO: {e} ---")
            flash("Ocorreu um erro ao gerar o relatório. Verifique as datas e tente novamente.", "danger")
            return redirect(url_for('relatorios'))

    return render_template('relatorios.html')


@app.route('/relatorio/enviar')
@login_required
@admin_required
def enviar_relatorio():
    # Esta rota agora é secundária, mas a mantemos caso queira usá-la.
    try:
        hoje = datetime.today()
        primeiro_dia_mes_atual = hoje.replace(day=1)
        ultimo_dia_mes_passado = primeiro_dia_mes_atual - timedelta(days=1)
        ano_relatorio, mes_relatorio = ultimo_dia_mes_passado.year, ultimo_dia_mes_passado.month

        total_receitas = db.session.query(func.sum(Receita.valor)).filter(extract('year', Receita.data) == ano_relatorio, extract('month', Receita.data) == mes_relatorio).scalar() or 0.0
        total_combustivel = db.session.query(func.sum(Abastecimento.valor_total)).filter(extract('year', Abastecimento.data) == ano_relatorio, extract('month', Abastecimento.data) == mes_relatorio).scalar() or 0.0
        total_manutencao = db.session.query(func.sum(Manutencao.custo)).filter(extract('year', Manutencao.data) == ano_relatorio, extract('month', Manutencao.data) == mes_relatorio).scalar() or 0.0
        total_despesas_gerais = db.session.query(func.sum(DespesaGeral.valor)).filter(extract('year', DespesaGeral.data) == ano_relatorio, extract('month', DespesaGeral.data) == mes_relatorio).scalar() or 0.0
        total_despesas = total_combustivel + total_manutencao + total_despesas_gerais
        saldo_final = total_receitas - total_despesas

        corpo_email = render_template('email_template.html', mes=mes_relatorio, ano=ano_relatorio, total_receitas=total_receitas, total_despesas=total_despesas, saldo_final=saldo_final)
        msg = Message(subject=f"Relatório Mensal Scala Gestão - {mes_relatorio}/{ano_relatorio}", sender=app.config['MAIL_USERNAME'], recipients=[app.config['MAIL_USERNAME']])
        msg.html = corpo_email
        mail.send(msg)
        flash('Relatório por e-mail enviado com sucesso!', 'success')
    except Exception as e:
        print(f"--- ERRO AO ENVIAR E-MAIL: {e} ---")
        flash('Ocorreu um erro ao enviar o e-mail. Verifique as credenciais e as configurações de segurança da sua conta. Mais detalhes no terminal.', 'danger')
    return redirect(url_for('home'))


# --- ROTAS DE CRUD (FROTA, FUNCIONÁRIOS, ETC.) ---
# O restante das suas rotas de CRUD continua aqui, sem alterações.
# Cole todas as suas rotas a partir de '# --- ROTAS DA FROTA ---' aqui.
@app.route('/frota')
@login_required
def frota():
    todos_veiculos = Veiculo.query.order_by(Veiculo.placa).all()
    return render_template('frota.html', lista_de_veiculos=todos_veiculos)

@app.route('/veiculo/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def adicionar_veiculo():
    if request.method == 'POST':
        novo_veiculo = Veiculo(placa=request.form['placa'].upper(), modelo=request.form['modelo'], ano=int(request.form['ano']), km_inicial=int(request.form['km_inicial']))
        db.session.add(novo_veiculo)
        db.session.commit()
        return redirect(url_for('frota'))
    return render_template('adicionar_veiculo.html')

@app.route('/veiculo/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_veiculo(id):
    veiculo = db.session.get(Veiculo, id)
    if not veiculo: return redirect(url_for('frota'))
    if request.method == 'POST':
        veiculo.placa = request.form['placa'].upper()
        veiculo.modelo = request.form['modelo']
        veiculo.ano = int(request.form['ano'])
        veiculo.km_inicial = int(request.form['km_inicial'])
        db.session.commit()
        return redirect(url_for('frota'))
    return render_template('editar_veiculo.html', veiculo=veiculo)

@app.route('/veiculo/excluir/<int:id>', methods=['POST'])
@login_required
@admin_required
def excluir_veiculo(id):
    veiculo = db.session.get(Veiculo, id)
    if veiculo:
        db.session.delete(veiculo)
        db.session.commit()
    return redirect(url_for('frota'))

@app.route('/funcionarios')
@login_required
def funcionarios():
    todos_funcionarios = Funcionario.query.order_by(Funcionario.nome).all()
    return render_template('funcionarios.html', lista_de_funcionarios=todos_funcionarios)

@app.route('/funcionario/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def adicionar_funcionario():
    if request.method == 'POST':
        novo_funcionario = Funcionario(
            nome=request.form['nome'], funcao=request.form['funcao'],
            data_admissao=datetime.strptime(request.form['data_admissao'], '%Y-%m-%d').date(),
            data_nascimento=datetime.strptime(request.form['data_nascimento'], '%Y-%m-%d').date() if request.form.get('data_nascimento') else None,
            cnh_numero=request.form['cnh_numero'], cnh_categoria=request.form['cnh_categoria'],
            salario_base=float(request.form['salario_base']),
            ajuda_custo_extra=float(request.form.get('ajuda_custo_extra', 0.0) or 0.0)
        )
        db.session.add(novo_funcionario)
        db.session.commit()
        return redirect(url_for('funcionarios'))
    return render_template('adicionar_funcionario.html')

@app.route('/funcionario/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_funcionario(id):
    func = db.session.get(Funcionario, id)
    if not func: return redirect(url_for('funcionarios'))
    if request.method == 'POST':
        func.nome = request.form['nome']
        func.funcao = request.form['funcao']
        func.data_admissao = datetime.strptime(request.form['data_admissao'], '%Y-%m-%d').date()
        data_nascimento_str = request.form.get('data_nascimento')
        func.data_nascimento = datetime.strptime(data_nascimento_str, '%Y-%m-%d').date() if data_nascimento_str else None
        func.cnh_numero = request.form['cnh_numero']
        func.cnh_categoria = request.form['cnh_categoria']
        func.salario_base = float(request.form['salario_base'])
        func.ajuda_custo_extra = float(request.form.get('ajuda_custo_extra', 0.0) or 0.0)
        db.session.commit()
        return redirect(url_for('funcionarios'))
    return render_template('editar_funcionario.html', funcionario=func)

@app.route('/funcionario/excluir/<int:id>', methods=['POST'])
@login_required
@admin_required
def excluir_funcionario(id):
    func = db.session.get(Funcionario, id)
    if func:
        db.session.delete(func)
        db.session.commit()
    return redirect(url_for('funcionarios'))

@app.route('/abastecimentos')
@login_required
def abastecimentos():
    lista_abastecimentos = Abastecimento.query.order_by(Abastecimento.data.desc()).all()
    return render_template('abastecimentos.html', abastecimentos=lista_abastecimentos)

@app.route('/abastecimento/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def adicionar_abastecimento():
    if request.method == 'POST':
        novo_abastecimento = Abastecimento(
            id_veiculo=int(request.form['id_veiculo']), id_funcionario=int(request.form['id_funcionario']),
            data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(),
            km_odometro=int(request.form['km_odometro']), litros=float(request.form['litros']), valor_total=float(request.form['valor_total'])
        )
        db.session.add(novo_abastecimento)
        db.session.commit()
        return redirect(url_for('abastecimentos'))
    veiculos_disp = Veiculo.query.all()
    funcionarios_disp = Funcionario.query.all()
    return render_template('adicionar_abastecimento.html', veiculos=veiculos_disp, funcionarios=funcionarios_disp)

@app.route('/abastecimento/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_abastecimento(id):
    abast = db.session.get(Abastecimento, id)
    if not abast: return redirect(url_for('abastecimentos'))
    if request.method == 'POST':
        abast.id_veiculo = int(request.form['id_veiculo'])
        abast.id_funcionario = int(request.form['id_funcionario'])
        abast.data = datetime.strptime(request.form['data'], '%Y-%m-%d').date()
        abast.km_odometro = int(request.form['km_odometro'])
        abast.litros = float(request.form['litros'])
        abast.valor_total = float(request.form['valor_total'])
        db.session.commit()
        return redirect(url_for('abastecimentos'))
    veiculos_disp = Veiculo.query.all()
    funcionarios_disp = Funcionario.query.all()
    return render_template('editar_abastecimento.html', abastecimento=abast, veiculos=veiculos_disp, funcionarios=funcionarios_disp)

@app.route('/abastecimento/excluir/<int:id>', methods=['POST'])
@login_required
@admin_required
def excluir_abastecimento(id):
    abast = db.session.get(Abastecimento, id)
    if abast:
        db.session.delete(abast)
        db.session.commit()
    return redirect(url_for('abastecimentos'))

@app.route('/manutencoes')
@login_required
def manutencoes():
    lista_manutencoes = Manutencao.query.order_by(Manutencao.data.desc()).all()
    return render_template('manutencoes.html', manutencoes=lista_manutencoes)

@app.route('/manutencao/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def adicionar_manutencao():
    if request.method == 'POST':
        nova_manutencao = Manutencao(
            id_veiculo=int(request.form['id_veiculo']), data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(),
            descricao_servico=request.form['descricao_servico'], custo=float(request.form['custo']),
            km_odometro=int(request.form['km_odometro'])
        )
        db.session.add(nova_manutencao)
        db.session.commit()
        return redirect(url_for('manutencoes'))
    veiculos_disp = Veiculo.query.all()
    return render_template('adicionar_manutencao.html', veiculos=veiculos_disp)

@app.route('/manutencao/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_manutencao(id):
    manutencao = db.session.get(Manutencao, id)
    if not manutencao: return redirect(url_for('manutencoes'))
    if request.method == 'POST':
        manutencao.id_veiculo = int(request.form['id_veiculo'])
        manutencao.data = datetime.strptime(request.form['data'], '%Y-%m-%d').date()
        manutencao.descricao_servico = request.form['descricao_servico']
        manutencao.custo = float(request.form['custo'])
        manutencao.km_odometro = int(request.form['km_odometro'])
        db.session.commit()
        return redirect(url_for('manutencoes'))
    veiculos_disp = Veiculo.query.all()
    return render_template('editar_manutencao.html', manutencao=manutencao, veiculos=veiculos_disp)

@app.route('/manutencao/excluir/<int:id>', methods=['POST'])
@login_required
@admin_required
def excluir_manutencao(id):
    manutencao = db.session.get(Manutencao, id)
    if manutencao:
        db.session.delete(manutencao)
        db.session.commit()
    return redirect(url_for('manutencoes'))

@app.route('/despesas')
@login_required
def despesas():
    lista_despesas = DespesaGeral.query.order_by(DespesaGeral.data.desc()).all()
    return render_template('despesas.html', despesas=lista_despesas)

@app.route('/despesa/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def adicionar_despesa():
    if request.method == 'POST':
        nova_despesa = DespesaGeral(
            data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(), categoria=request.form['categoria'],
            descricao=request.form['descricao'], valor=float(request.form['valor'])
        )
        db.session.add(nova_despesa)
        db.session.commit()
        return redirect(url_for('despesas'))
    return render_template('adicionar_despesa.html')

@app.route('/despesa/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_despesa(id):
    despesa = db.session.get(DespesaGeral, id)
    if not despesa: return redirect(url_for('despesas'))
    if request.method == 'POST':
        despesa.data = datetime.strptime(request.form['data'], '%Y-%m-%d').date()
        despesa.categoria = request.form['categoria']
        despesa.descricao = request.form['descricao']
        despesa.valor = float(request.form['valor'])
        db.session.commit()
        return redirect(url_for('despesas'))
    return render_template('editar_despesa.html', despesa=despesa)

@app.route('/despesa/excluir/<int:id>', methods=['POST'])
@login_required
@admin_required
def excluir_despesa(id):
    despesa = db.session.get(DespesaGeral, id)
    if despesa:
        db.session.delete(despesa)
        db.session.commit()
    return redirect(url_for('despesas'))

@app.route('/receitas')
@login_required
def receitas():
    lista_receitas = Receita.query.order_by(Receita.data.desc()).all()
    return render_template('receitas.html', receitas=lista_receitas)

@app.route('/receita/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def adicionar_receita():
    if request.method == 'POST':
        id_veiculo_form = request.form.get('id_veiculo')
        nova_receita = Receita(
            data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(), descricao=request.form['descricao'],
            valor=float(request.form['valor']),
            id_veiculo=int(id_veiculo_form) if id_veiculo_form and id_veiculo_form.isdigit() else None
        )
        db.session.add(nova_receita)
        db.session.commit()
        return redirect(url_for('receitas'))
    veiculos_disp = Veiculo.query.all()
    return render_template('adicionar_receita.html', veiculos=veiculos_disp)

@app.route('/receita/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_receita(id):
    receita = db.session.get(Receita, id)
    if not receita: return redirect(url_for('receitas'))
    if request.method == 'POST':
        id_veiculo_form = request.form.get('id_veiculo')
        receita.data = datetime.strptime(request.form['data'], '%Y-%m-%d').date()
        receita.descricao = request.form['descricao']
        receita.valor = float(request.form['valor'])
        receita.id_veiculo = int(id_veiculo_form) if id_veiculo_form and id_veiculo_form.isdigit() else None
        db.session.commit()
        return redirect(url_for('receitas'))
    veiculos_disp = Veiculo.query.all()
    return render_template('editar_receita.html', receita=receita, veiculos=veiculos_disp)

@app.route('/receita/excluir/<int:id>', methods=['POST'])
@login_required
@admin_required
def excluir_receita(id):
    receita = db.session.get(Receita, id)
    if receita:
        db.session.delete(receita)
        db.session.commit()
    return redirect(url_for('receitas'))


if __name__ == '__main__':
    app.run(debug=True)