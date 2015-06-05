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
import config

#connect to database

con = lite.connect(config.pathToData + 'psych.db') 
form = cgi.FieldStorage()

def gen_main_form():
    sid,cookie = whf.get_session_id();
    print cookie
    print 'Content-Type: text/html\n';
    print '<html><head><title>Psychic</title>';
    print '<link rel="stylesheet" href="../style.css" type="text/css" media="screen">';
    print '<link rel="stylesheet" href="../animate.css" type="text/css">';
    print '</head><body>';


    print '<script src="../jquery-1.11.2.min.js"></script>';
    print '<script src="../psych.js"></script>';
    print '<div class="page"><div class="pageinner"><div class="pageinnerinner">';
    #print '<h1>Psychoc Sally</h1>';
    print '<div id="conversation"></div>';
    print '<input type="text" id="chatbox" size="17" autofocus />';

    print '<script>if (!("autofocus" in document.createElement("input"))) {document.getElementById("chatbox").focus(); }</script>'; #does autofocus for old versions of IE.

    print '<button id="reply">Reply</button>';
    print '<br />';
    print '<div class="loader"><div class="circle">&nbsp;</div><div class="circle">&nbsp;</div><div class="circle">&nbsp;</div><div class="circle">&nbsp;</div></div>';
    print '</div>';
    print '</div></div>';
    print '</body></html>';

def process_ajax():
    sid,cookie = whf.get_session_id();
    print cookie
    print 'Content-Type: text/html\n'
    print '<html><body>'
  
    msg = '';
    userid = whf.get_user_id(con,sid);
    cur = con.cursor()
    cur.execute('SELECT COUNT(*) FROM qa WHERE userid=?;',(userid,));
    data = cur.fetchone();	
    cur.close()
    state = whf.get_conversation_state(con,sid)

