from django.shortcuts import render, get_object_or_404, render, render_to_response
from django.views import generic
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseServerError
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.template import RequestContext
from django.utils import timezone
from numpy.distutils import npy_pkg_config

from polls.models import Poll, Alternative, Voter
from vote.models import TransitivePreference, BinaryRelation
from vote.generic_views import *
from decimal import *

import datetime
import uuid
import re #regex
import operator
import numpy as np
import pulp
from itertools import combinations, permutations
import cvxopt


import logging
logger = logging.getLogger(__name__)

#####utils methods######

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


def get_relative_majority_graph(majority_graph_matrix):
    '''return the majortity grah with weighted edges  weighted_matrix[i,j] = max( n_ij-n_ji, 0)'''

    weighted_matrix = np.zeros(majority_graph_matrix.shape, int)
    for i, j in combinations(range(0,majority_graph_matrix.shape[0]), 2):
        weight = majority_graph_matrix[i, j] - majority_graph_matrix[j, i]
        if weight > 0:
            weighted_matrix[i,j]=weight
        elif weight < 0:
            weighted_matrix[j,i ] = -weight
    logger.debug("Compute the relative majority graph:  \r\n" + str(weighted_matrix))
    return weighted_matrix


def get_payoff_matrix_plurality_game(majority_graph_matrix):
    '''return the payoff matrix of the plurality game plurality_game[i,j] = n_ij-n_ji'''

    plurality_game = np.zeros(majority_graph_matrix.shape, int)
    for i, j in combinations(range(0,majority_graph_matrix.shape[0]), 2):
        weight = majority_graph_matrix[i, j] - majority_graph_matrix[j, i]
        plurality_game[i,j] = weight
        plurality_game[j,i] = -weight

    logger.debug("Compute the payoff matrix of the plurality game:  \r\n" + str(plurality_game))
    return plurality_game

def get_majority_graph_matrix(poll):
    ''' returns the majority graph under a matrix form
    alternative_pk_list is the list of the alternative classed by pk
    majority_graph_matrix[index_of_a_alternative_pk_list][index_of_b_in_alternative_pk_list] = n_ab
    since there is indeference, we need n_ab AND n_ba'''

    alternative_pk_list = []
    for alternatinive in poll.alternative_set.all().order_by("name").values("pk"):
        alternative_pk_list.append(alternatinive["pk"])
    majority_graph_matrix = np.zeros((len(alternative_pk_list), len(alternative_pk_list)), "int")

    if poll.input_type != 'Bi':
        #We need to convert the transitive preference to binary relations
        query_set_pref = TransitivePreference.objects.filter(alternative__poll = poll.pk).order_by(
            'voter__pk').distinct().all()  #.all() cache the value
        pref_list = list(query_set_pref.all())  #without list() the queryset is troncated
        voter_pk_list = list(query_set_pref.values('voter__pk').all())  #values() return a list of dict [{voter__pk:pk}]

        for i, j in combinations(range(alternative_pk_list.__len__()), 2):
            for voter_dict in voter_pk_list:
                voter_pk = voter_dict["voter__pk"]
                pref_voter_i = get_object_or_404(query_set_pref, voter__pk = voter_pk,
                                                 alternative = alternative_pk_list[i])
                pref_voter_j = get_object_or_404(query_set_pref, voter__pk = voter_pk,
                                                 alternative = alternative_pk_list[j])
                if pref_voter_i.rank < pref_voter_j.rank:
                    #alternative_i_pk P alternative_j_pk
                    majority_graph_matrix[i, j] += 1
                elif pref_voter_i.rank > pref_voter_j.rank:
                    #alternative_j_pk P alternative_i_pk
                    majority_graph_matrix[j, i] += 1
    else :
        #we get directly the binary relation from the DB
        query_set_bin_mg = BinaryRelation.objects.filter(dominant__poll = poll.pk, dominated__poll = poll.pk).order_by(
            'voter__pk').distinct().all()  #.all() cache the value

        for comparison in query_set_bin_mg:
            dominant_index = alternative_pk_list.index(comparison.dominant.pk)
            dominated_index = alternative_pk_list.index(comparison.dominated.pk)
            majority_graph_matrix[dominant_index,dominated_index] +=  1

    logger.debug("Get the majority graph : poll " + poll.pk.__str__() + " alternative's primary key of the matrix "
                 +  str(alternative_pk_list)  + " matrix: \r\n" + str(majority_graph_matrix))
    return majority_graph_matrix , alternative_pk_list

def get_transitive_preference(poll):
    '''returns a an array containing the transitive preferences for a given poll'''
    transitive_preference = []
    if poll.input_type == 'Bi':
        return None
    else:
        #else get the transtive preference preferences ordered by voter
        query_set_pref = TransitivePreference.objects.filter(alternative__poll = poll.pk).order_by('voter__pk'). \
            distinct().all() #.all() cache the value
        pref_list = list(query_set_pref.all()) #without list() the queryset is troncated
        voter_uuid_list = list(query_set_pref.values('voter__uuid').all()) #list of dict

        #construct the pref_matrix
        #pref_marix is [ [alts[] rank1], ...,[alts[] rank K]]#voter 1, ... , [[alts[] rank1], ...,
        # [alts[] rank K]]#voter N]
        for uuid_dict in voter_uuid_list:
            uuid_value = uuid_dict.get('voter__uuid', False)
            pref_voter = list(query_set_pref.filter(voter__uuid = uuid_value).order_by('rank').all())
            transitive_preference.append(pref_voter)
    logger.debug("Preference profile :" + str(transitive_preference) + ", inptut type: " + poll.input_type)
    return transitive_preference


def get_approval_matrix(poll, transitive_preference):
    '''return the approval matrix of the poll. lrow are alternatives, columns are voters.
    If the voter j aproved the alternative i  approval_matrix[i,j] = 1 else 0'''

    alternative_pk_list = []
    for alternatinive in poll.alternative_set.all().order_by("name").values("pk"):
        alternative_pk_list.append(alternatinive["pk"])

    n_alternaive = len(alternative_pk_list)
    n_voter = len(transitive_preference)

    approval_matrix = np.zeros((n_alternaive, n_voter), int)

    for idx_voter,voter_pref in enumerate(transitive_preference):
        best_alt = voter_pref[0] #get the best class of the dichotomous profile
        if best_alt.rank == 1:
            for alt in best_alt.alternative.all():
                idx_alt = alternative_pk_list.index(alt.pk)
                approval_matrix[idx_alt,idx_voter] = 1
    logger.debug("Aproval matrix for the poll :" + str(poll.pk) + " alternatives " + str(alternative_pk_list) + " matrix "+  str(approval_matrix))
    return approval_matrix, alternative_pk_list


