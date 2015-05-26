import pymc as pm
import numpy as np
import answer as ans
import other_helper_functions as ohf
import json
import urllib2
import urllib
import overpy
from operator import itemgetter, attrgetter, methodcaller
import pyproj
import zipfile,os.path,os
import sqlite3 as lite

import shapefile
from shapely.geometry import Point
from shapely.geometry import Polygon

class WhereAnswer(ans.Answer):
    """Where answer: handles figuring out what Output Areas the person might be in"""
    
    dataset = 'where';
    _landmarks = None;
    _boundaries = None;
    
    @classmethod
    def setup(cls,pathToData):
        """Creates databases and files, downloads data, and populates the datafiles"""

        #Data for the Output area shapes is from: http://census.edina.ac.uk/ukborders/easy_download/prebuilt/shape/infuse_oa_lyr_2011_clipped.zip
        #although similar data can also be found at: http://www.ons.gov.uk/ons/guide-method/geography/products/census/spatial/2011/index.html

        #If we don't have the file, download it.
        if not os.path.isfile("/tmp/psych_oa.zip"):
            print "Downloading census output area boundary shape data, this can take a long time..."
            url = 'http://census.edina.ac.uk/ukborders/easy_download/prebuilt/shape/infuse_oa_lyr_2011_clipped.zip'
            urllib.urlretrieve(url, "/tmp/psych_oa.zip")
        oa_zipfile = "/tmp/psych_oa.zip"

        #If it's not unzipped, unzip it.
        if not os.path.exists(pathToData+"/OA_shapes"):
            print "Unzipping"
            os.makedirs(pathToData+"/OA_shapes")
            zf = zipfile.ZipFile(oa_zipfile)
            for f in zf.infolist():
                zf.extract(f.filename,pathToData+"/OA_shapes")

        #If the boundaries are not yet in the database, put them there.
        if not os.path.isfile(pathToData + 'oa_boundaries.db'):  
            print "Adding boundaries to database, this can take a long time..."
            sf = shapefile.Reader(pathToData + "OA_shapes/infuse_oa_lyr_2011_clipped.shp")
            con = lite.connect(pathToData + 'oa_boundaries.db') 
            cur = con.cursor()
            cur.execute('DROP TABLE IF EXISTS boundaries')
            cur.execute('CREATE TABLE IF NOT EXISTS boundaries (id INTEGER PRIMARY KEY AUTOINCREMENT, bbox0 DECIMAL(9,6), bbox1 DECIMAL(9,6), bbox2 DECIMAL(9,6), bbox3 DECIMAL(9,6), shape VARCHAR(50000), record VARCHAR(50000));')
            cur.execute('CREATE INDEX bbox0 ON boundaries (bbox0);')
            cur.execute('CREATE INDEX bbox1 ON boundaries (bbox1);')
            cur.execute('CREATE INDEX bbox2 ON boundaries (bbox2);')
            cur.execute('CREATE INDEX bbox3 ON boundaries (bbox3);')

            cur.close()
            con.commit()
            a = []
            cur = con.cursor()

            for i in range(sf.numRecords):
                if ((i % 1000)==0):
                    print "%d of %d complete" % (i,sf.numRecords)
                    cur.close()
                    con.commit()
                    cur = con.cursor()
                shp = sf.shape(i)
                rec = sf.record(i)
                bbox= shp.bbox

                shpstring = json.dumps([[p[0],p[1]] for p in shp.points])
                recstring = json.dumps(rec)
                cur.execute('INSERT INTO boundaries (bbox0, bbox1, bbox2, bbox3, shape, record) VALUES (?,?,?,?,?,?)',(bbox[0],bbox[1],bbox[2],bbox[3],shpstring,recstring));
            cur.close()
            con.commit()
            con.close()

    @classmethod
    def init_db(cls):
        """Connects (and creates if necessary) database of landmarks

        Note:
          Only intended to be called by the constructor of an instance
        """
        if cls._landmarks is None:
            cls._landmarks = lite.connect(ans.Answer.pathToData+'landmarks.db')
            lmcur = cls._landmarks.cursor()
            cls._landmarks.execute('CREATE TABLE IF NOT EXISTS landmarks (landmark_id INTEGER, name VARCHAR(255), lat DECIMAL(9,6), lon DECIMAL(9,6), east DECIMAL(9,6), north DECIMAL(9,6), querylat DECIMAL(9,6), PRIMARY KEY (landmark_id));')
            cls._landmarks.execute('CREATE TABLE IF NOT EXISTS landmark_queries (querylat DECIMAL(9,6));')
            lmcur.close()
            cls._landmarks.commit()

        if cls._boundaries is None:
            cls._boundaries = lite.connect(ans.Answer.pathToData+'oa_boundaries.db')

    def __init__(self,name,dataitem,detail,answer=None):
        """Constructor, instantiate an answer associated with the distance from a landmark.
        We can later combine these using the facts dictionary to pass things between these classes...

        Args:
          name: The name of this feature
          dataitem: Can be either 'know' or 'distance' or 'where'
          landmark: The id of the landmark (for ids see the separate sql database TODO!)
          answer (default None): Either bool (if dataitem is 'know') or floating point (if dataitem is 'distance')
        """
        WhereAnswer.init_db()
        self.dataitem = dataitem
        self.detail = detail #depends on what precise question we're asking.
        self.answer = answer
        self.featurename = name
        
    #ask for all OSM features near lat,lon (within an area degreesDist from lat,lon, with key and value as specified
    #e.g. items = overpass_query(latitude, longitude ,0.1 ,'tourism', 'museum')
    @classmethod
    def overpass_query(cls,lat,lon,degreesDist,key,value):
  #      print "Checking for cache hit..."
        lmcur = cls._landmarks.cursor()        
        lmcur.execute("SELECT COUNT(*) FROM landmark_queries WHERE querylat=?;",(lat,))
        data = lmcur.fetchone();
        lmcur.close()
        if (data[0]>0):
  #          print "Cache hit found"
            lmcur = cls._landmarks.cursor()
            results = lmcur.execute("SELECT landmark_id, name, lat, lon, east, north FROM landmarks WHERE querylat=?;", (lat,));
            items = []
            for data in results:
                item = overpy.Node(data[0],data[2],data[3]);
                item.east = data[4]
                item.north = data[5]
                item.tags = {'name':data[1]}
                items.append(item)
            lmcur.close()
        else:
   #         print "Cache missed"
   #         print "OVERPASS QUERY"
   #         print lat,lon,degreesDist,key,value
            api = overpy.Overpass()
            #To do adjust addition to take into account latitude
            s = lat-degreesDist
            n = lat+degreesDist
            e = lon+degreesDist
            w = lon-degreesDist #doesn't handle 180 point well, don't run near poles.
            
            query = """<osm-script>
              <union>
                <query type="node">
                  <has-kv k="%s" v="%s" />
                  <bbox-query e="%0.2f" n="%0.2f" s="%0.2f" w="%0.2f"/>
                </query>
                <query type="way">
                  <has-kv k="%s" v="%s" />
                  <bbox-query e="%0.2f" n="%0.2f" s="%0.2f" w="%0.2f"/>      
                </query>
              </union>
              <union>
                <item/>
                <recurse type="down"/>
              </union>
              <print/>
            </osm-script>""" % (key,value,e,n,s,w,key,value,e,n,s,w)
            result = api.query(query)
            items = [];
            for way in result.ways:
                if ('name' in way.tags):
                    way.nodes[0].tags = way.tags
            for node in result.nodes:
                if (key in node.tags) and ('name' in node.tags):
                    item = node;
                    items.append(item)
                    
            for item in items:
                item.distsqr = (float(item.lat) - lat)**2 + (float(item.lon) - lon)**2;

            items =sorted(items, key=attrgetter('distsqr'))
            osgb36=pyproj.Proj("+init=EPSG:27700");
            for item in items:
                [e,n] = osgb36(item.lon,item.lat)
                item.east = e/1000.
                item.north = n/1000. #to km from .

            lmcur = cls._landmarks.cursor()        
            lmcur.execute("INSERT INTO landmark_queries (querylat) VALUES (?);",(lat,)) #Note that this has now been cached. Some queries might not have any rows created, hence why a second table is needed.
            for item in items:
                lmcur.execute("INSERT OR IGNORE INTO landmarks (landmark_id, name, lat, lon, east, north, querylat) VALUES (?,?,?,?,?,?,?);",(item.id,item.tags['name'],float(item.lat),float(item.lon),float(item.east),float(item.north),lat)) #TODO Speed up, combine into one query
            lmcur.close()
            cls._landmarks.commit()


      #  print "Done."
     #   for i in items:
     #       print i
        return items

    @classmethod
    def get_place(cls,lm_id):
    #Use the landmark id to get info of the landmark. This database was previously populated by the pick_question method
        lmcur = cls._landmarks.cursor()
        lmcur.execute("SELECT name, lat, lon, east, north FROM landmarks WHERE landmark_id=?",(lm_id,)) #TODO sanitise the source of self.detail?
        data = lmcur.fetchone();
        lmcur.close()
        if data==None:
            return "No idea where..."
        #TODO Handle if it doesn't manage a cache hit
        placename = data[0]
        lat = data[1]
        lon = data[2]
        east = data[3]
        north = data[4]
        return placename, lat, lon, east, north

    def question_to_text(self):
    	if (self.dataitem=='incity'):
            if (len(self.detail)>1):
                json_loc = json.loads(self.detail)
            else:
                return "Problems."#TODO HANDLE
            city = json_loc['city'];
            return "Is your home in or near %s? (yes or no)" % city
        if (self.dataitem=='city'):
            return "Which city or town are you in or near?"
        if (self.dataitem=='landmark'):
            return "Do you know %s?" % WhereAnswer.get_place(self.detail)[0]
        if (self.dataitem=='landmarkdist'):
            return "How far from your home is %s? (in kilometres, e.g. 2.3)" %  WhereAnswer.get_place(self.detail)[0]
        return "Some sort of place question..."
        
    def calc_probs(self): #TODO: DELETE THIS FUNCTION???
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
            p = np.array([0,0,0,0,0,0]);#TODO:!WHAT IS THIS DOING HERE?!!?!!!! TO FIX!
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
    
    def donut(self,X,Y,centreX,centreY,radius,width):
        radiussqr = radius**2;
        twowidthsqr = 2*width**2;
        normalising = 1./(width*np.sqrt(2.*np.pi));
        Z = np.zeros_like(X)
        for xi,(xrow,yrow) in enumerate(zip(X,Y)):
            for yi,(x,y) in enumerate(zip(xrow,yrow)):
                distsqr=((x-centreX)**2+(y-centreY)**2)
                exponent = (np.sqrt(distsqr)-radius)**2;
                Z[xi][yi] = np.exp(-exponent/twowidthsqr)*normalising
        scale = (X[0][1]-X[0][0])*(Y[1][0]-Y[0][0])
        Z = (Z/np.sum(Z))/scale
        return Z

    def calcDonuts(self,items,bbox,delta = 0.15):
        x = np.arange(bbox[0], bbox[2], delta)
        y = np.arange(bbox[1], bbox[3], delta)
        X, Y = np.meshgrid(x, y)
        points = []
        for it in items:
            point = [it['east'],it['north'],it['dist'],it['dist']*.3]
            points.append(point)
        Zrunning = np.ones_like(X);
        Zrunning = (Zrunning/np.sum(Zrunning))#/(delta**2)
        for point in points:
            Zpoint = self.donut(X,Y,point[0],point[1],point[2],point[3])        
            Zpoint = (Zpoint/np.sum(Zpoint))#/(delta**2)

            Zrunning = Zrunning * Zpoint;
            Zrunning = (Zrunning/np.sum(Zrunning))#/(delta**2)
        return (X,Y,Zrunning)

    def get_likely_OAs(self,bbox,X,Y,Z):
        #sf = shapefile.Reader(ans.Answer.pathToData + "OA_shapes/infuse_oa_lyr_2011.shp")
        #sf = shapefile.Reader(ans.Answer.pathToData + "old_OA_shapes/england_oac_2011.shp")
        #shps = sf.shapes()
        #recs = sf.records()
        #scaled by 1000 back to m again, as the OA boundary data is in metres.
        tempbbox = [b*1000 for b in bbox]

        bdcur = WhereAnswer._boundaries.cursor()        

        results = bdcur.execute("SELECT record, shape FROM boundaries WHERE bbox2>? AND bbox0<? AND bbox3>? AND bbox1<?",(tempbbox[0],tempbbox[2],tempbbox[1],tempbbox[3]))
        shps = []
        recs = []
        for res in results:
            shp_points = json.loads(res[1])
            rec = json.loads(res[0])
            shps.append(Polygon(shp_points))
            recs.append(rec)

      #  print "Found %d relevant shapes" % len(recs)
     #   print "X has shape:"
      #  print X.shape
        xs = X.flatten()
     #   print "Y has shape:"
     #   print Y.shape
        ys = Y.flatten()
     #   print "Z has shape:"
     #   print Z.shape
        zs = Z.flatten()
     #   print "%d points in grid" % len(xs)
        #Remove tiles without any probability associated, and scale to metres again
        xs = xs[zs>1e-5]*1000.
        ys = ys[zs>1e-5]*1000.
        zs = zs[zs>1e-5]*1000.
    #    print "%d points left" % len(xs)
        totalP = np.zeros(len(shps))
        for i,shp in enumerate(shps): #TODO I THINK THIS BIT IS SLOW
            for x,y,z in zip(xs,ys,zs):
                pnt = Point(x,y)
                if pnt.within(shp):
                    totalP[i] += z
        
        for i,(p,shp) in enumerate(zip(totalP,shps)):
            totalP[i] = p / shp.area
        
        totalP = totalP / np.sum(totalP) #normalise
        
        #if threshold means none or more than ten OAs are in the selection, change it
        #TODO: This doesn't seem to work (i.e. more than 10 can be included). Doesn't seem to be a problem though, although a little slow
        #might break if number<1
        #also means a shedload of API queries happened to the ONS for each of these OAs.
        thresh = 0.0001
        if (np.sum(totalP>thresh)>10) or (np.sum(totalP>thresh)<1):
            temp = totalP[:]
            temp.sort()
            thresh = temp[10]

        recs = np.array(recs)[totalP>0.0001]
     #   print "calculation complete."
        return [r[0] for r in recs], totalP[totalP>0.0001] #the nearby shapes and probabilities associated with each of them

    def append_facts(self,facts,all_answers):
        """Alters the facts dictionary in place, adding facts associated with
        this instance.

        Args:
          facts (dictionary): Dictionary of facts.
          all_answers: array of all instantiated answers.

        Returns:
          Nothing - the dictionary is altered inplace.
          
        Raises:
          DuplicateFeatureException: If an identically named fact already exists that clashes with this instance
        """
        if 'where' in facts:
            return #it is done already

        items = [];
        for a in all_answers:
            if a.dataset=='where':
                if a.dataitem == 'landmarkdist':
                    placename, lat, lon, east, north = WhereAnswer.get_place(a.detail)
                    try:
                        dist = float(a.answer)
                    except ValueError:
                        continue
                    item = {'placename':placename, 'lat':lat, 'lon':lon, 'east':east, 'north':north, 'dist':dist}
                    items.append(item)
        bbox = [0,0,0,0];
        margin = 15.
        bbox[0] = min([it['east'] for it in items])-margin;
        bbox[1] = min([it['north'] for it in items])-margin;
        bbox[2] = max([it['east'] for it in items])+margin;
        bbox[3] = max([it['north'] for it in items])+margin;
    #    print items
        res = ((bbox[2]+bbox[3]-bbox[1]-bbox[2])/2.)/10. #about 10x10 will do
        (X,Y,Z) = self.calcDonuts(items,bbox,res)
    #    print X.shape
        

        rs,ps = self.get_likely_OAs(bbox,X,Y,Z)
        if len(ps)>0:
            facts['where'] = {'probabilities':ps, 'OAs':rs}
        else:
            facts['where'] = {'probabilities':np.array([1]), 'OAs':['K04000001']}
        facts['where']['debug'] = {'X':X,'Y':Y,'Z':Z,'bbox':bbox}


    def append_features(self,features,facts): 
        """Alters the features dictionary in place, adds:
         - output_area

        Args:
          features (dictionary): Dictionary of pyMC probability distributions.
          facts (dictionary): Dictionary of facts known (this will include the labels of the OAs).  
        
        Raises:
          DuplicateFeatureException: If an identically named feature already exists that clashes with this instance
        """
            #TODO
        pass

    @classmethod
    def process_answer(cls, dataitem, detail, old_answer):
     #   print "PROCESSING ANSWER"
        #this function may alter an answer to provide additional information, or reformat it into a standard format.
        answer = {}
        answer['response'] = old_answer
        if dataitem=='incity':    #if it's asking if we're in a particular city
            if ohf.true_string(old_answer):   #and the answer's yes
                detail_data = json.loads(detail)
                answer['latitude'] = detail_data['latitude']
                answer['longitude'] = detail_data['longitude']
                answer['city'] = detail_data['city']
                answer['know'] = True #we know where we are... 
            else:
                answer['know'] = False
            return json.dumps(answer), detail
        if dataitem=='city':  #if they've been asked which city they're in...
            #load the city and stick details in the answer           
            name = old_answer
            url = 'http://api.geonames.org/wikipediaSearchJSON?title=%s&username=lionfish' % name

            try:
                raw_json = urllib2.urlopen(url).readline() #TODO SECURITY VULNERABILITY: This json is from the net and needs sanitising before it goes in the db.
                json_loc = json.loads(raw_json)

                maxrank = 0
                chosen_place = None
                for place in json_loc['geonames']:
                    if 'countryCode' in place:
                        if (place['countryCode']=='GB'):
                            if (place['rank']>maxrank):
                                chosen_place = place
                                maxrank = place['rank']
          
                    #TODO Handle not finding city
                    if (chosen_place==None):
                        answer['know'] = False
                    else:
                        answer['latitude'] = chosen_place['lat']
                        answer['longitude'] = chosen_place['lng']
                        answer['city'] = chosen_place['title']
                        answer['know'] = True #we know where we are... 
            except urllib2.HTTPError:
                answer['know'] = False
                answer['error'] = True

            return json.dumps(answer), detail

        return old_answer, detail



    @classmethod
    def pick_question(cls, questions_asked):
    #Picks a question to ask, using previous questions asked.
