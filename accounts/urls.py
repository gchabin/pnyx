from django.conf.urls import patterns, url
from accounts import views

urlpatterns = patterns('',
                       # ex: /accounts/register
                       url(r'^register/$', views.register_view, name='register'),
                       # ex: /accounts/login
                       url(r'^login/$',
                           'django.contrib.auth.views.login',
                           {'template_name': 'accounts/login.html'},
                           name='login'),
                       # ex: /accounts/logout
                       url(r'^logout/$', views.logout_view, name='logout'),
                       # ex: /accounts/password_change
                       url(r'^password_change/$',
                           'django.contrib.auth.views.password_change',
                           {'template_name': 'accounts/password_change_form.html'},
                           name = 'password_change'),
                       # ex: /accounts/password_change/done/
                       url(r'^password_change/done/$',
                           'django.contrib.auth.views.password_change_done',
                           {'template_name': 'accounts/password_change_done.html'},
                           name = 'password_change_done'),
                       # ex: /accounts/password_reset
                      url(r'^password_reset/$',
                          'django.contrib.auth.views.password_reset',
                          {'template_name': 'accounts/password_reset_form.html',
                           'email_template_name': 'accounts/password_reset_email.html',
                           'subject_template_name':'accounts/password_reset_subject.txt'},
                          name = 'password_reset'),
                      # ex: /accounts/password_reset/done/
                      url(r'^password_reset/done/$',
                          'django.contrib.auth.views.password_reset_done',
                          {'template_name': 'accounts/password_reset_done.html'},
                          name = 'password_reset_done'),
                      # ex: /accounts/reset/<uidb>-<token>/
                      url(r'^reset/(?P<uidb64>[0-9A-Za-z]+)-(?P<token>.+)/$',
                          'django.contrib.auth.views.password_reset_confirm',
                          {'template_name': 'accounts/password_reset_confirm.html'},
                          name = 'password_reset_confirm'),
                      # ex: /accounts/reset/done/
                      url(r'^reset/done/$',
                           'django.contrib.auth.views.password_reset_complete',
                           {'template_name': 'accounts/password_reset_complete.html'},
                            name = 'password_reset_complete'),
)