##inner methods
def process_vote_most_preferred_alternative(request, poll, voter_uuid):
    '''view that process a vote for a 'most preferred alternative ballot' and save the preferences in the database'''
    try:
        selected_choice = poll.alternative_set.get(pk = request.POST['choice'])

    except (KeyError, Alternative.DoesNotExist):
        # Redisplay the poll voting form.
        template_name = poll.get_ballot_template_name()
        return render(request, template_name,
                      {
                          'poll': poll,
                          'error_message': "You didn't select any choice.",
                          'voter_uuid':voter_uuid,
                          })

    else:
        # the rank attribute ensures the transitivity
        # transitive_preference conatins a unique alternative
        # the choice request needs to contain a unique alternative to be valid
        # the completeness is ensured assuming that all the other alternatives are ranked #2
        # they don't need to be saved in the db

        # get the voter from UUID
        voter = get_voter_by_uuid(voter_uuid)
        transitive_preference = TransitivePreference(
            voter= voter,
            rank = 1,
            )
        transitive_preference.save()
        transitive_preference.alternative.add(selected_choice)

        logger.debug("Vote of voter (" + str(voter.pk) +","+ voter.email + ") processed for poll " + str(poll.pk))
        return HttpResponseRedirect(reverse('vote:confirmation', kwargs = {'pk': poll.pk, 'voter_uuid':voter_uuid}))


def process_vote_dichotomous(request, poll, voter_uuid):
    '''view that process a vote for a 'dichotomous ballot' and save the preferences in the database'''
    # get the voter from UUID
    voter = get_voter_by_uuid(voter_uuid)

    #all alternive ID selected in POST['choice']
    selected_choice_id = request.POST.getlist('choice', False)
    query_set = poll.alternative_set.all()
    if selected_choice_id :
        # the rank attribute ensures the transitivity
        # transitive_preference all the top-ranked alternaives
        # the completeness is ensured assuming that all the other alternatives are ranked #2
        # they don't need to be saved in the db

        #the voter selected some alternatives
        selected_alternative = list(query_set.filter(id__in = selected_choice_id).all())
        # create a preference for the selected alternatives
        transitive_preference_selected = TransitivePreference(
            voter = voter,
            rank = 1,
            )
        transitive_preference_selected.save()
        for alternative in selected_alternative:
            transitive_preference_selected.alternative.add(alternative)
    # don't store the vote for unselected alternatives
    logger.debug("Vote of voter (" + str(voter.pk) + "," + voter.email + ") processed for poll " + str(poll.pk))
    return HttpResponseRedirect(reverse('vote:confirmation', kwargs = {'pk': poll.pk, 'voter_uuid': voter_uuid}))

def process_vote_linear_order(request, poll, voter_uuid):
    '''view that process a vote for a 'linear order ballot' and save the preferences in the database'''
    # get the voter from UUID
    voter = get_voter_by_uuid(voter_uuid)
    number_of_alt = len(poll.alternative_set.all())
    rank_list = []
    #check the validity of the ballot
    for k in range(1,number_of_alt+1):
        rank_list.append(request.POST.get('choice_'+str(k),False))
        if False in rank_list:
            # the list contains False
            return HttpResponseServerError("An error occured getting the choice " + str(k))
        elif len(rank_list)!=len(set(rank_list)):
            # the list contains duplicated values, redisplay the poll voting form.
            template_name = poll.get_ballot_template_name()
            return render(request, template_name,
                          {
                              'poll': poll,
                              'voter_uuid': voter_uuid,
                              'error_message': "Ties are not allowed",
                              })
    #the ranked list is valid, we create the transitive preferences
    alternative_list = []
    for  alt_id in rank_list:
        try:
            alternative_list.append(poll.alternative_set.get(pk = alt_id))
        except (KeyError, Alternative.DoesNotExist):
            # Error retrieveing the alternaitve
            return HttpResponseServerError("An error occured retriving the alternative id=" + str(alt_id))

    for alternative in alternative_list:
        # the rank attribute ensures the transitivity 
        # the transitive_preference contains a unique alternative, it ensures anti-symmetry
        # the completeness is ensured because the ballot needs to contain all alternatives
        transitive_preference = TransitivePreference(
            voter = voter,
            rank = alternative_list.index(alternative)+1,
            )
        transitive_preference.save()
        transitive_preference.alternative.add(alternative)

    logger.debug("Vote of voter (" + str(voter.pk) + "," + voter.email + ") processed for poll " + str(poll.pk))
    return HttpResponseRedirect(reverse('vote:confirmation', kwargs = {'pk': poll.pk, 'voter_uuid': voter_uuid}))

def process_vote_complete_preorder(request, poll, voter_uuid):
    '''view that process a vote for a 'preorders ballot' and save the preferences in the database'''
    # get the voter from UUID
    voter = get_voter_by_uuid(voter_uuid)
    number_of_alt = len(poll.alternative_set.all())
    rank_list = [[]]
    for k in range(1, number_of_alt + 1):

        rank_list.append(request.POST.getlist('choice_' + str(k), False))

    #test if an alternative is selected several time
    check_list = []
    for list in rank_list:
        #put all the alternatives in one list
        if list:
            check_list.extend(list)
    if len(check_list) != len(set(check_list)):
        # the list contains alternatives selected multipletime
        # Redisplay the poll voting form.
        template_name = poll.get_ballot_template_name()
        return render(request, template_name,
                      {
                          'poll': poll,
                          'error_message': "Alternative can be selected only once",
                          'voter_uuid': voter_uuid,
                          })

    elif len(check_list) != len( poll.alternative_set.all()):
        # Redisplay the poll voting form.
        template_name = poll.get_ballot_template_name()
        return render(request, template_name,
                      {
                          'poll': poll,
                          'error_message': "Please, select each alternative once",
                          'voter_uuid': voter_uuid,
                      })

    #the ranked list is valid create the profile
    alternative_list_list = [] # list of list of alt classed by ranked
    for alt_id_list in rank_list:
        if alt_id_list:
            alternative_list_list.append(poll.alternative_set.all().filter(id__in = alt_id_list).all())


    for alternative_list in alternative_list_list:

        # the rank attribute ensures the transitivity
        # the transitive_preference contains all the alternatives between which the voter is indifferent
        # the completeness is ensured because the ballot needs to contain all alternatives

        transitive_preference = TransitivePreference(
            voter = voter,
            rank = alternative_list_list.index(alternative_list) + 1,
            )
        transitive_preference.save()
        for alt in alternative_list:
            transitive_preference.alternative.add(alt)

    logger.debug("Vote of voter (" + str(voter.pk) + "," + voter.email + ") processed for poll " + str(poll.pk))
    return HttpResponseRedirect(reverse('vote:confirmation', kwargs = {'pk': poll.pk, 'voter_uuid': voter_uuid}))

