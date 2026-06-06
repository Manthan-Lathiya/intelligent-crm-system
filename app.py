from functools import wraps
import re
from datetime import datetime
import pandas as pd
import io
import os
from dotenv import load_dotenv
from google import genai
import json
import matplotlib.pyplot as plt
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, Image, TableStyle
from reportlab.lib import colors, pagesizes
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from flask import Flask, render_template, request, redirect, session, flash, jsonify, send_file
from sqlalchemy import func, distinct
from models import db, Users, Clients, Interactions, Projects, Expenses
from services.insight_engine import InsightEngine

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
db.init_app(app)

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

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
        session['user_email'] = user.email
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
@login_required
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
@login_required
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

@app.route('/reports', methods=['GET', 'POST'])
@login_required
def reports():

    if request.method == 'POST':
        user_id = session["user_id"]

        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")

        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        # ==========================
        # DATA AGGREGATION
        # ==========================

        revenue = db.session.query(
            func.coalesce(func.sum(Projects.budget), 0)
        ).filter(
            Projects.p_user_id == user_id,
            Projects.status == "Paid",
            Projects.due_date.between(start, end)
        ).scalar()

        expenses = db.session.query(
            func.coalesce(func.sum(Expenses.amount), 0)
        ).filter(
            Expenses.e_user_id == user_id,
            Expenses.date.between(start, end)
        ).scalar()

        profit = float(revenue) - float(expenses)

        # Monthly revenue
        monthly_data = db.session.query(
            func.date_format(Projects.due_date, "%Y-%m").label("month"),
            func.sum(Projects.budget)
        ).filter(
            Projects.p_user_id == user_id,
            Projects.status == "Paid",
            Projects.due_date.between(start, end)
        ).group_by("month").all()

        df = pd.DataFrame(monthly_data, columns=["month", "revenue"])

        # ==========================
        # TOP CLIENTS
        # ==========================

        top_clients = db.session.query(
            Clients.name,
            func.sum(Projects.budget)
        ).join(
            Projects, Clients.client_id == Projects.p_client_id
        ).filter(
            Projects.status == "Paid",
            Projects.p_user_id == user_id,
            Projects.due_date.between(start, end)
        ).group_by(Clients.name).order_by(
            func.sum(Projects.budget).desc()
        ).limit(5).all()

        # ==========================
        # GENERATE CHART IMAGE
        # ==========================

        img_buffer = io.BytesIO()

        if not df.empty:
            plt.figure(figsize=(6, 4))
            plt.plot(df["month"], df["revenue"])
            plt.title("Revenue Trend")
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(img_buffer, format="png")
            plt.close()

        img_buffer.seek(0)
        
        # ==========================
        # DERIVED ANALYTICS
        # ==========================

        profit_margin = 0
        burn_rate = 0
        risk_level = "Low"

        if revenue > 0:
            profit_margin = round((profit / revenue) * 100, 2)
        else:
            profit_margin = 0

        # Expense to revenue ratio
        expense_ratio = 0
        if revenue > 0:
            expense_ratio = round((expenses / revenue) * 100, 2)

        # Burn risk detection
        if revenue == 0 and expenses > 0:
            risk_level = "High"
        elif profit < 0:
            risk_level = "Medium"
        else:
            risk_level = "Low"

        # Top client dependency
        top_client_ratio = 0
        if top_clients and revenue > 0:
            top_client_ratio = round((float(top_clients[0][1]) / revenue) * 100, 2)


        # ==========================
        # GEMINI AI SUMMARY
        # ==========================

        try:
            prompt = f"""
            You are a senior financial analyst.

            Return ONLY valid JSON.
            Do NOT include markdown.
            Do NOT include explanations.
            Do NOT include formatting.

            Data:
            Period: {start_date} to {end_date}
            Revenue: {revenue}
            Expenses: {expenses}
            Profit: {profit}
            Profit Margin: {profit_margin}%
            Expense Ratio: {expense_ratio}%
            Risk Level: {risk_level}
            Top Client Dependency: {top_client_ratio}%

            Top Clients:
            {top_clients}

            Return JSON with this exact structure:

            {{
                "overall_performance": "...",
                "profitability_comment": "...",
                "risk_assessment": "...",
                "growth_signal": "...",
                "recommendation": "..."
            }}

            Each value must be under 30 words.
            Tone must be professional and calm.
            """



            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )

            raw_text = response.text.strip()

            try:
                summary_json = json.loads(raw_text)
            except:
                summary_json = {
                    "overall_performance": "Unable to generate AI summary.",
                    "profitability_comment": "",
                    "risk_assessment": "",
                    "growth_signal": "",
                    "recommendation": ""
                }

        except Exception as e:
            print(client.models.list())
            print("Gemini Error:", e)  # DO NOT REMOVE THIS
            summary_json = f"""
            Between {start_date} and {end_date},
            revenue was ${revenue}, expenses were ${expenses},
            resulting in profit of ${profit}.
            """



        # ==========================
        # BUILD PDF
        # ==========================

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=pagesizes.A4)
        elements = []
        styles = getSampleStyleSheet()
        
        elements.append(Paragraph("Executive Summary", styles["Heading2"]))
        elements.append(Spacer(1, 10))

        for key, value in summary_json.items():
            elements.append(Paragraph(f"<b>{key.replace('_',' ').title()}:</b> {value}", styles["Normal"]))
            elements.append(Spacer(1, 8))

        # KPI Table
        data = [
            ["Metric", "Value"],
            ["Total Revenue", f"${revenue}"],
            ["Total Expenses", f"${expenses}"],
            ["Profit", f"${profit}"],
        ]

        table = Table(data, colWidths=[200, 200])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('ALIGN',(1,1),(-1,-1),'RIGHT')
        ]))

        elements.append(table)
        elements.append(Spacer(1, 20))

        # Add Chart
        if not df.empty:
            elements.append(Paragraph("Revenue Trend", styles["Heading2"]))
            elements.append(Spacer(1, 10))
            elements.append(Image(img_buffer, width=5*inch, height=3*inch))
            elements.append(Spacer(1, 20))

        # Top Clients Table
        if top_clients:
            elements.append(Paragraph("Top Clients", styles["Heading2"]))
            elements.append(Spacer(1, 10))

            client_data = [["Client", "Revenue"]]
            for c in top_clients:
                client_data.append([c[0], f"${float(c[1])}"])

            client_table = Table(client_data, colWidths=[200, 200])
            client_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
                ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
                ('GRID', (0,0), (-1,-1), 1, colors.black),
                ('ALIGN',(1,1),(-1,-1),'RIGHT')
            ]))

            elements.append(client_table)

        doc.build(elements)

        buffer.seek(0)

        return send_file(
            buffer,
            as_attachment=True,
            download_name="Business_Report.pdf",
            mimetype='application/pdf'
        )

    return render_template("Reports.html")


@app.route("/insights")
@login_required
def insights():

    engine = InsightEngine(session["user_id"])
    data = engine.generate_all()

    # ---- AI Summary ----
    try:
        prompt = f"""
        You are a professional business analyst.

        Generate short 1 sentence summaries for:
        expense_summary
        profit_summary
        dependency_summary
        client_risk_summary

        Return JSON only.

        Expense Insight:
        {data.get("expense")}

        Profit Insight:
        {data.get("profit")}

        Client Dependency Insight:
        {data.get("dependency")}

        Client Risk Insight:
        {data.get("client_risk")}
        """

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        raw = response.text.strip().replace("```json", "").replace("```", "")
        summaries = json.loads(raw)

    except:
        summaries = {
            "expense_summary": "Expense trend evaluated.",
            "profit_summary": "Profit performance analyzed.",
            "dependency_summary": "Revenue concentration calculated.",
            "client_risk_summary": "Client inactivity reviewed."
        }

    return render_template(
        "Insights.html",
        insights=data,
        ai=summaries
    )


@app.route('/settings')
@login_required
def settings():
    return render_template('Settings.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


app.run(debug=True)