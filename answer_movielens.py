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


class MovieAnswer(ans.Answer):
    """Movielens answer: handles seen, ratings, etc associated with movie rankings"""
    
    #class database connections for movielens
    _movielens = None
    dataset = 'movielens';
    
    @classmethod
    def _init_db(cls):
        """Connect to movielens database

        Note:
          Only intended to be called by the constructor of an instance
        """
        if cls._movielens is None:
            conn = sqlite3.connect(ans.Answer.pathToData+'movielens.db')
            cls._movielens = conn.cursor()

    def get_movie_name(self,movie):
        """Returns the name of the movie with id passed
        """ 
        c_moviename = MovieAnswer._movielens.execute("SELECT title FROM movies WHERE movie=?;",(movie,));
        for r in c_moviename:
            return r[0]
        return "[name unknown]";
    
    def __init__(self,name,dataitem,movie,answer=None):
        """Constructor, instantiate an answer associated with seeing a movie.

        Args:
          name: The name of this feature
          dataitem: Can be either 'seen' or 'rated'
          movie: The id of the movie (for ids see movielens database)
          answer (default None): Either bool (if dataitem is 'seen') or integer (if dataitem is 'rated')
        """
        MovieAnswer._init_db()
        self.dataitem = dataitem
        self.movie = movie
        self.answer = answer
        self.featurename = name
        
    def question_to_text(self):
        m = self.get_movie_name(self.movie)
    	if (self.dataitem=='seen'):
            return "Have you seen %s? (yes or no)" % m
        if (self.dataitem=='rate'):
            return "Rate %s on a scale of 1 to 5" % m
        return "Some sort of movie question..."
        
    def calc_probs(self):
        self.probs = np.zeros([101,2,2]) #age, gender, seen or not seen
        for genderi,gender in enumerate(['M','F']):
            c_ages = MovieAnswer._movielens.execute("SELECT DISTINCT(age) FROM users;") #Maybe could do all this with some outer joins, but couldn't get them working.     
            ages = {};
            p = [];
            for i,r in enumerate(c_ages):
                ages[r[0]]=i
                p.append(0)   
            c_movie = MovieAnswer._movielens.execute("SELECT users.age,count(*) FROM users JOIN ratings ON users.user=ratings.user WHERE ratings.movie=? AND users.gender=? GROUP BY users.age ORDER BY users.age;",(self.movie,gender));
            for r in c_movie:
                p[ages[r[0]]] = r[1]
            c_all = MovieAnswer._movielens.execute("SELECT users.age,count(*) FROM users JOIN ratings ON users.user=ratings.user WHERE users.gender=? GROUP BY users.age ORDER BY users.age;",(gender));
            for r in c_all:
                p[ages[r[0]]] = 1.*p[ages[r[0]]]/r[1]
            p = np.array([0,0,0,0,0,0]);
            d = ans.distribute_probs(p,np.array([18,25,35,45,50,56]))
            self.probs[:,genderi,0] = d
            self.probs[:,genderi,1] = 1-d #TODO! WARNING ARE THESE THE RIGHT WAY 'ROUND?

    def get_pymc_function(self,features):
        """Returns a function for use with the pyMC module, either:
          - p(seen|age,gender)
          - p(rating|age,gender)

        Args:
          features (dictionary): Dictionary of pyMC probability distributions.
        
        Returns:
          function (@pm.deterministic): outputs probability given the parameters.
        """
        self.calc_probs() #calculates probs and puts them in self.probs
        probs = self.probs
        @pm.deterministic    
        def seenGivenAgeGender(age=features['factor_age'],gender=features['factor_gender']):
            pSeen_AgeGender = probs
            return pSeen_AgeGender[age][gender]
        return seenGivenAgeGender
    
    def append_features(self,features): 
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
        #gender: male or female
        if not 'factor_gender' in features:
            #flat prior
            features['factor_gender'] = pm.Categorical('factor_gender',np.array([0.5,0.5]));
        if self.featurename in features:
            raise DuplicateFeatureException('The "%s" feature is already in the feature list.' % self.featurename);
        features[self.featurename]=pm.Categorical(self.featurename, self.get_pymc_function(features), value=True, observed=True)

