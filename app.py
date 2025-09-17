import os
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, extract
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from weasyprint import HTML

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
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME') # Pega da variável de ambiente
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD') # Pega da variável de ambiente

db = SQLAlchemy(app)
mail = Mail(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Por favor, faça o login para acessar esta página."
login_manager.login_message_category = "info"

# --- DECORADOR DE ADMIN ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Você não tem permissão para acessar esta página.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# --- MODELOS ---
class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    role = db.Column(db.String(80), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))

class Veiculo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    placa = db.Column(db.String(10), unique=True, nullable=False)
    modelo = db.Column(db.String(100), nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    km_inicial = db.Column(db.Integer, nullable=False)
    abastecimentos = db.relationship('Abastecimento', backref='veiculo', lazy=True, cascade="all, delete-orphan")
    manutencoes = db.relationship('Manutencao', backref='veiculo', lazy=True, cascade="all, delete-orphan")
    receitas = db.relationship('Receita', backref='veiculo', lazy=True, cascade="all, delete-orphan")

class Funcionario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    funcao = db.Column(db.String(50), nullable=False)
    data_admissao = db.Column(db.Date, nullable=False)
    data_nascimento = db.Column(db.Date, nullable=True)
    cnh_numero = db.Column(db.String(20), nullable=True)
    cnh_categoria = db.Column(db.String(5), nullable=True)
    salario_base = db.Column(db.Float, nullable=False)
    ajuda_custo_extra = db.Column(db.Float, nullable=True, default=0.0)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    abastecimentos = db.relationship('Abastecimento', backref='funcionario', lazy=True)

class Abastecimento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False)
    litros = db.Column(db.Float, nullable=False)
    valor_total = db.Column(db.Float, nullable=False)
    km_odometro = db.Column(db.Integer, nullable=False)
    id_veiculo = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=False)
    id_funcionario = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)

class Manutencao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False)
    id_veiculo = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=False)
    descricao_servico = db.Column(db.Text, nullable=False)
    custo = db.Column(db.Float, nullable=False)
    km_odometro = db.Column(db.Integer, nullable=False)

