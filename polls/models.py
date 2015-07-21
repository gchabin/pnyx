#from StdSuites.Type_Names_Suite import type_element_info
from django.db import models
from django.contrib.auth.models import User
from django import forms
import datetime

from django.forms.utils import ErrorList
from django.utils import timezone
from django.core.urlresolvers import reverse_lazy
from django.core.exceptions import ValidationError

from captcha.fields import ReCaptchaField

import re #regex
import uuid
import logging

logger = logging.getLogger(__name__)

###########Choice/Select####

TIE_BREAKING = (
    ('Custom', 'Customized tie breaking rule'),
    ('Random', 'Randomized tie breaking rule'),
)

INPUT_TYPE = (
    ('Pf', 'Most preferred alternatives'),
    ('Di', 'Dichotomous preferences'),
    ('Li', 'Linear orders'),
    ('Pd', 'Complete preorders'),
    ('Bi', 'Complete binary relation'),
)

OUTPUT_TYPE = (
    ('B', 'Best ALternative'),
    ('L', 'Lottery'),
    ('R', 'Ranking'),
)

class MultipleChoiceFieldNoValidation(forms.MultipleChoiceField):
    def validate(self, value):
        pass


###########Model############
'''this object represents any participant to a poll. The uuid will be the authentification key used in private links.
 If the voter is unregistered (public poll) the address is default_voter@pnyx.com '''
class Voter(models.Model):

    email = models.EmailField(max_length=75, default = 'default_voter@pnyx.com')
    uuid = models.CharField(max_length = 36, default = uuid.uuid4,editable = False, unique= True)

    def __unicode__(self):
        return self.email

    def __str__(self):
        return self.email

'''This object represents the poll object and its properties.'''
class Poll(models.Model):

    name = models.CharField(max_length=60)
    question = models.CharField(max_length=200)
    description = models.TextField(null = True, blank = True)

    private = models.BooleanField(default=True)
    change_vote =  models.BooleanField(default=False)

    temporary_result = models.BooleanField(default=False)
    tie_breaking = models.CharField(max_length = 6, choices = TIE_BREAKING)
    tie_breaking_used = models.NullBooleanField( blank = True)

    input_type = models.CharField(max_length=2, choices=INPUT_TYPE)
    output_type = models.CharField(max_length=1, choices=OUTPUT_TYPE)

    creation_date = models.DateTimeField(auto_now_add=True )
    opening_date = models.DateTimeField(default=timezone.now())
    closing_date = models.DateTimeField(default=timezone.now())

    recursive_poll = models.BooleanField(default=False)
    recursive_period = models.PositiveIntegerField(blank = True , null = True)

    participant = models.ManyToManyField(Voter, blank = True)
    admin = models.ForeignKey(User)  #creator of the poll
    uuid = models.CharField(max_length = 36, default = uuid.uuid4, editable = False, unique = True) #not used but would allow to make links more complex (wiyh the uuid instead of id


    def get_absolute_url(self):
        return reverse_lazy('polls:index')

    def __unicode__(self):
        return unicode(self.name)

    def __str__(self):
        return self.name

    def was_published_recently(self):
        return self.creation_date >= timezone.now() - datetime.timedelta(days=1)

    def get_progress(self):
        if self.opening_date >= timezone.now() :
            return 0
        elif self.closing_date <= timezone.now() :
            return 100
        else:
            td1 = timezone.now() - self.opening_date
            td2 = self.closing_date - self.opening_date
            return int(100*td1.total_seconds() / td2.total_seconds())
        
    def get_remaining_time(self):
        if self.closing_date <= timezone.now() :
            td = datetime.timedelta(seconds=0)
        else:
            td = self.closing_date - timezone.now()
        return ':'.join(str(td).split(':')[:2])

    def get_choice_rule(self):

        choice_rule = None
        if self.output_type == 'B':
            if self.input_type == 'Pf' or self.input_type == 'Di':
                choice_rule = 'plurality'
            elif self.input_type == 'Li':
                choice_rule = 'borda'
            elif self.input_type == 'Pd':
                choice_rule = 'partially_ordered_borda'
            elif self.input_type == 'Bi':
                choice_rule = 'young'

        elif self.output_type == 'R':
            if self.input_type == 'Pf' or self.input_type == 'Di':
                choice_rule = 'plurality_score'
            elif self.input_type == 'Li' or self.input_type == 'Pd' or self.input_type == 'Bi':
                choice_rule = 'kemeny'

        elif self.output_type == 'L':
            if self.input_type == 'Pf':
                choice_rule = 'uniform_plurality_lottery'
            elif self.input_type == 'Di':
                choice_rule = 'uniform_approval_lottery'
            elif self.input_type == 'Li' or self.input_type == 'Pd' or self.input_type == 'Bi':
                choice_rule = 'maximal_lottery'

        logger.debug(
            "Get choice rule: input = " + self.input_type + " output: " + self.output_type + "=> choice rule:" + choice_rule)
        return choice_rule

    def get_ballot_template_name(self):
        template_name = None
        if self.input_type == 'Pf':
            template_name = 'vote/ballot_most_preferred_alternative.html'
        elif self.input_type == 'Di':
            template_name = 'vote/ballot_dichotomous.html'
        elif self.input_type == 'Li':
            template_name = 'vote/ballot_linear_order.html'
        elif self.input_type == 'Pd':
            template_name = 'vote/ballot_complete_preorder.html'
        elif self.input_type == 'Bi':
            template_name = 'vote/ballot_complete_binary_relation.html'
        return template_name


    def get_results_template_name(self):
        template_name = None
        if self.output_type == 'B':
            template_name = 'vote/results_best_alternative.html'
        elif self.output_type == 'L':
            template_name = 'vote/results_lottery.html'
        elif self.output_type == 'R':
            template_name = 'vote/results_ranking.html'
        return template_name

    was_published_recently.admin_order_field = 'creation_date'
    was_published_recently.boolean = True
    was_published_recently.short_description = 'Created recently?'