def process_vote_complete_binary_relation(request, poll, voter_uuid):
    '''view that process a vote for a 'binary relation ballot' and save the binary relations in the database'''

    # get the voter from UUID
    voter = get_voter_by_uuid(voter_uuid)

    for list in request.POST.lists():
        #get the the comparison from the POST request

        # the BinaryRelation contains only strict preferences
        # the completeness is ensured assuming that the lacking relations are indeferences
        # they don't need to be saved in the db

        if list[0]!="csrfmiddlewaretoken":
            #comparison_id1_id2
            alt_id = re.split('_', list[0])
            #the value returned by the form is the id of the dominant alt or -1 in case of indifference
            if int(list[1][0]) != -1:
                # need only the srtict preference
                if alt_id[1] == list[1][0]:
                    dominated_id = alt_id[2]
                    dominant_id = alt_id[1]
                else:
                    dominated_id = alt_id[1]
                    dominant_id = alt_id[2]
                dominant = poll.alternative_set.get(pk = dominant_id)
                dominated = poll.alternative_set.get(pk = dominated_id)
                pref = BinaryRelation(
                    voter = voter,
                    dominant = dominant,
                    dominated = dominated, )
                pref.save()

    logger.debug("Vote of voter (" + str(voter.pk) + "," + voter.email + ") processed for poll " + str(poll.pk))
    return HttpResponseRedirect(reverse('vote:confirmation', kwargs = {'pk': poll.pk, 'voter_uuid': voter_uuid}))


def compute_plurality_score( alternative_list, transitive_preference):
    '''compute the plurality score of a given a preference profile'''
    score_dict = {} #{ pk:score }
    value = []

    for alternative in alternative_list:
        #init the dict
        score_dict.setdefault(alternative.pk, 0)

    #update the score dictionary
    for voter_pref in transitive_preference:
        # need only the rank 1
        best_alt = voter_pref[0]
        if best_alt.rank == 1:
        # security (optional) to ensure we deal with top-ranked alternatives
            for alt in best_alt.alternative.all():
                score_dict[alt.pk] += 1

    #create the np array
    for alternative in alternative_list:
        value.append((alternative.pk, score_dict[alternative.pk], alternative.priority_rank))

    dtype = [('pk', int), ('score', float), ('priority', int)]
    score = np.array(value, dtype = dtype)  # create a structured array [(pk, score)]
    score['score'] *= -1
    sorted_score  = np.sort(score, order = ['score', 'priority'])
    sorted_score['score'] *= -1
    return  sorted_score

def process_result_best_alternative(poll, alternative_list, save_result, sorted_score ):
    '''process the results of social choice function for the template, and store them in the DB
    if we are computing final results'''
    winner_pk, winner_score, winner_priority = sorted_score[0]
    second_pk, second_score, second_priority = sorted_score[1]
    poll.tie_breaking_used = True if second_score == winner_score else False

    if save_result:
        show_detail = False
        logger.debug("Final " + poll.get_choice_rule() + " computed. score :" + str(
            sorted_score) + " tie breaking : " + str(poll.tie_breaking))
        #save the tie break
        poll.save()
        for alt in alternative_list:
            if alt.pk == winner_pk:
                alt.final_rank = 1
                winner = alt.name
            else:
                alt.final_rank = 2
            alt.save()

    else:
        show_detail = True
        logger.debug("Temp plurality "+ poll.get_choice_rule() + " computed. score :" + str(
            sorted_score) + ", tie breaking : " + str(poll.tie_breaking))
        winner = get_object_or_404(Alternative, pk = winner_pk).name

    template_name = poll.get_results_template_name()

    # replace the key (pk of the alt) by its name, drop priority
    score_with_alt_name = []
    for i in range(len(sorted_score)):
        score_with_alt_name.append((get_object_or_404(Alternative, pk = sorted_score[i][0]).name, sorted_score[i][1]))

    #load the number of voters for temporary result
    if poll.input_type =='Bi':
        query_set_pref = BinaryRelation.objects.filter(dominant__poll = poll.pk).order_by('voter__pk'). \
            distinct().all()  #.all() cache the value
        nb_voter = len(list(query_set_pref.values('voter__uuid').all()))
    else:
        pref_profile = get_transitive_preference(poll)
        nb_voter = len(pref_profile)


    return render_to_response(template_name, {
        "poll": poll,
        "winner": winner,
        "score": score_with_alt_name,
        "show_detail": show_detail,
        "nb_voter": nb_voter,
    }
    )


def process_result_ranking(poll, save_result, sorted_score):
    '''process the results of social wellfare function for the template, and store them in the DB
        if we are computing final results'''
    if save_result:
        show_detail = False
        logger.debug("Final "+ poll.get_choice_rule() + " computed:" +  str(sorted_score) + ", tie breaking " + str(poll.tie_breaking))

        #save the the result
        previous_score_value = 0.5 #(no score is decimal)
        if poll.get_choice_rule() != 'kemeny':
            poll.tie_breaking_used = False
        for index, (alternative_pk, score_value, alternative_priority) in enumerate(sorted_score):
            alt = get_object_or_404(Alternative, pk = alternative_pk)
            alt.final_rank = index + 1
            alt.save()
            if score_value == previous_score_value:
                poll.tie_breaking_used = True
            previous_score_value = score_value
        poll.save()

    else:
        choice_rule = poll.get_choice_rule()
        show_detail = True
        logger.debug("Temp " + poll.get_choice_rule() + " computed:" + str(sorted_score) +" , tie breaking " + str(poll.tie_breaking))

    # replace the key (pk of the alt) by its name, drop priority
    score_with_alt_name = []
    previous_score_value = 0.5  #(no score is decimal)
    if poll.get_choice_rule() != 'kemeny':
        poll.tie_breaking_used = False
    for i in range(len(sorted_score)):
        score_with_alt_name.append((get_object_or_404(Alternative, pk = sorted_score[i][0]).name, sorted_score[i][1]))
        if  sorted_score[i][1] == previous_score_value:
            poll.tie_breaking_used = True
        previous_score_value = sorted_score[i][1]
    template_name = poll.get_results_template_name()

    #load the number of voters for temporary result
    if poll.input_type == 'Bi':
        query_set_pref = BinaryRelation.objects.filter(dominant__poll = poll.pk).order_by('voter__pk'). \
            distinct().all()  #.all() cache the value
        nb_voter = len(list(query_set_pref.values('voter__uuid').all()))
    else:
        pref_profile = get_transitive_preference(poll)
        nb_voter = len(pref_profile)

    return render_to_response(template_name, {
        "poll": poll,
        "rank": score_with_alt_name,
        "show_detail": show_detail,
        "nb_voter": nb_voter,
    }
    )

