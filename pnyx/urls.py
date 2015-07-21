from django.conf.urls import patterns, include, url
from django.core.urlresolvers import reverse_lazy
from django.views.generic import RedirectView
from django.contrib import admin
from django.conf.urls.static import static
from django.conf import settings


admin.autodiscover()

urlpatterns = patterns('',

    #subapps
    url('^$', RedirectView.as_view(url=reverse_lazy('polls:index'), permanent=True)),
    url(r'^polls/', include('polls.urls', namespace="polls" )),
    url(r'^vote/', include('vote.urls', namespace = "vote")),
    url(r'^admin/', include(admin.site.urls), name='admin'),
    url(r'^accounts/', include('accounts.urls')),
    url(r'^about/', include('about.urls')),
)

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)