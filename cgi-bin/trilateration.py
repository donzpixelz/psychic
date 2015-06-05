from scipy.stats import norm
import numpy as np

#Calculates over the grid of cells, defined by the vectors X and Y,
#the 'donut' of probability that defines the likely location of the
#person, given that they are 'radius' distance from a landmark at
#location centreX, centreY.
#width is the standard deviation of the distribution of the error on
#their estimate.
def donut(X,Y,centreX,centreY,radius,width):
    import scipy.stats
    radiussqr = radius**2;
    twowidthsqr = 2*width**2;
    normalising = 1./(width*np.sqrt(2.*np.pi));
    Z = np.zeros_like(X)
    for xi,(xrow,yrow) in enumerate(zip(X,Y)):
        for yi,(x,y) in enumerate(zip(xrow,yrow)):
            distsqr=((x-centreX)**2+(y-centreY)**2)
            #dist-radius -> (dist-radius)^2 = dist^2 - 2dr + radius^2
            exponent = (np.sqrt(distsqr)-radius)**2;
            Z[xi][yi] = np.exp(-exponent/twowidthsqr)*normalising
            #Z[xi][yi] = scipy.stats.norm.pdf(dist,1.,0.1)
    scale = (X[0][1]-X[0][0])*(Y[1][0]-Y[0][0])
    Z = (Z/np.sum(Z))/scale
    return Z

#H[D_i|X]
#xs, ys = coordinates of prob distribution
#p = prob distribution, of X
#l = coordinates of landmark
#alpha = The standard deviation of the distance estimate is proportional (with factor alpha) to the distance estimate itself
def HofDgivenX(xs,ys,p,l,alpha):
    h = 0 #the entropy (added up over the distribution's area)
    p = p / np.sum(p) #normalise p
    for ix,x in enumerate(xs):
        for iy,y in enumerate(ys):
            #H[D_i|X] = sum(p(X=x) H[Di|X=x])_x
            #H[D_i|X=x] = alpha*||X-l||*sqrt(2*pi*e)            
            h += p[iy,ix] * np.sqrt((x-l[0])**2 + (y-l[1])**2) * alpha*np.sqrt(2*np.pi*np.e)
    return h

#marginalising over X: $P(D_i) = \int P(D_i|X)\;P(X)\;dX$
def PofD(xs,ys,p,l,alpha):
    h = 0
    probs = np.zeros(1000)
    delta = 0.1
    mind = 0.
    maxd = 8.
    totalp = np.arange(mind,maxd,delta)*0.
    N = 0
    for ix,x in enumerate(xs):
        for iy,y in enumerate(ys):
            #distance from X to landmark if X is at x,y
            d = np.sqrt((x-l[0])**2 + (y-l[1])**2)
            #handle case of landmark being ontop of X.
            if (d<0.001):
                d = 0.001
            #add P(X) * P(D_i|X)
            totalp += p[iy,ix] * norm.pdf(np.arange(mind,maxd,delta),d,alpha*d)
            N += 1
    totalp = totalp / np.sum(totalp) #TODO: Divide by N or sum(totalp)? - i.e. prob dist. or prob. density dist?
    return totalp

#H[D_i] uses the above calculation of P[D_i], and just uses
#the normal definition of H:
# -sum_d( P[D_i = d] * ln(P[D_i = d]) )
def HofD(xs,ys,p,l,alpha):
    ps = PofD(xs,ys,p,l,alpha)    
    s = 0
    for p in ps:
        if p>0:
            s += p*np.log(p)
    return -s

def sortLandmarks(landmarks,donealready,distances,landmarks_done_already):
    #create grid over which the inference will be made.
    lms_done = [] #done (we know the distance)
    lms_cand = [] #candidate (we don't know these yet)
    lms_dist = []
    
    ix = 0
    items = []
    for l in landmarks:
        if l.id in donealready:                 #we know it & have a distance
            lms_done.append([l.east/1000.,l.north/1000.])
            lms_dist.append(distances[ix])
            ix += 1
        elif l.id in landmarks_done_already:    #we didn't know this landmark
            pass
        else:                                   #this is a candidate future landmark
            lms_cand.append([l.east/1000.,l.north/1000.])
            items.append(l)
        
    margin = 5.
    xmin = min([l.east/1000. for l in landmarks])-margin
    xmax = max([l.east/1000. for l in landmarks])+margin
    ymin = min([l.north/1000. for l in landmarks])-margin
    ymax = max([l.north/1000. for l in landmarks])+margin
    
    delta = max(xmax-xmin,ymax-ymin)/30.    
    xs = np.arange(xmin, xmax, delta)
    ys = np.arange(ymin, ymax, delta)
    X, Y = np.meshgrid(xs, ys)
    p = np.ones_like(X)
    p = p / np.sum(p)
    alpha = .4

    for lm,dist in zip(lms_done,lms_dist):
        q = donut(X,Y,lm[0],lm[1],dist,alpha)
        p = p * q
        p = p / np.sum(p)
    entropy = []
    for it,l in zip(items,lms_cand): 
        hofd = HofD(xs,ys,p,l,alpha)
        hofdgivenX = HofDgivenX(xs,ys,p,l,alpha)
        entropy.append(hofdgivenX-hofd)
    sorteditems = [x for (y,x) in sorted(zip(entropy,items))]
    return sorteditems,p,sorted(entropy)