def process_result_lottery(poll, save_result, sorted_score):
    '''process the results of social decision schemes for the template, and store them in the DB
        if we are computing final results'''
    if save_result:
        logger.debug("Final " + poll.get_choice_rule() + " lottery  " + str(sorted_score))
        if poll.get_choice_rule() == 'random_dictatorship':
            poll.tie_breaking_used = False
        for alternative_pk, score_value, priority in sorted_score:
            alt = get_object_or_404(Alternative, pk = alternative_pk)
            alt.final_rank = score_value
            alt.save()

    else:
        logger.debug("Temp " + poll.get_choice_rule() + " computed: lottery  " + str(sorted_score))
        if poll.get_choice_rule() == 'random_dictatorship':
            poll.tie_breaking_used = False
    # replace the key (pk of the alt) by its name, drop priority
    lottery_with_alt_name = []
    for i in range(len(sorted_score)):
        lottery_with_alt_name.append((get_object_or_404(Alternative, pk = sorted_score[i][0]).name, sorted_score[i][1]))

    template_name = poll.get_results_template_name()

    #load the number of voters for temporary result
    if poll.input_type == 'Bi':
        query_set_pref = BinaryRelation.objects.filter(dominant__poll = poll.pk).order_by('voter__pk'). \
            distinct().all()  #.all() cache the value
        nb_voter = len(list(query_set_pref.values('voter__uuid').all()))
    else:
        pref_profile = get_transitive_preference(poll)
        nb_voter = len(pref_profile)


    return render_to_response(template_name, {
        "poll": poll,
        "lottery": lottery_with_alt_name,
        "nb_voter": nb_voter,
    }
    )


def plurality(request, poll, transitive_preference, save_result):
    '''compute the winner of plurality and approval voting'''

    alternative_list = poll.alternative_set.all()
    sorted_score = compute_plurality_score( alternative_list, transitive_preference)
    return process_result_best_alternative(poll, alternative_list, save_result, sorted_score)

def plurality_score(request, poll, transitive_preference, save_result):
    '''compute plurality and approval scores'''

    alternative_list = poll.alternative_set.all()
    sorted_score = compute_plurality_score( alternative_list, transitive_preference)
    return process_result_ranking(poll, save_result, sorted_score)


def borda(request, poll, transitive_preference, save_result):
    '''compute the winner of Borda's rule'''

    alternative_list = list(poll.alternative_set.all())
    nb_of_alt = len(alternative_list)

    score_dict = {}
    value = []

    #init the dictionary of {alternative_pk:score}
    for altenative in alternative_list:
        score_dict.setdefault(altenative.pk, 0)

    #update the dict
    for voter_pref in transitive_preference:
        for ranked_group in voter_pref:
            if len(ranked_group.alternative.all()) !=1:
                return HttpResponseServerError("Error: ties detected: " + str(ranked_group))
            alt = ranked_group.alternative.all()[0]
            score_dict[alt.pk] += nb_of_alt - ranked_group.rank

    for alternative in alternative_list:
        value.append((alternative.pk, score_dict[alternative.pk], alternative.priority_rank))

    dtype = [('pk', int), ('score', float), ('priority', int)]
    score = np.array(value, dtype = dtype)  # create a structured array with 'pk' as a column and score as another column
    score['score'] *= -1
    sorted_score = np.sort(score, order = ['score', 'priority'])
    sorted_score['score'] *= -1

    return process_result_best_alternative(poll, alternative_list, save_result, sorted_score)


def partially_ordered_borda(request, poll, transitive_preference, save_result):
    '''compute Bucket Borda's winner on preorders preference'''

    alternative_list = list(poll.alternative_set.all())
    nb_of_alt = len(alternative_list)
    score_dict = {}
    value = []

    #init the dict
    for altenative in alternative_list:
        score_dict.setdefault(altenative.pk, 0)

    #update the dict
    for voter_pref in transitive_preference:
        voter_pref.reverse()
        nb_of_lower_ranked_alt = 0;
        for ranked_group in voter_pref:
            bucket = ranked_group.alternative.all()
            bucket_size = len(bucket)
            for alt in bucket:
                #compute the score for all alternative by bucket
                score_dict[alt.pk] += 2 * nb_of_lower_ranked_alt + bucket_size - 1
            nb_of_lower_ranked_alt += bucket_size

    for alternative in alternative_list:
        value.append((alternative.pk, score_dict[alternative.pk], alternative.priority_rank))

    dtype = [('pk', int), ('score', float), ('priority', int)]
    score = np.array(value, dtype = dtype)  # create a structured array
    score['score'] *= -1
    sorted_score = np.sort(score, order = ['score', 'priority'])
    sorted_score['score'] *= -1

    return process_result_best_alternative(poll, alternative_list, save_result, sorted_score)

def young(request, poll, majority_graph_matrix, index_alternative_pk_array, save_result):
    '''compute young the winner of young score for complete binary relations'''
    alternative_list = list(poll.alternative_set.all())
    nb_of_alt = len(alternative_list)

    score_dict = {}
    value = []
    n_i_j = majority_graph_matrix.sum(axis = 1)
    n_j_i = majority_graph_matrix.sum(axis = 0)

    for alternative_index in index_alternative_pk_array:
        score_dict.setdefault(alternative_index, n_i_j[index_alternative_pk_array.index(alternative_index)] -
                                            n_j_i[index_alternative_pk_array.index(alternative_index)])

    for alternative in alternative_list:
        value.append((alternative.pk, score_dict[alternative.pk], alternative.priority_rank))

    dtype = [('pk', int), ('score', float), ('priority', int)]
    score = np.array(value, dtype = dtype)  # create a structured array
    score['score'] *= -1
    sorted_score = np.sort(score, order = ['score', 'priority'])
    sorted_score['score'] *= -1

    return process_result_best_alternative(poll, alternative_list, save_result, sorted_score)