'''The object represent an alternative from a poll'''
class Alternative(models.Model):

    name = models.CharField(max_length = 100)
    description = models.TextField(null = True, blank = True)
    poll = models.ForeignKey(Poll)
    priority_rank = models.IntegerField( null = True, blank = True)
    final_rank = models.FloatField(null = True, blank = True) #currently storing the final rank,
    # we cannot store the score because of the ties

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.name

##########Form##########

'''this form is part of the creation process. It contains the general settings about the poll to create'''
class CreatePollGeneralSettingForm(forms.Form):
    
    poll_name = forms.CharField(max_length=100)
    poll_question = forms.CharField(max_length=100)
    poll_description = forms.CharField(widget=forms.Textarea, required=False)
    poll_private_poll = forms.BooleanField(required=False)
    poll_temporary_result = forms.BooleanField(required=False)
    poll_private = forms.BooleanField(required=False)
    poll_change_vote = forms.BooleanField(required=False)

    opening_date = forms.DateTimeField( input_formats = ['%d/%m/%Y %H:%M', '%d-%m-%Y %H:%M'])
    closing_date = forms.DateTimeField( input_formats = ['%d/%m/%Y %H:%M', '%d-%m-%Y %H:%M'])

    recursive_poll = forms.BooleanField(required = False)
    recursive_period = forms.IntegerField(required=False)

    def is_valid(self):

        # run the parent validation first
        valid = super(CreatePollGeneralSettingForm, self).is_valid()
        #check in compatibility of the dates
        if valid and not timezone.now() - self.cleaned_data["opening_date"] < datetime.timedelta( minutes = 30):
            # 30 minutes tolerance allowed
            self._errors["opening_date"] = ErrorList([u"The opening date is already passed"])
            valid = False
        if  valid and not self.cleaned_data["opening_date"] < self.cleaned_data["closing_date"]:
            self._errors["closing_date"] = ErrorList([u"The closing date should be after the opening date"])
            valid = False

        delta_time = self.cleaned_data["closing_date"]- self.cleaned_data["opening_date"]

        if valid and self.cleaned_data["recursive_poll"] and not self.cleaned_data["recursive_period"]:
            self._errors["recursive_period"] = ErrorList(
                [u"Please enter a period"])
            valid = False
        if valid and self.cleaned_data["recursive_poll"] and  delta_time > datetime.timedelta(days=self.cleaned_data["recursive_period"]):
            self._errors["recursive_period"] = ErrorList([u"The period of the poll should be greater than the poll time frame"])
            valid = False

        return valid

'''this form is part of the creation process. It contains input type of the poll to create'''
class CreatePollInputForm(forms.Form):
    input_type = forms.ChoiceField(choices=INPUT_TYPE, widget=forms.RadioSelect())

'''this form is part of the creation process. It contains output type of the poll to create'''
class CreatePollOutputForm(forms.Form):
    output_type = forms.ChoiceField(choices=OUTPUT_TYPE, widget=forms.RadioSelect())

