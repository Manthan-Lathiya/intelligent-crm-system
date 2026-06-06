from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Users(db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.Date, nullable=False)
    
class Clients(db.Model):
    __tablename__ = 'clients'
    client_id = db.Column(db.Integer, nullable=False, primary_key=True)
    c_user_id = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    company_name = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    total_revenue = db.Column(db.Float, nullable=False)
    projects_count = db.Column(db.Integer, nullable=False)
    avatar = db.Column(db.String(2), nullable=False)
    
class Interactions(db.Model):
    __tablename__ = 'interactions'
    interaction_id = db.Column(db.Integer, nullable=False, primary_key=True)
    i_user_id = db.Column(db.Integer, nullable=False)
    i_client_id = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(10), nullable=False)
    subject = db.Column(db.String(50), nullable=False)
    summary = db.Column(db.String(200), nullable=False)
    date = db.Column(db.Date, nullable=False)
    
class Projects(db.Model):
    __tablename__ = 'projects'
    project_id = db.Column(db.Integer, primary_key=True)
    p_user_id = db.Column(db.Integer, nullable=False)
    p_client_id = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(10), nullable=False)
    budget = db.Column(db.Float, nullable=False)
    spent = db.Column(db.Float, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=False)

class Expenses(db.Model):
    __tablename__ = "expenses"
    expense_id = db.Column(db.Integer, primary_key=True)
    e_user_id = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    