def random_dictatorship(request, poll, transitive_preference, save_result):
    '''compute radom dictatorship lottery. on dichotomous profle with a unique best alt,
    RD is equivalent to a lottery based on the plurality score'''
    tie_breaking = poll.tie_breaking
    alternative_list = poll.alternative_set.all()
    sorted_score = compute_plurality_score(alternative_list, transitive_preference)
    sum_score = float(np.sum(sorted_score['score']))

    #normalize the plurality score
    getcontext().prec = 3
    getcontext().rounding = ROUND_DOWN
    for index in range(len(sorted_score)):
        sorted_score[index] = (sorted_score[index][0], Decimal(sorted_score[index][1] * 100) / Decimal(sum_score), sorted_score[index][2])
    return process_result_lottery(poll, save_result, sorted_score)


def kemeny(request, poll, penalty_weights, index_array, save_result):
    '''Compute Kemeny rankings with an MIP It selects a set of edges of the tournament graph that minimizes the penality
    weight and makes an antisymetric ranking'''
    logger.debug("Computing Kemeny's rank for poll " + str(poll.pk))
    n_alternatives = penalty_weights.shape[0]
    # The problem variable is created to contain the problem data
    prob = pulp.LpProblem("Kemeny Problem", pulp.LpMinimize)

    # The variable are created
    Sequence = ["{0:1d}".format(x) for x in range(n_alternatives)]  #convert range() to a list of string
    edge = pulp.LpVariable.dicts("Edge", (Sequence, Sequence), 0, 1, pulp.LpInteger)

    # The objective function is added to 'prob' first
    prob += pulp.lpSum([edge[r][c] * penalty_weights[r, c] for r in Sequence
                        for c in Sequence]), " weight of the graph"
    # Creation of the constrain
    # edge_i_i for all i =0
    for i in Sequence:
        prob += edge[i][i] == 0, "No loop of size 1:: " + i

    # constraints for every pair
    for i, j in combinations(range(n_alternatives), 2):
        prob += edge[str(i)][str(j)] + edge[str(j)][str(i)] == 1, "No loop of size 2: " + str(i) + "<=>" + str(j)

    # and for every cycle of length 3
    for i, j, k in combinations(range(n_alternatives), 3):
        prob += edge[str(i)][str(j)] + edge[str(j)][str(k)] + edge[str(k)][str(i)] >= 1, "No loop of size 3: (" + str(
            i) + "=>" + str(j) + "=>" + str(k) + "=>" + str(i) + ")"
        prob += edge[str(i)][str(k)] + edge[str(k)][str(j)] + edge[str(j)][str(i)] >= 1, "No loop of size 3: (" + str(
            i) + "=>" + str(k) + "=>" + str(j) + "=>" + str(i) + ")"

    # The problem is solved using PuLP's choice of Solver
    logger.debug("Call the LP solver: " + str(prob.numConstraints()) + " constrains, " + str(
        prob.numVariables()) + " variables " + str(prob.objective))
    logger.debug( "Constrains: ")
    for constrain_name  in prob.constraints.keys():
        logger.debug(constrain_name +"/ " + str(prob.constraints[constrain_name]))
    logger.debug("Penalty matrix: \r\n" + str(penalty_weights) )
    prob.solve()

    # The status of the solution is printed to the screen
    logger.debug("Status:" + str(pulp.LpStatus[prob.status]))

    # Each of the variables is printed with it's resolved optimum value
    for v in prob.variables():
        logger.debug(v.name + "=" + str(v.varValue))

    # Link the score with the alternative name and sort
    score_int = np.zeros(n_alternatives)
    for i in range(n_alternatives):
        for j in range(n_alternatives):
            score_int[i] += pulp.value(edge[str(i)][str(j)])

    #create the np array
    rank=[]
    for i  in range(n_alternatives):
        rank.append((index_array[i], score_int[i], get_object_or_404(Alternative, pk = index_array[i]).priority_rank))

    dtype = [('pk', int), ('score', float), ('priority', int)]
    score = np.array(rank, dtype = dtype)  # create a structured array
    score['score'] *= -1
    sorted_score = np.sort(score, order = ['score', 'priority'])
    sorted_score['score'] *= -1

    return process_result_ranking(poll, save_result, sorted_score)

def sub_maximal_lottery( objective_index, payoff_matrix, alternative_pk_array):
    '''compute a maximal lottery that maximize the score of a given alternative
    LP intepretation of maximal lottery is used :the maximal lottery are mixed maximin strategies of the plurality game'''
    logger.debug("Computing sup maximal lottery for alt " + str(objective_index))
    n_alternatives = payoff_matrix.shape[0]

    #Solved with an LP solver
    # The prob variable is created to contain the problem data
    prob = pulp.LpProblem("Maximal Lottery Problem", pulp.LpMaximize)

    # The variable are created
    Sequence = ["{0:1d}".format(x) for x in range(n_alternatives)]  #convert range() to a list of string
    p = pulp.LpVariable.dicts("P", Sequence, lowBound = 0)

    # The objective function is added to 'prob' first
    prob += p[str(objective_index)], "maximize the probality for alternative " + str(objective_index)

    # Creation of the constrain
    prob += pulp.lpSum([p[i] for i in Sequence]) == 1 , "Propability distribution"

    # Utility greater than the security level in case of every pure strategy of the opponent
    for j in range(n_alternatives):
        prob += pulp.lpSum([p[str(i)]*payoff_matrix[i,j] for i in range(n_alternatives)]) >= 0 , \
                "utility >= security level if pure strategy " + str(j)

    # The problem is solved using PuLP's choice of Solver
    logger.debug("Call the LP solver: " + str(prob.numConstraints()) + " constrains, " + str(
        prob.numVariables()) + " variables")
    logger.debug("Constrains: ")
    logger.debug("objective : max "+ str(prob.objective))
    for constrain_name in prob.constraints.keys():
        logger.debug(constrain_name + "/ " + str(prob.constraints[constrain_name]))

    prob.solve()

    # The status of the solution is printed to the screen
    logger.debug("Status:" + str(pulp.LpStatus[prob.status]))

    # Each of the variables is printed with it's resolved optimum value
    for v in prob.variables():
        logger.debug(v.name + "=" + str(v.varValue))

    # Link the score with the alternative name and sort
    lottery = []
    for i in range(n_alternatives):
        lottery.append(pulp.value(p[str(i)])*100)

    logger.debug("Sub Maximal lottery computed: lottery  " + str(lottery))

    return lottery

