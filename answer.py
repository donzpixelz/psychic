import pymc as pm
import numpy as np
import pandas as pd
import re
import xml.etree.ElementTree as ET
import urllib2
import sqlite3

class DuplicateFeatureException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


def distribute_probs(p,j,spread=False):
    """Distributes age probabilities.
    
    Distributes discrete age probabilities over the "more" continuous
    range from 0 to 100.
    
    Args:
        p - numpy array of probabilities (doesn't need to be normalised)
        j - numpy array of where the boundaries are. It is assumed the first value is from 0
            for example j=np.array([16,25,50]) will have four probabilities associated:
            between 0-15, 16-24, 25-49, 50+
	spread - default False. In the case where you're spreading the values over
	    p(r|0<a<10) where a is the parameter, into, e.g. p(r=4|a) we can say that
	    p(r|a=4) = p(r|0<a<10), unless we know something else.
          however...
	    if we're spreading p(0<a<10|r), then the probabilities will be divided
	    (assuming a uniform distribution) equally over the values of a in the range.
	    so p(a=4|r) = p(0<a<10|r)/10
        
    Returns:
        A numpy array of probabilities from 0 to 100.
        
    Example:
        distribute_probs(p,np.array([18,25,35,45,50,56]))
    """

    res = np.zeros(101)  
    jend = np.append(j,101)
    j = np.insert(j,0,0)
    for start,end,v in zip(j,jend,p):
        if (spread):
            res[start:end] = 1.0*v/(end-start)
        else:
            res[start:end] = 1.0*v
    return res

class Answer(object):
    """Base class for the possible types of data and answers given
    
    Important Note:
      The features need to be compatible between different class types and instances.
      Any new features need to have their structure documented to ensure compatibility.
      
    Important Note:
      Some features are factors and cannot be on the left of a conditional probability:
      p(A|B,C) #if A is a factor this is invalid.
      The features in this set are indicated by being prefixed with factor_.
      
      Maybe: a prior on that feature could be added to a FeaturePriorAnswers class
      
    Feature Descriptions:
      factor_age - a categorical list of ages of 100 values, from 0 to 100.
         each value is that person's age, so 32 means their age is 32<=a<33.
         the last value means 100 or more.
      factor_gender - a categorical list of two values (male or female)
      seen - whether a film's been seen (true or false)
      rating - the integer rating given to a film (between 0 and 5).
    """
    def __init__(self,name,dataitem,detail,answer=None):
        """Constructor method for base class: does nothing."""
        pass
    
    dataset = 'None'; #override this property with the name of your dataset
    pathToData = '../../cgi-data/';

    def question_to_text(self):
        return "Base class, no question."
    
    def get_pymc_function(self,features):
        """Returns a function for use with the pyMC module, using the
        features held in the 'features' dictionary.

        Note:
          Only features with relevant dependencies will actually be used.

        Args:
          features (dictionary): Dictionary of pyMC probability distributions.
        
        Returns:
          function (@pm.deterministic): outputs some probability given the parameters.
        """
        pass
    
    def append_features(self,features):
        """Alters the features dictionary in place, adding features associated with
        this instance.

        Note:
          Two types of features will be added;
           - parents: features that this distribution uses (i.e. on the right of the |)
           - this node: a feature describing the output of this node, for example whether
             they've seen a movie, have search for 'trains' on google, have a particular
             SNP, etc.

        Args:
          features (dictionary): Dictionary of pyMC probability distributions.
        
        Returns:
          Nothing - the dictionary is altered inplace.
          
        Raises:
          DuplicateFeatureException: If an identically named feature already exists that clashes with this instance
        """
        pass


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
    c = [cls for cls in Answer.__subclasses__() if cls.dataset==dataset]
    if len(c)==0:
        return "Don't know this type of data";
    d = c[0]('temp',dataitem,detail)
    return d.question_to_text()

def do_inference(cur,userid,feature):
    results = cur.execute('SELECT dataset, dataitem, detail, answer FROM qa WHERE userid=?;',(userid,));
    features = dict()
    answers = []
    tempiterator = 0
    for data in results:
        tempiterator += 1
   #     print data
        dataset = data[0]
        dataitem = data[1]
        detail = data[2]
        answer = data[3]
        if ((answer==None) or (len(answer)<2)):
            continue;
        c = [cls for cls in Answer.__subclasses__() if cls.dataset==dataset]
        if len(c)==0:
            return "Don't know this type of data";
        name = "%s_%s_%s_%s" % (dataset,dataitem,str(detail),str(answer));
        name = "item%d" % tempiterator
        answers.append(c[0](name,dataitem,detail,answer))
    for a in answers:
        a.append_features(features)

    model = pm.Model(features)
    mcmc = pm.MCMC(model)
    mcmc.sample(2000,200,3,progress_bar=False)
    trc = mcmc.trace(features['factor_age'])[:]
    trc.sort();
    minage = trc[int(len(trc)*0.25)]
    maxage = trc[int(len(trc)*0.75)]
    return (minage,maxage)
