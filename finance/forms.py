from django import forms
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm
from django.contrib.auth.models import User

from .models import Budget, Expense, ExpenseScan, Profile, SavingGoal


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class ExpenseForm(forms.ModelForm):
    date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )

    class Meta:
        model = Expense
        fields = ("amount", "category", "date", "description")
        widgets = {
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        }


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ("monthly_limit",)
        widgets = {
            "monthly_limit": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            )
        }


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("username", "email")
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
        }


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("profile_picture",)
        widgets = {
            "profile_picture": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }


class SavingGoalForm(forms.ModelForm):
    deadline = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )

    class Meta:
        model = SavingGoal
        fields = ("goal_name", "target_amount", "current_amount", "deadline")
        widgets = {
            "goal_name": forms.TextInput(attrs={"class": "form-control"}),
            "target_amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "current_amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        }


class ExpenseScanForm(forms.ModelForm):
    class Meta:
        model = ExpenseScan
        fields = ("image",)
        widgets = {
            "image": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),
        }


class ChatForm(forms.Form):
    question = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Ask about your spending, budget, goals, or beginner investing..."})
    )


class ProfileSettingsForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("dark_mode",)
        widgets = {
            "dark_mode": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class StyledPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(widget=forms.PasswordInput(attrs={"class": "form-control"}))
    new_password1 = forms.CharField(widget=forms.PasswordInput(attrs={"class": "form-control"}))
    new_password2 = forms.CharField(widget=forms.PasswordInput(attrs={"class": "form-control"}))
