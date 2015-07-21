from polls.models import *
from vote.views import get_majority_graph_matrix, get_transitive_preference
from vote.models import *

from django.utils import timezone
from django.shortcuts import get_object_or_404, render, render_to_response
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django.views import generic
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from formtools.wizard.views import SessionWizardView
from django.forms.utils import ErrorList
from django.core.mail import EmailMessage, send_mass_mail
from django.template.loader import render_to_string

from collections import Counter
import datetime, string, random
import re #regex
import uuid
import numpy as np
import logging
import pytz
logger = logging.getLogger(__name__)

############################
#Template declaration forthe form wizzard in poll creation
FORMS = [("0", CreatePollGeneralSettingForm),
         ("1", CreatePollInputForm),
         ("2", CreatePollOutputForm),
         ("3", CreatePollAlternativeForm),
         ("4", CreatePollParticipantForm),
         ("5", CreatePollPreviewForm),
         ]

TEMPLATES = {"0": "polls/create_poll_general_setting.html",
             "1": "polls/create_poll_input.html",
             "2": "polls/create_poll_output.html",
             "3": "polls/create_poll_alternative.html",
             "4": "polls/create_poll_participant.html",
             "5": "polls/create_poll_preview.html",
             }

######################
#inner methods

def set_upcoming_poll(poll, request, uuid):
    # retrieve the tie breaking rule and parse it
    alternative_name_by_priority = []
    alternative_set = list(poll.alternative_set.all().order_by("priority_rank"))

    tie_breaking_rule_before_update_string = ""
    for alt in alternative_set:
        alternative_name_by_priority.append(alt.name)
        tie_breaking_rule_before_update_string += alt.name
        tie_breaking_rule_before_update_string += ">"
    tie_breaking_rule_before_update_string = tie_breaking_rule_before_update_string[:-1] #delete the last "<"

    if request.method == 'POST':
        set_up_poll_form = SetUpUpcomingPollForm(request.POST)

        if set_up_poll_form.is_valid():
            change_on_alternative = False
            #remove the alternatives
            if  set_up_poll_form.cleaned_data['alternative_to_remove'].__len__() > 0:
                for name in set_up_poll_form.cleaned_data["alternative_to_remove"]:
                    alternative =  get_object_or_404(poll.alternative_set.all(),name = name )
                    alternative.delete()
                    change_on_alternative = True
                    alternative_name_by_priority.remove(name)
                    logger.debug("Alternative " + alternative.name + " removed from the poll " + str(poll.pk))

            #check if the new alternatives name are confilcting with the existing alternatives
            alt_name_desc_list = re.split(' *\r\n *', set_up_poll_form.cleaned_data['alternative_to_add'])

            if set_up_poll_form.cleaned_data['alternative_to_add'].__len__() > 0 and not poll.recursive_poll:
                for alt_desc in alt_name_desc_list:
                    val = re.split(' *-- *', alt_desc)
                    if val[0] in alternative_name_by_priority :
                        set_up_poll_form._errors["alternative_to_add"] =  ErrorList([u" The alternative " + val[0] + u"already exist"])
                        return render(request, 'polls/change_upcoming_poll_setting.html', {
                            'set_up_poll_form': set_up_poll_form, 'poll': poll
                        })

                for alt_desc in alt_name_desc_list:
                    val = re.split(' *-- *', alt_desc)
                    alternative_name = val[0]
                    alternative_description = val[-1] if len(val)>1 else None
                    alternative = Alternative(name = alternative_name,
                                              description = alternative_description,
                                              poll = poll,
                                              priority_rank = len(alternative_name_by_priority) + 1,
                                              )
                    alternative.save()
                    change_on_alternative = True
                    alternative_name_by_priority.append(val[0])

            # check the validity of tie breaking rule
            if set_up_poll_form.cleaned_data['tie_breaking']:
                #  extract the old tie breaking rule and check if the values are different
                alt_priority_list = re.split(' *> *', set_up_poll_form.cleaned_data['tie_breaking_rule'])

                if sorted(alt_priority_list) != sorted(alternative_name_by_priority):
                    set_up_poll_form._errors["tie_breaking_rule"] = ErrorList([u"Not all the altrenatives are specified, make sure you added the new alternatives"])
                    #redirect to form with error
                    logger.debug("set_upcoming_poll() error in tie breaking rule ")
                    return render(request, 'polls/change_upcoming_poll_setting.html', {
                        'set_up_poll_form': set_up_poll_form, 'poll': poll
                    })
                else :
                    #update the tie breaking rule attribute from the form
                    poll.tie_breaking = "Custom"

                    #update priority rank
                    alt_priority_list = re.split(' *> *', set_up_poll_form.cleaned_data['tie_breaking_rule'])
                    for idx, alt_name in enumerate(alt_priority_list):
                        alt = get_object_or_404(poll.alternative_set, name = alt_name)
                        alt.priority_rank = idx + 1
                        alt.save()

            elif poll.tie_breaking == 'Custom' or change_on_alternative:
                # the selected rules is randomized: the new tie breaking is randomly updated only if the previous rule
                # was custom or we made some changes on alternatives.
                # Create an random priority order or the alternativtives are modified

                random_tie_breaking_rule = np.random.permutation(len(alternative_name_by_priority))
                for idx, alt_name in enumerate(alternative_name_by_priority):
                    alt = get_object_or_404(poll.alternative_set, name = alt_name)
                    alt.priority_rank = random_tie_breaking_rule[idx] + 1
                    alt.save()

            # update if the value changed
            if poll.name != set_up_poll_form.cleaned_data['poll_name']:
                poll.name = set_up_poll_form.cleaned_data['poll_name']

            if poll.question != set_up_poll_form.cleaned_data['poll_question']:
                poll.question = set_up_poll_form.cleaned_data['poll_question']

            if  poll.description != set_up_poll_form.cleaned_data['poll_description']:
                poll.description = set_up_poll_form.cleaned_data['poll_description']

            if set_up_poll_form.cleaned_data['poll_temporary_result'] and  not poll.temporary_result :
                poll.temporary_result = set_up_poll_form.cleaned_data['poll_temporary_result']
            elif poll.temporary_result and not set_up_poll_form.cleaned_data['poll_temporary_result']:
                #if there is a change and the temporary resut is now not selected
                poll.temporary_result = False

            if set_up_poll_form.cleaned_data['poll_change_vote'] and not poll.change_vote:
                poll.change_vote = set_up_poll_form.cleaned_data['poll_change_vote']

            elif poll.change_vote and not set_up_poll_form.cleaned_data['poll_change_vote']:
                poll.change_vote = False

            notify_voter_change_visibility = False
            if set_up_poll_form.cleaned_data['poll_private'] and not poll.private:
                poll.private = True
                notify_voter_change_visibility = True
            elif poll.private and not set_up_poll_form.cleaned_data['poll_private']:
                poll.private = False
                notify_voter_change_visibility = True

            if notify_voter_change_visibility:
                message = ()
                #Send the new link for the ballot
                for voter in poll.participant.all():
                    if voter.email != 'default_voter@pnyx.com':
                        message_data = {
                            'admin': request.user,
                            'voter_uuid': voter.uuid if poll.private else 'public',
                            'poll': poll,
                            'domain': request.get_host(),
                            'protocol': request.is_secure() and 'https' or 'http',
                        }

                        logger.debug("Voter " + voter.email + " notified of new link for poll " + str(poll.pk))

                        message += (('The link of your pnyx ballot changed',
                                     render_to_string('polls/new_link_email.html', message_data),
                                     request.user.email,
                                     [voter.email]),)

                send_mass_mail(message, fail_silently = False)

            opening_date_form = set_up_poll_form.cleaned_data['opening_date']
            if poll.opening_date != opening_date_form:
                poll.opening_date = opening_date_form
            closing_date_form = set_up_poll_form.cleaned_data['closing_date']
            if poll.closing_date != closing_date_form:
                poll.closing_date = closing_date_form
            if poll.input_type != set_up_poll_form.cleaned_data['input_type']:
                poll.input_type = set_up_poll_form.cleaned_data['input_type']

            if poll.output_type != set_up_poll_form.cleaned_data['output_type']:
                poll.output_type = set_up_poll_form.cleaned_data['output_type']

            if (poll.tie_breaking == "Random" and  set_up_poll_form.cleaned_data['tie_breaking']):
                poll.tie_breaking = "Custom"
            elif (poll.tie_breaking == "Custom" and  not set_up_poll_form.cleaned_data['tie_breaking']):
                poll.tie_breaking = "Random"

            #add the new participants and email them
            if 'voter_to_add' in set_up_poll_form.cleaned_data.keys() and set_up_poll_form.cleaned_data['voter_to_add'].__len__() > 0:
                #specify the participants
                participant_list = re.split(' *\r\n *', set_up_poll_form.cleaned_data['voter_to_add'])
                message = ()
                for participant in participant_list:
                    if participant != "default_voter@pnyx.com":
                          # email used for all public poll

                        voter, created = Voter.objects.get_or_create(email = participant)
                        poll.participant.add(voter)

                        message_data = {
                            'admin': request.user,
                            'voter_uuid': voter.uuid if poll.private else 'public',
                            'poll': poll,
                            'domain': request.get_host(),
                            'protocol': request.is_secure() and 'https' or 'http',
                        }

                        logger.debug("Voter " + voter.email + " added to the poll " + str(poll.pk))

                        message += (('You have been added to a new poll on Pnyx',
                                     render_to_string('polls/added_to_poll_email.html', message_data),
                                     request.user.email,
                                     [participant]),)
                send_mass_mail(message, fail_silently = False)

            #remove participant and email them
            if 'voter_to_remove' in set_up_poll_form.cleaned_data.keys() and set_up_poll_form.cleaned_data['voter_to_remove'].__len__() > 0:
                message = ()
                for email in set_up_poll_form.cleaned_data["voter_to_remove"]:
                    voter = get_object_or_404(poll.participant.all(), email = email)
                    poll.participant.remove(voter)
                    message_data = {
                        'admin': request.user,
                        'poll': poll,
                        }
                    logger.debug("Voter " + voter.email + " removed from the poll " + str(poll.pk))
                    message += (('You have been removed from a poll on Pnyx',
                                 render_to_string('polls/removed_from_poll_email.html', message_data),
                                 request.user.email,
                                 [email]),)

                send_mass_mail(message, fail_silently = False)

            poll.save()
            logger.debug("Upcomming poll " + str(uuid) + " updated")
            return HttpResponseRedirect(reverse('polls:update_confirmation', kwargs = {'uuid': uuid}))
    else:

        tie_breaking = True if poll.tie_breaking == 'Custom' else False
        data = {'poll_name': poll.name,
                'poll_question' : poll.question,
                'poll_description': poll.description,
                'poll_temporary_result': poll.temporary_result,
                'opening_date': timezone.localtime(poll.opening_date).strftime('%d/%m/%Y %H:%M'),
                'closing_date': timezone.localtime(poll.closing_date).strftime('%d/%m/%Y %H:%M'),
                'input_type' : poll.input_type,
                'output_type' : poll.output_type,
                'tie_breaking' : tie_breaking,
                'poll_change_vote': poll.change_vote,
                'poll_private': poll.private,
                }

        if poll.tie_breaking == 'Custom':
            #add the ti breaking rule only if the current tie breaking rule is customized
            data['tie_breaking_rule']=tie_breaking_rule_before_update_string

        set_up_poll_form = SetUpUpcomingPollForm(data)
        logger.debug("set_upcoming_poll() data: " + str(data))
    return render(request, 'polls/change_upcoming_poll_setting.html', {
        'set_up_poll_form': set_up_poll_form, 'poll': poll , 'participant':poll.participant.all()
    })


