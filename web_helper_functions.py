#TODO: Figure out which of these are needed!
import sha, time, Cookie, os
import sqlite3 as lite
import uuid
import pandas as pd
import json
import random


##########TODO MOVE THESE CALL TO CLASSES###########################
def pick_movielens_question():
#temporary list of films I'VE seen!
	films = [(2541, 'Cruel Intentions (1999)'),
	 (969, 'African Queen, The (1951)'),
	 (1200, 'Aliens (1986)'),
	 (1704, 'Good Will Hunting (1997)'),
	 (3006, 'Insider, The (1999)'),
	 (2470, 'Crocodile Dundee (1986)'),
	 (3704, 'Mad Max Beyond Thunderdome (1985)')];
	filmn = random.randint(0,len(films)-1);
	movie_index = films[filmn][0];
	movie_name = films[filmn][1];
	return 'seen',movie_index;
	
def pick_census_question():
	return 'postcode', ''

def pickquestion(cur,userid):

	questions_asked = []
	results = cur.execute("SELECT dataset,dataitem,detail FROM qa WHERE userid=?",(userid,));
	for data in results:
		dataset = data[0]
		dataitem = data[1]
		detail = data[2]
		questions_asked.append(str(dataset)+"_"+str(dataitem)+"_"+str(detail));
#	print questions_asked

	for counter in range(100):
		if (random.random()<0.5):
			dataset = 'movielens';
			dataitem, detail = pick_movielens_question();	
		else:
			dataset = 'census';
			dataitem, detail = pick_census_question();
		#print (str(dataset)+"_"+str(dataitem)+"_"+str(detail))
		if not ( (str(dataset)+"_"+str(dataitem)+"_"+str(detail)) in questions_asked):
			break #we've found an unasked question

	return dataset, dataitem, detail
#########################################################
    

def outstanding_question(cur,userid):
	cur.execute('SELECT COUNT(*) FROM qa WHERE userid=? AND asked_last=1;',(userid,));
	data = cur.fetchone();
	if (data[0]>0): 
		return True;
	return False;

def add_question(cur,userid, dataset, dataitem, detail=''):
    cur.execute('UPDATE qa SET asked_last=0 WHERE userid=?;',(userid,));
    cur.execute('INSERT INTO qa (userid, dataset, dataitem, detail, asked_last) VALUES (?,?,?,?,1);',(userid,dataset,dataitem,detail,))

def set_answer_to_last_question(cur,userid, answer):
	cur.execute('UPDATE qa SET answer=?, asked_last=0 WHERE userid=? AND asked_last = 1;',(answer,userid,)); 

import sys
def get_session_id():
    cookie = Cookie.SimpleCookie()  
    string_cookie = os.environ.get('HTTP_COOKIE')
    # If new session
    if (string_cookie):
        cookie.load(string_cookie)
    if ((not string_cookie) or ('sid' not in cookie)):
        # The sid will be a hash of the server time
        sid = sha.new(repr(time.time())).hexdigest()
        # Set the sid in the cookie
        cookie['sid'] = sid
        # Will expire in a year
        cookie['sid']['expires'] = 12 * 30 * 24 * 60 * 60
    else:
        sid = cookie['sid'].value
    return sid, cookie

def get_user_id(cur,sid):
	cur.execute('SELECT user FROM sessions WHERE sessionid = ?' , (sid,));
	data = cur.fetchone();  
	if (data==None):
	        #not found, create a new user...
		try:
			cur.execute('INSERT INTO sessions (sessionid) VALUES (?)',(sid,));
			cur.execute('SELECT user FROM sessions WHERE sessionid = ?', (sid,));
			data = cur.fetchone();
		except lite.Error, e:
		    print >> sys.stderr, "Error %s:" % e.args[0]
        return data[0];

def set_conversation_state(cur,sid,state):
    cur.execute('INSERT OR REPLACE INTO conversation_state (state,sessionid) VALUES (?,?);',(state,sid));

def get_conversation_state(cur,sid):
    cur.execute('SELECT state FROM conversation_state WHERE sessionid = ?' , (sid,));
    data = cur.fetchone();  
    if (data==None):
        return 0
    else:
        return data[0]
