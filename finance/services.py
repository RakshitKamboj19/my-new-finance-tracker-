import base64
import csv
import io
import json
import logging
import os
import re
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import Achievement, Budget, Expense, Notification, SavingGoal

logger = logging.getLogger(__name__)

MISSING_KEY_MESSAGE = "AI advice not available. Please configure API key."
API_FAILURE_MESSAGE = "AI advice is temporarily unavailable. Please try again later."
EMPTY_RESPONSE_MESSAGE = "AI advice is temporarily unavailable because the model returned an empty response."
QUOTA_MESSAGE = "OpenAI quota exceeded. Please check your billing or project credits and try again."
OCR_FALLBACK_MESSAGE = "Receipt scan is available when OpenAI is configured."


def _get_openai_api_key():
    return (os.getenv("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", "") or "").strip()


def _extract_text_from_response(response):
    choices = getattr(response, "choices", None)
    if not choices:
        return ""
    message = getattr(choices[0], "message", None)
    if not message:
        return ""
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
            else:
                text = getattr(item, "text", None)
            if text:
                parts.append(str(text).strip())
        return "\n".join(part for part in parts if part).strip()
    return ""


def _serialize_category_breakdown(expenses):
    category_totals = defaultdict(lambda: Decimal("0.00"))
    for expense in expenses:
        category_totals[expense.category] += expense.amount
    return {key: float(value) for key, value in category_totals.items()}


def get_budget_snapshot(user, reference_date=None):
    today = reference_date or timezone.localdate()
    expenses = Expense.objects.filter(user=user, date__year=today.year, date__month=today.month)
    total_spending = expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    budget, _ = Budget.objects.get_or_create(user=user, defaults={"monthly_limit": Decimal("0.00")})
    remaining = budget.monthly_limit - total_spending
    highest_category = "-"
    category_data = _serialize_category_breakdown(expenses)
    if category_data:
        highest_category = max(category_data.items(), key=lambda item: item[1])[0]
    return {
        "expenses": expenses,
        "budget": budget,
        "total_spending": total_spending,
        "remaining": remaining,
        "category_data": category_data,
        "highest_category": highest_category,
    }


def get_monthly_trend(user, months=6):
    today = timezone.localdate()
    start_month = (today.replace(day=1) - timedelta(days=31 * (months - 1))).replace(day=1)
    qs = (
        Expense.objects.filter(user=user, date__gte=start_month)
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(total=Sum("amount"))
        .order_by("month")
    )
    labels = []
    values = []
    for item in qs:
        labels.append(item["month"].strftime("%b %Y"))
        values.append(float(item["total"] or 0))
    return {"labels": labels, "values": values}


def get_weekly_spending(user, days=7):
    today = timezone.localdate()
    labels = []
    values = []
    for offset in range(days - 1, -1, -1):
        current_day = today - timedelta(days=offset)
        total = Expense.objects.filter(user=user, date=current_day).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        labels.append(current_day.strftime("%d %b"))
        values.append(float(total))
    return {"labels": labels, "values": values}


def detect_recurring_expenses(user):
    recurring = []
    expenses = Expense.objects.filter(user=user).order_by("description", "amount", "date")
    buckets = defaultdict(list)
    for expense in expenses:
        key = (expense.description.strip().lower() or expense.category.lower(), expense.amount)
        buckets[key].append(expense)
    total_monthly = Decimal("0.00")
    for (description, amount), items in buckets.items():
        if len(items) >= 2:
            recurring.append(
                {
                    "label": items[0].description or items[0].category,
                    "amount": amount,
                    "count": len(items),
                    "category": items[0].category,
                }
            )
            total_monthly += amount
    return recurring[:5], total_monthly


def get_spending_patterns(user):
    snapshot = get_budget_snapshot(user)
    recurring, recurring_total = detect_recurring_expenses(user)
    insights = []
    if snapshot["highest_category"] != "-":
        insights.append(f"Your highest spending category this month is {snapshot['highest_category']}.")
    if snapshot["budget"].monthly_limit > 0:
        usage_ratio = float(snapshot["total_spending"] / snapshot["budget"].monthly_limit) if snapshot["budget"].monthly_limit else 0
        if usage_ratio >= 0.8:
            insights.append("You have already used more than 80% of your monthly budget.")
    if recurring:
        insights.append(f"You appear to have {len(recurring)} recurring expense patterns costing about Rs. {recurring_total} monthly.")
    if not insights:
        insights.append("Keep logging expenses to unlock richer spending pattern insights.")
    return insights