def set_closed_poll(poll, request, uuid):

    if request.method == 'POST':
        set_up_poll_form = SetUpClosedPollForm(request.POST)

        if set_up_poll_form.is_valid():
            # update if the value changed
            if poll.name != set_up_poll_form.cleaned_data['poll_name']:
                poll.name = set_up_poll_form.cleaned_data['poll_name']

            if  poll.description != set_up_poll_form.cleaned_data['poll_description']:
                poll.description = set_up_poll_form.cleaned_data['poll_description']

            poll.save()
            logger.debug("Closed poll " + str(poll.pk) + " updated")
            return HttpResponseRedirect(reverse('polls:update_confirmation', kwargs = {'uuid': uuid}))
    else:
        data = {'poll_name': poll.name,
                'poll_description': poll.description,
                }

        set_up_poll_form = SetUpClosedPollForm(data)

    return render(request, 'polls/change_closed_poll_setting.html', {
        'set_up_poll_form': set_up_poll_form, 'poll_uuid': uuid
    })


def set_opened_poll(poll, request, uuid):
    if request.method == 'POST':
        set_up_poll_form = SetUpOpenedPollForm(request.POST)
        if set_up_poll_form.is_valid():

            # update if the value changed
            if poll.name != set_up_poll_form.cleaned_data['poll_name']:
                poll.name = set_up_poll_form.cleaned_data['poll_name']

            if poll.description != set_up_poll_form.cleaned_data['poll_description']:
                poll.description = set_up_poll_form.cleaned_data['poll_description']

            if set_up_poll_form.cleaned_data['poll_temporary_result'] and \
                            poll.temporary_result != set_up_poll_form.cleaned_data['poll_temporary_result']:
                poll.temporary_result = set_up_poll_form.cleaned_data['poll_temporary_result']
            elif poll.temporary_result != False and not set_up_poll_form.cleaned_data['poll_temporary_result']:
                poll.temporary_result = False

            closing_date_form = set_up_poll_form.cleaned_data['closing_date']
            if poll.closing_date != closing_date_form:
                poll.closing_date = closing_date_form

            #add the new participants and email them
            if 'voter_to_add' in set_up_poll_form.cleaned_data.keys() and set_up_poll_form.cleaned_data[
                'voter_to_add'].__len__() > 0:
                #specify the participants
                participant_list = re.split(' *\r\n *', set_up_poll_form.cleaned_data['voter_to_add'])
                message = ()
                for participant in participant_list:
                    if participant != "default_voter@pnyx.com":
                        # email used for all public poll
                        voter, created = Voter.objects.get_or_create(email = participant)
                        poll.participant.add(voter)

                        message_data = {
                            'admin': request.user,
                            'voter_uuid': voter.uuid if poll.private else 'public',
                            'poll': poll,
                            'domain': request.get_host(),
                            'protocol': request.is_secure() and 'https' or 'http',
                        }

                        logger.debug("Voter " + voter.email + " added to the poll " + str(poll.pk))

                        message += (('You have been added to a new poll on Pnyx',
                                     render_to_string('polls/added_to_poll_email.html', message_data),
                                     request.user.email,
                                     [participant]),)
                send_mass_mail(message, fail_silently = False)

            poll.save()
            logger.debug("Opened poll " + str(uuid) + " updated")
            return HttpResponseRedirect(reverse('polls:update_confirmation', kwargs = {'uuid': uuid}))
    else:
        data = {'poll_name': poll.name,
                'poll_description': poll.description,
                'poll_temporary_result': poll.temporary_result,
                'closing_date': timezone.localtime(poll.closing_date).strftime('%d/%m/%Y %H:%M'),
                }
        set_up_poll_form = SetUpOpenedPollForm(data)
    return render(request, 'polls/change_opened_poll_setting.html', {
        'set_up_poll_form': set_up_poll_form, 'poll_uuid': uuid
    })



