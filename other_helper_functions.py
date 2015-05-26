import answer as ans
import random

#todo: currently have to import all the answer... classes
import answer_babynames
import answer_census
import answer_facebook
import answer_movielens
import answer_where
import answer_postcode

import pymc as pm
import numpy as np
import web_helper_functions as whf

#Functions to help pick questions, get question strings, etc...

def true_string(st):
    if st == None:
        return False
    if (st[0].upper()=='Y'): #yes,Yes,Yep,YEP,y,Y
        return True
    if (st[0].upper()=='T'): #True,true,T,t
        return True
    return False #false,False,F,Wrong,Nope,No,(correct)

def pick_question(con,userid):
#    print "PICK QUESTION"
    questions_asked = []
    questions_only_asked = []
    cur = con.cursor()
    results = cur.execute("SELECT dataset,dataitem,detail,answer FROM qa WHERE userid=?",(userid,));
    for data in results:
        dataset = data[0]
        dataitem = data[1]
        detail = data[2]
        answer = data[3]
        question = {'dataset':dataset, 'dataitem':dataitem, 'detail':detail, 'answer':answer}
        questions_asked.append(question)
        question = "%s_%s_%s" % (dataset, dataitem, detail)
        questions_only_asked.append(question) #this doesn't include the answer so we can look for if we've asked the question already.
    cur.close()

    found = False           #have we found a question?
    for counter in range(20):
        c = [cls for cls in ans.Answer.__subclasses__() if cls.dataset not in ['postcode']] #stops it asking about postcode
       # c = [cls for cls in ans.Answer.__subclasses__()] #       c = [cls for cls in ans.Answer.__subclasses__() if cls.dataset in ['where','postcode']] #TODO TESTING ONLY        c = [cls for cls in ans.Answer.__subclasses__() if cls.dataset not in ['movielens','postcode']] #TODO TESTING ONLY        
        cl = random.choice(c)
 #       print cl.dataset
        cl.init_db() #normally should be started from an instance?? but we don't really mind.
        dataitem, detail = cl.pick_question(questions_asked)
        dataset = cl.dataset
        if (dataitem=='None' or dataitem=='Skip'):
 #           print "NONE or SKIP"
            continue;
        question = "%s_%s_%s" % (dataset, dataitem, detail)
        if (question in questions_only_asked):
#            print "DUPLICATE"
            continue
        else:
            found = True
            break
    if not found:
        return None, None, None
    return dataset, dataitem, detail

def pick_none_questions(con,userid): #these are datasets that we don't need to ask questions to use #TODO COMBINE WITH ABOVE FN
    questions_asked_string = []
    questions_asked = []
    cur = con.cursor()
    results = cur.execute("SELECT dataset,dataitem,detail,answer FROM qa WHERE userid=?",(userid,));
    for data in results:
        dataset = data[0]
        dataitem = data[1]
        detail = data[2]
        answer = data[3]
        questions_asked_string.append(str(dataset)+"_"+str(dataitem)+"_"+str(detail));
        question = {'dataset':dataset, 'dataitem':dataitem, 'detail':detail, 'answer':answer}
        questions_asked.append(question)
    cur.close()
    
    c = [cls for cls in ans.Answer.__subclasses__()]
    for cl in c:
        cl.init_db() #normally should be started from an instance?? but we don't really mind.
        dataitem, detail = cl.pick_question(questions_asked)
        dataset = cl.dataset
        if (dataitem=='None'):
            whf.add_question(con, userid, dataset, dataitem, detail,0);

#overall method to instantiate and recover the question for user 'userid'
def get_last_question_string(con,userid):
    cur = con.cursor()
    cur.execute('SELECT dataset, dataitem, detail FROM qa WHERE userid=? AND asked_last = 1;',(userid,));
    data = cur.fetchone();
    cur.close()
    if (data==None): #we shouldn't get to this state... TODO Handle this better.
        return "No more questions!";
    dataset = data[0]
    dataitem = data[1]
    detail = data[2]    
    c = [cls for cls in ans.Answer.__subclasses__() if cls.dataset==dataset]
    if len(c)==0:
        return "Don't know this type of data";
    d = c[0]('temp',dataitem,detail)
    return d.question_to_text()