class DespesaGeral(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False)
    descricao = db.Column(db.String(200), nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    valor = db.Column(db.Float, nullable=False)

class Receita(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False)
    descricao = db.Column(db.String(200), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    id_veiculo = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=True)

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

# --- ROTAS PRINCIPAIS E RELATÓRIOS ---
@app.route('/')
@login_required
def home():
    ano_selecionado = request.args.get('ano', default=datetime.now().year, type=int)
    mes_selecionado = request.args.get('mes', default=datetime.now().month, type=int)
    total_veiculos = Veiculo.query.count()
    total_funcionarios = Funcionario.query.filter_by(ativo=True).count()
    gastos_por_categoria = {}
    total_combustivel = db.session.query(func.sum(Abastecimento.valor_total)).filter(extract('year', Abastecimento.data) == ano_selecionado, extract('month', Abastecimento.data) == mes_selecionado).scalar() or 0.0
    if total_combustivel > 0: gastos_por_categoria['Combustível'] = round(total_combustivel, 2)
    total_manutencao = db.session.query(func.sum(Manutencao.custo)).filter(extract('year', Manutencao.data) == ano_selecionado, extract('month', Manutencao.data) == mes_selecionado).scalar() or 0.0
    if total_manutencao > 0: gastos_por_categoria['Manutenção'] = round(total_manutencao, 2)
    despesas_agrupadas = db.session.query(DespesaGeral.categoria, func.sum(DespesaGeral.valor)).filter(extract('year', DespesaGeral.data) == ano_selecionado, extract('month', DespesaGeral.data) == mes_selecionado).group_by(DespesaGeral.categoria).all()
    for categoria, total in despesas_agrupadas:
        if total and total > 0: gastos_por_categoria[categoria] = round(gastos_por_categoria.get(categoria, 0) + total, 2)
    total_gastos_mes = sum(gastos_por_categoria.values())
    total_receitas_mes = db.session.query(func.sum(Receita.valor)).filter(extract('year', Receita.data) == ano_selecionado, extract('month', Receita.data) == mes_selecionado).scalar() or 0.0
    saldo_mes = round(total_receitas_mes - total_gastos_mes, 2)
    chart_labels = list(gastos_por_categoria.keys())
    chart_data = list(gastos_por_categoria.values())
    anos_disponiveis = range(datetime.now().year, 2019, -1)
    return render_template('index.html', total_veiculos=total_veiculos, total_funcionarios=total_funcionarios, total_gastos_mes=round(total_gastos_mes, 2), total_receitas_mes=round(total_receitas_mes, 2), saldo_mes=saldo_mes, chart_labels=chart_labels, chart_data=chart_data, anos_disponiveis=anos_disponiveis, ano_selecionado=ano_selecionado, mes_selecionado=mes_selecionado)

def calcular_dados_relatorio(ano, mes):
    total_receitas = db.session.query(func.sum(Receita.valor)).filter(extract('year', Receita.data) == ano, extract('month', Receita.data) == mes).scalar() or 0.0
    total_combustivel = db.session.query(func.sum(Abastecimento.valor_total)).filter(extract('year', Abastecimento.data) == ano, extract('month', Abastecimento.data) == mes).scalar() or 0.0
    total_manutencao = db.session.query(func.sum(Manutencao.custo)).filter(extract('year', Manutencao.data) == ano, extract('month', Manutencao.data) == mes).scalar() or 0.0
    total_despesas_gerais = db.session.query(func.sum(DespesaGeral.valor)).filter(extract('year', DespesaGeral.data) == ano, extract('month', DespesaGeral.data) == mes).scalar() or 0.0
    total_despesas = total_combustivel + total_manutencao + total_despesas_gerais
    saldo_final = total_receitas - total_despesas
    return {"mes": mes, "ano": ano, "total_receitas": total_receitas, "total_despesas": total_despesas, "saldo_final": saldo_final, "total_combustivel": total_combustivel, "total_manutencao": total_manutencao, "total_despesas_gerais": total_despesas_gerais}

@app.route('/relatorios', methods=['GET', 'POST'])
@login_required
@admin_required
def relatorios():
    if request.method == 'POST':
        mes = request.form.get('mes')
        ano = request.form.get('ano')
        return redirect(url_for('visualizar_relatorio', ano=ano, mes=mes))
    anos_disponiveis = range(datetime.now().year, 2019, -1)
    return render_template('relatorios.html', anos_disponiveis=anos_disponiveis)

@app.route('/relatorio/visualizar/<int:ano>/<int:mes>')
@login_required
@admin_required
def visualizar_relatorio(ano, mes):
    dados = calcular_dados_relatorio(ano, mes)
    return render_template('relatorio_visualizar.html', dados=dados)

@app.route('/relatorio/pdf/<int:ano>/<int:mes>')
@login_required
@admin_required
def gerar_relatorio_pdf(ano, mes):
    dados = calcular_dados_relatorio(ano, mes)
    html = render_template('relatorio_template.html', dados=dados)
    pdf = HTML(string=html).write_pdf()
    return Response(pdf, mimetype='application/pdf', headers={'Content-Disposition': f'attachment;filename=relatorio_{mes}_{ano}.pdf'})

@app.route('/relatorio/enviar', methods=['POST'])
@login_required
@admin_required
def enviar_relatorio_email():
    try:
        email_destinatario = request.form.get('email')
        ano = request.form.get('ano')
        mes = request.form.get('mes')
        dados = calcular_dados_relatorio(int(ano), int(mes))
        corpo_email = render_template('relatorio_template.html', dados=dados)
        msg = Message(subject=f"Relatório Mensal Scala Gestão - {mes}/{ano}", sender=app.config['MAIL_USERNAME'], recipients=[email_destinatario])
        msg.html = corpo_email
        mail.send(msg)
        flash(f'Relatório enviado com sucesso para {email_destinatario}!', 'success')
    except Exception as e:
        flash(f'Ocorreu um erro ao enviar o e-mail: {e}', 'danger')
    return redirect(url_for('relatorios'))

# --- ROTAS DA FROTA ---
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
        novo_veiculo = Veiculo(placa=request.form['placa'], modelo=request.form['modelo'], ano=int(request.form['ano']), km_inicial=int(request.form['km_inicial']))
        db.session.add(novo_veiculo)
        db.session.commit()
        return redirect(url_for('frota'))
    return render_template('adicionar_veiculo.html')

@app.route('/veiculo/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_veiculo(id):
    veiculo = Veiculo.query.get_or_404(id)
    if request.method == 'POST':
        veiculo.placa = request.form['placa']
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
    veiculo = Veiculo.query.get_or_404(id)
    db.session.delete(veiculo)
    db.session.commit()
    return redirect(url_for('frota'))

# --- ROTAS DE FUNCIONÁRIOS ---
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
        novo_funcionario = Funcionario(nome=request.form['nome'], funcao=request.form['funcao'], data_admissao=datetime.strptime(request.form['data_admissao'], '%Y-%m-%d').date(), data_nascimento=datetime.strptime(request.form['data_nascimento'], '%Y-%m-%d').date() if request.form['data_nascimento'] else None, cnh_numero=request.form['cnh_numero'], cnh_categoria=request.form['cnh_categoria'], salario_base=float(request.form['salario_base']), ajuda_custo_extra=float(request.form['ajuda_custo_extra']) if request.form['ajuda_custo_extra'] else 0.0)
        db.session.add(novo_funcionario)
        db.session.commit()
        return redirect(url_for('funcionarios'))
    return render_template('adicionar_funcionario.html')

@app.route('/funcionario/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_funcionario(id):
    func = Funcionario.query.get_or_404(id)
    if request.method == 'POST':
        func.nome = request.form['nome']
        func.funcao = request.form['funcao']
        func.data_admissao = datetime.strptime(request.form['data_admissao'], '%Y-%m-%d').date()
        data_nascimento_str = request.form['data_nascimento']
        func.data_nascimento = datetime.strptime(data_nascimento_str, '%Y-%m-%d').date() if data_nascimento_str else None
        func.cnh_numero = request.form['cnh_numero']
        func.cnh_categoria = request.form['cnh_categoria']
        func.salario_base = float(request.form['salario_base'])
        func.ajuda_custo_extra = float(request.form['ajuda_custo_extra']) if request.form['ajuda_custo_extra'] else 0.0
        db.session.commit()
        return redirect(url_for('funcionarios'))
    return render_template('editar_funcionario.html', funcionario=func)

@app.route('/funcionario/excluir/<int:id>', methods=['POST'])
@login_required
@admin_required
def excluir_funcionario(id):
    func = Funcionario.query.get_or_404(id)
    db.session.delete(func)
    db.session.commit()
    return redirect(url_for('funcionarios'))

# --- ROTAS DE ABASTECIMENTO ---
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
        novo_abastecimento = Abastecimento(id_veiculo=int(request.form['id_veiculo']), id_funcionario=int(request.form['id_funcionario']), data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(), km_odometro=int(request.form['km_odometro']), litros=float(request.form['litros']), valor_total=float(request.form['valor_total']))
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
    abast = Abastecimento.query.get_or_404(id)
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
    abast = Abastecimento.query.get_or_404(id)
    db.session.delete(abast)
    db.session.commit()
    return redirect(url_for('abastecimentos'))

# --- ROTAS DE MANUTENÇÕES ---
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
        nova_manutencao = Manutencao(id_veiculo=int(request.form['id_veiculo']), data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(), descricao_servico=request.form['descricao_servico'], custo=float(request.form['custo']), km_odometro=int(request.form['km_odometro']))
        db.session.add(nova_manutencao)
        db.session.commit()
        return redirect(url_for('manutencoes'))
    veiculos_disp = Veiculo.query.all()
    return render_template('adicionar_manutencao.html', veiculos=veiculos_disp)

@app.route('/manutencao/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_manutencao(id):
    manutencao = Manutencao.query.get_or_404(id)
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
    manutencao = Manutencao.query.get_or_404(id)
    db.session.delete(manutencao)
    db.session.commit()
    return redirect(url_for('manutencoes'))

# --- ROTAS DE DESPESAS GERAIS ---
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
        nova_despesa = DespesaGeral(data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(), categoria=request.form['categoria'], descricao=request.form['descricao'], valor=float(request.form['valor']))
        db.session.add(nova_despesa)
        db.session.commit()
        return redirect(url_for('despesas'))
    return render_template('adicionar_despesa.html')

@app.route('/despesa/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_despesa(id):
    despesa = DespesaGeral.query.get_or_404(id)
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
    despesa = DespesaGeral.query.get_or_404(id)
    db.session.delete(despesa)
    db.session.commit()
    return redirect(url_for('despesas'))

# --- ROTAS DE RECEITAS ---
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
        nova_receita = Receita(data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(), descricao=request.form['descricao'], valor=float(request.form['valor']), id_veiculo=int(id_veiculo_form) if id_veiculo_form else None)
        db.session.add(nova_receita)
        db.session.commit()
        return redirect(url_for('receitas'))
    veiculos_disp = Veiculo.query.all()
    return render_template('adicionar_receita.html', veiculos=veiculos_disp)

@app.route('/receita/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_receita(id):
    receita = Receita.query.get_or_404(id)
    if request.method == 'POST':
        id_veiculo_form = request.form.get('id_veiculo')
        receita.data = datetime.strptime(request.form['data'], '%Y-%m-%d').date()
        receita.descricao = request.form['descricao']
        receita.valor = float(request.form['valor'])
        receita.id_veiculo = int(id_veiculo_form) if id_veiculo_form else None
        db.session.commit()
        return redirect(url_for('receitas'))
    veiculos_disp = Veiculo.query.all()
    return render_template('editar_receita.html', receita=receita, veiculos=veiculos_disp)

@app.route('/receita/excluir/<int:id>', methods=['POST'])
@login_required
@admin_required
def excluir_receita(id):
    receita = Receita.query.get_or_404(id)
    db.session.delete(receita)
    db.session.commit()
    return redirect(url_for('receitas'))