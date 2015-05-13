#!/usr/bin/env python
#TODO: Figure out which of these are needed!
import sha, time, Cookie, os
import sqlite3 as lite
import uuid
import pandas as pd
import json
import random
import cgi
import web_helper_functions as whf
import answer
import answer_functions

#initialise and connect to database

pathToData = '../../cgi-data/';
con = lite.connect(pathToData + 'psych.db') 
cur = con.cursor()
##Note on database tables. Their creation:
#CREATE TABLE qa (userid integer, dataset varchar(255), dataitem varchar(255), detail varchar(255), answered integer, asked_last integer, answer varchar(255));
#CREATE TABLE sessions (user integer primary key autoincrement, sessionid varchar(255));
##

form = cgi.FieldStorage()

def gen_main_form():
    sid,cookie = whf.get_session_id();
    print cookie
    print 'Content-Type: text/html\n';
    print '<html><head><title>Psychic</title><link rel="stylesheet" href="../style.css" type="text/css" media="screen"></head><body>';
    print '<h1>Psychic</h1>';

    print '<script src="../jquery-1.11.2.min.js"></script>';
    print '<script src="../psych.js"></script>';
    print '<h1 id="fb-welcome"></h1>';
    print '<span id="conversation"></span><br />';
    print '<textarea id="chatbox"></textarea>';
    print '<button id="reply">Reply</button>';
    print '</body></html>';

def process_ajax():
    sid,cookie = whf.get_session_id();
    print cookie
    print 'Content-Type: text/html\n'
    print '<html><body>'    
    msg = '';
    userid = whf.get_user_id(cur,sid);
    if ('reply' in form):
        whf.set_answer_to_last_question(cur, userid, form['reply'].value);
    if (not whf.outstanding_question(cur,userid)):
        dataset, dataitem, detail = answer_functions.pick_question(cur,userid);
        whf.add_question(cur, userid, dataset, dataitem, detail);
    cur.execute('SELECT COUNT(*) FROM qa WHERE userid=?;',(userid,));
    data = cur.fetchone();	
    if (data[0]>5):         
        state = whf.get_conversation_state(cur,sid)
        if (state==0):
            msg = 'Enough questions! I shall now peer into my crystal ball of now, to find your age... (this might take me a while)<!--query-->';
            whf.set_conversation_state(cur,sid,1)
        if (state==1):
            con.commit()
            answer_range = answer_functions.do_inference(cur,userid,['factor_age','factor_gender']);
        #    print answer_range
            msg = 'You are aged between %d and %d.\n<br />' % (answer_range['factor_age'][0],answer_range['factor_age'][1]);
            if (answer_range['factor_gender'][2]>0.9):
                msg = msg + 'You are female.'
            elif (answer_range['factor_gender'][2]<0.1):
                msg = msg + 'You are male.'
            else:
                msg = msg + 'I don\'t know if you\'re male or female';

            whf.set_conversation_state(cur,sid,2)
        
#       msg = 'Enough questions, please visit the <a href="index.cgi?infer=on&userid=%d&feature=age">calculation</a> to see an estimate of your age. It\'s quite slow: Please be patient.' % userid;
    else:
        msg = answer_functions.get_last_question_string(cur,userid);
    if (data[0]==1): 
        msg = 'Hello, welcome to this psychic experience. As this is still being tested, the app hasn\'t been submitted for review by facebook. Please allow the blocked popup and agree to the data share. Then: I will ask you some questions, and, using my psychic powers (and maths) I shall predict the unpredictable!<br/></br>\n' + msg;
    #msg = msg + "%d" % data[0];
    if ('reply' in form):
        print('<span class="reply">'+form['reply'].value+'</span><br />');
    print('<span class="msg">'+msg+'</span><br />');
    print '</body></html>'

def process_facebook():
    if not whf.in_session():
        print 'Content-Type: text/html\n'
        print '<html><body>Cookie missing</body></html>'
        return #we'll sort out facebook once we have a session id (it's not been created and added to a cookie yet).
    sid,cookie = whf.get_session_id();
    print cookie
    print 'Content-Type: text/html\n'
    print '<html><body>'    
  #  print cookie
    userid = whf.get_user_id(cur,sid); 
#convert tricky cgi form into simple dictionary.
    data = {}
    for key in form:
        data[key] = form[key].value
#stick this in the database
    import json
    whf.set_answer_to_new_question(cur, userid, 'facebook', 'data', '', json.dumps(data)) #form['reply[birthday]'].value)

#def run_inference():
#    sid,cookie = whf.get_session_id();
#    print cookie
#    print 'Content-Type: text/html\n'
#    print '<html><body>'
#    userid = whf.get_user_id(cur,sid);
#    feature = form['feature']
#    answer_range = answer_functions.do_inference(cur,userid,feature);
#    ages = answer_range[0]
#    msg = 'You are aged between %d and %d!' % (ages[0],ages[1]);

if ('ajax' in form):
	process_ajax()
#elif ('infer' in form):
#	run_inference()
elif ('facebook' in form):
    process_facebook()
else:
	gen_main_form()

con.commit();
con.close();
