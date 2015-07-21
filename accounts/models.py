from django.db import models
from django.contrib.auth.models import User
from django import forms
from django.contrib.auth.forms import UserCreationForm
from captcha.fields import ReCaptchaField
from django.conf import settings

class CreateUserForm(UserCreationForm):
    
    email = forms.EmailField(required=True)
    captcha = ReCaptchaField(
        public_key=settings.REGISTRATION_RECAPTCHA_PUBLIC_KEY,
        private_key=settings.REGISTRATION_RECAPTCHA_PRIVATE_KEY,
    )
    
    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def save(self, commit=True):
        user = super(CreateUserForm, self).save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user