'''this form is part of the creation process. It contains alternatives and the tie breaking rule of the poll to create'''
class CreatePollAlternativeForm(forms.Form):

    alternative= forms.CharField(widget=forms.Textarea)
    tie_breaking = forms.BooleanField(required=False)
    #tie_breaking = forms.ChoiceField(choices=TIE_BREAKING, widget=forms.RadioSelect())
    tie_breaking_rule = forms.CharField(widget = forms.Textarea, required = False)

    def is_valid(self):
        # run the parent validation first
        valid = super(CreatePollAlternativeForm, self).is_valid()
        #check if the regex is valid
        if valid:
            #valid if one alternative per line with name smaller than 100 char
            # Create alternative object
            alt_name_desc_list = re.split(' *\r\n *', self.cleaned_data['alternative'])
            alt_name_list = []
            for alt_desc in alt_name_desc_list:
                val = re.split(' *-- *', alt_desc)
                if len(val[0])>100:
                    self._errors["alternative"] = ErrorList([u"An alternative name has to be smaller than 100 characters"])
                    valid = False
                elif not val[0]:
                    self._errors["alternative"] = ErrorList([u"Alternative names cannot be empty, the last line may be empty"])
                    valid = False
                else:
                    alt_name_list.append(val[0])
        if valid and len(set(alt_name_list)) != len(alt_name_list):
            self._errors["alternative"] = ErrorList([u"Several alternatives cannot share the same name within a poll"])
            valid = False
        if valid and self.cleaned_data['tie_breaking']:
            # check if repeated value
            alt_priority_list = re.split(' *> *', self.cleaned_data['tie_breaking_rule'])
            if sorted(alt_priority_list) != sorted(alt_name_list):
                logger.debug(str(alt_priority_list) + "////" +str(alt_name_list))
                self._errors["tie_breaking_rule"] = ErrorList([u"Not all the alternatives are specified"])
                valid = False
        return valid

'''this form is part of the creation process. It contains participant's emails of the poll to create'''
class CreatePollParticipantForm(forms.Form):
    participant= forms.CharField(widget=forms.Textarea, required= False)

    def is_valid(self):
        valid = super(CreatePollParticipantForm, self).is_valid()
        #check if the regex is valid
        if "participant" in self.cleaned_data.keys() and len(self.cleaned_data["participant"]) > 0:
            # the contains participant key with non-empty  string
            m = re.match('$|([a-zA-Z0_9](\w|\.|-)*@[a-zA-Z0_9](\w|\.|-)*\.[a-zA-Z]{1,63}\r\n)*'
                         '([a-zA-Z0_9](\w|\.|-)*@[a-zA-Z0_9](\w|\.|-)*\.[a-zA-Z]{1,63}$)',
                         self.cleaned_data["participant"])
            if valid and not m:
                #m is false if the matching rule is not verified
                self._errors["participant"] = ErrorList([u"Please enter one valid email per line"])
                valid = False
        return valid

'''this form is part of the creation process. It is an empty form to display the preview step.'''
class CreatePollPreviewForm(forms.Form):
    poll_preview = forms.BooleanField(required=False)

'''Contains the information to update if the poll is already running.'''
class SetUpOpenedPollForm(forms.Form):
    poll_name = forms.CharField(max_length=100)
    poll_description = forms.CharField(widget=forms.Textarea, required=False)
    poll_temporary_result = forms.BooleanField(required=False)

    closing_date = forms.DateTimeField(input_formats = ['%d/%m/%Y %H:%M', '%d-%m-%Y %H:%M'])

    voter_to_add = forms.CharField(widget = forms.Textarea, required = False)

    def is_valid(self):
        valid = super(SetUpOpenedPollForm, self).is_valid()
        #check in compatibility of the dates
        if valid and not self.cleaned_data["closing_date"] > timezone.now():
            self._errors["closing_date"] = ErrorList([u"The closing date already passed"])
            valid = False

        if "voter_to_add" in self.cleaned_data.keys() and len(self.cleaned_data["voter_to_add"]) > 0:
            m = re.match('$|([a-zA-Z0_9](\w|\.|-)*@[a-zA-Z0_9](\w|\.|-)*\.[a-zA-Z]{1,63}\r\n)*'
                         '([a-zA-Z0_9](\w|\.|-)*@[a-zA-Z0_9](\w|\.|-)*\.[a-zA-Z]{1,63}$)',
                         self.cleaned_data["voter_to_add"])

            if valid and not m:
                #Please enter one valid email per line"
                self._errors["voter_to_add"] = ErrorList([u"Please enter one valid email per line"])
                valid = False

        return valid

