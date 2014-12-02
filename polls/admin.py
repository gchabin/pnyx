from django.contrib import admin
from polls.models import Poll, Alternative, Voter

admin.site.register(Poll)
admin.site.register(Alternative)
admin.site.register(Voter)