__author__ = 'guillaumechabin'
'''This command process the poll that has been closed. It notifies the users and computes the results'''

from django.core.management.base import NoArgsCommand
from polls.models import Poll, Voter
from django.utils import timezone
from django.core.mail import send_mass_mail
from django.template.loader import render_to_string

import kronos
import datetime

import logging
logger = logging.getLogger(__name__)

@kronos.register('* * * * *') #cron settings to run every minute
class Command(NoArgsCommand):
    help = 'Closes the polls for voting, notifies the users and computes the results'

    def handle_noargs(self, **options):
        time_interval = datetime.timedelta(minutes=1)
        timestamp = timezone.now().replace(second=0, microsecond=0)
        # get recently closed polls
        recently_closed_poll_list = Poll.objects.filter(
            closing_date__lt = timestamp
        ).filter(
            closing_date__gte = timestamp - time_interval
        )

        for poll in recently_closed_poll_list:
            #self.stdout.write('Poll: '+str(poll.pk), ending = '')
            # TODO compute the winner
            # if the poll contains user : send notify them
            participant_list = list(poll.participant.all())
            email_list = ()
            for participant in participant_list:
                message = ()
                if participant.email != "default_voter@pnyx.com":
                    # email used for all public poll
                    self.stdout.write('Voter: ' +participant.email, ending = '')
                    message_data = {
                        'admin': poll.admin,
                        'voter_uuid': participant.uuid if poll.private else 'public',
                        'poll': poll,
                        'domain': 'pnyx.dss.in.tum.de',
                        'protocol': 'https',
                    }
                    logger.debug("Voter " + participant.email + " notified about the end of the poll " + str(poll.pk))

                    message += (('Your Pnyx poll has been closed, please check the final results',
                                 render_to_string('polls/poll_closed_email.html', message_data),
                                 'team.pnyx@gmail.com',
                                 [participant.email]),)
            send_mass_mail(message, fail_silently = False)