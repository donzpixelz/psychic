import answer as ans
import random
import answer_babynames
import answer_census
import answer_facebook
import answer_movielens
import pymc as pm
import numpy as np
import web_helper_functions as whf

#Functions to help pick questions, get question strings, etc...

def pick_question(cur,userid):
    questions_asked = []
    results = cur.execute("SELECT dataset,dataitem,detail FROM qa WHERE userid=?",(userid,));
    for data in results:
	    dataset = data[0]
	    dataitem = data[1]
	    detail = data[2]
	    questions_asked.append(str(dataset)+"_"+str(dataitem)+"_"+str(detail));

    for counter in range(100):
        c = [cls for cls in ans.Answer.__subclasses__()]
        cl = random.choice(c)
        dataitem, detail = cl.pick_question()
        dataset = cl.dataset
        if (dataitem=='None' or dataitem=='Skip'):
            continue;

        if not ( (str(dataset)+"_"+str(dataitem)+"_"+str(detail)) in questions_asked):
		    break #we've found an unasked question

    return dataset, dataitem, detail

def pick_none_questions(cur,userid): #these are datasets that we don't need to ask questions to use
    questions_asked = []
    results = cur.execute("SELECT dataset,dataitem,detail FROM qa WHERE userid=?",(userid,));
    for data in results:
	    dataset = data[0]
	    dataitem = data[1]
	    detail = data[2]
	    questions_asked.append(str(dataset)+"_"+str(dataitem)+"_"+str(detail));

    
    c = [cls for cls in ans.Answer.__subclasses__()]
    for cl in c:
        dataitem, detail = cl.pick_question()
        dataset = cl.dataset
        if (dataitem=='None'):
            whf.add_question(cur, userid, dataset, dataitem, detail,0);

#overall method to instantiate and recover the question for user 'userid'
def get_last_question_string(cur,userid):
    cur.execute('SELECT dataset, dataitem, detail FROM qa WHERE userid=? AND asked_last = 1;',(userid,));
    data = cur.fetchone();  
    if (data==None):
         #not found
        return "Can't remember what I was asking...";
    dataset = data[0]
    dataitem = data[1]
    detail = data[2]    
    c = [cls for cls in ans.Answer.__subclasses__() if cls.dataset==dataset]
    if len(c)==0:
        return "Don't know this type of data";
#    print "----"
#    print dataitem
#    print detail
    d = c[0]('temp',dataitem,detail)
    return d.question_to_text()

def do_inference(cur,userid,feature_list):
#feature_list = features we want estimates for
    pick_none_questions(cur,userid) #populate database with data
    results = cur.execute('SELECT dataset, dataitem, detail, answer FROM qa WHERE userid=? AND asked_last=0;',(userid,)); #asked_last=0 -> don't want datasets without answers.
    features = dict()
    answers = []
    tempiterator = 0
    for data in results:
  #      print "Infering on %s" % data[0]
        tempiterator += 1
   #     print data
        dataset = data[0]
        dataitem = data[1]
        detail = data[2]
        answer = data[3]
#some datasets get their inference from the 'facts' dictionary, not from the answer.
#        if ((answer==None) or (len(answer)<2)):
#            continue;
        c = [cls for cls in ans.Answer.__subclasses__() if cls.dataset==dataset]
        if len(c)==0:
            print "Don't know this type of data: %s" % dataset;  
            return [0,0]
   #     print "::", dataset
        name = "%s_%s_%s_%s" % (dataset,dataitem,str(detail),str(answer));
        name = "item%d" % tempiterator
        answers.append(c[0](name,dataitem,detail,answer))

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
        a.append_facts(facts)

    for a in answers:
        a.append_features(features,facts)

  #  print str(facts);
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
    return output
