from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("signup/", views.signup_view, name="signup"),
    path("login/", auth_views.LoginView.as_view(template_name="login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("profile/", views.profile_view, name="profile"),
    path("reports/", views.reports_view, name="reports"),
    path("reports/pdf/", views.download_report_pdf, name="download_report_pdf"),
    path("goals/", views.goals_view, name="goals"),
    path("goals/<int:pk>/edit/", views.edit_goal, name="edit_goal"),
    path("goals/<int:pk>/delete/", views.delete_goal, name="delete_goal"),
    path("chat/", views.chat_view, name="chat"),
    path("settings/", views.settings_view, name="settings"),
    path("expenses/add/", views.add_expense, name="add_expense"),
    path("expenses/scan/", views.scan_expense_view, name="scan_expense"),
    path("expenses/export/csv/", views.export_csv_view, name="export_csv"),
    path("expenses/export/excel/", views.export_excel_view, name="export_excel"),
    path("expenses/<int:pk>/edit/", views.edit_expense, name="edit_expense"),
    path("expenses/<int:pk>/delete/", views.delete_expense, name="delete_expense"),
    path("ai-advice/generate/", views.generate_ai_advice_view, name="generate_ai_advice"),
]
