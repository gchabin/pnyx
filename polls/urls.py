from django.conf.urls import patterns, url
from polls import views

urlpatterns = patterns('',
    # ex: /polls/
    url(r'^$',
        views.IndexView.as_view(),
        name='index'),
    # ex: /polls/mypolls
    url(r'^mypolls/$',
        views.ManagePollView.as_view(),
        name='manage_poll'),
    # ex: /polls/forbidden
    url(r'^forbidden/$',
        views.NoRightView.as_view(),
        name = 'no_right'),
    # ex: /polls/mypolls/5/
    url(r'^mypolls/(?P<pk>\d+)/$',
        views.DetailView.as_view(),
        name='detail'),
    # ex: /polls/mypolls/5/settings/
    url(r'^mypolls/(?P<pk>\d+)/settings/$',
        views.change_settings_view,
        name='setup'),
    # ex: /polls/mypolls/5/settings/updated/
    url(r'^mypolls/(?P<pk>\d+)/settings/updated/$',
        views.UpdateConfirmationView.as_view(),
        name='update_confirmation'),
    # ex: /polls/mypolls/5/email-participants/
    url(r'^mypolls/(?P<pk>\d+)/email-participants/$',
        views.EmailParticipant.as_view(),
        name = 'email_participant'),
    # ex: /polls/mypolls/5/settings/email-participants/send/
    url(r'^mypolls/(?P<pk>\d+)/email-participants/send/$',
        views.EmailParticipantConfirmation.as_view(),
        name = 'email_participant_confirmation'),
    # ex: /polls/mypolls/5/settings/delete/
    url(r'^mypolls/(?P<pk>\d+)/delete/$',
        views.DeletePollView.as_view(),
        name = 'delete_poll'),
    # ex: /polls/mypolls/5/preflib/
    url(r'^mypolls/(?P<pk>\d+)/preflib/$',
        views.PreflibView.as_view(),
        name = 'preflib'),
    # ex: /polls/poll/add/
    url(r'^poll/add/$',
        views.CreatePollWizardView.as_view(),
        name='create_poll'),
    # ex: /poll/add/confirmation
    url(r'^poll/add/(?P<pk>\d+)/confirmation/$',
        views.CreatePollConfirmation.as_view(),
        name = 'create_poll_confirmation'),
    # ex: /polls/oops
    url(r'^oops/$',
        views.OopsView.as_view(),
        name = 'oops'),
)