from django.conf.urls import patterns, url
from about import views

urlpatterns = patterns('',
                       url('^$',
                           views.AboutView.as_view(),
                           name='about'),
)