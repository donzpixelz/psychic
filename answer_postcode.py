import pymc as pm
import numpy as np
import pandas as pd
import re
import xml.etree.ElementTree as ET
import urllib2
import sqlite3
import answer as ans
import urllib
import zipfile,os.path,os
import sqlalchemy as sa
import pandas as pd


from StringIO import StringIO
from zipfile import ZipFile

class PostcodeAnswer(ans.Answer):
    """Postcode answer: handles getting the postcode"""

        #class 'static' holder for the geo database
    _geo = None
    dataset = 'postcode';


    
    @classmethod
    def setup(cls,pathToData):
        """Creates databases and files, downloads data, and populates the datafiles"""
        #Sets up postcode->Outputarea data, from http://www.ons.gov.uk/ons/guide-method/geography/products/census/lookup/other/index.html
        url = 'https://geoportal.statistics.gov.uk/Docs/Lookups/Postcodes_(Enumeration)_(2011)_to_output_areas_(2011)_to_lower_layer_SOA_(2011)_to_middle_layer_SOA_(2011)_to_local_authority_districts_(2011)_E+W_lookup.zip'

        if not os.path.isfile("/tmp/psych_postcodes/postcodes.zip"):
            print "Downloading "+url
            if not os.path.exists('/tmp/psych_postcodes'):
                os.makedirs('/tmp/psych_postcodes')
            urllib.urlretrieve(url, "/tmp/psych_postcodes/postcodes.zip")
        postcode_zipfile = "/tmp/psych_postcodes/postcodes.zip"

        if not os.path.isfile("/tmp/psych_postcodes/PCD11_OA11_LSOA11_MSOA11_LAD11_EW_LU.csv"):   
            print "Opening postcodes.zip"
            zf = zipfile.ZipFile(postcode_zipfile)
            for f in zf.infolist():       
                zf.extract(f.filename,"/tmp/psych_postcodes")

        if not os.path.isfile(pathToData+'geo.db'):
            print "Saving geo-postcode/output area data to geo.db"
            db = sa.create_engine('sqlite:///'+pathToData+'geo.db');
            con = db.raw_connection(); #http://docs.sqlalchemy.org/en/rel_0_9/core/connections.html#dbapi-connections
            con.connection.text_factory = str;
            geo = pd.read_csv('/tmp/psych_postcodes/PCD11_OA11_LSOA11_MSOA11_LAD11_EW_LU.csv',encoding='utf-8',dtype=str);
            geo.to_sql('geo',con,index=False,if_exists='replace')
            con.close();



    @classmethod
    def init_db(cls):
        """Connects to the geo database.

        Note:
          Only intended to be called by the constructor of an instance
        """
 #       print "Loading geographical dataset";
        if cls._geo is None:
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
    
    def __init__(self,name,dataitem,itemdetails,answer=None):
        """Constructor, instantiate an answer

        Args:
          name: The name of this feature
          dataitem: 'postcode'
          itemdetails: Details about the item
          answer (default None): Either a string if the item's the postcode or...
        """
        PostcodeAnswer.init_db()
        self.dataitem = dataitem
        self.itemdetails = itemdetails #not sure this is used yet
        self.featurename = name
        self.answer = answer

    def question_to_text(self):
     #   if (self.dataitem=='postcode'):
        return "What's your postcode?"
      #  return "Some sort of postcode question..."
        
    def append_facts(self,facts,all_answers):
        if (self.answer!=None):
            postcode = PostcodeAnswer.adjustcode(self.answer);
            c_oa = PostcodeAnswer._geo.execute("SELECT OA11CD FROM geo WHERE PCD7=?;",(postcode,));
            oas = None;
            for r in c_oa:
                oas = [r[0]]
            if (oas != None):
                facts['where'] = {'probabilities':np.array([1.]), 'OAs':oas}

    @classmethod
    def pick_question(self,questions_asked):
	    return 'postcode', ''

