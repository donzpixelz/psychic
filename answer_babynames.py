import pymc as pm
import numpy as np
import pandas as pd
import re
import xml.etree.ElementTree as ET
import urllib2
import sqlite3
import answer as ans
import pickle
import answer as ans

from StringIO import StringIO
from zipfile import ZipFile

class BabyNamesAnswer(ans.Answer):
    """Babynames answer: produces a probability distribution based on the person's name"""
        #see: http://www.ons.gov.uk/ons/rel/vsob1/baby-names--england-and-wales/1904-1994/index.html for info
        #class 'static' holder for the movielens database
    dataset = 'babynames';

    @classmethod            #TODO DELETE!!!!
    def getAgeDist(cls,geoArea,returnList):
        """Gets the age distribution given the label of a particular geographical area"""
        pathToONS = 'http://data.ons.gov.uk/ons/api/data/dataset/';
        dataSet = 'QS103EW'; #QS103EW = age by year...
        apiKey = 'cHkIiioOQX';
        geographicalHierarchy = '2011STATH';
        
        url = ('%s%s/dwn.csv?context=Census&geog=%s&dm/%s=%s&totals=false&apikey=%s' % 
        (pathToONS,dataSet,geographicalHierarchy,geographicalHierarchy,geoArea,apiKey))
        response = urllib2.urlopen(url);
        xml_data = response.read();
        root = ET.fromstring(xml_data);
        href = root[1][0][0].text #TO DO: Need to get the path to the href using names not indices.
        
        url = urllib2.urlopen(href);
        zipfile = ZipFile(StringIO(url.read()))
        for filename in zipfile.namelist():
            if (filename[-3:]=='csv'):
                data = pd.read_csv(zipfile.open(filename),skiprows=np.append(np.array(range(8)),10))
               # print filename
                #print zipfile.open(filename).read()
                
        data = data.T
        popages = data[0].values[3:]
       # return popages
        returnList[0] = popages #now return via the argument so this can be called as a thread
    
    def __init__(self,name,dataitem,itemdetails,answer=None):
        """Constructor, instantiate an answer associated with the name of the individual

        Args:
          name: The name of this feature
          dataitem: Can be name...but not really used.
          itemdetails: Details about the item, not really used.
          answer (default None): The name of the person
        """
        self.dataitem = dataitem
        self.itemdetails = itemdetails
        self.featurename = name
        self.answer = answer

    def question_to_text(self):
        if (self.dataitem=='name'):
            return "What's your name?"#TODO We don't need to ask a question, get it from Facts dictionary.
        return "Some sort of census question..."

    @classmethod
    def pick_question(self):
    	#return 'name', '' #could return None,None in future, depending on if we get name from facebook
        return 'None', 'None' #None string used to help database

    def calc_probs(self):
        self.probs = np.zeros([101,2,2]) #age, gender(M,F), for and not for the person's name
        nameps = pickle.load( open( ans.Answer.pathToData+"names.p", "rb" ) )
        years = nameps['years']
        ages = [2015-y for y in years] #todo use current year
        if self.answer == None:
            ans_given = 'None' #this won't be found and the default prior will be used instead
        else:
            ans_given = self.answer
        contractions = pickle.load( open( ans.Answer.pathToData + "contractions.p", "rb" ) )

#        ans_given = 'rachel'
        if ans_given.upper() in contractions:
            possible_name_list = contractions[ans_given.upper()];
        else:
            possible_name_list = [ans_given.upper()]

        nameused = possible_name_list[0] #in future could search/integrate over.
        print "(using name %s)" % nameused
        if (nameused in nameps['boys']):
            p_male = nameps['boys'][nameused]
        else:
            p_male = np.ones(len(years))*0.00000001 #todo: what if their name isn't in the list?
        if (nameused in nameps['girls']):
            p_female = nameps['girls'][nameused]
        else:
            p_female = np.ones(len(years))*0.00000001 #TODO

        p_male = p_male[-1:0:-1]
        p_female = p_female[-1:0:-1]
        ages = ages[-1:0:-1]
        p_male = np.hstack([p_male,p_male[-1]])
        p_female = np.hstack([p_female,p_female[-1]])
        ages.append(101) #add last boundary

        p_male = ans.distribute_probs(p_male,ages)
        p_female = ans.distribute_probs(p_female,ages)

        self.probs = np.zeros([101,2,2])
        self.probs[:,0,1] = p_male#*5000
        self.probs[:,0,0] = 1-p_male#*5000
        self.probs[:,1,1] = p_female#*5000
        self.probs[:,1,0] = 1-p_female#*5000

     #   print self.probs

    def get_pymc_function(self,features):
        """Returns a function for use with the pyMC module:
          - p(name|age,gender)
          - ...
        Args:
          features (dictionary): Dictionary of pyMC probability distributions.
        Returns:
          function (@pm.deterministic): outputs probability given the parameters.
        """
        ##TODO HANDLE OF self.answer IS NONE
        self.calc_probs()
        probs = self.probs
        @pm.deterministic    
        def seenGivenAgeGender(age=features['factor_age'], gender=features['factor_gender']):
            p = probs
#            print p[age]
            return p[age][gender]
        return seenGivenAgeGender
    
    def append_features(self,features,facts): 
        """Alters the features dictionary in place, adds:
         - age
         - gender
         - this instance's feature
         
        Args:
          features (dictionary): Dictionary of pyMC probability distributions.
          facts (dictionary): should already be populated with facts
        
        Raises:
          DuplicateFeatureException: If an identically named feature already exists that clashes with this instance
        """
        #age: 0-100
        if 'first_name' in facts:
            self.answer = facts['first_name']
        else:
            self.answer = None
        if not 'factor_age' in features:
            p = np.ones(101) #flat prior
            p = p/p.sum()
            features['factor_age'] = pm.Categorical('factor_age',p);
        if not 'factor_gender' in features:
            #flat prior
            features['factor_gender'] = pm.Categorical('factor_gender',np.array([0.5,0.5]));
        if self.featurename in features:
            raise DuplicateFeatureException('The "%s" feature is already in the feature list.' % self.featurename);
        features[self.featurename]=pm.Categorical(self.featurename, self.get_pymc_function(features), value=True, observed=True)
