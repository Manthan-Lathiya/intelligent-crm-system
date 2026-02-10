from functools import wraps
import re
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, distinct

app = Flask(__name__)
app.secret_key = "9065425f976cf3a967617fd8b1aeb8e92ef1f3b9a792861e93fb2dcfdfd8cd4a"
app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://root:0202@localhost/smart_crm_system"
db = SQLAlchemy(app)

class Users(db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.String(50), nullable=False)
    
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
    date = db.Column(db.String(50), nullable=False)
    
class Projects(db.Model):
    __tablename__ = 'projects'
    project_id = db.Column(db.Integer, primary_key=True)
    p_user_id = db.Column(db.Integer, nullable=False)
    p_client_id = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(10), nullable=False)
    budget = db.Column(db.Integer, nullable=False)
    spent = db.Column(db.Integer, nullable=False)
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
    
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return wrap

def is_valid_email(email):
    EMAIL_REGEX = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(EMAIL_REGEX, email)

def is_strong_password(password):
    if len(password) < 8:
        return "Password must be at least 8 characters"

    if not re.search(r"[A-Z]", password):
        return "Password must contain an uppercase letter"

    if not re.search(r"[a-z]", password):
        return "Password must contain a lowercase letter"

    if not re.search(r"[0-9]", password):
        return "Password must contain a number"

    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return "Password must contain a special character"

    if " " in password:
        return "Password must not contain spaces"

    return None  # password is valid
    
@app.route('/')
def home():
    return render_template('Landing.html')

@app.route('/signup', methods = ['GET', 'POST'])
def signup():
    if(request.method == 'POST'):
        user_name = request.form.get('user_name')
        user_email =  request.form.get('user_email')
        user_password = request.form.get('user_password')
        
        if len(user_name) < 2:
            flash("Name too short")
            return redirect('/signup')

        if not is_valid_email(user_email):
            flash("Invalid email address")
            return redirect('/signup')

        password_error = is_strong_password(user_password)
        if password_error:
            flash(password_error)
            return redirect('/signup')

        if Users.query.filter_by(email=user_email).first():
            flash("Email already registered")
            return redirect('/signup')
        
        entry = Users(name = user_name, email = user_email, password = user_password, created_at=datetime.now())
        db.session.add(entry)
        db.session.commit()
        return redirect('/login')
    return render_template('Signup.html')

