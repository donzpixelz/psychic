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

#Some helpful functions
def hasNumbers(strings):
    '''Returns true if any of the strings in the 'strings' array have a digit in them.'''
    for s in strings:
        if any(char.isdigit() for char in s):
            return True
    return False

def dict_to_array(data):
    '''Turns a hierarchy of dictionaries into a numpy array
    returns:
        - the numpy array
        - a list of lists of labels (each list records the labels on that dimension)
    example:
        res, labs = dict_to_array({'aged 3-5':{'males':{'rabbits':3,'dogs':4,'cats':1},'females':{'rabbits':3,'dogs':0,'cats':2}},'aged 0-2':{'males':{'rabbits':4,'dogs':2,'cats':1},'females':{'rabbits':1,'dogs':0,'cats':4}}})
        
        res   array([[[1, 4, 2],[4, 1, 0]],[[1, 3, 4],[2, 3, 0]]])
        labs  [['aged 0-2', 'aged 3-5'], ['males', 'females'], ['cats', 'rabbits', 'dogs']]
    '''
    
    res = []
    if not isinstance(data,dict):
        return data, []
    labels = []
    for e in data:        
        if 'Total' not in e:
            lower_dict, lower_labels = dict_to_array(data[e])
            res.append(lower_dict)
            labels.append(e)
    if hasNumbers(labels): #automatically sorts labels containing numbers by the numerical value of the first number.
        numbers = []
        for lab in labels:
            numbers.append(re.search(r'\d+', lab).group())
        numbers, labels, res = (list(t) for t in zip(*sorted(zip(numbers, labels, res))))  
    lower_labels.insert(0,labels)
    return np.array(res), lower_labels



