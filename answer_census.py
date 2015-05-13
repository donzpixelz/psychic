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
    """Census answer: handles postcode & age"""

        #class 'static' holder for the movielens database
    _geo = None
    dataset = 'census';
    
    @classmethod
    def _init_db(cls):
        """Connects to the geo database.

        Note:
          Only intended to be called by the constructor of an instance
        """
 #       print "Loading geographical dataset";
        if cls._geo is None:
           	#cls._geo = pd.read_csv('census_geography/PCD11_OA11_LSOA11_MSOA11_LAD11_EW_LU.csv');
            conn = sqlite3.connect(ans.Answer.pathToData+'geo.db')
            cls._geo = conn.cursor()

     
    @classmethod
    def adjustcode(cls,postcode):
        """Formats postcode into 7 character format, so "a1 2cd" becomes "A1  2CD" or "Gl54 1AB" becomes "GL541AB"."""
        postcode = postcode.upper()
        res = re.search('([A-Z]{1,2}[0-9]{1,2}) *([0-9][A-Z]{2})',postcode);
        if (res==None):
            return postcode #TODO can't understand it, just send it back, need to do something better, throw an exception?
        groups = res.groups()
        if len(groups)==2:
            first = groups[0]
            last = groups[1]
            middle = " "*(7-(len(first)+len(last)))
            return first+middle+last
        return postcode #TODO can't understand it, just send it back, need to do something better, throw an exception?
    
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
           #     print filename
                #print zipfile.open(filename).read()
                
        data = data.T
    #    print data
        popages = data[0].values[3:]
       # return popages
        returnList[0] = popages #now return via the argument so this can be called as a thread
    
    def __init__(self,name,dataitem,itemdetails,answer=None):
        """Constructor, instantiate an answer associated with seeing a movie.

        Args:
          name: The name of this feature
          dataitem: Can be 'postcode' or ...
          itemdetails: Details about the item
          answer (default None): Either a string if the item's the postcode or...
        """
        CensusAnswer._init_db()
        self.dataitem = dataitem
        self.itemdetails = itemdetails #not sure this is used yet
        self.featurename = name
        self.answer = answer

    def question_to_text(self):
        if (self.dataitem=='postcode'):
            return "What's your postcode?"
        return "Some sort of census question..."
        
    def calc_probs(self):
        self.probs = np.zeros([101,2]) #age, in or not in the output area

        if (self.answer==None):
            postcode = 'K04000001'; #somewhere in England/Wales we assume! TODO
        else:
            postcode = CensusAnswer.adjustcode(self.answer);
        c_oa = CensusAnswer._geo.execute("SELECT OA11CD FROM geo WHERE PCD7=?;",(postcode,));
        oa = 'K04000001'; #use England/wales if we don't know it.
        for r in c_oa:
            oa = r[0]

        from threading import Thread
        tempA = [0]
#        print oa
        dA = Thread(target=CensusAnswer.getAgeDist,args=(oa,tempA))
        dA.start()
        tempB = [0]
        dB = Thread(target=CensusAnswer.getAgeDist,args=('K04000001',tempB))
        dB.start()

        dA.join()
        dB.join()
        localAgeDist = tempA[0]
        nationalAgeDist = tempB[0]
   #     print localAgeDist
   #     print nationalAgeDist

  #      temp1 = [0]
  #      CensusAnswer.getAgeDist(oa,temp1)
  #      localAgeDist = temp1[0]
  #      temp2 = [0]
  #      CensusAnswer.getAgeDist('K04000001',temp2)
  #      nationalAgeDist = temp2[0]
     

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

        p = (0.0001+localAgeDist)/nationalAgeDist

        self.probs[:,0] = 1-p
        self.probs[:,1] = p

    def get_pymc_function(self,features):
        """Returns a function for use with the pyMC module, either:
          - p(postcode|age)
          - ...
        Args:
          features (dictionary): Dictionary of pyMC probability distributions.
        Returns:
          function (@pm.deterministic): outputs probability given the parameters.
        """
        self.calc_probs()
        probs = self.probs
        @pm.deterministic    
        def seenGivenAgeGender(age=features['factor_age']):
            pSeen_AgeGender = probs
            return pSeen_AgeGender[age]
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
        if not 'factor_age' in features:
            p = np.ones(101) #flat prior
            p = p/p.sum()
            features['factor_age'] = pm.Categorical('factor_age',p);
        if self.featurename in features:
            raise DuplicateFeatureException('The "%s" feature is already in the feature list.' % self.featurename);
        features[self.featurename]=pm.Categorical(self.featurename, self.get_pymc_function(features), value=True, observed=True)
 
    @classmethod
    def pick_question(self):
	    return 'postcode', ''

