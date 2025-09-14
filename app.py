import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'scala.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODELOS ---
class Veiculo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    placa = db.Column(db.String(10), unique=True, nullable=False)
    modelo = db.Column(db.String(100), nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    km_inicial = db.Column(db.Integer, nullable=False)
    
    abastecimentos = db.relationship('Abastecimento', backref='veiculo', lazy=True, cascade="all, delete-orphan")
    manutencoes = db.relationship('Manutencao', backref='veiculo', lazy=True, cascade="all, delete-orphan")
    receitas = db.relationship('Receita', backref='veiculo', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Veiculo {self.placa}>'

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

    def __repr__(self):
        return f'<Funcionario {self.nome}>'

class Abastecimento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False)
    litros = db.Column(db.Float, nullable=False)
    valor_total = db.Column(db.Float, nullable=False)
    km_odometro = db.Column(db.Integer, nullable=False)
    id_veiculo = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=False)
    id_funcionario = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)

    def __repr__(self):
        return f'<Abastecimento id={self.id}>'

class Manutencao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False)
    id_veiculo = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=False)
    descricao_servico = db.Column(db.Text, nullable=False)
    custo = db.Column(db.Float, nullable=False)
    km_odometro = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return f'<Manutencao id={self.id}>'

class DespesaGeral(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False)
    descricao = db.Column(db.String(200), nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    valor = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f'<DespesaGeral id={self.id}>'

class Receita(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False)
    descricao = db.Column(db.String(200), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    id_veiculo = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=True) # Opcional

    def __repr__(self):
        return f'<Receita id={self.id}>'

# --- ROTAS DE VEÍCULOS ---
@app.route('/')
def home():
    todos_veiculos = Veiculo.query.order_by(Veiculo.placa).all()
    return render_template('index.html', lista_de_veiculos=todos_veiculos)

@app.route('/veiculo/novo', methods=['GET', 'POST'])
def adicionar_veiculo():
    if request.method == 'POST':
        placa = request.form['placa']
        modelo = request.form['modelo']
        ano = request.form['ano']
        km_inicial = request.form['km_inicial']
        novo_veiculo = Veiculo(placa=placa, modelo=modelo, ano=ano, km_inicial=km_inicial)
        db.session.add(novo_veiculo)
        db.session.commit()
        return redirect(url_for('home'))
    return render_template('adicionar_veiculo.html')

@app.route('/veiculo/editar/<int:id>', methods=['GET', 'POST'])
def editar_veiculo(id):
    veiculo = Veiculo.query.get_or_404(id)
    if request.method == 'POST':
        veiculo.placa = request.form['placa']
        veiculo.modelo = request.form['modelo']
        veiculo.ano = request.form['ano']
        veiculo.km_inicial = request.form['km_inicial']
        db.session.commit()
        return redirect(url_for('home'))
    return render_template('editar_veiculo.html', veiculo=veiculo)

@app.route('/veiculo/excluir/<int:id>', methods=['POST'])
def excluir_veiculo(id):
    veiculo_para_excluir = Veiculo.query.get_or_404(id)
    db.session.delete(veiculo_para_excluir)
    db.session.commit()
    return redirect(url_for('home'))

# --- ROTAS DE FUNCIONÁRIOS ---
@app.route('/funcionarios')
def funcionarios():
    todos_funcionarios = Funcionario.query.order_by(Funcionario.nome).all()
    return render_template('funcionarios.html', lista_de_funcionarios=todos_funcionarios)

@app.route('/funcionario/novo', methods=['GET', 'POST'])
def adicionar_funcionario():
    if request.method == 'POST':
        nome = request.form['nome']
        funcao = request.form['funcao']
        data_admissao = datetime.strptime(request.form['data_admissao'], '%Y-%m-%d').date()
        data_nascimento_str = request.form['data_nascimento']
        data_nascimento = datetime.strptime(data_nascimento_str, '%Y-%m-%d').date() if data_nascimento_str else None
        salario_base = float(request.form['salario_base'])
        ajuda_custo_extra = float(request.form['ajuda_custo_extra']) if request.form['ajuda_custo_extra'] else 0.0
        novo_funcionario = Funcionario(nome=nome, funcao=funcao, data_admissao=data_admissao, data_nascimento=data_nascimento, cnh_numero=request.form['cnh_numero'], cnh_categoria=request.form['cnh_categoria'], salario_base=salario_base, ajuda_custo_extra=ajuda_custo_extra)
        db.session.add(novo_funcionario)
        db.session.commit()
        return redirect(url_for('funcionarios'))
    return render_template('adicionar_funcionario.html')

@app.route('/funcionario/editar/<int:id>', methods=['GET', 'POST'])
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
def excluir_funcionario(id):
    func_para_excluir = Funcionario.query.get_or_404(id)
    db.session.delete(func_para_excluir)
    db.session.commit()
    return redirect(url_for('funcionarios'))

# --- ROTAS DE ABASTECIMENTO ---
@app.route('/abastecimentos')
def abastecimentos():
    lista_abastecimentos = Abastecimento.query.order_by(Abastecimento.data.desc()).all()
    return render_template('abastecimentos.html', abastecimentos=lista_abastecimentos)

@app.route('/abastecimento/novo', methods=['GET', 'POST'])
def adicionar_abastecimento():
    if request.method == 'POST':
        novo_abastecimento = Abastecimento(
            id_veiculo=int(request.form['id_veiculo']),
            id_funcionario=int(request.form['id_funcionario']),
            data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(),
            km_odometro=int(request.form['km_odometro']),
            litros=float(request.form['litros']),
            valor_total=float(request.form['valor_total'])
        )
        db.session.add(novo_abastecimento)
        db.session.commit()
        return redirect(url_for('abastecimentos'))

    veiculos_disp = Veiculo.query.all()
    funcionarios_disp = Funcionario.query.all()
    return render_template('adicionar_abastecimento.html', veiculos=veiculos_disp, funcionarios=funcionarios_disp)

@app.route('/abastecimento/editar/<int:id>', methods=['GET', 'POST'])
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
def excluir_abastecimento(id):
    abast_para_excluir = Abastecimento.query.get_or_404(id)
    db.session.delete(abast_para_excluir)
    db.session.commit()
    return redirect(url_for('abastecimentos'))

# --- ROTAS DE MANUTENÇÕES ---
@app.route('/manutencoes')
def manutencoes():
    lista_manutencoes = Manutencao.query.order_by(Manutencao.data.desc()).all()
    return render_template('manutencoes.html', manutencoes=lista_manutencoes)

@app.route('/manutencao/novo', methods=['GET', 'POST'])
def adicionar_manutencao():
    if request.method == 'POST':
        nova_manutencao = Manutencao(
            id_veiculo=int(request.form['id_veiculo']),
            data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(),
            descricao_servico=request.form['descricao_servico'],
            custo=float(request.form['custo']),
            km_odometro=int(request.form['km_odometro'])
        )
        db.session.add(nova_manutencao)
        db.session.commit()
        return redirect(url_for('manutencoes'))
    
    veiculos_disp = Veiculo.query.all()
    return render_template('adicionar_manutencao.html', veiculos=veiculos_disp)

@app.route('/manutencao/editar/<int:id>', methods=['GET', 'POST'])
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
def excluir_manutencao(id):
    manutencao = Manutencao.query.get_or_404(id)
    db.session.delete(manutencao)
    db.session.commit()
    return redirect(url_for('manutencoes'))

# --- ROTAS DE DESPESAS GERAIS ---
@app.route('/despesas')
def despesas():
    lista_despesas = DespesaGeral.query.order_by(DespesaGeral.data.desc()).all()
    return render_template('despesas.html', despesas=lista_despesas)

@app.route('/despesa/novo', methods=['GET', 'POST'])
def adicionar_despesa():
    if request.method == 'POST':
        nova_despesa = DespesaGeral(
            data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(),
            categoria=request.form['categoria'],
            descricao=request.form['descricao'],
            valor=float(request.form['valor'])
        )
        db.session.add(nova_despesa)
        db.session.commit()
        return redirect(url_for('despesas'))
    return render_template('adicionar_despesa.html')

@app.route('/despesa/editar/<int:id>', methods=['GET', 'POST'])
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
def excluir_despesa(id):
    despesa = DespesaGeral.query.get_or_404(id)
    db.session.delete(despesa)
    db.session.commit()
    return redirect(url_for('despesas'))

# --- ROTAS DE RECEITAS ---
@app.route('/receitas')
def receitas():
    lista_receitas = Receita.query.order_by(Receita.data.desc()).all()
    return render_template('receitas.html', receitas=lista_receitas)

@app.route('/receita/novo', methods=['GET', 'POST'])
def adicionar_receita():
    if request.method == 'POST':
        id_veiculo_form = request.form.get('id_veiculo')
        nova_receita = Receita(
            data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(),
            descricao=request.form['descricao'],
            valor=float(request.form['valor']),
            id_veiculo=int(id_veiculo_form) if id_veiculo_form else None
        )
        db.session.add(nova_receita)
        db.session.commit()
        return redirect(url_for('receitas'))
    
    veiculos_disp = Veiculo.query.all()
    return render_template('adicionar_receita.html', veiculos=veiculos_disp)

@app.route('/receita/editar/<int:id>', methods=['GET', 'POST'])
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
def excluir_receita(id):
    receita = Receita.query.get_or_404(id)
    db.session.delete(receita)
    db.session.commit()
    return redirect(url_for('receitas'))