# psychic
Online psychic

Runs on a webserver.

TODO: Move all these instructions to a single script:

==First two datasets are needed from the net that don't have APIs==
1) Download movielens data:
http://files.grouplens.org/datasets/movielens/

2) Download the census postcode to output data:
http://data.gov.uk/dataset/enumeration-postcodes-2011-to-output-areas-2011-to-lower-layer-super-output-areas-2011-to-middl

3) To make the webserver quick we shift this into an SQL database:
To load the census postcode to Output area database and movielens database:

import sqlalchemy as sa
import pandas as pd
ratings = pd.read_table('ml-1m/ratings.dat',sep='::',names=['user','movie','rating','time'],encoding='utf-8');
users = pd.read_table('ml-1m/users.dat',sep='::',names=['user','gender','age','occupation','zip'],encoding='utf-8');
movies = pd.read_table('ml-1m/movies.dat',sep='::',names=['movie','title','genre'],encoding='utf-8');
db = sa.create_engine('sqlite:///movielens.db');
con = db.raw_connection(); #need raw connect to allow access to rollback, see: http://stackoverflow.com/questions/20401392/read-frame-with-sqlalchemy-mysql-and-pandas
con.connection.text_factory = str;
ratings.to_sql('ratings',con,index=False,if_exists='replace');
users.to_sql('users',con,index=False,if_exists='replace');
movies.to_sql('movies',con,index=False,if_exists='replace');
con.close();
db = sa.create_engine('sqlite:///geo.db');
con = db.raw_connection(); #http://docs.sqlalchemy.org/en/rel_0_9/core/connections.html#dbapi-connections
con.connection.text_factory = str;
geo = pd.read_csv('census_geography/PCD11_OA11_LSOA11_MSOA11_LAD11_EW_LU.csv',encoding='utf-8',dtype=str);
geo.to_sql('geo',con,index=False,if_exists='replace',dtype=str);
con.close();

4) Index the SQL:

Within the movielens database:
CREATE INDEX user_ratings ON ratings (user);
CREATE INDEX user_users ON users(user);
CREATE INDEX movie ON ratings(movie);
CREATE INDEX age ON users(age);

Within the geo database:
CREATE INDEX PCD7 ON geo(PCD7);

5) Setup psych.db

CREATE TABLE qa (userid integer, dataset varchar(255), dataitem varchar(255), detail varchar(255), answered integer, asked_last integer, answer varchar(255));
CREATE TABLE sessions (user integer primary key autoincrement, sessionid varchar(255));
CREATE TABLE conversation_state (sessionid varchar(255) primary key, state integer);
----------------------

