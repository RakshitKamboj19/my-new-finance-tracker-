from django.contrib import admin

from .models import AIAdvice, Achievement, Budget, ChatMessage, Expense, ExpenseScan, Notification, Profile, SavingGoal

admin.site.site_header = "TeckWay MoneyTracker Admin"
admin.site.site_title = "TeckWay MoneyTracker"
admin.site.index_title = "Welcome to TeckWay MoneyTracker Dashboard"


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "category", "date")
    list_filter = ("category", "date")
    search_fields = ("description", "user__username")


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ("user", "monthly_limit")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "dark_mode", "saving_streak")


@admin.register(AIAdvice)
class AIAdviceAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at")
    search_fields = ("user__username", "advice_text")


@admin.register(SavingGoal)
class SavingGoalAdmin(admin.ModelAdmin):
    list_display = ("user", "goal_name", "target_amount", "current_amount", "deadline")
    list_filter = ("deadline",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "level", "is_read", "created_at")
    list_filter = ("level", "is_read")


@admin.register(ExpenseScan)
class ExpenseScanAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "extracted_amount", "extracted_category")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "created_at")
    search_fields = ("message", "user__username")


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ("user", "badge_name", "created_at")
