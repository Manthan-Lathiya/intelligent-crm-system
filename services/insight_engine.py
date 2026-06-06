from datetime import date, timedelta
from sqlalchemy import func
from models import db, Clients, Interactions, Projects, Expenses

class InsightEngine :
    
    def __init__(self, user_id):
        self.user_id = user_id
    
    def client_risk_algorithm(self):

        today = date.today()
        cutoff_60 = today - timedelta(days=60)
        cutoff_30 = today - timedelta(days=30)

        clients = Clients.query.filter_by(
            c_user_id=self.user_id
        ).all()

        results = []

        for c in clients:

            # ---- Inactivity ----
            last_interaction = db.session.query(
                func.max(Interactions.date)
            ).filter(
                Interactions.i_client_id == c.client_id
            ).scalar()

            inactivity_days = 999
            if last_interaction:
                inactivity_days = (today - last_interaction).days

            inactivity_score = 1 if inactivity_days > 60 else 0

            # ---- Revenue in last 60 days ----
            recent_revenue = db.session.query(
                func.coalesce(func.sum(Projects.budget), 0)
            ).filter(
                Projects.p_client_id == c.client_id,
                Projects.status == "Paid",
                Projects.due_date >= cutoff_60
            ).scalar()

            revenue_score = 1 if recent_revenue == 0 else 0

            # ---- Interaction in last 30 days ----
            recent_interactions = db.session.query(
                func.count(Interactions.interaction_id)
            ).filter(
                Interactions.i_client_id == c.client_id,
                Interactions.date >= cutoff_30
            ).scalar()

            interaction_score = 1 if recent_interactions == 0 else 0

            # ---- Final Weighted Score ----
            risk_score = (
                0.4 * inactivity_score +
                0.3 * revenue_score +
                0.3 * interaction_score
            )

            # Priority logic
            if risk_score >= 0.7:
                priority = "high"
            elif risk_score >= 0.4:
                priority = "medium"
            else:
                priority = "low"

            # Only show medium & high risk clients
            if priority != "low":
                results.append({
                    "client_name": c.name,
                    "days_inactive": inactivity_days,
                    "risk_score": round(risk_score, 2),
                    "priority": priority
                })

        return results

    def expense_spike_algorithm(self):
        column = func.date_format(Expenses.date, "%Y-%m").label("month")
        data = db.session.query(
            func.date_format(Expenses.date, "%Y-%m"),
            func.sum(Expenses.amount)
        ).filter(
            Expenses.e_user_id == self.user_id
        ).group_by(column).order_by(column).all()

        if len(data) < 2:
            return {
                "metric": "expense_growth",
                "status": "not_enough_data"
            }

        last_month, last_value = data[-1]
        prev_month, prev_value = data[-2]

        last_value = float(last_value)
        prev_value = float(prev_value)

        if prev_value == 0:
            change = 0
        else:
            change = ((last_value - prev_value) / prev_value) * 100

        if change > 40:
            priority = "high"
        elif change > 15:
            priority = "medium"
        else:
            priority = "low"

        return {
            "metric": "expense_growth",
            "last_month": last_month,
            "previous_month": prev_month,
            "last_value": last_value,
            "previous_value": prev_value,
            "percentage_change": round(change, 2),
            "direction": "increase" if change > 0 else "decrease",
            "priority": priority
        }

    def profit_health_algorithm(self):
        revenue = db.session.query(
            func.coalesce(func.sum(Projects.budget), 0)
        ).filter(
            Projects.p_user_id == self.user_id,
            Projects.status == "Paid"
        ).scalar()

        expenses = db.session.query(
            func.coalesce(func.sum(Expenses.amount), 0)
        ).filter(
            Expenses.e_user_id == self.user_id
        ).scalar()

        if revenue == 0:
            return {
                "metric": "profit_margin",
                "status": "no_revenue"
            }

        profit = revenue - expenses
        margin = (profit / revenue) * 100

        if margin < 10:
            priority = "high"
        elif margin < 25:
            priority = "medium"
        else:
            priority = "low"

        return {
            "metric": "profit_margin",
            "total_revenue": float(revenue),
            "total_expenses": float(expenses),
            "profit": float(profit),
            "margin_percent": round(margin, 2),
            "priority": priority
        }

    def client_dependency(self):
        
        total_revenue = db.session.query(
            func.coalesce(func.sum(Projects.budget), 0)
        ).filter(
            Projects.p_user_id == self.user_id,
            Projects.status == "Paid"
        ).scalar()

        if total_revenue == 0:
            return {
                "metric": "client_dependency",
                "status": "no_revenue",
                "priority": "low"
            }

        top_client = db.session.query(
            Clients.name,
            func.sum(Projects.budget)
        ).join(
            Projects, Clients.client_id == Projects.p_client_id
        ).filter(
            Projects.p_user_id == self.user_id,
            Projects.status == "Paid"
        ).group_by(Clients.name).order_by(
            func.sum(Projects.budget).desc()
        ).first()

        top_client_name = top_client[0]
        top_client_revenue = float(top_client[1])

        dependency_percent = (top_client_revenue / float(total_revenue)) * 100

        # Priority logic
        if dependency_percent > 60:
            priority = "high"
        elif dependency_percent > 35:
            priority = "medium"
        else:
            priority = "low"

        return {
            "metric": "client_dependency",
            "top_client_name": top_client_name,
            "top_client_revenue": top_client_revenue,
            "total_revenue": float(total_revenue),
            "dependency_percent": round(dependency_percent, 2),
            "priority": priority
        }

    def generate_all(self):
        return {
            "expense": self.expense_spike_algorithm(),
            "profit": self.profit_health_algorithm(),
            "dependency": self.client_dependency(),
            "client_risk": self.client_risk_algorithm()
        }