def maximal_lottery(request, poll, payoff_matrix, alternative_pk_array, save_result):
    ''' approximate the barycenter of maximal loteries set by taking the average of sevral maximal lotteries'''
    n_alternatives = payoff_matrix.shape[0]

    # matrix of the lottery of each sub prblem
    lottery_matrix = np.zeros((n_alternatives,n_alternatives))
    for index , alt_pk in enumerate(alternative_pk_array):
        lottery_matrix[index,:]  = sub_maximal_lottery(index, payoff_matrix, alternative_pk_array)
    #the maximal lottery are mixed maximin strategies of the plurality game
    logger.debug("All sub lottery computed:\r\n  " + str(lottery_matrix))
    #remove duplicate rows:
    lottery_matrix = np.ascontiguousarray(lottery_matrix)
    unique_lottery_matrix = np.unique(lottery_matrix.view([('', lottery_matrix.dtype)] * lottery_matrix.shape[1]))
    unique_lottery_matrix = unique_lottery_matrix.view(lottery_matrix.dtype).reshape((unique_lottery_matrix.shape[0], lottery_matrix.shape[1]))
    average = np.average(unique_lottery_matrix , axis=0)
    lottery = {}
    getcontext().prec = 3
    getcontext().rounding = ROUND_DOWN
    for i in range(n_alternatives):
        lottery.setdefault(alternative_pk_array[i], Decimal(average[i])*1)
    sorted_score = sorted(lottery.iteritems(), key = operator.itemgetter(0))

    if save_result:
        logger.debug("Final Maximal lottery computed: lottery computed: lottery  " + str(sorted_score))
        for alternative_pk, score_value in sorted_score:
            alt = get_object_or_404(Alternative, pk = alternative_pk)
            alt.final_rank = score_value
            alt.save()
    else:
        logger.debug("Temp Maximal lottery computed: lottery " + str(sorted_score))

    # replace the key (pk of the alt) by its name

    for i in range(len(sorted_score)):
        sorted_score[i] = (get_object_or_404(Alternative, pk = sorted_score[i][0]).name, sorted_score[i][1])

    template_name = poll.get_results_template_name()

    return render_to_response(template_name, {
        "poll": poll,
        "lottery": sorted_score,
        }
    )

# not used in pnyx
def strict_maximal_lottery(request, poll, payoff_matrix, alternative_pk_array, save_result):
    ''' compute a strict maximal lottery with LP'''
    logger.debug("Computing maximal lottery for poll " + str(poll.pk))
    n_alternatives = payoff_matrix.shape[0]

    #Solved with an LP solver
    # The prob variable is created to contain the problem data
    prob = pulp.LpProblem("Strict Maximal Lottery Problem", pulp.LpMaximize)

    # The variable are created
    Sequence = ["{0:1d}".format(x) for x in range(n_alternatives)]  #convert range() to a list of string
    p = pulp.LpVariable.dicts("P", Sequence, lowBound = 0)
    u = pulp.LpVariable("u", lowBound = 0)

    # The objective function is added to 'prob' first
    prob += u, "objective function"

    # Creation of the constrain
    prob += pulp.lpSum([p[b] for b in Sequence]) == 1 , "Propability distribution"

    # Utility greater than the security level in case of every pure strategy of the oponent
    for a in range(n_alternatives):
        prob += pulp.lpSum([p[str(b)]*payoff_matrix[a,b] for j in range(n_alternatives)]) + u <= p[str(a)] , \
                " inequality for alt " + str(a)

    # The problem is solved using PuLP's choice of Solver
    logger.debug("Call the LP solver: " + str(prob.numConstraints()) + " constrains, " + str(
        prob.numVariables()) + " variables")
    logger.debug("Constrains: ")
    for constrain_name in prob.constraints.keys():
        logger.debug(constrain_name + "/ " + str(prob.constraints[constrain_name]))

    prob.solve()

    # The status of the solution is printed to the screen
    logger.debug("Status:" + str(pulp.LpStatus[prob.status]))

    # Each of the variables is printed with it's resolved optimum value
    for v in prob.variables():
        logger.debug(v.name + "=" + str(v.varValue))

    # Link the score with the alternative name and sort
    lottery = {}
    for i in range(n_alternatives):
        lottery.setdefault(alternative_pk_array[i], np.floor(pulp.value(p[str(i)])*1000)/10)
    sorted_score = sorted(lottery.iteritems(), key = operator.itemgetter(0))

    if save_result:
        logger.debug("Final Strict Maximal lottery computed: lottery computed: lottery  " + str(sorted_score))
        for alternative_pk, score_value in sorted_score:
            alt = get_object_or_404(Alternative, pk = alternative_pk)
            alt.final_rank = score_value
            alt.save()
    else:
        logger.debug("Temp Strict Maximal lottery computed: lottery " + str(sorted_score))

    # replace the key (pk of the alt) by its name
    for i in range(len(sorted_score)):
        sorted_score[i] = (get_object_or_404(Alternative, pk = sorted_score[i][0]).name, sorted_score[i][1])

    template_name = poll.get_results_template_name()

    return render_to_response(template_name, {
        "poll": poll,
        "lottery": sorted_score,
        }
    )


def nash(request, poll, utilitaian_matrix, alternative_pk_array, save_result):
    '''compute the nash solution with convex optimization'''
    logger.debug("Computing ultilitarian nash solution for poll " + str(poll.pk))
    cvxopt.solvers.options['maxiters'] = 500
    cvxopt.solvers.options['abstol'] = 1e-5
    cvxopt.solvers.options['reltol'] = 1e-4

    n_alternatives, n_voter = utilitaian_matrix.shape
    # maximize   sum_{n = 1..n_alternatives} log(U_n*x)
    # under     x>=0
    #           sum_{i=1..n_alternatives}(x_i)=1
    # variables x

    def F(x = None, z = None):
        '''fucntion required for the optimization process see cvxopt docs for more info'''
        if x is None: return 0, cvxopt.matrix(1./n_alternatives, (n_alternatives,1))
        if min(x) <= 0.0:
            return None
        f = -sum(np.log(np.dot(utilitaian_matrix.T,x)))
        #grad(f) = U^T *(1/(U_1*x),..,1/(U_N)*x))
        Df = -cvxopt.matrix(np.dot(utilitaian_matrix,(np.dot(utilitaian_matrix.T,x) ** -1)).T)
        if z is None:
            return f, Df
        H = cvxopt.matrix(0., (n_alternatives,n_alternatives))
        for i in range(0, n_alternatives):
            for j in range(0,n_alternatives):
                if i>=j:
                    U_ijU_jn = np.matrix([utilitaian_matrix[i,n]*utilitaian_matrix[j,n] for n in range(0, n_voter)])
                    H[i,j] = np.dot(U_ijU_jn, (np.dot(utilitaian_matrix.T, x) ** -2))
        return f, Df, H

    #constrains to define a ditstribution
    G = -cvxopt.matrix(np.identity(n_alternatives))
    h = cvxopt.matrix(0.,(n_alternatives,1))
    A = cvxopt.matrix(1.,(1, n_alternatives))
    b = cvxopt.matrix(1.,(1,1))

    sol = cvxopt.solvers.cp(F, A = A, b = b, G=G, h=h)
    opt_value = sol['x']
    logger.debug("Optimization " + str(sol['status']) + ":"+ str(sol['x']) )

    # Link the score with the alternative name and sort
    lottery = []
    for i in range(n_alternatives):
        lottery.append((alternative_pk_array[i], np.floor(sol['x'][i]*1000)/10,
                        get_object_or_404(Alternative, pk = alternative_pk_array[i]).priority_rank)
        )

    dtype = [('pk', int), ('score', float), ('priority', int)]
    score = np.array(lottery, dtype = dtype)  # create a structured array
    score['score'] *= -1
    sorted_score = np.sort(score, order = ['score', 'priority'])
    sorted_score['score'] *= -1

    return process_result_lottery(poll, save_result, sorted_score)


