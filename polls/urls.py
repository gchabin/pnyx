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
    url(r'^mypolls/(?P<uuid>[a-z0-9\-]+)/$',
        views.DetailView.as_view(),
        name='detail'),
    # ex: /polls/mypolls/5/settings/
    url(r'^mypolls/(?P<uuid>[a-z0-9\-]+)/settings/$',
        views.change_settings_view,
        name='setup'),
    # ex: /polls/mypolls/5/settings/updated/
    url(r'^mypolls/(?P<uuid>[a-z0-9\-]+)/settings/updated/$',
        views.UpdateConfirmationView.as_view(),
        name='update_confirmation'),
    # ex: /polls/mypolls/5/email-participants/
    url(r'^mypolls/(?P<uuid>[a-z0-9\-]+)/email-participants/$',
        views.EmailParticipant.as_view(),
        name = 'email_participant'),
    # ex: /polls/mypolls/5/settings/email-participants/sent/
    url(r'^mypolls/(?P<uuid>[a-z0-9\-]+)/email-participants/sent/$',
        views.EmailParticipantConfirmation.as_view(),
        name = 'email_participant_confirmation'),
    # ex: /polls/mypolls/5/send-link/
    url(r'^mypolls/(?P<uuid>[a-z0-9\-]+)/send-link/$',
        views.send_link_participant,
        name = 'send_link_participant'),
    # ex: /polls/mypolls/5/send-link/sent/
    url(r'^mypolls/(?P<uuid>[a-z0-9\-]+)/send-link/sent/$',
        views.EmailParticipantConfirmation.as_view(),
        name = 'send_link_participant_confirmation'),
    # ex: /polls/mypolls/5/settings/delete/
    url(r'^mypolls/(?P<uuid>[a-z0-9\-]+)/delete/$',
        views.DeletePollView.as_view(),
        name = 'delete_poll'),
    # ex: /polls/mypolls/5/preflib/
    url(r'^mypolls/(?P<uuid>[a-z0-9\-]+)/preflib/$',
        views.PreflibView.as_view(),
        name = 'preflib'),
    # ex: /polls/poll/add/
    url(r'^poll/add/$',
        views.CreatePollWizardView.as_view(),
        name='create_poll'),
    # ex: /poll/add/confirmation
    url(r'^poll/add/(?P<uuid>[a-z0-9\-]+)/confirmation/$',
        views.CreatePollConfirmation.as_view(),
        name = 'create_poll_confirmation'),
    # ex: /polls/oops
    url(r'^oops/$',
        views.OopsView.as_view(),
        name = 'oops'),
)