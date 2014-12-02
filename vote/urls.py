from django.conf.urls import patterns, url
from django.http import HttpResponse
from vote import views, generic_views

urlpatterns = patterns('',
                        # ex: /polls/5/vote/
                        url(
                            r'^(?P<pk>\d+)/(?P<voter_uuid>[a-z0-9\-]+)/$',
                            views.get_ballot_view,
                            name = 'get_ballot_view'),

                        url(r'^(?P<pk>\d+)/(?P<voter_uuid>[a-z0-9\-]+)/vote/$',
                            views.vote,
                            name = 'vote'),

                        url(r'^(?P<pk>\d+)/(?P<voter_uuid>[a-z0-9\-]+)/confirmation/$',
                            generic_views.Confirmation.as_view(),
                            name = 'confirmation'),

                        url(r'^(?P<pk>\d+)/(?P<voter_uuid>[a-z0-9\-]+)/already_voted/$',
                            generic_views.AlreadyVoted.as_view(),
                            name = 'already_voted'),

                        url(r'^(?P<pk>\d+)/(?P<voter_uuid>[a-z0-9\-]+)/unauthorized/$',
                            generic_views.Unauthorized.as_view(),
                            name = 'unauthorized'),

                        url(r'^(?P<pk>\d+)/(?P<voter_uuid>[a-z0-9\-]+)/temp-results/$',
                            views.temporary_results,
                                name = 'temp_results'),

                        url(r'^(?P<pk>\d+)/(?P<voter_uuid>[a-z0-9\-]+)/results/$',
                            views.results,
                            name = 'results'),

                        url(r'^(?P<pk>\d+)/(?P<voter_uuid>[a-z0-9\-]+)/no-temp-results/$',
                            generic_views.NoTemporaryResultsView.as_view(),
                            name = 'no_temp_results'),

                        url(r'^(?P<pk>\d+)/(?P<voter_uuid>[a-z0-9\-]+)/closed/$',
                            generic_views.PollClosedView.as_view(),
                            name = 'poll_closed'),

                        url(r'^(?P<pk>\d+)/(?P<voter_uuid>[a-z0-9\-]+)/not-closed-yet/$',
                            generic_views.PollNotClosedView.as_view(),
                            name = 'poll_not_closed_yet'),

                        url(r'^(?P<pk>\d+)/(?P<voter_uuid>[a-z0-9\-]+)/not-opened-yet/$',
                            generic_views.PollNotOpenedView.as_view(),
                            name = 'poll_not_opened_yet'),
                       )