def compute_and_display_results(request, poll , save_result):
    '''compute the score of poll, store the result in the database if this final results and display the result page
    the right choice rule is selected dynamically'''

    choice_rule = poll.get_choice_rule()
    if choice_rule == 'young' or choice_rule == "kemeny" or choice_rule == 'maximal_lottery':
        #the input is a majority graph for these rules
        majority_graph_matrix , index_array =  get_majority_graph_matrix( poll)
        if choice_rule == 'young':
            return young(request, poll, majority_graph_matrix, index_array, save_result)
        elif choice_rule == 'kemeny':
            #process the majority matrix to get the strictly relative majority
            relative_majority_graph_matrix = get_relative_majority_graph(majority_graph_matrix)
            return kemeny(request, poll, relative_majority_graph_matrix.T, index_array, save_result)
        elif choice_rule == 'maximal_lottery':
            payoff_matrix = get_payoff_matrix_plurality_game(majority_graph_matrix)
            return maximal_lottery(request, poll, payoff_matrix, index_array, save_result)

    else:
        #if the input is a profile matrix
        transitive_preference = get_transitive_preference( poll)
        if choice_rule == 'plurality':
            return plurality(request, poll, transitive_preference, save_result)
        elif choice_rule == 'plurality_score':
            return plurality_score(request, poll, transitive_preference, save_result)
        elif choice_rule == 'borda':
            return borda(request, poll, transitive_preference, save_result)
        elif choice_rule == 'partially_ordered_borda':
            return partially_ordered_borda(request, poll, transitive_preference, save_result)
        elif choice_rule == 'random_dictatorship':
            return random_dictatorship(request, poll, transitive_preference, save_result)
        elif choice_rule == 'nash':
            utilitaian_matrix, alternative_pk_array = get_approval_matrix(poll, transitive_preference)
            return nash(request, poll, utilitaian_matrix, alternative_pk_array , save_result)

        return HttpResponseServerError("the choice rule" + choice_rule + " is not supported")

def display_results(request, poll, voter_uuid):
    '''get the final results from the database and display the result page'''
    result  = poll.alternative_set.all().order_by('final_rank').values('name' , 'final_rank')
    output_type = poll.output_type
    template_name = poll.get_results_template_name()

    if output_type == 'B':
        winner = ""
        for alt in result:
            if alt["final_rank"] == 1.0:
                winner = alt["name"]
        return render_to_response(template_name, {
            "poll": poll,
            "winner": winner,
            }
        )

    elif output_type == 'L':
        lottery = []
        for alt in result:
            lottery.append((alt["name"],alt["final_rank"]))
        return render_to_response(template_name, {
            "poll": poll,
            "lottery": lottery,
            }
        )
    elif output_type == 'R':
        rank = []
        for alt in result:
            rank.append((alt["name"], alt["final_rank"]))
        return render_to_response(template_name, {
            "poll": poll,
            "rank": rank,
            }
        )

    return HttpResponseServerError("the output type " + output_type + " is not supported")

####views###
def get_ballot_view(request, pk, voter_uuid):
    '''display the ballot page. The template is chosen dynamicaly'''

    poll = get_object_or_404(Poll, pk=pk)
    ballot_data = {}
    # check if the voter is valid
    if voter_uuid == 'public' and not poll.private:
        pass

    elif poll.private:
        try:
            # get the voter from UUID
            voter = get_voter_by_uuid(voter_uuid)
            poll.participant.all().get(uuid = voter_uuid)
            # check if he voted allready
            if poll.input_type == 'Bi':
                previous_vote = BinaryRelation.objects.filter(voter = voter, dominant__poll = poll.pk).order_by('dominant' , 'dominated')
                if len(previous_vote) != 0 and not poll.change_vote:
                    # the vote is already saved and the voter cannot change the vote
                    return HttpResponseRedirect(
                        reverse('vote:already_voted', kwargs = {'pk': poll.pk, 'voter_uuid': voter_uuid}))
                elif len(previous_vote) != 0:
                    # the vote is already saved and the voter CAN change the vote
                    # get the data from the vote and parse it to the ballot
                    for comparison in list(previous_vote):
                        if comparison.dominant.pk < comparison.dominated.pk:
                            ballot_data[str(comparison.dominant.pk) + "_" + str(comparison.dominated.pk)] = comparison.dominant.pk
                        else :
                            ballot_data[str(comparison.dominated.pk) + "_" + str(comparison.dominant.pk)] = comparison.dominant.pk

            else:
                previous_vote = TransitivePreference.objects.filter(voter = voter, alternative__poll = poll.pk).order_by('rank')
                if len(previous_vote) != 0 and not poll.change_vote:
                    # the vote is already saved and the voter cannot change the vote
                    return HttpResponseRedirect(
                        reverse('vote:already_voted', kwargs = {'pk': poll.pk, 'voter_uuid': voter_uuid}))
                elif len(previous_vote) !=0:
                    logger.debug("previous  vote retrieved from database: " + str(previous_vote))
                    # the vote is already saved and the voter CAN change the vote
                    # get the data from the vote and parse it to the ballot
                    for pref in list(previous_vote):
                        ballot_data[pref.rank] = pref.alternative.all()
        except (KeyError, Voter.DoesNotExist):
            return HttpResponseRedirect(
                reverse('vote:unauthorized', kwargs = {'pk': poll.pk, 'voter_uuid': voter_uuid}))

    else:
        return HttpResponseServerError("Invalid voetr UUID")

    if poll.closing_date < timezone.now():
        #return the poll is closed
        return HttpResponseRedirect(reverse('vote:poll_closed', kwargs = {'pk': pk , 'voter_uuid': voter_uuid}))
    elif poll.opening_date > timezone.now():
        #return the poll not opened yet
        return HttpResponseRedirect(reverse('vote:poll_not_opened_yet', kwargs = {'pk': pk , 'voter_uuid': voter_uuid}))

    template_name = poll.get_ballot_template_name()
    if template_name is None:
        return HttpResponseServerError("the input type " + input_type + " is not supported")
    return render_to_response(template_name,
                              {"poll": poll,
                               'voter_uuid':voter_uuid,
                               'ballot_data':ballot_data},
                                RequestContext(request))


