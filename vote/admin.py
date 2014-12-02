from django.contrib import admin
from vote.models import TransitivePreference, BinaryRelation


admin.site.register(TransitivePreference)
admin.site.register(BinaryRelation)