# init_db.py
from app import app
from database import db
from models import Usuario
from werkzeug.security import generate_password_hash

def criar_usuarios_iniciais():
    with app.app_context():
        print("Criando todas as tabelas do banco de dados...")
        db.create_all()
        print("Tabelas criadas.")

        # Cria usuário ADMIN se não existir
        if not Usuario.query.filter_by(username='admin').first():
            print("Criando usuário 'admin'...")
            hashed_password = generate_password_hash('admin', method='pbkdf2:sha256') # Senha: admin
            admin_user = Usuario(username='admin', password_hash=hashed_password, role='admin')
            db.session.add(admin_user)
            print("Usuário 'admin' criado com sucesso! (Senha: admin)")
        else:
            print("Usuário 'admin' já existe.")

        # Cria usuário VISITANTE se não existir
        if not Usuario.query.filter_by(username='visitante').first():
            print("Criando usuário 'visitante'...")
            hashed_password = generate_password_hash('visitante', method='pbkdf2:sha256') # Senha: visitante
            visitor_user = Usuario(username='visitante', password_hash=hashed_password, role='visitante')
            db.session.add(visitor_user)
            print("Usuário 'visitante' criado com sucesso! (Senha: visitante)")
        else:
            print("Usuário 'visitante' já existe.")
        
        db.session.commit()

if __name__ == '__main__':
    criar_usuarios_iniciais()