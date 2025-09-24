# models.py
from database import db  # Importa o objeto 'db' do nosso novo arquivo
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

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