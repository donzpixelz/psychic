import pymc as pm
import numpy as np
import pandas as pd
import re
import xml.etree.ElementTree as ET
import urllib2
import sqlite3
import answer as ans

from StringIO import StringIO
from zipfile import ZipFile

class CensusAnswer(ans.Answer):
    """Census answer: handles gender & age"""

    dataset = 'census';
    
    @classmethod
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
          
        data = data.T
        popages = data[0].values[3:]
       # return popages
        returnList[0] = popages #now return via the argument so this can be called as a thread
    
    def __init__(self,name,dataitem,itemdetails,answer=None):
        """Constructor, instantiate an answer...

        Args:
          name: The name of this feature
          dataitem: 'agegender'
          itemdetails: None
          answer=None
        """
        self.dataitem = dataitem
        self.itemdetails = itemdetails 
        self.featurename = name
        self.answer = answer

    def question_to_text(self):
        return "No questions"
        
    def calc_probs(self,facts):
       
        if 'where' in facts:
            oas = facts['where']['OAs']
        else:
            oas = ['K04000001'] #don't know where we are, just use whole of England and Wales to get a prior.

        from threading import Thread
        threadData = []
        threads = []
        oas.append('K04000001') #last OA is whole of England+Wales
        for oa in oas:
           # print "Starting thread: %s" % oa
            data = [0]
            threadData.append(data)
            t = Thread(target=CensusAnswer.getAgeDist,args=(oa,data))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        localAgeDists = [td[0] for td in threadData[:-1]]

        nationalAgeDist = threadData[-1][0]

        #we want p(postcode|age), which we assume is equal to p(output area|age)
        #if n = number of people in output area
        #   N = number of people
        #   na = number of people of age a in output area
        #   Na = number of people of age a
        #
        #p(output area|age) = p(age|output area) x p(output area) / p(age)
        #
        #we can write the three terms on the right as:
        #
        #p(age|output area) = na/n
        #p(output area) = n/N
        #p(age) = Na/N
        #
        #substituting in... na/n x n/N / (Na/N) = (na/N) / (Na/N) = na/Na
        #so localAgeDist/nationalAgeDist

     #   print "API queries complete..."

        self.probs = np.zeros([101,len(localAgeDists),2]) #age, in or not in the output area
        for i,dist in enumerate(localAgeDists):
            p = (0.0001+dist)/nationalAgeDist
            self.probs[:,i,0] = 1-p
            self.probs[:,i,1] = p

    def get_pymc_function(self,features):
        """Returns a function for use with the pyMC module, either:
          - p(postcode|age)
          - ...
        Args:
          features (dictionary): Dictionary of pyMC probability distributions.
        Returns:
          function (@pm.deterministic): outputs probability given the parameters.
        """
        probs = self.probs
        @pm.deterministic    
        def seenGivenAgeGender(age=features['factor_age'],oa=features['oa']):
            pSeen_AgeGender = probs
            return pSeen_AgeGender[age,oa]
        return seenGivenAgeGender
    
    def append_features(self,features,facts): 
        """Alters the features dictionary in place, adds:
         - age
         - gender
         - this instance's feature
         
        Args:
          features (dictionary): Dictionary of pyMC probability distributions.
        
        Raises:
          DuplicateFeatureException: If an identically named feature already exists that clashes with this instance
        """
        #age: 0-100
        self.calc_probs(facts)
        if not 'factor_age' in features:
            p = np.ones(101) #flat prior
            p = p/p.sum()
            features['factor_age'] = pm.Categorical('factor_age',p);
        if not 'oa' in features:
            if 'where' in facts:
                p = facts['where']['probabilities'] #prior is weighted by how likely each OA is
                p = p/p.sum() #not necessary.
           #     print facts['where']
                features['oa'] = pm.Categorical('oa',p);
            else:
                features['oa'] = pm.Categorical('oa',np.array([1]));      
        if self.featurename in features:
            raise DuplicateFeatureException('The "%s" feature is already in the feature list.' % self.featurename);
        features[self.featurename]=pm.Categorical(self.featurename, self.get_pymc_function(features), value=True, observed=True)
 
    @classmethod
    def pick_question(self,questions_asked):
	    return 'None','agegender'

