from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def create_profiles(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL.split('.')[0], settings.AUTH_USER_MODEL.split('.')[1])
    Profile = apps.get_model("finance", "Profile")
    for user in User.objects.all():
        Profile.objects.get_or_create(user=user)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("finance", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Achievement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("badge_name", models.CharField(max_length=100)),
                ("message", models.TextField()),
                ("icon", models.CharField(default="bi-trophy", max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="achievements", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"], "unique_together": {("user", "badge_name")}},
        ),
        migrations.CreateModel(
            name="ChatMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("user", "User"), ("assistant", "Assistant")], max_length=20)),
                ("message", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="chat_messages", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="ExpenseScan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image", models.ImageField(upload_to="expense_scans/")),
                ("extracted_amount", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("extracted_date", models.DateField(blank=True, null=True)),
                ("extracted_category", models.CharField(blank=True, max_length=20)),
                ("extracted_description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="expense_scans", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=120)),
                ("message", models.TextField()),
                ("level", models.CharField(choices=[("info", "Info"), ("warning", "Warning"), ("danger", "Danger"), ("success", "Success")], default="info", max_length=20)),
                ("is_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Profile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("profile_picture", models.ImageField(blank=True, null=True, upload_to="profiles/")),
                ("dark_mode", models.BooleanField(default=False)),
                ("saving_streak", models.PositiveIntegerField(default=0)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="profile", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="SavingGoal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("goal_name", models.CharField(max_length=120)),
                ("target_amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("current_amount", models.DecimalField(decimal_places=2, default="0.00", max_digits=10)),
                ("deadline", models.DateField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="saving_goals", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["deadline", "goal_name"]},
        ),
        migrations.RunPython(create_profiles, migrations.RunPython.noop),
    ]
