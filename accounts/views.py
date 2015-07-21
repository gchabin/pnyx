from accounts.models import CreateUserForm
from django.views import generic
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.shortcuts import get_object_or_404, render, render_to_response
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django import forms
from django.contrib.auth import authenticate, login, logout


import logging
logger = logging.getLogger(__name__)


def register_view(request):
    if request.method == 'POST':
        registration_form = CreateUserForm(request.POST)

        if registration_form.is_valid():
            user = registration_form.save()
            #create authentification
            user = authenticate(username=registration_form.cleaned_data['username'], password=registration_form.cleaned_data['password1'])
            login(request, user)
            return HttpResponseRedirect(reverse('polls:index'))
    else:
        registration_form = CreateUserForm()
    return render(request, 'accounts/register.html', {
       'registration_form': registration_form,
       })

def change_settings(request, pk, *args, **kwargs):
    current_user = get_object_or_404(User,pk=pk )
    if request.method == 'POST':
        registration_form = CreateUserForm(request.POST)

        if registration_form.is_valid():
            user = registration_form.save()
            return HttpResponseRedirect(reverse('polls:index'))
    else:
        registration_form = CreateUserForm()
    return render(request, 'accounts/register.html', {
       'registration_form': registration_form,
       })

def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse('login'))