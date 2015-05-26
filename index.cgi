#!/home/msmith/anaconda/bin/python
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
import other_helper_functions as ohf


#connect to database

con = lite.connect(pathToData + 'psych.db') 
form = cgi.FieldStorage()

def gen_main_form():
    sid,cookie = whf.get_session_id();
    print cookie
    print 'Content-Type: text/html\n';
    print '<html><head><title>Psychic</title><link rel="stylesheet" href="../style.css" type="text/css" media="screen"></head><body>';


    print '<script src="../jquery-1.11.2.min.js"></script>';
    print '<script src="../psych.js"></script>';
    print '<div class="page">';
    print '<h1>Psychoc Sally</h1>';
    print '<div id="conversation"></div>';
    print '<input type="text" id="chatbox" size="10" />';
    print '<button id="reply">Reply</button>';
    print '</div>';
    print '</body></html>';

def process_ajax():
    sid,cookie = whf.get_session_id();
    print cookie
    print 'Content-Type: text/html\n'
    print '<html><body>'    
    msg = '';
    userid = whf.get_user_id(con,sid);
    if ('reply' in form):
        ohf.set_answer_to_last_question(con, userid, form['reply'].value);
    cur = con.cursor()
    cur.execute('SELECT COUNT(*) FROM qa WHERE userid=?;',(userid,));
    data = cur.fetchone();	
    cur.close()
    state = whf.get_conversation_state(con,sid)
 #   print state
 #   print "TESTING"
    if (state==0):
        if (data[0]>10):
            msg = 'Enough questions! I shall now peer into my crystal ball of now, to find your age... (this might take me a while)<!--query-->';
            whf.set_conversation_state(con,sid,1)
        else:
            moreQavailable = True
            if (not whf.outstanding_question(con,userid)):
                moreQavailable = False
                dataset, dataitem, detail = ohf.pick_question(con,userid);
                if (dataset!=None):
                    moreQavailable = True
                    whf.add_question(con, userid, dataset, dataitem, detail);
                else:
                    #not found any new questions. TODO: We shouldn't really get into this situation, as we should
                    #have more questions always available. However, if we do; set conversation to state=1, to reveal what
                    #we know.
                    whf.set_conversation_state(con,sid,1)
                    msg = "I've no more questions to ask! <!--query-->";
            if moreQavailable:
                msg = ohf.get_last_question_string(con,userid);
    if (state==1):
        answer_range, model, mcmc, features, facts  = ohf.do_inference(con,userid,['factor_age','factor_gender']);
    #    print answer_range
        msg = 'You are aged between %d and %d.\n<br />' % (answer_range['factor_age'][0],answer_range['factor_age'][1]);
        if (answer_range['factor_gender'][2]>0.9):
            msg = msg + 'You are female.'
        elif (answer_range['factor_gender'][2]<0.1):
            msg = msg + 'You are male.'
        else:
            msg = msg + 'I don\'t know if you\'re male or female';

        whf.set_conversation_state(con,sid,2)
    if (state==2):
        msg = "We're done."
#       msg = 'Enough questions, please visit the <a href="index.cgi?infer=on&userid=%d&feature=age">calculation</a> to see an estimate of your age. It\'s quite slow: Please be patient.' % userid;
    
      
    if (data[0]==0): 
        msg = 'Welcome to this psychic experience. I will ask you some questions, and, using my psychic powers (and maths) I shall predict the unpredictable!<br/></br>\n' + msg;
  #      msg = 'Hello, welcome to this psychic experience. As this is still being tested, the app hasn\'t been submitted for review by facebook. Please allow the blocked popup and agree to the data share. Then: I will ask you some questions, and, using my psychic powers (and maths) I shall predict the unpredictable!<br/></br>\n' + msg;
    #msg = msg + "%d" % data[0];
    if ('reply' in form):
        print('<div class="reply"><span class="innerreply">'+form['reply'].value+'</span></div>');
    print('<div class="msg"><span class="innermsg">'+msg+'</span></div>');
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
    userid = whf.get_user_id(con,sid); 
#convert tricky cgi form into simple dictionary.
    data = {}
    for key in form:
        data[key] = form[key].value
#stick this in the database
    import json
    whf.set_answer_to_new_question(con, userid, 'facebook', 'data', '', json.dumps(data)) #form['reply[birthday]'].value)

if ('ajax' in form):
	process_ajax()
#elif ('infer' in form):
#	run_inference()
elif ('facebook' in form):
    process_facebook()
elif ('setup' in form): #If setup is passed, then we download all the stuff the site might need.
    ohf.setupdatabase(con)
else:
	gen_main_form()

con.commit();
con.close();
