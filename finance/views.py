import json
from datetime import datetime

from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    BudgetForm,
    ChatForm,
    ExpenseForm,
    ExpenseScanForm,
    ProfileForm,
    ProfileSettingsForm,
    SavingGoalForm,
    SignUpForm,
    StyledPasswordChangeForm,
    UserUpdateForm,
)
from .models import AIAdvice, ChatMessage, Expense, SavingGoal
from .services import (
    API_FAILURE_MESSAGE,
    EMPTY_RESPONSE_MESSAGE,
    MISSING_KEY_MESSAGE,
    QUOTA_MESSAGE,
    award_achievements,
    build_monthly_report,
    build_pdf_report,
    calculate_goal_suggestions,
    detect_recurring_expenses,
    export_expenses_csv,
    export_expenses_excel,
    generate_ai_advice,
    generate_chat_reply,
    generate_investment_suggestions,
    generate_report_summary,
    get_budget_snapshot,
    get_monthly_trend,
    get_spending_patterns,
    get_weekly_spending,
    scan_receipt,
    sync_smart_notifications,
)


def _build_ai_status(latest_advice):
    if not latest_advice:
        return {
            "label": "Not generated yet",
            "badge_class": "bg-secondary-subtle text-secondary-emphasis",
            "message": "Generate advice to get a quick student-friendly spending summary.",
        }

    advice_text = latest_advice.advice_text
    if advice_text == MISSING_KEY_MESSAGE:
        return {
            "label": "Setup needed",
            "badge_class": "bg-warning-subtle text-warning-emphasis",
            "message": "Add a valid OpenAI API key in your environment or .env file, then restart the server.",
        }
    if advice_text == QUOTA_MESSAGE:
        return {
            "label": "Quota issue",
            "badge_class": "bg-danger-subtle text-danger-emphasis",
            "message": "Your OpenAI project has no remaining credits or billing is inactive.",
        }
    if advice_text in {API_FAILURE_MESSAGE, EMPTY_RESPONSE_MESSAGE}:
        return {
            "label": "Temporarily unavailable",
            "badge_class": "bg-warning-subtle text-warning-emphasis",
            "message": "The request reached the AI service but did not return usable advice. Check the server logs for the exact error.",
        }
    return {
        "label": "Live AI advice",
        "badge_class": "bg-success-subtle text-success-emphasis",
        "message": "The latest advice was generated successfully from your current monthly data.",
    }


def home(request):
    return render(request, "home.html")


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your account was created successfully.")
        return redirect("dashboard")
    return render(request, "signup.html", {"form": form})


@login_required
def dashboard(request):
    snapshot = get_budget_snapshot(request.user)
    budget = snapshot["budget"]

    if request.method == "POST":
        budget_form = BudgetForm(request.POST, instance=budget)
        if budget_form.is_valid():
            budget_form.save()
            messages.success(request, "Monthly budget updated successfully.")
            return redirect("dashboard")
    else:
        budget_form = BudgetForm(instance=budget)

    expenses = Expense.objects.filter(user=request.user)
    advice_queryset = AIAdvice.objects.filter(user=request.user)
    latest_advice = advice_queryset.first()
    recent_advices = advice_queryset[:5]
    notifications = sync_smart_notifications(request.user)
    recurring_expenses, recurring_total = detect_recurring_expenses(request.user)
    goals = SavingGoal.objects.filter(user=request.user)[:4]
    goal_suggestions = calculate_goal_suggestions(request.user)[:3]
    achievements = award_achievements(request.user)
    spending_patterns = get_spending_patterns(request.user)
    investments = generate_investment_suggestions(request.user)
    monthly_trend = get_monthly_trend(request.user)
    weekly_spending = get_weekly_spending(request.user)

    context = {
        "expenses": expenses[:10],
        "total_spending": snapshot["total_spending"],
        "budget": budget,
        "remaining_budget": snapshot["remaining"],
        "budget_form": budget_form,
        "alerts": [notification.message for notification in notifications],
        "notifications": notifications,
        "latest_advice": latest_advice,
        "recent_advices": recent_advices,
        "ai_status": _build_ai_status(latest_advice),
        "chart_labels": json.dumps(list(snapshot["category_data"].keys()) or ["No data"]),
        "chart_values": json.dumps(list(snapshot["category_data"].values()) or [0]),
        "line_labels": json.dumps(monthly_trend["labels"]),
        "line_values": json.dumps(monthly_trend["values"]),
        "weekly_labels": json.dumps(weekly_spending["labels"]),
        "weekly_values": json.dumps(weekly_spending["values"]),
        "recurring_expenses": recurring_expenses,
        "recurring_total": recurring_total,
        "goals": goals,
        "goal_suggestions": goal_suggestions,
        "achievements": achievements,
        "spending_patterns": spending_patterns,
        "investment_suggestions": investments,
    }
    return render(request, "dashboard.html", context)


@login_required
def profile_view(request):
    profile = request.user.profile
    snapshot = get_budget_snapshot(request.user)
    expenses = Expense.objects.filter(user=request.user)

    user_form = UserUpdateForm(request.POST or None, instance=request.user)
    profile_form = ProfileForm(request.POST or None, request.FILES or None, instance=profile)

    if request.method == "POST" and user_form.is_valid() and profile_form.is_valid():
        user_form.save()
        profile_form.save()
        messages.success(request, "Profile updated successfully.")
        return redirect("profile")

    context = {
        "user_form": user_form,
        "profile_form": profile_form,
        "total_expenses_count": expenses.count(),
        "total_expenses_sum": expenses.aggregate(total=Sum("amount"))["total"] or 0,
        "monthly_budget": snapshot["budget"].monthly_limit,
        "remaining_balance": snapshot["remaining"],
        "highest_category": snapshot["highest_category"],
    }
    return render(request, "profile.html", context)


