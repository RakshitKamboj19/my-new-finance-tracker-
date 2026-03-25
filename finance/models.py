from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class Expense(models.Model):
    CATEGORY_CHOICES = [
        ("Food", "Food"),
        ("Travel", "Travel"),
        ("Shopping", "Shopping"),
        ("Bills", "Bills"),
        ("Other", "Other"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="expenses",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    date = models.DateField()
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.user.username} - {self.category} - {self.amount}"


class Budget(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="budget",
    )
    monthly_limit = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.user.username} budget"

    @property
    def limit_or_zero(self):
        return self.monthly_limit or Decimal("0.00")


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    profile_picture = models.ImageField(upload_to="profiles/", blank=True, null=True)
    dark_mode = models.BooleanField(default=False)
    saving_streak = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Profile for {self.user.username}"


class AIAdvice(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_advices",
    )
    advice_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Advice for {self.user.username} at {self.created_at:%Y-%m-%d %H:%M}"


class SavingGoal(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="saving_goals")
    goal_name = models.CharField(max_length=120)
    target_amount = models.DecimalField(max_digits=10, decimal_places=2)
    current_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    deadline = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["deadline", "goal_name"]

    def __str__(self):
        return f"{self.goal_name} ({self.user.username})"

    @property
    def progress_percentage(self):
        if not self.target_amount:
            return 0
        return min(100, round((self.current_amount / self.target_amount) * 100, 2))

    @property
    def remaining_amount(self):
        return max(Decimal("0.00"), self.target_amount - self.current_amount)

    @property
    def days_left(self):
        return max((self.deadline - timezone.localdate()).days, 0)


class Notification(models.Model):
    LEVEL_CHOICES = [
        ("info", "Info"),
        ("warning", "Warning"),
        ("danger", "Danger"),
        ("success", "Success"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=120)
    message = models.TextField()
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default="info")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} - {self.user.username}"


class ExpenseScan(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="expense_scans")
    image = models.ImageField(upload_to="expense_scans/")
    extracted_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    extracted_date = models.DateField(blank=True, null=True)
    extracted_category = models.CharField(max_length=20, blank=True)
    extracted_description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class ChatMessage(models.Model):
    ROLE_CHOICES = [("user", "User"), ("assistant", "Assistant")]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_messages")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.role}"


class Achievement(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="achievements")
    badge_name = models.CharField(max_length=100)
    message = models.TextField()
    icon = models.CharField(max_length=50, default="bi-trophy")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("user", "badge_name")

    def __str__(self):
        return f"{self.badge_name} - {self.user.username}"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    Profile.objects.get_or_create(user=instance)
