import pymc as pm
import numpy as np
import pandas as pd
import re
import xml.etree.ElementTree as ET
import urllib2
import sqlite3
import answer as ans
import json

from StringIO import StringIO
from zipfile import ZipFile

class FacebookAnswer(ans.Answer):
    """Facebook answer: handles facebook reply"""
    dataset = 'facebook';

    def __init__(self,name,dataitem,itemdetails,answer=None):
        """Constructor, instantiate an answer associated with seeing a movie.

        Args:
          name: The name of this feature
          dataitem: Can be 'name' or ...
          itemdetails: Details about the item
          answer (default None): Either a string if the item's the name or...
        """
        self.dataitem = dataitem
        self.itemdetails = itemdetails #not sure this is used yet
        self.featurename = name
        self.answer = answer
        if ((answer==None) or (len(answer)<2)):
            return
        self.data = json.loads(answer)

    def append_facts(self,facts):
        if ((self.answer==None) or (len(self.answer)<2)):
            return #don't do anything

        """This adds facts to the facts dictionary in place:
        - name
        - dob
        - ...
        """
#       print "FACEBOOK"
#       print self.data
        if ('reply[birthday]' in self.data):
            facts['dob'] = self.data['reply[birthday]'] #TODO: Turn from string to meaningful date
        if ('reply[first_name]' in self.data):
            facts['first_name'] = self.data['reply[first_name]']

    @classmethod
    def pick_question(self):
        return 'Skip', 'None'       #we don't want to ask questions to get this data