#user can delete the data at any point
    if ('keystrokerecord' in form):
        cur = con.cursor()
        #print json.loads(form['keystrokerecord'].value);
        keystrokes = form['keystrokerecord'].value;
        import datetime
        dt = str(datetime.datetime.now());
        cur.execute('INSERT INTO keystrokes (qid, keystrokes, date) VALUES ((SELECT qid FROM qa WHERE userid=? AND asked_last=1), ?, ?);',(userid,keystrokes,dt))
        cur.close()
        con.commit()
    if ('reply' in form):
        if form['reply'].value.upper()[0:3]=='SET':
            print "Setting..."
            a = form['reply'].value.upper().split(',')
            if (a[1]=='NAME'):
                print "Name..."
                temp = '{"reply[first_name]": "%s"}' % a[2]
                print temp
                print userid
                cur = con.cursor()
                cur.execute("UPDATE qa SET answer=? WHERE userid=? AND dataset='facebook'",(temp,userid))
                print "EXE"
                cur.close()
                con.commit()
                print "Done."
                print "Updating names to %s." % a[2]
                return

        if form['reply'].value.upper()=='DELETE':
            msg = "Your data has been deleted."
            ohf.delete_users_data(con,userid)
            whf.set_conversation_state(con,sid,100)
            state = -1;
    if (state==100):
        msg = "The answers you gave to us about you have been erased.";
    if (state==0):
        msg = 'Welcome to this psychic experience. I will ask you some questions, and, using my psychic powers (and maths) I shall predict the unpredictable!<br/></br> <!--query-->';
        whf.set_conversation_state(con,sid,1)
    if (state==1):
        if ('reply' in form):
            ohf.set_answer_to_last_question(con, userid, form['reply'].value);

        if (data[0]>12):
            msg = 'Enough questions! I shall now peer into my crystal ball of now, to find your age... (this might take me a while)<!--query-->';
            whf.set_conversation_state(con,sid,2)
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
                    whf.set_conversation_state(con,sid,2)
                    msg = "I've no more questions to ask! <!--query-->";
            if moreQavailable:
                msg = ohf.get_last_question_string(con,userid); 
    if (state==2):
        answer_range, model, mcmc, features, facts  = ohf.do_inference(con,userid,['factor_age','factor_gender']);
    #    print answer_range
        msg = 'You are aged between %d and %d.\n<br />' % (answer_range['factor_age'][0],answer_range['factor_age'][1]);
        if (answer_range['factor_gender'][2]>0.9):
            msg = msg + 'You are female.'
        elif (answer_range['factor_gender'][2]<0.1):
            msg = msg + 'You are male.'
        else:
            msg = msg + 'I don\'t know if you\'re male or female';


        rel = mcmc.trace('religion')[:]
        from answer_census import CensusAnswer
        listOfReligions = []
        import numpy as np
        for i,r in enumerate(CensusAnswer.religion_text):
            if (np.mean(rel==i)>0.17):
                listOfReligions.append(r)
        if (len(listOfReligions)>1):
            relmsg = ', '.join(listOfReligions[:-1]) + ' or ' + listOfReligions[-1]
        else:
            relmsg = listOfReligions[0]
        msg = msg + " I think you are " + relmsg + '. <!--query-->'
        msg = '<b>' + msg + '</b>';
        whf.set_conversation_state(con,sid,3)
    if (state==3):
        if ('reply' in form):
            ans = form['reply'].value
            msg = "%s? Interesting. <!--query-->" % ans; #TODO: SANITISE INPUT
            ohf.set_answer_to_last_question(con, userid, ans);
        else:
            cur = con.cursor()
            results = cur.execute('SELECT dataitem FROM qa WHERE dataset = "direct" AND userid = ?', (userid,));
            dataitems = ['age','religion']
            for data in results:
                dataitems.remove(data[0])
            cur.close()
            if (len(dataitems)==0):
                whf.set_conversation_state(con,sid,4)
                msg = "One more thing... <!--query-->";
            else:
                if (dataitems[0]=='age'):
                    msg = "I wonder if I was correct about your age. What is your actual age (if you don't mind me asking?)";
                    whf.add_question(con, userid, 'direct', 'age', ''); 
                if (dataitems[0]=='religion'):
                    msg = "I wonder if I was correct about your religion. What religion (or none) do you identify as?";
                    whf.add_question(con, userid, 'direct', 'religion', ''); 
    if (state==4):
        msg = "If it's ok with you, we would like to keep these answers to improve our psychic abilities in future. We won't use your data for anything else, or pass it on to anyone else.<br/>";
        msg+= "If you want us to delete the data, you can type 'delete' here, now, or at any time in the future. <!--query-->";
        whf.set_conversation_state(con,sid,5)
    if (state==5):
        msg = "Thanks for helping with the psychic experiment: It's now complete. To find out more, please follow us on twitter."
#       msg = 'Enough questions, please visit the <a href="index.cgi?infer=on&userid=%d&feature=age">calculation</a> to see an estimate of your age. It\'s quite slow: Please be patient.' % userid;
    
     
    if ('reply' in form):
        print('<div class="reply"><span class="innerreply">'+form['reply'].value+'</span><div class="replypic"></div></div>');
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


def process_env_data():
    sid,cookie = whf.get_session_id()
    print cookie
    print 'Content-Type: text/html\n'
    print '<html><body>'    
    userid = whf.get_user_id(con,sid); 
    import json
    import os
    user_agent_info = os.environ
    whf.set_answer_to_new_question(con, userid, 'user_agent_info', 'data', '', str(user_agent_info)) #TODO optimise: Only do this if this row isn't in the database already.

if ('ajax' in form):
    process_ajax()
    process_env_data()
elif ('facebook' in form):
    process_facebook()
elif ('setup' in form): #If setup is passed, then we download all the stuff the site might need.
    ohf.setupdatabase(con)
else:
    gen_main_form()

con.commit();
con.close();