class CensusAnswer(ans.Answer):
    """Census answer: handles gender & age"""

    dataset = 'census';
    religions = ['Christian','Buddhist','Hindu','Jewish','Muslim','Sikh','Other religion','No religion']
    religion_text = ['Christian','Buddhist','Hindu','Jewish','Muslim','Sikh','religious (but I do\'t know which)','of no religion']

    @classmethod
    def ONSapiQuery(cls,geoArea, dataSet):
        """Performs an API query to the ONS database, for the given geo area and dataset
        The data is stored in 'data' and is also converted into an N-dimensional 'matrix' using a hierarchy of dictionaries."""
        pathToONS = 'http://data.ons.gov.uk/ons/api/data/dataset/';
        apiKey = 'cHkIiioOQX';
        geographicalHierarchy = '2011STATH';
        url = ('%s%s/dwn.csv?context=Census&geog=%s&dm/%s=%s&totals=false&apikey=%s' % 
        (pathToONS,dataSet,geographicalHierarchy,geographicalHierarchy,geoArea,apiKey))
        response = urllib2.urlopen(url);
        xml_data = response.read();
        root = ET.fromstring(xml_data);
        href = root[1][0][0].text #TODO: Need to get the path to the href using names not indices.
        url = urllib2.urlopen(href);
        zipfile = ZipFile(StringIO(url.read()))
        for filename in zipfile.namelist():
            if (filename[-3:]=='csv'):
                #Handle API change
                #data = pd.read_csv(zipfile.open(filename),skiprows=np.append(np.array(range(8)),10))
                data = pd.read_csv(zipfile.open(filename),skiprows=np.array(range(8)),skipfooter=1,header=0)


        #Gets it into a N-dimensional hierarchy of dictionaries
        values = data.ix[0,:]
        matrix = {}
        for col,v in zip(data.columns,values):
            c = col.split('~')
            if (len(c)>1):
                temp = matrix
                for ix in range(len(c)):
                    if ('Total' in c[ix]):
                        break
                    if c[ix] in temp:
                        temp = temp[c[ix]]
                    else:
                        if ix==len(c)-1:
                            temp[c[ix]] = v
                        else:
                            temp[c[ix]] = {}
                            temp = temp[c[ix]]
        return data, matrix

    @classmethod
    def getAgeDist(cls,geoArea,returnList):
        """Gets the age distribution given the label of a particular geographical area"""
        data, matrix = cls.ONSapiQuery(geoArea,'QS103EW')        #QS103EW = age by year...
        data = data.T
        popages = data[0].values[3:]
        # return popages
        returnList[0] = popages #now return via the argument so this can be called as a thread

    @classmethod
    def getReligionDist(cls,geoArea,returnList):
        """Gets the religion distribution given the label of a particular geographical area"""
        data,mat = cls.ONSapiQuery(geoArea,'LC2107EW')        #LC2107EW = religion by age, gender, etc
        arr,labs = dict_to_array(mat) #Convert the dictionary hierarchy to a numpy array
        order = [[i for i,l in enumerate(labs[2]) if l==r][0] for r in cls.religions] #sort religion by the order we want it in.
        arr = np.array(arr) #convert to numpy array
        arr = arr[:,:,order] #put religions in correct order.
        arr = arr * 1.0
        for x in range(arr.shape[0]):
            for y in range(arr.shape[1]):
                arr[x,y,:] += 1.0
                arr[x,y,:] = 1.0*arr[x,y,:] / np.sum(1.0*arr[x,y,:])
        #gender is sorted by 'male', 'female', age by numerical-order and religion as specified in the cls.religions vector
        returnList[0] = arr #now return via the argument so this can be called as a thread
    
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
        
    def calc_probs_religion(self,facts):
       
        if 'where' in facts:
            oas = facts['where']['OAs']
        else:
            oas = ['K04000001'] #don't know where we are, just use whole of England and Wales to get a prior.

        from threading import Thread
        threadData = []
        threads = []
    #    oas.append('K04000001') #last OA is whole of England+Wales #DON'T NEED THAT HERE
        for oa in oas:
            data = [0]
            threadData.append(data)
            t = Thread(target=CensusAnswer.getReligionDist,args=(oa,data))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        localDists = [td[0] for td in threadData[:-1]]


        shape = localDists[0].shape
        #self.rel_probs = np.empty((len(localDists),shape[0],shape[1],shape[2],2))
        self.rel_probs = np.empty((len(localDists),shape[0],shape[1],shape[2]))
        for i,p in enumerate(localDists):
            #self.rel_probs[i,:,:,:,0] = 1-p
            #self.rel_probs[i,:,:,:,1] = p
            self.rel_probs[i,:,:,:] = p
        #Probabilities are p(religion|outputarea,gender,age)
        #organised as: [oa,genderi,agei,religioni]
        #so sum[0,0,0,:,1]=1

    def calc_probs_age(self,facts):
       
        if 'where' in facts:
            oas = facts['where']['OAs']
        else:
          #  print "WARNING: WE DON'T KNOW ANY GEOGRAPHICAL INFORMATION" ##DELETE
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

        self.age_probs = np.zeros([101,len(localAgeDists),2]) #age, in or not in the output area
        for i,dist in enumerate(localAgeDists):
            p = (0.0001+dist)/nationalAgeDist
            self.age_probs[:,i,0] = 1-p
            self.age_probs[:,i,1] = p

    def get_pymc_function_age(self,features):
        """Returns a function for use with the pyMC module:
        Args:
          features (dictionary): Dictionary of pyMC probability distributions.
        Returns:
          function (@pm.deterministic): outputs probability given the parameters.
        """
        probs = self.age_probs
        @pm.deterministic    
        def givenAgeGender(age=features['factor_age'],oa=features['oa']):
            pAgeGender = probs
            return pAgeGender[age,oa]
        return givenAgeGender

    def get_pymc_function_religion(self,features):
        probs = self.rel_probs
        @pm.deterministic    
        def givenReligion(age=features['factor_age'],oa=features['oa'],gender=features['factor_gender']):
            pReligion = probs
            #the religion dataset is only split into a few bins of age, so handling that here:
            if (age<16):
                age_p = 0
            elif (age<25):
                age_p = 1
            elif (age<35):
                age_p = 2
            elif (age<50):
                age_p = 3
            elif (age<65):
                age_p = 4
            elif (age<75):
                age_p = 5
            else:
                age_p = 6
            return pReligion[oa,gender,age_p]
        return givenReligion
    
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
        self.calc_probs_age(facts)
        self.calc_probs_religion(facts)
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
        if self.featurename+"_age" in features:
            raise DuplicateFeatureException('The "%s" feature is already in the feature list.' % self.featurename+"_age");
        if "religion" in features:
            raise DuplicateFeatureException('The "%s" feature is already in the feature list.' % "religion");

        features[self.featurename+"_age"]=pm.Categorical(self.featurename+"_age", self.get_pymc_function_age(features), value=True, observed=True)
        features["religion"]=pm.Categorical("religion", self.get_pymc_function_religion(features)) #, value=True, observed=False)
 
    @classmethod
    def pick_question(self,questions_asked):
	    return 'None','agegender'