@login_required
def add_expense(request):
    form = ExpenseForm(request.POST or None)
    scan_form = ExpenseScanForm()
    if request.method == "POST" and form.is_valid():
        expense = form.save(commit=False)
        expense.user = request.user
        expense.save()
        messages.success(request, "Expense added successfully.")
        return redirect("dashboard")
    return render(request, "add_expense.html", {"form": form, "scan_form": scan_form, "page_title": "Add Expense"})


@login_required
def scan_expense_view(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    scan_form = ExpenseScanForm(request.POST, request.FILES)
    expense_form = ExpenseForm()
    if scan_form.is_valid():
        scan = scan_form.save(commit=False)
        scan.user = request.user
        scan.save()
        result = scan_receipt(scan.image)
        parsed_date = timezone.localdate()
        if result.get("date"):
            try:
                parsed_date = datetime.strptime(str(result["date"]), "%Y-%m-%d").date()
            except ValueError:
                parsed_date = timezone.localdate()
        initial = {
            "amount": result.get("amount"),
            "date": parsed_date,
            "category": result.get("category") if result.get("category") in dict(Expense.CATEGORY_CHOICES) else "Other",
            "description": result.get("description"),
        }
        expense_form = ExpenseForm(initial=initial)
        scan.extracted_amount = result.get("amount")
        scan.extracted_date = parsed_date
        scan.extracted_category = result.get("category") or "Other"
        scan.extracted_description = result.get("description")
        scan.save()
        messages.info(request, "Receipt processed. Review the autofilled fields before saving.")
    else:
        messages.warning(request, "Please upload a valid bill image.")
    return render(request, "add_expense.html", {"form": expense_form, "scan_form": scan_form, "page_title": "Add Expense"})


@login_required
def edit_expense(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    form = ExpenseForm(request.POST or None, instance=expense)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Expense updated successfully.")
        return redirect("dashboard")
    return render(request, "add_expense.html", {"form": form, "scan_form": ExpenseScanForm(), "page_title": "Edit Expense"})


@login_required
def delete_expense(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    if request.method == "POST":
        expense.delete()
        messages.success(request, "Expense deleted successfully.")
    return redirect("dashboard")


@login_required
def generate_ai_advice_view(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    advice_text = generate_ai_advice(request.user)
    AIAdvice.objects.create(user=request.user, advice_text=advice_text)
    if advice_text in {MISSING_KEY_MESSAGE, QUOTA_MESSAGE, API_FAILURE_MESSAGE, EMPTY_RESPONSE_MESSAGE}:
        messages.warning(request, advice_text)
    else:
        messages.success(request, "AI advice generated successfully.")
    return redirect("dashboard")


@login_required
def reports_view(request):
    report_data = build_monthly_report(request.user)
    ai_summary = generate_report_summary(request.user, report_data)
    return render(request, "reports.html", {"report": report_data, "ai_summary": ai_summary})


@login_required
def download_report_pdf(request):
    report_data = build_monthly_report(request.user)
    pdf_bytes = build_pdf_report(report_data, request.user.username)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="finsmart-monthly-report.pdf"'
    return response


@login_required
def goals_view(request):
    form = SavingGoalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        goal = form.save(commit=False)
        goal.user = request.user
        goal.save()
        messages.success(request, "Savings goal created successfully.")
        return redirect("goals")
    goals = SavingGoal.objects.filter(user=request.user)
    return render(request, "goals.html", {"form": form, "goals": goals, "goal_suggestions": calculate_goal_suggestions(request.user)})


@login_required
def edit_goal(request, pk):
    goal = get_object_or_404(SavingGoal, pk=pk, user=request.user)
    form = SavingGoalForm(request.POST or None, instance=goal)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Savings goal updated successfully.")
        return redirect("goals")
    goals = SavingGoal.objects.filter(user=request.user)
    return render(request, "goals.html", {"form": form, "goals": goals, "editing_goal": goal, "goal_suggestions": calculate_goal_suggestions(request.user)})


@login_required
def delete_goal(request, pk):
    goal = get_object_or_404(SavingGoal, pk=pk, user=request.user)
    if request.method == "POST":
        goal.delete()
        messages.success(request, "Savings goal deleted successfully.")
    return redirect("goals")


@login_required
def chat_view(request):
    form = ChatForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        question = form.cleaned_data["question"]
        ChatMessage.objects.create(user=request.user, role="user", message=question)
        reply = generate_chat_reply(request.user, question)
        ChatMessage.objects.create(user=request.user, role="assistant", message=reply)
        messages.success(request, "AI chat reply generated.")
        return redirect("chat")
    history = ChatMessage.objects.filter(user=request.user)
    return render(request, "chat.html", {"form": form, "history": history})


@login_required
def settings_view(request):
    profile_form = ProfileSettingsForm(request.POST or None, instance=request.user.profile)
    password_form = StyledPasswordChangeForm(user=request.user, data=request.POST or None)

    if request.method == "POST":
        form_type = request.POST.get("form_type")
        if form_type == "preferences" and profile_form.is_valid():
            profile_form.save()
            messages.success(request, "Preferences updated successfully.")
            return redirect("settings")
        if form_type == "password" and password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Password changed successfully.")
            return redirect("settings")

    return render(request, "settings.html", {"profile_settings_form": profile_form, "password_form": password_form})


@login_required
def export_csv_view(request):
    content = export_expenses_csv(request.user)
    response = HttpResponse(content, content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="finsmart-expenses.csv"'
    return response


@login_required
def export_excel_view(request):
    content = export_expenses_excel(request.user)
    response = HttpResponse(content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="finsmart-expenses.xlsx"'
    return response
