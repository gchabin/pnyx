from django.db import models
from polls.models import *
from django.contrib.auth.models import User
from django import forms
import datetime
from django.forms.utils import ErrorList
from django.utils import timezone
from django.core.urlresolvers import reverse_lazy
from django.core.exceptions import ValidationError
import re #regex



def validate_stricly_positive(value):
    if value  <= 0:
        raise ValidationError('%s is not a stricly positiv number' % value)

class TransitivePreference(models.Model):

    alternative = models.ManyToManyField(Alternative)
    rank = models. PositiveIntegerField(validators=[validate_stricly_positive])
    voter = models.ForeignKey(Voter)


    def __unicode__(self):
        return str(self.rank) +":" +str(self.alternative.all())

    def __str__(self):
        return str(self.rank) + ":" + str(self.alternative.all())


class BinaryRelation(models.Model):

    dominant = models.ForeignKey(Alternative, related_name='dominant')
    dominated = models.ForeignKey(Alternative, related_name='dominated')
    voter = models.ForeignKey(Voter)


    def __unicode__(self):
        return str(self.dominant.name) + "->" + str(self.dominated.name)


    def __str__(self):
        return str(self.dominant.name) + "->" + str(self.dominated.name)