def generate_ai_advice(user):
    api_key = _get_openai_api_key()
    if not api_key:
        logger.error("OPENAI_API_KEY is missing.")
        return MISSING_KEY_MESSAGE

    snapshot = get_budget_snapshot(user)
    recurring, recurring_total = detect_recurring_expenses(user)
    prompt = f"""You are a personal finance advisor for students.

Analyze this financial data:
- Total Spending: {snapshot['total_spending']}
- Budget: {snapshot['budget'].monthly_limit}
- Remaining: {snapshot['remaining']}
- Category Breakdown: {snapshot['category_data']}
- Highest Category: {snapshot['highest_category']}
- Recurring Monthly Cost: {recurring_total}

Give:
- Specific savings advice
- Overspending warnings
- Practical suggestions
- One simple weekly action

Keep response short and actionable."""

    try:
        from openai import OpenAI, RateLimitError

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "You are a concise personal finance advisor for students."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=220,
        )
        advice_text = _extract_text_from_response(response)
        if not advice_text:
            logger.error("OpenAI returned an empty response. Raw response: %s", response)
            return EMPTY_RESPONSE_MESSAGE
        return advice_text
    except RateLimitError as exc:
        logger.exception("OpenAI quota/rate-limit error: %s", exc)
        return QUOTA_MESSAGE
    except Exception as exc:
        logger.exception("OpenAI advice generation failed: %s", exc)
        return API_FAILURE_MESSAGE


def generate_report_summary(user, report_data):
    api_key = _get_openai_api_key()
    fallback = (
        f"You spent Rs. {report_data['total_spending']} this month. "
        f"Your highest category was {report_data['highest_category']}. "
        f"Remaining budget stands at Rs. {report_data['remaining']}."
    )
    if not api_key:
        return fallback
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        prompt = f"Summarize this monthly student finance report in 4 short sentences: {report_data}"
        response = client.chat.completions.create(
            model=getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=180,
        )
        text = _extract_text_from_response(response)
        return text or fallback
    except Exception as exc:
        logger.exception("Report summary generation failed: %s", exc)
        return fallback


def generate_chat_reply(user, question):
    api_key = _get_openai_api_key()
    snapshot = get_budget_snapshot(user)
    context = f"Budget: {snapshot['budget'].monthly_limit}, Total: {snapshot['total_spending']}, Remaining: {snapshot['remaining']}, Categories: {snapshot['category_data']}"
    fallback = (
        "AI chat is unavailable right now. Based on your current data, focus on your highest spending category, "
        "review recurring costs, and protect part of your remaining budget for savings."
    )
    if not api_key:
        return fallback
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "You are a helpful finance coach for students."},
                {"role": "user", "content": f"Context: {context}\n\nQuestion: {question}"},
            ],
            max_tokens=280,
        )
        return _extract_text_from_response(response) or fallback
    except Exception as exc:
        logger.exception("Chat assistant failed: %s", exc)
        return fallback


def generate_investment_suggestions(user):
    snapshot = get_budget_snapshot(user)
    suggestions = [
        "Build an emergency buffer before taking any investment risk.",
        "Start with low-cost index funds or recurring deposits once your budget is stable.",
        "Keep investment money separate from rent, food, and tuition essentials.",
    ]
    if snapshot["remaining"] > 0:
        suggestions.insert(0, f"You currently have about Rs. {snapshot['remaining']} remaining; consider allocating a small fixed percentage to beginner investments.")
    return suggestions[:3]


def sync_smart_notifications(user):
    snapshot = get_budget_snapshot(user)
    budget_amount = snapshot["budget"].monthly_limit
    total_spending = snapshot["total_spending"]
    if budget_amount > 0 and total_spending >= budget_amount:
        Notification.objects.get_or_create(
            user=user,
            title="Budget exceeded",
            message="You have crossed your full monthly budget. Review your largest categories today.",
            level="danger",
            is_read=False,
        )
    if budget_amount > 0 and total_spending >= (budget_amount * Decimal("0.80")) and total_spending < budget_amount:
        Notification.objects.get_or_create(
            user=user,
            title="Budget usage at 80%",
            message="You have crossed 80% of your monthly budget. Consider slowing discretionary spending.",
            level="warning",
            is_read=False,
        )
    return Notification.objects.filter(user=user)[:5]