def vote(request, pk, voter_uuid):
    '''call afer a ballot submission. Check the validity of the vote and process it.'''

    poll = get_object_or_404(Poll, pk=pk)
    input_type = poll.input_type

    # check if the voter is valid
    if voter_uuid == 'public' and not poll.private:
        pass
    elif poll.private:
        try:
                # get the voter from UUID
                voter = get_voter_by_uuid(voter_uuid)
                poll.participant.all().get(uuid = voter_uuid)

                # check if he voted allready
                if poll.input_type == 'Bi':
                    previous_vote = BinaryRelation.objects.filter(voter = voter, dominant__poll = poll.pk).order_by(
                        'dominant', 'dominated')
                    if len(previous_vote) != 0 and not poll.change_vote:
                        # the vote is already saved and the voter cannot change the vote
                        return HttpResponseRedirect(
                            reverse('vote:already_voted', kwargs = {'pk': poll.pk, 'voter_uuid': voter_uuid}))
                    elif len(previous_vote) != 0:
                        # the vote is already saved and the voter CAN change the vote
                        # delete the previous vote
                        previous_vote.delete()

                else:
                    previous_vote = TransitivePreference.objects.filter(voter = voter,
                                                                     alternative__poll = poll.pk).order_by('rank')
                    if len(previous_vote) != 0 and not poll.change_vote:
                        # the vote is already saved and the voter cannot change the vote
                        return HttpResponseRedirect(
                            reverse('vote:already_voted', kwargs = {'pk': poll.pk, 'voter_uuid': voter_uuid}))
                    elif len(previous_vote) != 0:
                        logger.debug("previous  vote retrieved from database: " + str(previous_vote))
                        # the vote is already saved and the voter CAN change the vote
                        # delete the previous vote
                        previous_vote.delete()

        except (KeyError, Voter.DoesNotExist):
            return HttpResponseRedirect(
                reverse('vote:unauthorized', kwargs = {'pk': poll.pk, 'voter_uuid': voter_uuid}))

    else:
        return HttpResponseServerError("Voter UUID not valid")


    if poll.closing_date < timezone.now():
        #return the poll is closed
        return HttpResponseRedirect(reverse('vote:poll_closed', kwargs = {'pk': pk, 'voter_uuid': voter_uuid}))
    elif poll.opening_date > timezone.now():
        #return the poll not opened yet
        return HttpResponseRedirect(reverse('vote:poll_not_opened_yet', kwargs = {'pk': pk, 'voter_uuid': voter_uuid}))

    if input_type == 'Pf':
        return process_vote_most_preferred_alternative(request, poll, voter_uuid)
    elif input_type == 'Di':
        return process_vote_dichotomous(request, poll, voter_uuid)
    elif input_type == 'Li':
        return process_vote_linear_order(request, poll, voter_uuid)
    elif input_type == 'Pd':
        return process_vote_complete_preorder(request, poll, voter_uuid)
    elif input_type == 'Bi':
        return process_vote_complete_binary_relation(request, poll, voter_uuid)
    else:
        return HttpResponseServerError("the input type " + input_type + " is not supported")


def temporary_results(request, pk, voter_uuid):
    '''compute and display temporary results of a given poll'''
    poll = get_object_or_404(Poll, pk = pk)

    if not (poll.temporary_result or poll.admin == request.user):
        #return temporary result not available for this poll
        return HttpResponseRedirect(reverse('vote:no_temp_results', kwargs = {'pk': poll.pk, 'voter_uuid': voter_uuid}))

    # check if the voter is valid
    elif voter_uuid == 'public' and not poll.private:
        pass
    elif poll.admin == request.user and voter_uuid == 'admin':
        pass
    elif poll.private:
        try:
            # get the voter from UUID
            voter = get_voter_by_uuid(voter_uuid)
            poll.participant.all().get(uuid = voter_uuid)
        except (KeyError, Voter.DoesNotExist):
            return HttpResponseRedirect(
                reverse('vote:unauthorized', kwargs = {'pk': poll.pk, 'voter_uuid': voter_uuid}))

    else:
        return HttpResponseServerError("The voter UUID is not valid")

    return  compute_and_display_results(request, poll, False)


def results(request, pk, voter_uuid):
    '''compute and display final results of a given poll'''

    poll = get_object_or_404(Poll, pk=pk)

    # check if the voter is valid
    if voter_uuid == 'public' and not poll.private:
        pass
    elif poll.admin == request.user and voter_uuid == 'admin':
        pass
    elif poll.private:
        try:
            # get the voter from UUID
            voter = get_voter_by_uuid(voter_uuid)
            poll.participant.all().get(uuid = voter_uuid)
        except (KeyError, Voter.DoesNotExist):
            return HttpResponseRedirect(
                reverse('vote:unauthorized', kwargs = {'pk': poll.pk, 'voter_uuid': voter_uuid}))

    elif voter_uuid != 'public':
        return HttpResponseServerError("public poll voter UUID should be public")

    #check if the poll is periodic
    if not poll.recursive_poll:
        if timezone.now() < poll.closing_date:
            #return the result are not available
            return HttpResponseRedirect(reverse('vote:poll_not_closed_yet', kwargs = {'pk': pk , 'voter_uuid': voter_uuid}))

        #check a result is already computed
        if poll.alternative_set.all()[0].final_rank == None:
            return  compute_and_display_results(request, poll, True)

        else :
            return display_results(request, poll, voter_uuid)
    else :
        if (timezone.now() < poll.closing_date and timezone.now() > poll.opening_date)\
                or (timezone.now() < poll.opening_date and poll.alternative_set.all()[0].final_rank == None):
            #return the result are not available
            return HttpResponseRedirect(
                reverse('vote:poll_not_closed_yet', kwargs = {'pk': pk, 'voter_uuid': voter_uuid}))

        else :
            if timezone.now() > poll.closing_date:
                #update the timeframe
                poll.closing_date  = poll.closing_date  + datetime.timedelta(days = poll.recursive_period)
                poll.opening_date = poll.opening_date + datetime.timedelta(days = poll.recursive_period)
                poll.save()
                logger.debug("Time frame of the repeated poll " + str(poll.pk) + " updtated")
            return compute_and_display_results(request, poll, True)