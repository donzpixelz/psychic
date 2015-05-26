#TODO: Figure out which of these are needed!
import sha, time, Cookie, os
import sqlite3 as lite
import uuid
import pandas as pd
import json
import random

def outstanding_question(con,userid):
    cur = con.cursor()
    cur.execute('SELECT COUNT(*) FROM qa WHERE userid=? AND asked_last=1;',(userid,));
    data = cur.fetchone();
    cur.close()
    if (data[0]>0): 
	    return True;
    return False;

def add_question(con,userid, dataset, dataitem, detail='',unanswered=1): #set unanswered=0 if we don't need a reply
    cur = con.cursor()
    cur.execute('UPDATE qa SET asked_last=0 WHERE userid=?;',(userid,));
    cur.close()
    con.commit()
    cur = con.cursor()
    cur.execute('SELECT COUNT(*) FROM qa WHERE userid = ? AND dataset = ? AND dataitem = ? AND detail = ?', (userid,dataset,dataitem,detail,));
    data = cur.fetchone();
    cur.close()
   
    if (data[0]==0):
        cur = con.cursor()
        cur.execute('INSERT OR IGNORE INTO qa (userid, dataset, dataitem, detail, asked_last) VALUES (?,?,?,?,?);',(userid,dataset,dataitem,detail,unanswered))
        cur.close()
        con.commit()

import sys
def in_session(): #Check if we're in a session yet
    cookie = Cookie.SimpleCookie()  
    string_cookie = os.environ.get('HTTP_COOKIE')
    if (string_cookie):
        cookie.load(string_cookie)
    if ((not string_cookie) or ('sid' not in cookie)):
        return False
    return True

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

def get_user_id(con,sid):
    cur = con.cursor()
    cur.execute('SELECT user FROM sessions WHERE sessionid = ?' , (sid,));
    data = cur.fetchone();  
    cur.close()
    if (data==None):
        cur = con.cursor()
        cur.execute('INSERT INTO sessions (sessionid) VALUES (?)',(sid,));
        cur.close()
        con.commit()
        cur = con.cursor()
        cur.execute('SELECT user FROM sessions WHERE sessionid = ?', (sid,));
        data = cur.fetchone();
        cur.close()
    return data[0];

def set_conversation_state(con,sid,state):
    cur = con.cursor()
    cur.execute('INSERT OR REPLACE INTO conversation_state (state,sessionid) VALUES (?,?);',(state,sid));
    cur.close()
    con.commit()

def get_conversation_state(con,sid):
    cur = con.cursor()
    cur.execute('SELECT state FROM conversation_state WHERE sessionid = ?' , (sid,));
    data = cur.fetchone();  
    cur.close()
    if (data==None):
        return 0
    else:
        return data[0]

def set_answer_to_new_question(con,userid, dataset, dataitem, detail, answer):
#we don't want to mess with the normal question/answer flow, so keep ask_last = 0
    cur = con.cursor()
    cur.execute('INSERT OR REPLACE INTO qa (userid, dataset, dataitem, detail, answer, asked_last) VALUES (?,?,?,?,?,0);',(userid,dataset,dataitem,detail,answer))
    cur.close()
    con.commit()
