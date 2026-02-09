from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('Landing.html')

@app.route('/signup')
def signup():
    return render_template('Signup.html')

@app.route('/login')
def login():
    return render_template('Login.html')

@app.route('/dashboard')
def dashboard():
    return render_template('Dashboard.html')

@app.route('/clients')
def clients():
    return render_template('Clients.html')

@app.route('/client_profile')
def client_profile():
    return render_template('Client_Profile.html')

@app.route('/interactions')
def interactions():
    return render_template('Interactions.html')

@app.route('/projects')
def projects():
    return render_template('Projects.html')

@app.route('/revenue')
def revenue():
    return render_template('Revenue.html')

@app.route('/expenses')
def expenses():
    return render_template('Expenses.html')

@app.route('/analytics')
def analytics():
    return render_template('Analytics.html')

@app.route('/insights')
def insights():
    return render_template('Insights.html')

@app.route('/settings')
def settings():
    return render_template('Settings.html')

app.run(debug=True)