#incity->yes
#incity->no --> city->name
#landmark->yes --> landmarkdist->distance
#landmark->no --> landmark...

                #from the questions and answers so far given, do we...
        know_city = False  #...know the city where they are?
        not_in_city = False #...know they aren't in the city we guessed (from their IP address)?
        failed = False

        city_details = {}
        outstanding_landmarks = []      #List of landmarks we know they know, but we don't know how far they are.           
        landmarks_done_already = [];    #List of landmarks we know the distance to already

        for qa in questions_asked:
            if qa['dataset']=='where':          #if it is a landmark->where question        
                if qa['dataitem']=='incity':    #and it's asking if we're in a particular city
                    if qa['answer']=='no':
                        not_in_city = True
                    else:
                        answerdata = json.loads(qa['answer']) #TODO Handle ValueError exception 
                        if answerdata['know']:    #and the answer's yes
                            city_details = answerdata
                            know_city = True;
                        else:                       
                            not_in_city = True;

                if qa['dataitem']=='city':      #if we've asked which city they are in...
                    answerdata = json.loads(qa['answer'])
                    if answerdata['know']:
                        city_details = answerdata
                        know_city = True;
                    else:
                        know_city = False
                        failed = True #We've no idea where they are

                if qa['dataitem'] == 'landmark':
                    if ohf.true_string(qa['answer']):
                        outstanding_landmarks.append(int(qa['detail']));
                    landmarks_done_already.append(int(qa['detail']));
                if qa['dataitem'] == 'landmarkdist':
                    outstanding_landmarks.remove(int(qa['detail']));
        
        if failed:
            return 'None', '' #Give up: we can't create any sensible questions
           
        if not know_city:   #if we don't know the city we're in...
            if not_in_city: #if we're not in the place we guessed using their IP, ask their city
                return 'city',''
            else:           #if we don't know that, we need to ask if they're where their IP is.
                url = 'https://freegeoip.net/json/';
                try:
                    raw_json = urllib2.urlopen(url).readline() #TODO SECURITY VULNERABILITY: This json is from the net and needs sanitising before it goes in the db.
                except urllib2.HTTPError:
                    raw_json = ''
                    return 'city',''

                data = {}
                json_loc = json.loads(raw_json)
                data['latitude'] = json_loc['latitude']
                data['longitude'] = json_loc['longitude']
                data['city'] = json_loc['city']
                #TODO: CACHE IN DB 
                return 'incity',json.dumps(data)

        #at this point we should know the city.
        if (len(outstanding_landmarks)==0):
            #pick a new landmark to ask about...
               
            items = cls.overpass_query(city_details['latitude'],city_details['longitude'],0.1,'tourism', 'museum')
            
            new_item = None
            for item in items:
                if not item.id in landmarks_done_already:
                    new_item = item
                    break
            if new_item == None:
                #no more places to ask about
                return 'None', ''
            return 'landmark',new_item.id
        else:
            return 'landmarkdist',outstanding_landmarks[0]
            