########################
#views

'''view of the home page'''
class IndexView(generic.ListView):

    template_name = 'polls/index.html'
    context_object_name = 'latest_poll_list'

    def get_queryset(self):
        #return the last 3 published polls
        return Poll.objects.filter(admin = self.request.user).order_by('-creation_date')[:3]

    #decorate the class based view
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(IndexView, self).dispatch(*args, **kwargs)

'''view of to create a new poll'''
class CreatePollWizardView(SessionWizardView):

    form_list = [CreatePollGeneralSettingForm,
                 CreatePollInputForm,
                 CreatePollOutputForm,
                 CreatePollAlternativeForm,
                 CreatePollParticipantForm,
                 CreatePollPreviewForm]

    #decorate the class based view
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(SessionWizardView, self).dispatch(*args, **kwargs)

    def get_template_names(self):
        return [TEMPLATES[self.steps.current]]

    ''' add some default data to the form'''
    def get_form_initial(self, step):

        if step == '0':
            # add the default opening date and closing date
            opening_date_default = timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M')
            closing_date_default = timezone.localtime(timezone.now() + datetime.timedelta(days=1)).strftime('%d/%m/%Y %H:%M')
            # set the poll to private
            poll_private_default = True
            return self.initial_dict.get(step, {'opening_date': opening_date_default, 'closing_date': closing_date_default, 'poll_private': poll_private_default})
        return self.initial_dict.get(step, {})


    '''load extra data for the template'''
    def get_context_data(self, form, **kwargs):

        context = super(CreatePollWizardView, self).get_context_data(form = form, **kwargs)
        #load the data for the preview step
        if self.steps.current == self.steps.last:
            poll_data = self.get_cleaned_data_for_step('0') #returned type is dict
            poll_data.update(self.get_cleaned_data_for_step('1'))
            poll_data.update(self.get_cleaned_data_for_step('2'))
            context.update({'poll_data': poll_data})

            # Create alternative object
            alt_desc_list = re.split(' *\r\n *', self.get_cleaned_data_for_step('3')["alternative"])
            alternative_data = []
            for alt_desc in alt_desc_list:
                val = re.split(' *-- *', alt_desc)
                alternative_name = val[0]
                alternative_description = val[-1] if len(val) > 1 else None
                alternative_data.append(
                    dict(alternative_name = alternative_name,
                         alternative_description = alternative_description))
            context.update({'alternative_data': alternative_data})

            if self.get_cleaned_data_for_step('3')["tie_breaking"] == 'Custom':
                tie_breaking_data = self.get_cleaned_data_for_step('3')["tie_breaking_rule"]
                context.update({'tie_breaking_data': tie_breaking_data})

            participant_data = re.split(' *\r\n *', self.get_cleaned_data_for_step('4')["participant"])
            context.update({'participant_data': participant_data})
        return context

    '''method run before going to the next step'''
    def render_next_step(self, form, **kwargs):
        if self.steps.next == self.steps.last and self.get_cleaned_data_for_step('0') == None:
            #redirect if the poll creation took too much time such that the poll opening date is not valid anymore
            return HttpResponseRedirect(reverse('polls:oops'))
        return super(CreatePollWizardView, self).render_next_step(form = form, **kwargs)

    '''after the final submission'''
    def done(self, form_list, **kwargs):

        #check if all form are valid
        for form in form_list :
            logger.debug("done() : form extracted " + str(form))
            if not form.is_valid():
                logger.debug("done() : form not valid")
                return HttpResponseRedirect(reverse('polls:oops'))

        #get the voter object linked to the logged in user exist or create it
        admin = self.request.user

        poll_name = form_list[0].cleaned_data['poll_name']
        poll_question = form_list[0].cleaned_data['poll_question']
        poll_description = form_list[0].cleaned_data['poll_description']
        poll_temporary_result = form_list[0].cleaned_data['poll_temporary_result']
        poll_private = form_list[0].cleaned_data['poll_private']
        poll_change_vote = form_list[0].cleaned_data['poll_change_vote']
        recursive_poll = form_list[0].cleaned_data["recursive_poll"]
        recursive_period = form_list[0].cleaned_data["recursive_period"]

        opening_date = form_list[0].cleaned_data['opening_date']
        closing_date = form_list[0].cleaned_data['closing_date']
        input_type = form_list[1].cleaned_data['input_type']
        output_type = form_list[2].cleaned_data['output_type']

        if form_list[3].cleaned_data['tie_breaking']:
            tie_breaking = 'Custom'
        else:
            tie_breaking = 'Random'

        poll = Poll(admin = admin,
                    uuid = uuid.uuid4(),
                    name = poll_name,
                    question = poll_question,
                    description = poll_description,
                    temporary_result = poll_temporary_result,
                    private = poll_private,
                    input_type = input_type,
                    output_type = output_type,
                    creation_date = timezone.now(),
                    opening_date = opening_date,
                    closing_date = closing_date,
                    tie_breaking = tie_breaking,
                    change_vote = poll_change_vote,
                    recursive_poll = recursive_poll,
                    recursive_period = recursive_period,
                    )
        poll.save()
        logger.debug("New poll created : " + poll.name + " (pk:" + str(poll.pk) + ")" )

        # Create alternative object
        alt_desc_list = re.split(' *\r\n *', form_list[3].cleaned_data['alternative'])

        # Process tie breaking
        if tie_breaking == 'Custom':
            tie_breaking_rule = re.split(' *> *', form_list[3].cleaned_data['tie_breaking_rule']  )
            logger.debug("done() tie_breaking_rule  splited " + str(tie_breaking_rule))
        else :
            # create a randomized tie breaking rule
            random_tie_breaking_rule = np.random.permutation(len(alt_desc_list))

        for idx, alt_desc in enumerate(alt_desc_list):
            val = re.split(' *-- *', alt_desc)
            alternative_name = val[0]
            alternative_description = val[-1] if len(val) > 1 else None
            altenaritive_priority = tie_breaking_rule.index( alternative_name ) +1 if tie_breaking == 'Custom' else  random_tie_breaking_rule[idx] +1

            alternative = Alternative( name = alternative_name,
                                       description = alternative_description,
                                       poll = poll,
                                       priority_rank = altenaritive_priority,
                                       )
            alternative.save()
            logger.debug("New Alternative : " + alternative.name + " (pk:" + str(alternative.pk) + " poll:" + alternative.poll.name +")")

        if 'participant' in form_list[4].cleaned_data.keys() and form_list[4].cleaned_data['participant'].__len__() > 0:
            #specify the participants
            participant_list = re.split(' *\r\n *', form_list[4].cleaned_data['participant'])
            message =()
            for participant in participant_list:
                if participant != "default_voter@pnyx.com":
                    # email used for all public poll
                    voter, created = Voter.objects.get_or_create(email= participant)
                    poll.participant.add(voter)

                    message_data = {
                        'admin': self.request.user,
                        'voter_uuid': voter.uuid if poll.private else 'public',
                        'poll': poll,
                        'domain': self.request.get_host(),
                        'protocol': self.request.is_secure() and 'https' or 'http',
                    }

                    logger.debug("Voter " + voter.email + " added to the poll " + str(poll.pk))

                    message += (('You have been added to a new poll on Pnyx',
                                render_to_string('polls/added_to_poll_email.html', message_data),
                                self.request.user.email,
                                [participant]),)
            send_mass_mail(message, fail_silently = False)

        #redirect to the confirmation page
        return HttpResponseRedirect(reverse('polls:create_poll_confirmation', kwargs={'uuid': poll.uuid}))