def calculate_goal_suggestions(user):
    suggestions = []
    for goal in SavingGoal.objects.filter(user=user):
        days_left = max(goal.days_left, 1)
        suggestions.append({"goal": goal, "daily_saving": round(goal.remaining_amount / Decimal(days_left), 2)})
    return suggestions


def award_achievements(user):
    if user.expenses.count() >= 1:
        Achievement.objects.get_or_create(
            user=user,
            badge_name="First Expense Logged",
            defaults={"message": "You started tracking your spending.", "icon": "bi-lightning-charge"},
        )
    if SavingGoal.objects.filter(user=user).exists():
        Achievement.objects.get_or_create(
            user=user,
            badge_name="Goal Setter",
            defaults={"message": "You created your first savings goal.", "icon": "bi-bullseye"},
        )
    if SavingGoal.objects.filter(user=user, current_amount__gte=models.F("target_amount")).exists():
        Achievement.objects.get_or_create(
            user=user,
            badge_name="Goal Crusher",
            defaults={"message": "You completed a savings goal.", "icon": "bi-trophy"},
        )
    return Achievement.objects.filter(user=user)[:6]


def build_monthly_report(user, reference_date=None):
    snapshot = get_budget_snapshot(user, reference_date)
    recurring, recurring_total = detect_recurring_expenses(user)
    return {
        "total_spending": snapshot["total_spending"],
        "budget": snapshot["budget"].monthly_limit,
        "remaining": snapshot["remaining"],
        "highest_category": snapshot["highest_category"],
        "category_breakdown": snapshot["category_data"],
        "savings_summary": f"Remaining balance this month: Rs. {snapshot['remaining']}",
        "recurring_total": recurring_total,
        "recurring_items": recurring,
    }


def export_expenses_csv(user):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Date", "Category", "Description", "Amount"])
    for expense in Expense.objects.filter(user=user).order_by("-date"):
        writer.writerow([expense.date, expense.category, expense.description, expense.amount])
    return buffer.getvalue()


def export_expenses_excel(user):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Expenses"
    sheet.append(["Date", "Category", "Description", "Amount"])
    for expense in Expense.objects.filter(user=user).order_by("-date"):
        sheet.append([str(expense.date), expense.category, expense.description, float(expense.amount)])
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def build_pdf_report(report_data, username):
    output = io.BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"FinSmart Monthly Report - {username}", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Total Spending: Rs. {report_data['total_spending']}", styles["BodyText"]),
        Paragraph(f"Monthly Budget: Rs. {report_data['budget']}", styles["BodyText"]),
        Paragraph(f"Remaining Balance: Rs. {report_data['remaining']}", styles["BodyText"]),
        Paragraph(f"Highest Category: {report_data['highest_category']}", styles["BodyText"]),
        Spacer(1, 12),
    ]
    table_data = [["Category", "Amount"]]
    for category, amount in report_data["category_breakdown"].items():
        table_data.append([category, f"Rs. {amount}"])
    table = Table(table_data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dbe7f4")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
    ]))
    story.append(table)
    document.build(story)
    return output.getvalue()


def scan_receipt(image_file):
    api_key = _get_openai_api_key()
    result = {"amount": None, "date": None, "category": "Other", "description": OCR_FALLBACK_MESSAGE}

    if api_key:
        try:
            from openai import OpenAI

            image_bytes = image_file.read()
            image_file.seek(0)
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract receipt amount, date (YYYY-MM-DD if possible), category from Food/Travel/Shopping/Bills/Other, and a short description. Respond as JSON with keys amount, date, category, description."},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                    ],
                }],
                max_tokens=250,
            )
            text = _extract_text_from_response(response)
            data = json.loads(text)
            result.update({
                "amount": Decimal(str(data.get("amount"))) if data.get("amount") else None,
                "date": data.get("date") or None,
                "category": data.get("category") or "Other",
                "description": data.get("description") or "Scanned receipt",
            })
            return result
        except Exception as exc:
            logger.exception("Receipt scan via OpenAI failed: %s", exc)

    filename = getattr(image_file, "name", "receipt")
    amount_match = re.search(r"(\d+[\.,]\d{2})", filename)
    if amount_match:
        result["amount"] = Decimal(amount_match.group(1).replace(",", "."))
    result["description"] = "Receipt uploaded. Add details manually or configure AI scanning for autofill."
    return result