'''Contains the information to update if the poll is already closed.'''
class SetUpClosedPollForm(forms.Form):
    poll_name = forms.CharField(max_length = 100)
    poll_description = forms.CharField(widget = forms.Textarea, required = False)

'''Contains the information to update if the poll is not opened yet.'''
class SetUpUpcomingPollForm(forms.Form):
    poll_name = forms.CharField(max_length = 100)
    poll_question = forms.CharField(max_length = 100)
    poll_description = forms.CharField(widget = forms.Textarea, required = False)

    voter_to_remove = MultipleChoiceFieldNoValidation(required = False)
    voter_to_add = forms.CharField(widget = forms.Textarea, required = False)

    alternative_to_remove = MultipleChoiceFieldNoValidation(required = False)
    alternative_to_add = forms.CharField(widget = forms.Textarea, required = False)

    poll_private = forms.BooleanField(required=False)
    poll_change_vote = forms.BooleanField(required=False)

    poll_temporary_result = forms.BooleanField(required = False)
    tie_breaking = forms.BooleanField(required=False)
    tie_breaking_rule = forms.CharField(widget = forms.Textarea, required = False)

    opening_date = forms.DateTimeField(input_formats = ['%d/%m/%Y %H:%M', '%d-%m-%Y %H:%M'])
    closing_date = forms.DateTimeField(input_formats = ['%d/%m/%Y %H:%M', '%d-%m-%Y %H:%M'])

    input_type = forms.ChoiceField(choices = INPUT_TYPE, widget = forms.RadioSelect())
    output_type = forms.ChoiceField(choices = OUTPUT_TYPE, widget = forms.RadioSelect())

    def is_valid(self):
        # run the parent validation first
        valid = super(SetUpUpcomingPollForm, self).is_valid()

        #check in compatibility of the dates
        if valid and not timezone.now() - self.cleaned_data["opening_date"] < datetime.timedelta( minutes = 5):
            #tolerance of 5 minutes
            self._errors["opening_date"] = ErrorList([u"The opening date already passed"])
            valid = False

        if valid and not self.cleaned_data["opening_date"] < self.cleaned_data["closing_date"]:
            self._errors["closing_date"] = ErrorList(
                [u"The closing date should be after the opening date"])
            valid = False

        if valid and len(self.cleaned_data["alternative_to_add"]) > 0:
            #valid if one alternative per line with name smaller than 100 char
            # Create alternative object
            alt_name_desc_list = re.split(' *\r\n *', self.cleaned_data['alternative_to_add'])
            alt_name_list = []
            for alt_desc in alt_name_desc_list:
                val = re.split(' *-- *', alt_desc)
                if len(val[0]) > 100:
                    self._errors["alternative_to_add"] = ErrorList(
                        [u"An alternative name has to be smaller than 100 characters"])
                    valid = False
                elif not val[0]:
                    self._errors["alternative_to_add"] = ErrorList([u"Alterninative name cannot be empty, the last line may be empty"])
                    valid = False
                else:
                    alt_name_list.append(val[0])
            if valid and len(set(alt_name_list)) != len(alt_name_list):
                self._errors["alternative_to_add"] = ErrorList([u"Several alternatives cannot share the same name"])
                #we need to check if there is a conflict with the existing alternatives in the view
                valid = False

        if "voter_to_add" in self.cleaned_data.keys() and len(self.cleaned_data["voter_to_add"]) > 0:
            m = re.match('$|([a-zA-Z0_9](\w|\.|-)*@[a-zA-Z0_9](\w|\.|-)*\.[a-zA-Z]{1,63}\r\n)*'
                         '([a-zA-Z0_9](\w|\.|-)*@[a-zA-Z0_9](\w|\.|-)*\.[a-zA-Z]{1,63})$',
                         self.cleaned_data["voter_to_add"])

            if valid and not m:
                #one email per line
                self._errors["voter_to_add"] = ErrorList([u"Please enter one valid email per line"])
                valid = False
            n = re.match('.*default_voter@pnyx.com.*', self.cleaned_data["voter_to_add"])

            if valid and not n:
                #one email per line
                self._errors["voter_to_add"] = ErrorList([u"This email is used by the system"])
                valid = False
        # check the validity of tie breaking rule in view (need existing information about the poll)
        return valid

class EmailParticipantForm(forms.Form):
        subject = forms.CharField()
        message = forms.CharField(widget = forms.Textarea)
        captcha = ReCaptchaField()

class SendLinkParticipantForm(forms.Form):
    notify_all = forms.BooleanField(required = False)
    participant_to_notify = MultipleChoiceFieldNoValidation(required = False)