'''confirmation page that the poll is created'''
class CreatePollConfirmation(generic.TemplateView):
    template_name = "polls/create_poll_confirmation.html"

    #decorate the class based view
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(CreatePollConfirmation, self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(CreatePollConfirmation, self).get_context_data(**kwargs)
        context['domain'] = self.request.get_host()
        context['protocol'] = self.request.is_secure() and 'https' or 'http'
        context['private'] = get_object_or_404(Poll, uuid = kwargs['uuid']).private

        return context

'''dashboard with all existing polls'''
class ManagePollView(generic.ListView):
    template_name = 'polls/manage_poll.html'
    context_object_name = 'current_poll_list'

    #decorate the class based view
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(ManagePollView, self).dispatch(*args, **kwargs)

    def get_queryset(self):
        #return the running polls
        logger.debug("Get the polls currently opened for the Manage View" )
        timestamp = timezone.now()
        key =  Poll.objects.filter(
            admin = self.request.user
        ).filter(
            opening_date__lte= timestamp
        ).filter(
            closing_date__gte = timestamp
        ).order_by(
            '-creation_date'
        )
        return key
    '''add the other polls'''
    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        logger.debug("Add the upcoming polls and the closed ones for the Manage View")
        context = super(ManagePollView, self).get_context_data(**kwargs)
        timestamp = timezone.now()
        context['upcoming_poll_list'] = Poll.objects.filter(
            admin = self.request.user
        ).exclude(
            opening_date__lte= timestamp
        ).order_by(
            '-creation_date'
        )

        context['closed_poll_list'] = Poll.objects.filter(
            admin = self.request.user
        ).exclude(
            closing_date__gte= timestamp
        ).order_by(
            '-creation_date'
        )
        return context

'''view detailing all the proprties of one poll'''
class DetailView(generic.DetailView):

    slug_url_kwarg = 'uuid'
    slug_field = 'uuid'
    model = Poll
    template_name = 'polls/detail.html'

    #decorate the class based view
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        poll = Poll.objects.get(uuid = kwargs['uuid'])
        if not poll.admin == request.user:
            logger.debug("user and admin are different: no right to see the details")
            return HttpResponseRedirect(reverse('polls:no_right'))
        return super(DetailView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(DetailView, self).get_context_data(**kwargs)
        poll = context['poll']
        if poll.tie_breaking == 'Custom':
            tie_breaking_rule = ""
            alternative_set = list(poll.alternative_set.all().order_by('priority_rank'))
            for alt in alternative_set:
                tie_breaking_rule += alt.name
                tie_breaking_rule += ">"
            tie_breaking_rule = tie_breaking_rule[:-1]  #delete the last "<"
            context['tie_breaking_rule'] = tie_breaking_rule

        return context

'''view confirming the changes performed on an existing poll'''
class UpdateConfirmationView(generic.DetailView):
    slug_url_kwarg = 'uuid'
    slug_field = 'uuid'
    model = Poll
    template_name = 'polls/change_poll_confirmation.html'

    #decorate the class based view
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        poll = Poll.objects.get(uuid = kwargs['uuid'])
        if not poll.admin == request.user:
            logger.debug("user and admin are different: no right to modify the poll")
            return HttpResponseRedirect(reverse('polls:no_right'))
        return super(UpdateConfirmationView, self).dispatch(request, *args, **kwargs)

'''view when a user try to see a poll of another user'''
class NoRightView(generic.TemplateView):
    template_name = 'polls/no_right.html'

'''view that delete and confirm the deletion of a poll'''
class DeletePollView(generic.DetailView):
    slug_url_kwarg = 'uuid'
    slug_field = 'uuid'
    model = Poll
    template_name = 'polls/delete_poll.html'

    #decorate the class based view
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        poll = Poll.objects.get(uuid = kwargs['uuid'])
        if not poll.admin == request.user:
            logger.debug("user and admin are different: no right to delete the poll")
            return HttpResponseRedirect(reverse('polls:no_right'))
        return super(DeletePollView, self).dispatch(request, *args, **kwargs)

    #override get_context_data to delete the poll
    def get_context_data(self, **kwargs):
        context = super(DeletePollView, self).get_context_data(**kwargs)
        poll = context['poll']
        poll.delete()
        logger.debug("Poll " + str(poll.pk) + "deleted")
        return context

'''view containg the preference profile under preflibs standards'''
class PreflibView(generic.DetailView):
    slug_url_kwarg = 'uuid'
    slug_field = 'uuid'
    model = Poll
    template_name = 'polls/preflib.html'

    #decorate the class based view
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        poll = Poll.objects.get(uuid = kwargs['uuid'])
        if not poll.admin == request.user:
            logger.debug("user and admin are different")
            return HttpResponseRedirect(reverse('polls:no_right'))
        return super(PreflibView, self).dispatch(request, *args, **kwargs)

    #add the preference profile
    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super(PreflibView, self).get_context_data(**kwargs)
        poll = context['poll']
        alternative_set = list(poll.alternative_set.all())
        alt_name_list = []
        for alt in alternative_set:
            alt_name_list.append(alt.name)
        context['alternative_set'] = alternative_set
        pref_lib = []
        if poll.input_type =='Bi':

            majority_graph_matrix, alternative_pk_list = get_majority_graph_matrix(poll)
            query_set_pref = BinaryRelation.objects.filter(dominant__poll = poll.pk).order_by('voter__pk'). \
                distinct().all()  #.all() cache the value
            context['nb_voter'] = len(list(query_set_pref.values('voter__uuid').all()))
            context['nb_vote'] = majority_graph_matrix.sum()
            context['nb_unique_order'] = np.count_nonzero(majority_graph_matrix)


            for (x,y), value in np.ndenumerate(majority_graph_matrix):
                if value != 0:
                    pref_lib.append(str(value) + ',' + str(poll.alternative_set.get(pk = alternative_pk_list[x]).name) +
                                    ',' + str(poll.alternative_set.get(pk = alternative_pk_list[y]).name))

        else:
            pref_profile = get_transitive_preference(poll)
            context['nb_voter'] = len(pref_profile)
            context['nb_vote'] = len(pref_profile)
            for pref_voter in pref_profile:
                #the preference of one voter
                pref_lib.append('')
                for pref in pref_voter:
                    #pref for rank #idx for the voter
                    if len(pref.alternative.all()) == 1:
                        pref_lib[-1] += pref.alternative.all()[0].name + ','
                    else:
                        pref_lib[-1] += '{'
                        for alt in pref.alternative.all():
                            pref_lib[-1] += alt.name + ','
                        pref_lib[-1] = pref_lib[-1][:-1]  #delete the last ","
                        pref_lib[-1] +='},'

                    if poll.input_type == 'Pf' or poll.input_type == 'Di':
                        unselected_alt = [e for e in alt_name_list if e not in pref_lib[-1]]
                        if len(unselected_alt) == 1:
                            pref_lib[-1] += unselected_alt[0] + ','
                        elif len(unselected_alt)>1:
                            pref_lib[-1] += '{'
                            for alt_name in unselected_alt:
                                pref_lib[-1] += alt_name + ','
                            pref_lib[-1] = pref_lib[-1][:-1]  #delete the last ","
                            pref_lib[-1] += '},'

                pref_lib[-1] = pref_lib[-1][:-1]  #delete the last ","

            #remove duplicated value
            counter =  Counter(pref_lib)
            pref_lib=[]
            for key, value in counter.iteritems():
                pref_lib.append(str(value) + ',' + key)

            context['nb_unique_order'] = len(pref_lib)

        for idx, current_pref in enumerate(pref_lib):
            for index, alt in enumerate(alternative_set):
                current_pref = current_pref.replace(alt.name, str(index + 1))
            pref_lib[idx] = current_pref

        context['pref_lib']=pref_lib
        logger.debug("Preflib of poll " + str(poll.pk) + "computed")
        return context

'''view that allows to update the settings of an existing poll.
Depeding on the status of the poll an adapted poll will be used'''
@login_required
def change_settings_view(request, uuid, *args, **kwargs):

    poll = Poll.objects.get(uuid = uuid)
    if not poll.admin == request.user:
        logger.debug("user and admin are different: no right to see the details")
        return HttpResponseRedirect(reverse('polls:no_right'))
    elif poll.opening_date >= timezone.now():
        #the poll is not opened yet
        return set_upcoming_poll(poll, request, uuid)
    elif poll.closing_date <= timezone.now():
        #the poll is closed
        return set_closed_poll(poll, request, uuid)
    else:
        #the poll is opened
        return set_opened_poll(poll, request, uuid)

'''send a email to the participant of a given poll. This is sent through pnyx email adress'''
class EmailParticipant(generic.FormView):
    slug_url_kwarg = 'uuid'
    slug_field = 'uuid'
    template_name = 'polls/email_participant.html'
    form_class = EmailParticipantForm

    def form_valid(self, form):
        # This method is called when valid form data has been POSTed.
        # It should return an HttpResponse.
        participant_list = list(get_object_or_404(Poll, uuid = self.kwargs['uuid']).participant.all())
        email_list = ()
        for participant in participant_list:
            email_list += (participant.email),
        if email_list:
            #specify the participants
            email = EmailMessage(subject = form.cleaned_data['subject'], body = form.cleaned_data['message'], from_email = self.request.user.email, bcc = email_list)
            email.send(fail_silently = False)
        return HttpResponseRedirect(reverse('polls:detail', kwargs = self.kwargs))

'''View confirming the emails have been sent'''
class EmailParticipantConfirmation(generic.DetailView):
    #not used
    slug_url_kwarg = 'uuid'
    slug_field = 'uuid'
    model = Poll
    template_name = 'polls/email_participant_confirmation.html'

    #decorate the class based view
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        poll = Poll.objects.get(uuid = kwargs['uuid'])
        if not poll.admin == request.user:
            logger.debug("user and admin are different: no right to delete the poll")
            return HttpResponseRedirect(reverse('polls:no_right'))
        return super(EmailParticipantConfirmation, self).dispatch(request, *args, **kwargs)

'''Resend the links of a given poll to the participants. This is sent through pnyx email adress'''
@login_required
def send_link_participant(request, uuid, *args, **kwargs):

    poll = get_object_or_404(Poll, uuid = uuid)
    if not poll.admin == request.user:
        logger.debug("user and admin are different: no right to see send_link_participant")
        return HttpResponseRedirect(reverse('polls:no_right'))
    else:
        if request.method == 'POST':
            send_link_form = SendLinkParticipantForm(request.POST)
            print send_link_form
            print send_link_form.cleaned_data
            #print send_link_form.cleaned_data
            # add the new participants and email them
            if 'notify_all' in send_link_form.cleaned_data.keys():
                # add all voters in the list
                tmp_list = list(poll.participant.all())
                participant_list = list()
                for tmp in tmp_list:
                    participant_list.append(tmp.email)

            elif 'participant_to_notify' in send_link_form.cleaned_data.keys() \
                    and send_link_form.cleaned_data['participant_to_notify'].__len__() > 0:
                # add the selected voter
                participant_list = list(
                    send_link_form.cleaned_data["participant_to_notify"]
                )

            message = ()
            for email in participant_list:
                if email != "default_voter@pnyx.com":
                    voter, created = Voter.objects.get_or_create(email = email)
                    if created:
                        # remove the new voter
                        voter.delete()
                    else:
                        message_data = {
                            'admin': request.user,
                            'voter_uuid': voter.uuid if poll.private else 'public',
                            'poll': poll,
                            'domain': request.get_host(),
                            'protocol': request.is_secure() and 'https' or 'http',
                        }
                        logger.debug("Voter " + voter.email + " notifed of poll's links " + str(poll.pk))
                        message += (('The links to your Pnyx poll',
                                     render_to_string('polls/send_link_participant_email.html', message_data),
                                     request.user.email,
                                     [email]),)

            send_mass_mail(message, fail_silently = False)

            return HttpResponseRedirect(reverse('polls:detail', kwargs = {'uuid': uuid}))
        else:
            send_link_form = SetUpClosedPollForm()

        return render(request, 'polls/send_link_participant.html', {
            'send_link_form': send_link_form,
            'poll':poll,
            'poll_uuid': uuid,
            'voter_uuid': 'voter-id-abc123' if poll.private else 'public',
            'domain': request.get_host(),
            'protocol': request.is_secure() and 'https' or 'http',

        })

class OopsView(generic.TemplateView):
    template_name = 'polls/oops.html'