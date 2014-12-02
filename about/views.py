from django.shortcuts import render
from django.views import generic


class AboutView(generic.TemplateView):
    template_name = 'about/about.html'