def do_inference(con,userid,feature_list):
#    print "cogs turning... please wait"
#feature_list = features we want estimates for
    pick_none_questions(con,userid) #populate database with data
    cur = con.cursor()
    results = cur.execute('SELECT dataset, dataitem, detail, answer FROM qa WHERE userid=? AND asked_last=0;',(userid,)); #asked_last=0 -> don't want datasets without answers.
    features = dict()
    answers = []
    tempiterator = 0
    for data in results:
        tempiterator += 1
        dataset = data[0]
        dataitem = data[1]
        detail = data[2]
        answer = data[3]
#some datasets get their inference from the 'facts' dictionary, not from the answer.
#        if ((answer==None) or (len(answer)<2)):
#            continue;
        c = [cls for cls in ans.Answer.__subclasses__() if cls.dataset==dataset]
        if len(c)==0:
        #Don't know this type of data:
            return [0,0]
        name = "%s_%s_%s_%s" % (dataset,dataitem,str(detail),str(answer));
        name = "item%d" % tempiterator
        answers.append(c[0](name,dataitem,detail,answer))
    cur.close() #todo - get the data out the DB then close it before calling this loop

#There are now two dictionaries, facts and features.
# - Facts are detailed statements about a person with a very large space (e.g. precise address, name, date of birth, etc)
#which we know with some considerable certainty
#
# - Features are those things we know less about, or that we need to perform inference over. For example age, location,
#etc...
#
#TODO: Add some facts that we've not done (e.g. output area)?? (not sure we'll know that precisely, in the long-run).
#
#The facts are used by the append_features method to help generate a probability distribution. For example, if the person's
#name is in the facts dictionary as 'Robert', then if the NamesAnswer class is instantiated, it can then use that to produce
#a feature over a person's gender.
    facts = {}
 
    for a in answers:
#        print "appending facts from %s" % a.dataset
        a.append_facts(facts, answers)

    for a in answers:
#        print "appending features from %s" % a.dataset
        a.append_features(features,facts)

    if ('factor_age' not in features):
        return [0,100];

    model = pm.Model(features)
    mcmc = pm.MCMC(model)
    mcmc.sample(10000,1000,4,progress_bar=False)
    output = {}
    for feature in feature_list:
        trc = mcmc.trace(features[feature])[:]
        trc.sort();
        minval = trc[int(len(trc)*0.25)]
        maxval = trc[int(len(trc)*0.75)]
        meanval = np.mean(trc)
        output[feature] = (minval,maxval,meanval)

    return output, model, mcmc, features, facts

def set_answer_to_last_question(con,userid, answer):
    cur = con.cursor()
#    print userid
    cur.execute("SELECT dataset, dataitem, detail FROM qa WHERE asked_last = 1 AND userid = ?;",(userid,))
    data = cur.fetchone();
    cur.close()
    if data!=None:
        dataset = data[0];
        dataitem = data[1];
        detail = data[2]
        c = [cls for cls in ans.Answer.__subclasses__() if cls.dataset==dataset]
#        print "processing answer..."
#        print dataset, dataitem, detail
        if len(c)>0:
#            print "PROCESSING!"
            answer, detail = c[0].process_answer(dataitem,detail,answer)
            cur = con.cursor()
            cur.execute('UPDATE qa SET answer = ?, detail = ?, asked_last = 0 WHERE userid = ? AND asked_last = 1;',(answer,detail,userid,)); 
            cur.close()
            con.commit()
            return
    cur = con.cursor()
    cur.execute('UPDATE qa SET answer = ?, asked_last = 0 WHERE userid = ? AND asked_last = 1;',(answer,userid,)); 
    cur.close()
    con.commit()
