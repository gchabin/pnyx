from django.shortcuts import render, get_object_or_404, render, render_to_response
from django.views import generic
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseServerError
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.template import RequestContext
from django.utils import timezone

from polls.models import Poll, Alternative, Voter
from vote.models import TransitivePreference, BinaryRelation

import uuid
import logging
logger = logging.getLogger(__name__)



def get_voter_by_uuid(voter_uuid):
    '''get the voter object with its uuid. If a uuid is 'public' a default voter is created'''

    if voter_uuid == 'public':
        #if uuid is 'public', a default voter is created
        voter, created = Voter.objects.get_or_create(
            email = 'unknown_voter@pnyx.com',
            uuid = str(uuid.uuid4()),  #36 byte random uuid,
        )
        logger.debug("Voter " + str(voter.pk) + " " + voter.email + "created")
    else:
        voter = Voter.objects.filter( uuid = voter_uuid)[0:1].get()
    return voter


class NoTemporaryResultsView(generic.TemplateView):
    '''inform the voter that the temporary results are not available. If the admin loads this
     page he is redirected to the temp results'''
    template_name = 'vote/no_temporary_results.html'

    def get(self, request, *args, **kwargs):
        poll = get_object_or_404(Poll, uuid = kwargs["uuid"])
        if  poll.temporary_result or poll.admin == request.user:
            #return temporary result if available for this poll
            return HttpResponseRedirect(reverse('vote:temp_results', kwargs = kwargs))
        return render_to_response( self.template_name)

class PollNotClosedView(generic.DetailView):
    '''If the voter wants to access to the final results of a not closed poll'''
    slug_url_kwarg = 'uuid'
    slug_field = 'uuid'
    model = Poll
    template_name = 'vote/poll_not_closed.html'

    def get(self, request, *args, **kwargs):
        poll = get_object_or_404(Poll, uuid = kwargs["uuid"])
        if not timezone.now() < poll.closing_date:
            #return temporary result if available for this poll
            return HttpResponseRedirect(reverse('vote:results', kwargs = kwargs))
        return render_to_response(self.template_name,  {'poll': poll, 'voter_uuid': kwargs["voter_uuid"]} )

class PollClosedView(generic.DetailView):
    '''If the voter wants to access to the ballot of a closed poll'''
    slug_url_kwarg = 'uuid'
    slug_field = 'uuid'
    model = Poll
    template_name = 'vote/poll_closed.html'

    def get_context_data(self, **kwargs):
        # Add the voter_uuid to the args (for the template view)
        context = super(PollClosedView, self).get_context_data(**kwargs)
        context['voter_uuid'] = self.kwargs['voter_uuid']
        return context

class PollNotOpenedView(generic.DetailView):
    '''If the voter wants to access to the ballot of a poll not opened yet'''
    slug_url_kwarg = 'uuid'
    slug_field = 'uuid'
    model = Poll
    template_name = 'vote/poll_not_opened.html'

    def get_context_data(self, **kwargs):
        # Add the voter_uuid to the args (for the template view)
        context = super(PollNotOpenedView, self).get_context_data(**kwargs)
        context['voter_uuid'] = self.kwargs['voter_uuid']
        return context

    def get(self, request, *args, **kwargs):
        slug_url_kwarg = 'uuid'
        slug_field = 'uuid'
        poll = get_object_or_404(Poll, uuid = kwargs["uuid"])
        if timezone.now() >= poll.opening_date:
            #return temporary result if available for this poll
            return HttpResponseRedirect(reverse('vote:get_ballot_view', kwargs = kwargs))
        return render_to_response(self.template_name, {'poll': poll, 'voter_uuid': kwargs["voter_uuid"]})

class Confirmation(generic.DetailView):
    '''confirm to the voter the vote has been processed.'''
    slug_url_kwarg = 'uuid'
    slug_field = 'uuid'
    model = Poll
    template_name = "vote/confirmation.html"

    def get_context_data(self, **kwargs):
        # Add the voter_uuid to the args (for the template view)
        context = super(Confirmation, self).get_context_data(**kwargs)
        context['voter_uuid'] = self.kwargs['voter_uuid']
        context['domain'] = self.request.get_host()
        context['protocol'] = self.request.is_secure() and 'https' or 'http'

        return context

class AlreadyVoted(generic.DetailView):
    '''if a voter tries to vote twice and it's not allowed'''
    slug_url_kwarg = 'uuid'
    slug_field = 'uuid'
    model = Poll
    template_name = "vote/already_voted.html"

    def get_context_data(self, **kwargs):
        # Add the voter_uuid to the args (for the template view)
        context = super(AlreadyVoted, self).get_context_data(**kwargs)
        context['voter_uuid'] = self.kwargs['voter_uuid']
        context['domain'] = self.request.get_host()
        context['protocol'] = self.request.is_secure() and 'https' or 'http'

        return context

class Unauthorized(generic.DetailView):
    '''the voter wants to access to a ballot where he is not registered'''
    slug_url_kwarg = 'uuid'
    slug_field = 'uuid'
    model = Poll
    template_name = "vote/unauthorized.html"

    def get(self, request, *args, **kwargs):
        poll = get_object_or_404(Poll, uuid = kwargs["uuid"])
        voter_uuid= kwargs["voter_uuid"]
        if not poll.private:
            return HttpResponseRedirect(
                reverse('vote:get_ballot_view', kwargs = kwargs))
        if poll.private and voter_uuid != 'public':
            #we need to check only if the poll is private
            try:
                # get the voter from UUID
                voter = get_voter_by_uuid(voter_uuid)
                poll.participant.all().get(uuid = voter_uuid)
                return HttpResponseRedirect(
                    reverse('vote:get_ballot_view', kwargs = kwargs))
            except (KeyError, Voter.DoesNotExist):
               pass
        return render_to_response(self.template_name, {'poll': poll, 'voter_uuid': kwargs["voter_uuid"]})

class WrongUuid(generic.TemplateView):
    template_name = 'vote/wrong_uuid.html'