@app.route('/login', methods = ['GET', 'POST'])
def login():
    if(request.method == 'POST'):
        user_email =  request.form.get('user_email')
        user_password = request.form.get('user_password')
        
        user = Users.query.filter_by(email=user_email).first()
        if ((not user) or (user.password != user_password)):
            flash("Invalid email or password")
            return redirect('/login')

        session['user_id'] = user.user_id
        session['user_name'] = user.name
        print(session)
        return redirect('/dashboard')
    return render_template('Login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session["user_id"]

    # Revenue (Paid projects only)
    total_revenue = db.session.query(
        func.coalesce(func.sum(Projects.budget), 0)
    ).filter(
        Projects.p_user_id == user_id,
        Projects.status == "Paid"
    ).scalar()

    # Total expenses
    total_expenses = db.session.query(
        func.coalesce(func.sum(Expenses.amount), 0)
    ).filter(
        Expenses.e_user_id == user_id
    ).scalar()

    # Profit (derived)
    profit = (float)(total_revenue) - total_expenses

    # Total clients
    total_clients = Clients.query.filter_by(
        c_user_id=user_id
    ).count()

    # Paying clients
    paying_clients = db.session.query(
        distinct(Projects.p_client_id)
    ).filter(
        Projects.p_user_id == user_id,
        Projects.status == "Paid"
    ).count()

    # Pending projects (not paid yet)
    pending_projects = Projects.query.filter(
        Projects.p_user_id == user_id,
        Projects.status != "Paid"
    ).count()

    return render_template(
        "Dashboard.html",
        total_revenue=total_revenue,
        total_expenses=total_expenses,
        profit=profit,
        total_clients=total_clients,
        paying_clients=paying_clients,
        pending_projects=pending_projects
    )

@app.route('/clients')
@login_required
def clients():
    all_clients = Clients.query.filter_by(c_user_id=session['user_id']).all()
    return render_template('Clients.html', clients = all_clients)

@app.route("/add_client", methods=["POST"])
def add_client():
    data = request.json
    a = data['name'].split(' ')
    avatar = ''
    for i in a:
        avatar += i[0].capitalize()
    
    client = Clients(
        c_user_id=session['user_id'],  
        name=data["name"],
        email=data["email"],
        phone=data["phone"],
        company_name=data["company"],
        status=data["status"],
        total_revenue=data["revenue"],
        projects_count=0,
        avatar=avatar
    )

    db.session.add(client)
    db.session.commit()

    return jsonify({"success": True})


@app.route("/client/<int:client_id>")
@login_required
def client_profile(client_id):
    user_id = session["user_id"]

    # Client (security check included)
    client = Clients.query.filter_by(
        client_id=client_id,
        c_user_id=user_id
    ).first_or_404()

    # Projects of this client
    projects = Projects.query.filter_by(
        p_client_id=client_id,
        p_user_id=user_id
    ).order_by(Projects.due_date.desc()).all()

    # Total revenue from this client (PAID only)
    revenue = db.session.query(
        func.coalesce(func.sum(Projects.budget), 0)
    ).filter(
        Projects.p_client_id == client_id,
        Projects.p_user_id == user_id,
        Projects.status == "Paid"
    ).scalar()

    # Interactions
    interactions = Interactions.query.filter_by(
        i_client_id=client_id,
        i_user_id=user_id
    ).order_by(Interactions.date.desc()).limit(5).all()

    return render_template(
        "Client_Profile.html",
        client=client,
        projects=projects,
        revenue=revenue,
        interactions=interactions
    )


@app.route('/interactions')
@login_required
def interactions():
    clients = Clients.query.filter_by(c_user_id=session['user_id']).all()
    interactions = Interactions.query.order_by(
        Interactions.date.desc()
    ).all()

    return render_template(
        "Interactions.html",
        clients=clients,
        interactions=interactions
    )

@app.route("/add_interaction", methods=["POST"])
def add_interaction():
    data = request.get_json()

    interaction = Interactions(
        i_user_id=session["user_id"],
        i_client_id=data["client_id"],
        type=data["type"],
        subject=data["subject"],
        summary=data["summary"],
        date=data["date"]
    )

    db.session.add(interaction)
    db.session.commit()

    return jsonify({"success": True})

@app.route('/projects')
@login_required
def projects():
    clients = Clients.query.filter_by(c_user_id=session['user_id']).all()
    projects = Projects.query.filter_by(
        p_user_id=session['user_id']
    ).order_by(Projects.due_date).all()

    return render_template(
        "Projects.html",
        projects=projects,
        clients=clients
    )

@app.route("/add_project", methods=["POST"])
def add_project():
    data = request.get_json()

    project = Projects(
        p_user_id=session["user_id"],
        p_client_id=data["client_id"],
        name=data["name"],
        status=data["status"],
        budget=data["budget"],
        spent=data["spent"],
        start_date=data["start_date"],
        due_date=data["due_date"]
    )

    db.session.add(project)
    db.session.commit()

    return jsonify({"success": True})


@app.route('/revenue')
@login_required
def revenue():
    user_id = session["user_id"]
    clients = Clients.query.filter_by(c_user_id=session['user_id']).all()
    # Total revenue
    total_revenue = db.session.query(
        func.coalesce(func.sum(Projects.budget), 0)
    ).filter(
        Projects.p_user_id == user_id,
        Projects.status == "Paid"
    ).scalar()

    # Monthly revenue
    monthly = db.session.query(
        func.date_format(Projects.due_date, "%Y-%m").label("month"),
        func.sum(Projects.budget)
    ).filter(
        Projects.p_user_id == user_id,
        Projects.status == "Paid"
    ).group_by("month").order_by("month").all()

    # Paid projects list
    paid_projects = Projects.query.filter_by(
        p_user_id=user_id,
        status="Paid"
    ).order_by(Projects.due_date.desc()).all()
    
    active_clients = Clients.query.filter_by(
        c_user_id=session["user_id"],
        status='Active'
    ).count()


    return render_template(
        "Revenue.html",
        clients=clients,
        active_clients=active_clients,
        total_revenue=total_revenue,
        monthly=monthly,
        projects=paid_projects
    )

@app.route("/expenses")
@login_required
def expenses():
    user_id = session["user_id"]

    total_expenses = db.session.query(
        func.coalesce(func.sum(Expenses.amount), 0)
    ).filter(
        Expenses.e_user_id == user_id
    ).scalar()

    all_expenses = Expenses.query.filter_by(
        e_user_id=user_id
    ).order_by(Expenses.date.desc()).all()

    return render_template(
        "Expenses.html",
        total_expenses=total_expenses,
        expenses=all_expenses
    )

@app.route("/add_expense", methods=["POST"])
@login_required
def add_expense():
    data = request.get_json()

    expense = Expenses(
        e_user_id=session["user_id"],
        title=data["title"],
        category=data["category"],
        amount=data["amount"],
        date=data["date"]
    )

    db.session.add(expense)
    db.session.commit()

    return jsonify({"success": True})

@app.route('/analytics')
@login_required
def analytics():
    return render_template('Analytics.html')

@app.route("/api/analytics/revenue")
@login_required
def analytics_revenue():
    data = db.session.query(
        func.date_format(Projects.due_date, "%Y-%m").label("month"),
        func.sum(Projects.budget)
    ).filter(
        Projects.p_user_id == session["user_id"],
        Projects.status == "Paid"
    ).group_by("month").order_by("month").all()

    return jsonify({
        "labels": [d.month for d in data],
        "values": [float(d[1]) for d in data]
    })

@app.route("/api/analytics/expenses")
@login_required
def analytics_expenses():
    data = db.session.query(
        func.date_format(Expenses.date, "%Y-%m").label("month"),
        func.sum(Expenses.amount)
    ).filter(
        Expenses.e_user_id == session["user_id"]
    ).group_by("month").order_by("month").all()

    return jsonify({
        "labels": [d.month for d in data],
        "values": [float(d[1]) for d in data]
    })

@app.route("/api/analytics/profit")
@login_required
def analytics_profit():
    r_month = func.date_format(Projects.due_date, "%Y-%m").label("month")
    revenue = dict(
        db.session.query(
            r_month,
            func.sum(Projects.budget)
        ).filter(
            Projects.p_user_id == session["user_id"],
            Projects.status == "Paid"
        ).group_by(r_month).order_by(r_month).all()
    )

    e_month = func.date_format(Expenses.date, "%Y-%m").label("month")
    expenses = dict(
        db.session.query(
            e_month,
            func.sum(Expenses.amount)
        ).filter(
            Expenses.e_user_id == session["user_id"]
        ).group_by(e_month).order_by(e_month).all()
    )

    months = sorted(set(revenue.keys()) | set(expenses.keys()))

    profit = [
        float(revenue.get(m, 0)) - float(expenses.get(m, 0))
        for m in months
    ]

    return jsonify({
        "labels": months,
        "values": profit
    })

@app.route("/api/analytics/revenue_by_client")
@login_required
def analytics_revenue_by_client():
    data = db.session.query(
        Clients.name,
        func.sum(Projects.budget)
    ).join(
        Projects, Clients.client_id == Projects.p_client_id
    ).filter(
        Projects.status == "Paid",
        Projects.p_user_id == session["user_id"]
    ).group_by(Clients.name).order_by(
        func.sum(Projects.budget).desc()
    ).limit(5).all()

    return jsonify({
        "labels": [d[0] for d in data],
        "values": [float(d[1]) for d in data]
    })


@app.route('/insights')
@login_required
def insights():
    return render_template('Insights.html')

@app.route('/settings')
@login_required
def settings():
    return render_template('Settings.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

app.run(debug=True)