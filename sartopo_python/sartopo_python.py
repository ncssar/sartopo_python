# #############################################################################
#
#  sartopo_python.py - python interfaces to the sartopo API
#
#   developed for Nevada County Sheriff's Search and Rescue
#    Copyright (c) 2020 Tom Grundy
#
#   Sartopo / Caltopo currently does not have a publicly available API;
#    this code calls the non-publicized API that could change at any time.
#
#   This module is intended to provide a simple, API-version-agnostic sartopo
#    interface to other applications.
#
#   This python code is in no way supported or maintained by caltopo LLC
#    or the authors of caltopo.com or sartopo.com.
#
#  www.github.com/ncssar/sartopo_python
#
#  Contact the author at nccaves@yahoo.com
#   Attribution, feedback, bug reports and feature requests are appreciated
#
############################################################
#
# EXAMPLES:
#
#     from sartopo_python import SartopoSession
#     import time
#     
#     sts=SartopoSession('localhost:8080','<offlineMapID>')
#     fid=sts.addFolder('MyFolder')
#     sts.addMarker(39,-120,'stuff')
#     sts.addMarker(39.01,-120.01,'myStuff',folderId=fid)
#     r=sts.getFeatures('Marker')
#     print('r:'+str(r))
#     print('moving the marker after a pause:'+r[0]['id'])
#     time.sleep(5)
#     sts.addMarker(39.02,-120.02,r[0]['properties']['title'],existingId=r[0]['id'])
#     
#     sts2=SartopoSession(
#         'sartopo.com',
#         '<onlineMapID>',
#         configpath='../../sts.ini',
#         account='<accountName>')
#     fid2=sts2.addFolder('MyOnlineFolder')
#     sts2.addMarker(39,-120,'onlineStuff')
#     sts2.addMarker(39.01,-119.99,'onlineStuff2',folderId=fid2)
#     r2=sts2.getFeatures('Marker')
#     print('return value from getFeatures('Marker'):')
#     print(json.dumps(r2,indent=3))
#     time.sleep(15)
#     print('moving online after a pause:'+r2[0]['id'])
#     sts2.addMarker(39.02,-119.98,r2[0]['properties']['title'],existingId=r2[0]['id'])
#
#
#  Threading
#
#  When self.sync is True, we want to call doSync, then wait n seconds after
#  the response, then call doSync again, etc.  This is not strictly the same
#  as calling doSync every n seconds, since it may take several seconds for
#  the response to be completed, for large data or slow connection or both.
# 
#  We could use the timer object (a subclass of Threading), but that
#  would cause a new thread to be spawned for each iteration, which might
#  cause python resource or memory issues after a long time.  So, instead,
#  we use one thread for syncing, which does a blocking sleep of n
#  seconds after each completed response.  This sync thread is separate
#  from the main thread, so that its blocking sleeps (or slow responses) do
#  not block the rest of the program.
# 
#  The sync thread is created by calling self.start().  A call to self.stop()
#  simply sets self.sync to False, which causes the sync thread to end itself
#  after the next request/response.
#
#  Since self.doSync is called repeatedly if self.sync is True, the sync
#  thread would stay alive forever, even after the calling program ends; so,
#  at the end of each sync iteration, self.doSync checks to see if the main
#  thread is still alive, and terminates the sync thread if the main thread
#  is no longer alive.
#
#  To avoid the recursion limit, doSync is called iteratively rather than
#  recursivley, in _syncLoop which is only meant to be called from start().
#
#  To prevent main-thread requests from being sent while a sync request is
#  in process, doSync sets self.syncing just before sending the 'since'
#  request, and leaves it set until the sync response is processed.
#   TO DO: If a main-thread request wants to be sent while self.syncing is
#   set, the request is queued, and is sent after the next sync response is
#   processed.
#
#  NOTE : is this block-and-queue necessary?  Since the http requests
#  and responses should be able to synchronize themselves, maybe it's not
#  needed here?
# 
#
#  REVISION HISTORY
#-----------------------------------------------------------------------------
#   DATE   |  AUTHOR  |  NOTES
#-----------------------------------------------------------------------------
#  8-29-18    TMG        First version - creates folders and markers
#  10-7-18    TMG        allow session on network other than localhost; allow
#                           three-character mapID; overhaul to work with
#                           significant api changes in v4151 of sar.jar -
#                           probably not backwards compatible; will require
#                           changes to code that calls these functions
# 11-19-18    TMG        clean up for first package release
#  6-29-19    TMG        add getFeatures to return a list of map features with IDs;
#                          move an existing marker by specifying existing marker ID
#   7-3-19    TMG        return folderId, if it exists, with each feature returned
#                          by getFeatures, to allow filtering by folder; modify
#                          setupSession to only return API version 1 if the
#                          API is version 1 AND the map ID is valid
#  3-30-20    TMG        fix #3: v1.0.6: change the return value structure from getFeatures
#                          to return the entire json structure for each feature;
#                          this enables preservation of marker-symbol when moving
#                          an existing marker
#  5-30-20    TMG        fix #2: v1.1.0: send signed requests to sartopo.com (online)
#   6-2-20    TMG        v1.1.1: fix #5 (use correct meaning of 'expires');
#                           fix #6 (__init__ returns None on failure)
#   4-5-21    TMG        sync (fix #17)
#  6-15-21    TMG        add geometry operations cut, expand, crop
#  6-27-21    TMG        stop sync when main thread terminates (fix #19)
#  6-28-21    TMG        remove spurs to fix self-intersecting polygons (fix #20)
#  6-29-21    TMG        return gracefully if shapes do not intersect (fix #21)
#  6-30-21    TMG        fix #26; various error handling and logging improvements
#  6-30-21    TMG        do an initial since(0) request even if sync=False (fix #25)
#   7-4-21    TMG        preserve complex lines during crop (fix #29); other cleanup
#   8-8-21    TMG        sync and getFeature/s overhaul: sync iteratively instead of
#                         recursively; handle cache refreshing such that downstream
#                         apps should never need to access .mapData, but should only
#                         make calls to getFeature/s (fix #23)
#   8-9-21    TMG        add new objects to .mapData immediately (fix #28)
#-----------------------------------------------------------------------------

import hmac
import base64
import requests
import json
import configparser
import os
import time
import logging
import sys
import threading
import copy

# import objgraph
# import psutil

# process=psutil.Process(os.getpid())

# syncing=False

# shapely.geometry improts will generate a logging message if numpy is not installed;
#  numpy is not actually required
from shapely.geometry import LineString,Point,Polygon,MultiLineString,MultiPolygon,GeometryCollection
from shapely.ops import split,unary_union

# silent exception class to be raised during __init__ and handlded by the caller,
#  since __init__ should always return None: https://stackoverflow.com/questions/20059766
class STSException(BaseException):
    pass

class SartopoSession():
    def __init__(self,
            domainAndPort='localhost:8080',
            mapID=None,
            configpath=None,
            account=None,
            id=None, # 12-character credential ID
            key=None, # credential key
            accountId=None, # 6-character accountId
            accountIdInternet=None, # in case CTD requires a different accountId than sartopo.com/caltopo.com
            sync=True,
            syncInterval=5,
            syncTimeout=10,
            syncDumpFile=None,
            cacheDumpFile=None,
            propertyUpdateCallback=None,
            geometryUpdateCallback=None,
            newFeatureCallback=None,
            deletedFeatureCallback=None,
            syncCallback=None,
            useFiddlerProxy=False):
        self.s=requests.session()
        self.apiVersion=-1
        if not mapID or not isinstance(mapID,str) or len(mapID)<3:
            logging.warning('WARNING: you must specify a three-or-more-character sartopo map ID string (end of the URL) when opening a SartopoSession object.')
            raise STSException
        self.mapID=mapID
        self.domainAndPort=domainAndPort
        # configpath, account, id, and key are used to build
        #  signed requests for sartopo.com
        self.configpath=configpath
        self.account=account
        self.queue={}
        self.mapData={'ids':{},'state':{'features':[]}}
        self.id=id
        self.key=key
        self.accountId=accountId
        self.accountIdInternet=accountIdInternet
        self.sync=sync
        self.syncTimeout=syncTimeout
        self.syncPause=False
        self.propertyUpdateCallback=propertyUpdateCallback
        self.geometryUpdateCallback=geometryUpdateCallback
        self.newFeatureCallback=newFeatureCallback
        self.deletedFeatureCallback=deletedFeatureCallback
        self.syncCallback=syncCallback
        self.syncInterval=syncInterval
        self.syncCompletedCount=0
        self.lastSuccessfulSyncTimestamp=0 # the server's integer milliseconds 'sincce' request completion time
        self.lastSuccessfulSyncTSLocal=0 # this object's integer milliseconds sync completion time
        self.syncDumpFile=syncDumpFile
        self.cacheDumpFile=cacheDumpFile
        self.useFiddlerProxy=useFiddlerProxy
        self.syncing=False
        if not self.setupSession():
            raise STSException
        
    def setupSession(self):
        # set a flag: is this an internet session?
        #  if so, id and key are strictly required, and accountId is needed to print
        #  if not, all three are only needed in order to print
        internet=self.domainAndPort and self.domainAndPort.lower() in ['sartopo.com','caltopo.com']
        id=None
        key=None
        accountId=None
        accountIdInternet=None
        # if configpath and account are specified,
        #  conigpath must be the full pathname of a configparser-compliant
        #  config file, and account must be the name of a section within it,
        #  containing keys 'id' and 'key'.
        # otherwise, those parameters must have been specified in this object's
        #  constructor.
        # if both are specified, first the config section is read and then
        #  any parameters of this object are used to override the config file
        #  values.
        # if any of those three values are still not specified, abort.
        if self.configpath is not None:
            if os.path.isfile(self.configpath):
                if self.account is None:
                    logging.error("config file '"+self.configpath+"' is specified, but no account name is specified.")
                    return False
                config=configparser.ConfigParser()
                config.read(self.configpath)
                if self.account not in config.sections():
                    logging.error("specified account '"+self.account+"' has no entry in config file '"+self.configpath+"'.")
                    return False
                section=config[self.account]
                id=section.get("id",None)
                key=section.get("key",None)
                accountId=section.get("accountId",None)
                accountIdInternet=section.get("accountIdInternet",None)
                if internet:
                    if id is None or key is None:
                        logging.error("account entry '"+self.account+"' in config file '"+self.configpath+"' is not complete:\n  it must specify 'id' and 'key'.")
                        return False
                    if accountId is None:
                        logging.warning("account entry '"+self.account+"' in config file '"+self.configpath+"' does not specify 'accountId': you will not be able to generate PDF files from this session.")
                else:
                    if id is None or key is None or accountId is None:
                        logging.warning("account entry '"+self.account+"' in config file '"+self.configpath+"' is not complete:\n  it must specify 'id', 'key', and 'accountId' if you want to generate PDF files from this session.")
                    if accountIdInternet is None:
                        logging.warning("account entry '"+self.account+"' in config file '"+self.configpath+"' does not specify 'accountIdInternet': if a different accountId is required for caltopo.com/saratopo.com vs. for CalTopo Desktop, you will not be able to send PDF generation jobs to the internet from this session.")
            else:
                logging.error("specified config file '"+self.configpath+"' does not exist.")
                return False

        # now allow values specified in constructor to override config file values
        if self.id is not None:
            id=self.id
        if self.key is not None:
            key=self.key
        if self.accountId is not None:
            accountId=self.accountId
        if self.accountIdInternet is not None:
            accountIdInternet=self.accountIdInternet
        # finally, save them back as parameters of this object
        self.id=id
        self.key=key
        self.accountId=accountId
        self.accountIdInternet=accountIdInternet

        if internet:
            if self.id is None:
                logging.error("sartopo session is invalid: 'id' must be specified for online maps")
                return False
            if self.key is None:
                logging.error("sartopo session is invalid: 'key' must be specified for online maps")
                return False

        # # by default, do not assume any sartopo session is running;
        # # send a GET request to http://localhost:8080/api/v1/map/
        # #  response code 200 = new API
        # #  otherwise:
        # #    send a GET request to http://localhost:8080/rest/
        # #     response code 200 = old API
        
        # self.apiUrlMid="/invalid/"
        # url="http://"+self.domainAndPort+"/api/v1/map/"
        # logging.info("searching for API v1: sending get to "+url)
        # try:
        #     r=self.s.get(url,timeout=10)
        # except:
        #     logging.error("no response from first get request; aborting; should get a response of 400 at this point for api v0")
        #     return False
        # else:
        #     logging.info("response code = "+str(r.status_code))
        #     if r.status_code==200:
        #         # now validate the mapID, since the initial test doesn't care about mapID
        #         mapUrl="http://"+self.domainAndPort+"/m/"+self.mapID
        #         try:
        #             r=self.s.get(mapUrl,timeout=10)
        #         except:
        #             logging.error("API version 1 detected, but the get request timed out so the mapID is not valid: "+mapUrl)
        #             return False
        #         else:
        #             if r.status_code==200:
        #                 # now we know the API is valid and the mapID is valid
        #                 self.apiVersion=1
        #                 self.apiUrlMid="/api/v1/map/[MAPID]/"
        #             else:
        #                 logging.error("API version 1 detected, but the map-specific URL '"+self.mapID+"' returned a code of "+str(r.status_code)+" so this session is not valid.")
        #                 return False
        #     else:
        #         url="http://"+self.domainAndPort+"/rest/marker/"
        #         logging.info("searching for API v0: sending get to "+url)
        #         try:
        #             r=self.s.get(url,timeout=10)
        #         except:
        #             logging.info("no response from second get request")
        #         else:
        #             logging.info("response code = "+str(r.status_code))
        #             if r.status_code==200:
        #                 self.apiVersion=0
        #                 self.apiUrlMid="/rest/"
        #                 # for v0, send a get to the map URL to authenticate the session
        #                 url="http://"+self.domainAndPort+"/m/"+self.mapID
        #                 logging.info("sending API v0 authentication request to url "+url)
        #                 try:
        #                     r=self.s.get(url,timeout=10)
        #                 except:
        #                     logging.info("no response during authentication for API v0")
        #                 else:
        #                     logging.info("response code = "+str(r.status_code))
        #                     if r.status_code==200:
        #                         logging.info("API v0 session is now authenticated")
        
        # try these hardcodes, instead of the above dummy-request, to see if it avoids the NPE's
        self.apiVersion=1
        self.apiUrlMid="/api/v1/map/[MAPID]/"

        # To enable Fiddler support, so Fiddler can see outgoing requests sent from this code,
        #  add 'proxies=self.proxyDict' argument to request calls and use locahost port 8888
        #  (the default Fiddler proxy port number - configurable in Fiddler connection settings).
        #  Note that if Fiddler is NOT running, but the proxies are set, this would throw
        #  an exception each time.  So, if Fiddler proxies are requested, confirm here first.
        self.proxyDict=None
        if self.useFiddlerProxy:
            logging.info('This session was requested to use the Fiddler proxy.  Verifying that the proxy host is running...')
            try:
                r=requests.get('http://127.0.0.1:8888')
            except:
                logging.warning('Fiddler proxy host does not appear to be running.  This session will not use Fiddler proxies.')
            else:
                logging.info('  Fiddler ping response appears valid; setting the proxies: r='+str(r))
                self.proxyDict={
                    'http':'http://127.0.0.1:8888',
                    'https':'https://127.0.0.1:8888',
                    'ftp':'ftp://127.0.0.1:8888'
                }

        self.sendUserdata() # to get session cookies, in case this client has not connected in a long time

        # new map requested
        # 1. send a POST request to /map - payload (tested on CTD 4225; won't work with <4221) =
        if self.mapID=='[NEW]':
            j={}
            j['properties']={
                'mapConfig':json.dumps({'activeLayers':[['mbt',1]]}),
                'cfgLocked':True,
                'title':'new',
                'mode':'sar' # 'cal' for recreation, 'sar' for SAR
            }
            j['state']={
                'type':'FeatureCollection',
                'features':[
                    # At least one feature must exist to set the 'updated' field of the map;
                    #  otherwise it always shows up at the bottom of the map list when sorted
                    #  chronologically.  Definitely best to have it show up adjacent to the
                    #  incident map.
                    {
                        'geometry': {
                            'coordinates': [-120,39,0,0],
                            'type':'Point'
                        },
                        'id':'11111111-1111-1111-1111-111111111111',
                        'type':'Feature',
                        'properties':{
                            'creator':accountId,
                            'title':'NewMapDummyMarker',
                            'class':'Marker'
                        }
                    }
                ]
            }
            # logging.info('dap='+str(self.domainAndPort))
            # logging.info('payload='+str(json.dumps(j,indent=3)))
            r=self.sendRequest('post','[NEW]',j,domainAndPort=self.domainAndPort)
            if r:
                self.mapID=r.rstrip('/').split('/')[-1]
                self.s=requests.session()
                self.sendUserdata() # to get session cookies for new session
                time.sleep(1) # to avoid a 401 on the subsequent get request
                self.delMarker(id='11111111-1111-1111-1111-111111111111')
            else:
                logging.info('New map request failed.  See the log for details.')
                return False

        
        # logging.info("API version:"+str(self.apiVersion))
        # sync needs to be done here instead of in the caller, so that
        #  edit functions can have access to the full json
        self.syncThreadStarted=False
        self.syncPauseManual=False

        # regardless of whether sync is specified, we need to do the initial cache population
        #   here in the main thread, so that mapData is populated right away
        logging.info('Initial cache population begins.')
        self.doSync()
        logging.info('Initial cache population complete.')

        if self.sync:
            self.start()

        return True


    def sendUserdata(self,activeLayers=[['mbt',1]],center=[-120,39],zoom=13):
        j={
            'map':{
                # 'config':{
                #     'activeLayers':activeLayers
                # },
                'center':center,
                'zoom':zoom
            }
        }
        # logging.info('dap='+str(self.domainAndPort))
        # logging.info('payload='+str(json.dumps(j,indent=3)))
        self.sendRequest('post','api/v0/userdata',j,domainAndPort=self.domainAndPort)

    def doSync(self):
        # logging.info('sync marker: '+self.mapID+' begin')
        if self.syncing:
            logging.warning('sync-within-sync requested; returning to calling code.')
            return False
        self.syncing=True

        # Keys under 'result':
        # 1 - 'ids' will only exist on first sync or after a deletion, so, if 'ids' exists
        #     then just use it to replace the entire cached 'ids', and also do cleanup later
        #     by deleting any state->features from the cache whose 'id' value is not in 'ids'
        # 2 - state->features is an array of changed existing features, and the array will
        #     have complete data for 'geometry', 'id', 'type', and 'properties', so, for each
        #     item in state->features, just replace the entire existing cached feature of
        #     the same id

        # logging.info('Sending sartopo "since" request...')
        rj=self.sendRequest('get','since/'+str(max(0,self.lastSuccessfulSyncTimestamp-500)),None,returnJson='ALL',timeout=self.syncTimeout)
        if rj and rj['status']=='ok':
            if self.syncDumpFile:
                with open(insertBeforeExt(self.syncDumpFile,'.since'+str(max(0,self.lastSuccessfulSyncTimestamp-500))),"w") as f:
                    f.write(json.dumps(rj,indent=3))
            # response timestamp is an integer number of milliseconds; equivalent to
            # int(time.time()*1000))
            self.lastSuccessfulSyncTimestamp=rj['result']['timestamp']
            # logging.info('Successful sartopo sync: timestamp='+str(self.lastSuccessfulSyncTimestamp))
            if self.syncCallback:
                self.syncCallback()
            rjr=rj['result']
            rjrsf=rjr['state']['features']
            
            # 1 - if 'ids' exists, use it verbatim; cleanup happens later
            idsBefore=None
            if 'ids' in rjr.keys():
                idsBefore=copy.deepcopy(self.mapData['ids'])
                self.mapData['ids']=rjr['ids']
                logging.info('  Updating "ids"')
            
            # 2 - update existing features as needed
            if len(rjrsf)>0:
                logging.info('  processing '+str(len(rjrsf))+' feature(s):'+str([x['id'] for x in rjrsf]))
                # logging.info(json.dumps(rj,indent=3))
                for f in rjrsf:
                    rjrfid=f['id']
                    prop=f['properties']
                    title=str(prop.get('title',None))
                    featureClass=str(prop['class'])
                    processed=False
                    for i in range(len(self.mapData['state']['features'])):
                        # only modify existing cache data if id and class are both matches:
                        #  subset apptracks can have the same id as the finished apptrack shape
                        if self.mapData['state']['features'][i]['id']==rjrfid and self.mapData['state']['features'][i]['properties']['class']==featureClass:
                            # don't simply overwrite the entire feature entry:
                            #  - if only geometry was changed, indicated by properties['nop']=true,
                            #    then leave properties alone and just overwrite geometry;
                            #  - if only properties were changed, geometry will not be in the response,
                            #    so leave geometry alone
                            #  SO:
                            #  - if f->prop->title exists, replace the entire prop dict
                            #  - if f->geometry exists, replace the entire geometry dict
                            if 'title' in prop.keys():
                                if self.mapData['state']['features'][i]['properties']!=prop:
                                    logging.info('  Updating properties for '+featureClass+':'+title)
                                    # logging.info('    old:'+json.dumps(self.mapData['state']['features'][i]['properties']))
                                    # logging.info('    new:'+json.dumps(prop))
                                    self.mapData['state']['features'][i]['properties']=prop
                                    if self.propertyUpdateCallback:
                                        self.propertyUpdateCallback(f)
                                else:
                                    logging.info('  response contained properties for '+featureClass+':'+title+' but they matched the cache, so no cache update or callback is performed')
                            if title=='None':
                                title=self.mapData['state']['features'][i]['properties']['title']
                            if 'geometry' in f.keys():
                                if self.mapData['state']['features'][i]['geometry']!=f['geometry']:
                                    logging.info('  Updating geometry for '+featureClass+':'+title)
                                    # if geometry.incremental exists and is true, append new coordinates to existing coordinates
                                    # otherwise, replace the entire geometry value
                                    fg=f['geometry']
                                    mdsfg=self.mapData['state']['features'][i]['geometry']
                                    if fg.get('incremental',None):
                                        mdsfgc=mdsfg['coordinates']
                                        latestExistingTS=mdsfgc[-1][3]
                                        fgc=fg.get('coordinates',[])
                                        # avoid duplicates without walking the entire existing list of points;
                                        #  assume that timestamps are strictly increasing in list item sequence
                                        # walk forward through new points:
                                        # if timestamp is more recent than latest existing point, then append the rest of the new point list
                                        for n in range(len(fgc)):
                                            if fgc[n][3]>latestExistingTS:
                                                mdsfgc+=fgc[n:]
                                                break
                                        mdsfg['size']=len(mdsfgc)
                                    else:
                                        self.mapData['state']['features'][i]['geometry']=f['geometry']
                                    if self.geometryUpdateCallback:
                                        self.geometryUpdateCallback(f)
                                else:
                                    logging.info('  response contained geometry for '+featureClass+':'+title+' but it matched the cache, so no cache update or callback is performed')
                            processed=True
                            break
                    # 2b - otherwise, create it - and add to ids so it doesn't get cleaned
                    if not processed:
                        # logging.info('Adding to cache:'+featureClass+':'+title)
                        self.mapData['state']['features'].append(f)
                        if f['id'] not in self.mapData['ids'][prop['class']]:
                            self.mapData['ids'][prop['class']].append(f['id'])
                        # logging.info('mapData immediate:\n'+json.dumps(self.mapData,indent=3))
                        if self.newFeatureCallback:
                            self.newFeatureCallback(f)

            # 3 - cleanup - remove features from the cache whose ids are no longer in cached id list
            #  (ids will be part of the response whenever feature(s) were added or deleted)
            #  (finishing an apptrack moves the id from AppTracks to Shapes, so the id count is not affected)
            #  (if the server does not remove the apptrack correctly after finishing, the same id will
            #   be in AppTracks and in Shapes)
            # beforeStr='mapData before cleanup:'+json.dumps(self.mapData,indent=3)
            #  at this point in the code, the deleted feature has been removed from ids but is still part of state-features
            # self.mapIDs=sum(self.mapData['ids'].values(),[])
            # mapSFIDsBefore=[f['id'] for f in self.mapData['state']['features']]
            # edit the cache directly: https://stackoverflow.com/a/1157174/3577105

            if idsBefore:
                deletedDict={}
                deletedAnythingFlag=False
                for c in idsBefore.keys():
                    for id in idsBefore[c]:
                        if id not in self.mapData['ids'][c]:
                            self.mapData['state']['features'][:]=(f for f in self.mapData['state']['features'] if not(f['id']==id and f['properties']['class']==c))
                            deletedDict.setdefault(c,[]).append(id)
                            deletedAnythingFlag=True
                            if self.deletedFeatureCallback:
                                self.deletedFeatureCallback(id,c)
                if deletedAnythingFlag:
                    logging.info('deleted items have been removed from cache:\n'+json.dumps(deletedDict,indent=3))
            

            # l1=len(self.mapData['state']['features'])
            # logging.info('before:'+str(l1)+':'+str(self.mapData['state']['features']))
            # self.mapData['state']['features'][:]=(f for f in self.mapData['state']['features'] if f['id'] in self.mapIDs)
            # mapSFIDs=[f['id'] for f in self.mapData['state']['features']]
            # l2=len(self.mapData['state']['features'])
            # logging.info('after:'+str(l1)+':'+str(self.mapData['state']['features']))
            # if l2!=l1:
            #     deletedIds=list(set(mapSFIDsBefore)-set(mapSFIDs))
            #     logging.info('cleaned up '+str(l1-l2)+' feature(s) from the cache:'+str(deletedIds))
            #     if self.deletedFeatureCallback:
            #         for did in deletedIds:
            #             self.deletedFeatureCallback(did)
                # logging.info(beforeStr)
                # logging.info('mapData after cleanup:'+json.dumps(self.mapData,indent=3))

            # logging.info('mapData:\n'+json.dumps(self.mapData,indent=3))
            # logging.info('\n'+self.mapID+':\n  mapIDs:'+str(self.mapIDs)+'\nmapSFIDs:'+str(mapSFIDs))

            # bug: i is defined as an index into mapSFIDs but is used as an index into self.mapData['state']['features']:
            # # for i in range(len(mapSFIDs)):
            # #     if mapSFIDs[i] not in self.mapIDs:
            # #         prop=self.mapData['state']['features'][i]['properties']
            # #         logging.info('  Deleting '+mapSFIDs[i]+':'+str(prop['class'])+':'+str(prop['title']))
            # #         if self.deletedFeatureCallback:
            # #             self.deletedFeatureCallback(self.mapData['state']['features'][i])
            # #         del self.mapData['state']['features'][i]
            

            if self.cacheDumpFile:
                with open(insertBeforeExt(self.cacheDumpFile,'.cache'+str(max(0,self.lastSuccessfulSyncTimestamp))),"w") as f:
                    f.write('sync cleanup:')
                    f.write('  mapIDs='+str(self.mapID)+'\n\n')
                    # f.write('  mapSFIDs='+str(mapSFIDs)+'\n\n')
                    f.write(json.dumps(self.mapData,indent=3))

            # self.syncing=False
            self.lastSuccessfulSyncTSLocal=int(time.time()*1000)
            if self.sync:
                if not threading.main_thread().is_alive():
                    logging.info('Main thread has ended; sync is stopping...')
                    self.sync=False
                # if threading.main_thread().is_alive():
                #     # this is where the blocking sleep happens, instead of spawning a new thread;
                #     #  normally this function is being called in a separate thread anyway, so
                #     #  the main thread can continue while this thread sleeps
                #     logging.info('  sleeping for specified sync interval ('+str(self.syncInterval)+' seconds)...')
                #     time.sleep(self.syncInterval)
                #     while self.syncPause: # wait until at least one second after sendRequest finishes
                #         logging.info('  sync is paused - sleeping for one second')
                #         time.sleep(1)
                #     self.doSync() # will this trigger the recursion limit eventually?  Rethink looping method!
                # else:
                #     logging.info('Main thread has ended; sync is stopping...')

        else:
            logging.error('Sync returned invalid or no response; sync aborted:'+str(rj))
            self.sync=False
            self.apiVersion=-1 # downstream tools may use apiVersion as indicator of link status
        self.syncing=False
        # logging.info('sync marker: '+self.mapID+' end')

    # refresh - update the cache (self.mapData) by calling doSync once;
    #   only relevant if sync is off; if the latest refresh is within the sync interval value (even when sync is off),
    #   then don't do a refresh unless forceImmediate is True
    #  since doSync() would be called from this thread, it is always blocking
    def refresh(self,blocking=False,forceImmediate=False):
        msg='refresh requested for map '+self.mapID+': '
        if self.syncing:
            msg+='sync already in progress'
            logging.info(msg)
        else:
            d=int(time.time()*1000)-self.lastSuccessfulSyncTSLocal # integer ms since last completed sync
            msg+=str(d)+'ms since last completed sync; '
            if d>(self.syncInterval*1000):
                msg+='longer than syncInterval: syncing now'
                logging.info(msg)
                self.doSync()
            else:
                msg+='shorter than syncInterval; '
                if forceImmediate:
                    msg+='forceImmediate specified: syncing now'
                    logging.info(msg)
                    self.doSync()
                else:
                    msg+='forceImmediate not specified: not syncing now'
                    # logging.info(msg)
    
    def __del__(self):
        logging.info('SartopoSession instance deleted for map '+self.mapID+'.')
        if self.sync:
            self.stop()

    def start(self):
        self.sync=True
        if self.syncThreadStarted:
            logging.info('Sartopo sync is already running for map '+self.mapID+'.')
        else:
            threading.Thread(target=self._syncLoop).start()
            logging.info('Sartopo syncing initiated for map '+self.mapID+'.')
            self.syncThreadStarted=True

    def stop(self):
        logging.info('Sartopo sync terminating for map '+self.mapID+'.')
        self.sync=False

    def pause(self):
        logging.info('Pausing sync for map '+self.mapID+'...')
        self.syncPauseManual=True

    def resume(self):
        logging.info('Resuming sync for map '+self.mapID+'.')
        self.syncPauseManual=False
    
    # _syncLoop - should only be called from self.start(), which calls _syncLoop in a new thread.
    #  This is just a loop that calls doSync.  To prevent an endless loop, doSync must be
    #  able to terminate the thread if the main thread has ended; also note that any other
    #  code can end sync by setting self.sync to False.  This allows doSync to be
    #  iterative rather than recursive (which would eventually hit recursion limit issues),
    #  and it allows the blocking sleep call to happen here instead of inside doSync.
    def _syncLoop(self):
        if self.syncCompletedCount==0:
            logging.info('This is the first sync attempt; pausing for the normal sync interval before starting sync.')
            time.sleep(self.syncInterval)
        while self.sync:
            if not self.syncPauseManual:
                self.syncPauseMessageGiven=False
                while self.syncPause:
                    if not threading.main_thread().is_alive():
                        logging.info('Main thread has ended; sync is stopping...')
                        self.syncPause=False
                        self.sync=False
                    if not self.syncPauseMessageGiven:
                        logging.info(self.mapID+': sync pause begins; sync will not happen until sync pause ends')
                        self.syncPauseMessageGiven=True
                    time.sleep(1)
                if self.syncPauseMessageGiven:
                    logging.info(self.mapID+': sync pause ends; resuming sync')
                    self.syncPauseMessageGiven=False
                syncWaited=0
                while self.syncing and syncWaited<20: # wait for any current callbacks within doSync() to complete, with timeout of 20 sec
                    logging.info(' [sync from _syncLoop is waiting for current sync processing to finish, up to '+str(20-syncWaited)+' more seconds...]')
                    time.sleep(1)
                    syncWaited+=1
                try:
                    self.doSync()
                    self.syncCompletedCount+=1
                except Exception as e:
                    logging.exception('Exception during sync of map '+self.mapID+'; stopping sync:') # logging.exception logs details and traceback
                    # remove sync blockers, to let the thread shut down cleanly, avoiding a zombie loop when sync restart is attempted
                    self.syncPause=False
                    self.syncing=False
                    self.syncThreadStarted=False
                    self.sync=False
            if self.sync: # don't bother with the sleep if sync is no longer True
                time.sleep(self.syncInterval)

    def sendRequest(self,type,apiUrlEnd,j,id="",returnJson=None,timeout=None,domainAndPort=None):
        # objgraph.show_growth()
        # logging.info('RAM:'+str(process.memory_info().rss/1024**2)+'MB')
        self.syncPause=True
        timeout=timeout or self.syncTimeout
        newMap='[NEW]' in apiUrlEnd  # specific mapID that indicates a new map should be created
        if self.apiVersion<0:
            logging.error("sendRequest: sartopo session is invalid; request aborted: type="+str(type)+" apiUrlEnd="+str(apiUrlEnd))
            return False
        mid=self.apiUrlMid
        if 'api/' in apiUrlEnd.lower():
            mid='/'
        else:
            apiUrlEnd=apiUrlEnd.lower()
            if self.apiVersion>0:
                apiUrlEnd=apiUrlEnd.capitalize()
            if apiUrlEnd.startswith("Since"): # 'since' must be lowercase even in API v1
                apiUrlEnd=apiUrlEnd.lower()
        # append id (if any) to apiUrlEnd so that it is a part of the request
        #  destination and also a part of the pre-hashed data for signed requests
        if id and id!="": # sending online request with slash at the end causes failure
            apiUrlEnd=apiUrlEnd+"/"+id
        mid=mid.replace("[MAPID]",self.mapID)
        apiUrlEnd=apiUrlEnd.replace("[MAPID]",self.mapID)
        domainAndPort=domainAndPort or self.domainAndPort # use arg value if specified
        if not domainAndPort:
            logging.error("sendRequest was attempted but no valid domainAndPort was specified.")
            return False
        prefix='http://'
        # set a flag: is this an internet request?
        accountId=self.accountId
        internet=domainAndPort.lower() in ['sartopo.com','caltopo.com']
        if internet:
            if self.accountIdInternet:
                accountId=self.accountIdInternet
            else:
                logging.warning('A request is about to be sent to the internet, but accountIdInternet was not specified.  The request will use accountId, but will fail if that ID does not have valid permissions at the internet host.')
            prefix='https://'
            if not self.key or not self.id:
                logging.error("There was an attempt to send an internet request, but 'id' and/or 'key' was not specified for this session.  The request will not be sent.")
                return False
        url=prefix+domainAndPort+mid+apiUrlEnd
        wrapInJsonKey=True
        if newMap:
            url=prefix+domainAndPort+'/api/v1/acct/'+accountId+'/CollaborativeMap' # works for CTD 4221 and up
        if '/since/' not in url:
            logging.info("sending "+str(type)+" to "+url)
        if type=="post":
            if wrapInJsonKey:
                params={}
                params["json"]=json.dumps(j)
            else:
                params=j
            if internet:
                expires=int(time.time()*1000)+120000 # 2 minutes from current time, in milliseconds
                data="POST "+mid+apiUrlEnd+"\n"+str(expires)+"\n"+json.dumps(j)
                # logging.info("pre-hashed data:"+data)                
                token=hmac.new(base64.b64decode(self.key),data.encode(),'sha256').digest()
                token=base64.b64encode(token).decode()
                # logging.info("hashed data:"+str(token))
                params["id"]=self.id
                params["expires"]=expires
                params["signature"]=token
                paramsPrint=copy.deepcopy(params)
                paramsPrint['id']='.....'
                paramsPrint['signature']='.....'
            else:
                paramsPrint=params
            # logging.info("SENDING POST to '"+url+"':")
            # logging.info(json.dumps(paramsPrint,indent=3))
            # don't print the entire PDF generation request - upstream code can print a PDF data summary
            if 'PDFLink' not in url:
                logging.info(jsonForLog(paramsPrint))
            r=self.s.post(url,data=params,timeout=timeout,proxies=self.proxyDict,allow_redirects=False)
        elif type=="get": # no need for json in GET; sending null JSON causes downstream error
            # logging.info("SENDING GET to '"+url+"':")
            r=self.s.get(url,timeout=timeout,proxies=self.proxyDict)
        elif type=="delete":
            params={}
            if "sartopo.com" in self.domainAndPort.lower():
                expires=int(time.time()*1000)+120000 # 2 minutes from current time, in milliseconds
                data="DELETE "+mid+apiUrlEnd+"\n"+str(expires)+"\n"  #last newline needed as placeholder for json
                # logging.info("pre-hashed data:"+data)                
                token=hmac.new(base64.b64decode(self.key),data.encode(),'sha256').digest()
                token=base64.b64encode(token).decode()
#                 logging.info("hashed data:"+str(token))
                params["json"]=''   # no body, but is required
                params["id"]=self.id
                params["expires"]=expires
                params["signature"]=token
            #     paramsPrint=copy.deepcopy(params)
            #     paramsPrint['id']='.....'
            #     paramsPrint['signature']='.....'
            # else:
            #     paramsPrint=params
            # logging.info("SENDING DELETE to '"+url+"':")
            # logging.info(json.dumps(paramsPrint,indent=3))
            # logging.info("Key:"+str(self.key))
            r=self.s.delete(url,params=params,timeout=timeout,proxies=self.proxyDict)   ## use params for query vs data for body data
            # logging.info("URL:"+str(url))
            # logging.info("Ris:"+str(r))
        else:
            logging.error("sendRequest: Unrecognized request type:"+str(type))
            self.syncPause=False
            return False

        if r.status_code!=200:
            logging.info("response code = "+str(r.status_code))

        if newMap:
            # for CTD 4221 and newer, and internet, a new map request should return 200, and the response data
            #  should contain the new map ID in response['result']['id']
            # for CTD 4214, a new map request should return 3xx response (redirect); if allow_redirects=False is
            #  in the response, the redirect target will appear as the 'Location' response header.
            if r.status_code==200:
                try:
                    rj=r.json()
                except:
                    logging.error('New map request failed: response had do decodable json:'+str(r.status_code)+':'+r.text)
                    self.syncPause=False
                    return False
                else:
                    rjr=rj.get('result')
                    newUrl=None
                    if rjr:
                        newUrl=rjr['id']
                    if newUrl:
                        logging.info('New map URL:'+newUrl)
                        self.syncPause=False
                        return newUrl
                    else:
                        logging.error('No new map URL was returned in the response json:'+str(r.status_code)+':'+json.dumps(rj))
                        self.syncPause=False
                        return False
            else:
                logging.error('New map request failed:'+str(r.status_code)+':'+r.text)
                self.syncPause=False
                return False

            # old redirect method worked with CTD 4214:
            # if url.endswith('/map'):
            #     if 300<=r.status_code<=399:
            #         # logging.info("response headers:"+str(json.dumps(dict(r.headers),indent=3)))
            #         newUrl=r.headers.get('Location',None)
            #         if newUrl:
            #             logging.info('New map URL:'+newUrl)
            #             self.syncPause=False
            #             return newUrl
            #         else:
            #             logging.info('No new map URL was returned in the response header.')
            #             self.syncPause=False
            #             return False
            #     else:
            #         logging.info('Unexpected response from new map request:'+str(r.status_code)+':'+r.text)
            #         return False
            # else:
            #     if r.status_code==200:
            #         logging.info('200 response from new map request:'+r.text)
            #         return False
            #     else:
            #         logging.info('Unexpected response from new map request:'+str(r.status_code)+':'+r.text)
            #         return False


        else:
            if returnJson:
                # logging.info('response:'+str(r))
                try:
                    rj=r.json()
                except:
                    logging.error("sendRequest: response had no decodable json:"+str(r))
                    self.syncPause=False
                    return False
                else:
                    if 'status' in rj and rj['status'].lower()!='ok':
                        logging.warning('response status other than "ok":  '+str(rj))
                        self.syncPause=False
                        return rj
                    if returnJson=="ID":
                        id=None
                        if 'result' in rj and 'id' in rj['result']:
                            id=rj['result']['id']
                        elif 'id' in rj:
                            id=rj['id']
                        elif not rj['result']['state']['features']:  # response if no new info
                            self.syncPause=False
                            return 0
                        elif 'result' in rj and 'id' in rj['result']['state']['features'][0]:
                            id=rj['result']['state']['features'][0]['id']
                        else:
                            logging.info("sendRequest: No valid ID was returned from the request:")
                            logging.info(json.dumps(rj,indent=3))
                        self.syncPause=False
                        return id
                    if returnJson=="ALL":
                        # since CTD 4221 returns 'title' as an empty string for all assignments,
                        #  set 'title' to <letter><space><number> for all assignments here
                        # this code looks fairly resource intensive; for a map with 50 assignments, initial sync
                        #  is about 6.5% slower with this if clause than without, but it would be good to profile
                        #  memory consumption too - is this calling .keys() and creating new lists each time?
                        #  maybe better to wrap it all in try/except, but, would that iterate over all features?
                        if 'result' in rj.keys() and 'state' in rj['result'].keys() and 'features' in rj['result']['state'].keys():
                            alist=[f for f in rj['result']['state']['features'] if 'properties' in f.keys() and 'class' in f['properties'].keys() and f['properties']['class'].lower()=='assignment']
                            for a in alist:
                                a['properties']['title']=a['properties']['letter']+' '+a['properties']['number']
                        self.syncPause=False
                        return rj
        self.syncPause=False
        
    def addFolder(self,
            label="New Folder",
            queue=False):
        j={}
        j['properties']={}
        j['properties']['title']=label
        if queue:
            self.queue.setdefault('folder',[]).append(j)
            return 0
        else:
            # return self.sendRequest("post","folder",j,returnJson="ID")
            # add to .mapData immediately
            rj=self.sendRequest('post','folder',j,returnJson='ALL')
            rjr=rj['result']
            id=rjr['id']
            self.mapData['ids'].setdefault('Folder',[]).append(id)
            self.mapData['state']['features'].append(rjr)
            return id
    
    def addMarker(self,
            lat,
            lon,
            title='New Marker',
            description='',
            color='#FF0000',
            symbol='point',
            rotation=None,
            folderId=None,
            existingId=None,
            update=0,
            size=1,
            queue=False):
        j={}
        jp={}
        jg={}
        jp['class']='Marker'
        jp['updated']=update
        jp['marker-color']=color
        jp['marker-symbol']=symbol
        jp['marker-size']=size
        jp['marker-rotation']=rotation
        jp['title']=title
        if folderId is not None:
            jp['folderId']=folderId
        jp['description']=description
        jg['type']='Point'
        jg['coordinates']=[float(lon),float(lat)]
        j['properties']=jp
        j['geometry']=jg
        j['type']='Feature'
        if existingId is not None:
            j['id']=existingId
        # logging.info("sending json: "+json.dumps(j,indent=3))
        if queue:
            self.queue.setdefault('Marker',[]).append(j)
            return 0
        else:
            # return self.sendRequest('post','marker',j,id=existingId,returnJson='ID')
            # add to .mapData immediately
            rj=self.sendRequest('post','marker',j,id=existingId,returnJson='ALL')
            rjr=rj['result']
            id=rjr['id']
            self.mapData['ids'].setdefault('Marker',[]).append(id)
            self.mapData['state']['features'].append(rjr)
            return id

    def addLine(self,
            points,
            title='New Line',
            description='',
            width=2,
            opacity=1,
            color='#FF0000',
            pattern='solid',
            gpstype='TRACK',
            folderId=None,
            existingId=None,
            queue=False,
            timeout=10):
        j={}
        jp={}
        jg={}
        jp['title']=title
        if folderId is not None:
            jp['folderId']=folderId
        jp['description']=description
        jp['stroke-width']=width
        jp['stroke-opacity']=opacity
        jp['stroke']=color
        jp['pattern']=pattern
        jp['gpstype']=gpstype
        jg['type']='LineString'
        jg['coordinates']=points
        j['properties']=jp
        j['geometry']=jg
        if existingId is not None:
            j['id']=existingId
        # logging.info("sending json: "+json.dumps(j,indent=3))
        if queue:
            self.queue.setdefault('Shape',[]).append(j)
            return 0
        else:
            # return self.sendRequest("post","Shape",j,id=existingId,returnJson="ID",timeout=timeout)
            # add to .mapData immediately
            rj=self.sendRequest('post','Shape',j,id=existingId,returnJson='ALL',timeout=timeout)
            rjr=rj['result']
            id=rjr['id']
            self.mapData['ids'].setdefault('Shape',[]).append(id)
            self.mapData['state']['features'].append(rjr)
            return id

    def addPolygon(self,
            points,
            title='New Shape',
            folderId=None,
            description='',
            strokeOpacity=1,
            strokeWidth=2,
            fillOpacity=0.1,
            stroke='#FF0000',
            fill='#FF0000',
            gpstype='TRACK',
            existingId=None,
            queue=False):
        j={}
        jp={}
        jg={}
        jp['title']=title
        if folderId is not None:
            jp['folderId']=folderId
        jp['description']=description
        jp['stroke-width']=strokeWidth
        jp['stroke-opacity']=strokeOpacity
        jp['stroke']=stroke
        jp['fill']=fill
        jp['fill-opacity']=fillOpacity
        jp['gpstype']=gpstype
        jg['type']='Polygon'
        jg['coordinates']=[points]
        j['properties']=jp
        j['geometry']=jg
        if existingId is not None:
            j['id']=existingId
        # logging.info("sending json: "+json.dumps(j,indent=3))
        if queue:
            self.queue.setdefault('Shape',[]).append(j)
            return 0
        else:
            # return self.sendRequest('post','Shape',j,id=existingId,returnJson='ID')
            # add to .mapData immediately
            rj=self.sendRequest('post','Shape',j,id=existingId,returnJson='ALL')
            rjr=rj['result']
            id=rjr['id']
            self.mapData['ids'].setdefault('Shape',[]).append(id)
            self.mapData['state']['features'].append(rjr)
            return id

    def addLineAssignment(self,
            points,
            number=None,
            letter=None,
            opId=None,
            folderId=None,
            resourceType='GROUND',
            teamSize=0,
            priority='LOW',
            responsivePOD='LOW',
            unresponsivePOD='LOW',
            cluePOD='LOW',
            description='',
            previousEfforts='',
            transportation='',
            timeAllocated=0,
            primaryFrequency='',
            secondaryFrequency='',
            preparedBy='',
            gpstype='TRACK',
            status='DRAFT',
            existingId=None,
            queue=False):
        j={}
        jp={}
        jg={}
        if number is not None:
            jp['number']=number
        if letter is not None:
            jp['letter']=letter
        if opId is not None:
            jp['operationalPeriodId']=opId
        if folderId is not None:
            jp['folderId']=folderId
        jp['resourceType']=resourceType
        jp['teamSize']=teamSize
        jp['priority']=priority
        jp['responsivePOD']=responsivePOD
        jp['unresponsivePOD']=unresponsivePOD
        jp['cluePOD']=cluePOD
        jp['description']=description
        jp['previousEfforts']=previousEfforts
        jp['transportation']=transportation
        jp['timeAllocated']=timeAllocated
        jp['primaryFrequency']=primaryFrequency
        jp['secondaryFrequency']=secondaryFrequency
        jp['preparedBy']=preparedBy
        jp['gpstype']=gpstype
        jp['status']=status
        jg['type']='LineString'
        jg['coordinates']=points
        j['properties']=jp
        j['geometry']=jg
        if existingId is not None:
            j['id']=existingId
        # logging.info("sending json: "+json.dumps(j,indent=3))
        if queue:
            self.queue.setdefault('Assignment',[]).append(j)
            return 0
        else:
            return self.sendRequest('post','Assignment',j,id=existingId,returnJson='ID')

    # buffers: in the web interface, adding a buffer results in two requests:
    #   1. api/v0/geodata/buffer - payload = drawn centerline, response = polygon points
    #   2. api/v1/map/<mapID>/Assignment or /Shape - payload = as usual, using the 
    #        response from the previous request as the list of polygon points, with
    #        geometry type = Polygon
    #   so, while it may be quicker to just perform the buffer calculation here
    #       and avoid the need to do the first request, the algorithm may be complicated and
    #       should stay consistent, so it's probably safest to do both requests just as the
    #       web interface does.

    # def getBufferPoints(self,centerLinePoints,size):
    #     j={}
    #     jg={}
    #     jg['type']='LineString'
    #     jg['coordinates']=centerLinePoints
    #     j['geometry']=jg
    #     j['size']=size
    #     rj=self.sendRequest('post','api/v0/geodata/buffer',j,None,returnJson='ALL')
    #     logging.info('generated buffer response:'+json.dumps(rj,indent=3))
    #     return rj

    def addAreaAssignment(self,
            points,
            number=None,
            letter=None,
            opId=None,
            folderId=None,
            resourceType='GROUND',
            teamSize=0,
            priority='LOW',
            responsivePOD='LOW',
            unresponsivePOD='LOW',
            cluePOD='LOW',
            description='',
            previousEfforts='',
            transportation='',
            timeAllocated=0,
            primaryFrequency='',
            secondaryFrequency='',
            preparedBy='',
            gpstype='TRACK',
            status='DRAFT',
            existingId=None,
            queue=False):
        j={}
        jp={}
        jg={}
        if number is not None:
            jp['number']=number
        if letter is not None:
            jp['letter']=letter
        if opId is not None:
            jp['operationalPeriodId']=opId
        if folderId is not None:
            jp['folderId']=folderId
        jp['resourceType']=resourceType
        jp['teamSize']=teamSize
        jp['priority']=priority
        jp['responsivePOD']=responsivePOD
        jp['unresponsivePOD']=unresponsivePOD
        jp['cluePOD']=cluePOD
        jp['description']=description
        jp['previousEfforts']=previousEfforts
        jp['transportation']=transportation
        jp['timeAllocated']=timeAllocated
        jp['primaryFrequency']=primaryFrequency
        jp['secondaryFrequency']=secondaryFrequency
        jp['preparedBy']=preparedBy
        jp['gpstype']=gpstype
        jp['status']=status
        jg['type']='Polygon'
        jg['coordinates']=[points]
        j['properties']=jp
        j['geometry']=jg
        if existingId is not None:
            j['id']=existingId
        # logging.info("sending json: "+json.dumps(j,indent=3))
        if queue:
            self.queue.setdefault('Assignment',[]).append(j)
            return 0
        else:
            return self.sendRequest('post','Assignment',j,id=existingId,returnJson='ID')

    def flush(self,timeout=20):
        self.sendRequest('post','api/v0/map/[MAPID]/save',self.queue,timeout=timeout)
        self.queue={}

    # def center(self,lat,lon,z):
    #     .

    def addAppTrack(self,points,cnt=None,startTrack=True,title="New AppTrack",since=0,description="",folderId=None,existingId=""):
        j={}
        jp={}
        jg={}
        jp['class']='AppTrack'
        jp['updated']=int(time.time()*1000)
        jp['title']=title
        ##########################jp['nop']=True
        if folderId:
            jp['folderId']=folderId
        jp['description']=description
        jg['type']='LineString'
        jg['coordinates']=points
        jg['incremental']=True
        if cnt is None:
            cnt=len(points)
        jg['size']=cnt       # cnt includes number of coord in this call
        j['properties']=jp
        j['geometry']=jg
        j['type']='Feature'
        # if 0 == 1:      ## set for no existing ID
        ###if existingId:
            # j['id']=existingId   # get ID from first call - using Shape
        # else:
        existingId = ""
        #logging.info("sending json: "+json.dumps(j,indent=3))
        #logging.info("ID:"+str(existingId))
        # if 1 == 1:
        ##if startTrack == 1:
        logging.info("At request first time track"+str(existingId)+":"+str(j))
        return self.sendRequest("post","Shape",j,id=str(existingId),returnJson="ID")
        # else:
        #     logging.info("At request adding points to track:"+str(existingId)+":"+str(since)+":"+str(j))
        #     return self.sendRequest("post","since/"+str(since),j,id=str(existingId),returnJson="ID")

    def delMarker(self,id=""):
        self.delFeature(id=id,fClass="marker")

    def delFeature(self,id="",fClass=None):
        if not fClass:
            f=self.getFeature(id=id)
            if f:
                fClass=f['properties']['class']
            else:
                logging.error('delFeature: requested id "'+id+'" does not exist in the cache')
                return False
        return self.sendRequest("delete",fClass,None,id=str(id),returnJson="ALL")

    # getFeatures - attempts to get data from the local cache (self.madData); refreshes and tries again if necessary
    #   determining if a refresh is necessary:
    #   - if the requested feature/s is/are not in the cache, and it has been longer than syncInterval since the last refresh,
    #      then do a new refresh; otherwise return an empty list []
    #   - if the requested feature/s IS/ARE in the cache, do we need to do a refresh anyway?  Only if forceRefresh is True.
    def getFeatures(self,
            featureClass=None,
            title=None,
            id=None,
            featureClassExcludeList=[],
            letterOnly=False,
            allowMultiTitleMatch=False,
            since=0,
            timeout=False,
            forceRefresh=False):
        timeout=timeout or self.syncTimeout
        # rj=self.sendRequest('get','since/'+str(since),None,returnJson='ALL',timeout=timeout)
        # call refresh now; refresh will decide whether it needs to do a new doSync call, based
        #  on time since last doSync response - or, if specified with forceImmediate, will call
        #  doSync regardless of time since last doSync response
        self.refresh(forceImmediate=forceRefresh)
        # if forceRefresh:
        #     self.refresh(forceImmediate=True) # this is a blocking call
        # else:
    
        # if syncing loop is not on, call refresh now; refresh will call doSync if the previous sync response
        #  was longer than syncInterval ago, but will return without syncing otherwise
        
        # if not self.sync: 
        if featureClass is None and title is None and id is None:
            return self.mapData # if no feature class or title or id is specified, return the entire cache
        else:
            titleMatchCount=0
            rval=[]
            features=self.mapData['state']['features']
            # logging.info('features:\n'+json.dumps(features,indent=3))
            for feature in features:
                prop=feature.get('properties',None)
                if prop and isinstance(prop,dict):
                    pk=prop.keys()
                else:
                    logging.error('getFeatures: "properties" does not exist or is not a dict:'+str(feature))
                    return []
                c=prop['class']
                # logging.info('checking class='+c+'  id='+feature['id'])
                if feature['id']==id:
                    # logging.info(' id match:'+id)
                    if featureClass:
                        # logging.info('   featureClass specified:'+featureClass)
                        if c.lower()==featureClass.lower():
                            rval.append(feature)
                            # logging.info('     match')
                            break
                        # else:
                            # logging.info('     but class '+c+' did not match')
                    else:
                        rval.append(feature)
                        break
                if id is None and (c==featureClass or (featureClass is None and c not in featureClassExcludeList)):
                    if title is None:
                        rval.append(feature)
                    if 'title' in pk:
                        if letterOnly:
                            s=prop['title'].split()
                            # avoid exception when title exists but is blank
                            if len(s)>0:
                                if s[0]==title: # since assignments title may include number (not desired for edits) 
                                    titleMatchCount+=1
                                    rval.append(feature)
                        else:        
                            if prop['title'].rstrip()==title: # since assignments without number could still have a space after letter
                                titleMatchCount+=1
                                rval.append(feature)
                            elif 'letter' in pk: # if the title wasn't a match, try the letter if it exists
                                if prop.get('letter','').rstrip()==title:
                                    titleMatchCount+=1
                                    rval.append(feature)
                    else:
                        logging.error('getFeatures: no title key exists:'+str(feature))
            if len(rval)==0:
                # question: do we want to try a refresh and try one more time?
                logging.info('getFeatures: No features match the specified criteria.')
                logging.info('  (was looking for featureClass='+str(featureClass)+'  title='+str(title)+'  id='+str(id)+')')
                return []
            if titleMatchCount>1:
                if allowMultiTitleMatch:
                    return rval
                else:
                    logging.warning('getFeatures: More than one feature matches the specified title.')
                    return []
            else:
                return rval

    # getFeature - same interface as getFeatures, expecting only one result;
    #   if the number of results is not exactly one, return with an error
    def getFeature(self,
            featureClass=None,
            title=None,
            id=None,
            featureClassExcludeList=[],
            letterOnly=False,
            allowMultiTitleMatch=False,
            since=0,
            timeout=False,
            forceRefresh=False):
        r=self.getFeatures(
            featureClass=featureClass,
            title=title,
            id=id,
            featureClassExcludeList=featureClassExcludeList,
            letterOnly=letterOnly,
            allowMultiTitleMatch=allowMultiTitleMatch,
            since=since,
            timeout=timeout,
            forceRefresh=forceRefresh)
        if isinstance(r,list):
            if len(r)==1:
                return r[0]
            elif len(r)<1:
                logging.warning('getFeature: no match')
                return False
            else:
                msg='getFeature: more than one match found while looking for feature:'
                if featureClass:
                    msg+=' featureClass='+str(featureClass)
                if title:
                    msg+=' title='+str(title)
                if id:
                    msg+=' id='+str(id)
                logging.warning(msg)
                logging.info(str(r))
                return False
        else:
            logging.error('getFeature: return from getFeatures was not a list: '+str(r))

    # editFeature(id=None,className=None,title=None,letter=None,properties=None,geometry=None)
    # edit any properties and/or geometry of specified map feature

    #   - id, className, title, letter - used to identify the feature to be edited;
    #      if not enough info is given or it results in ambiguity, return with an error
    #         - id - optional argument; if specified, no search is needed
    #         - className - required argument, since it will be sent as part of the URL
    #         - title, letter - if id is not specified, exactly one of these must be specified
    
    #   - properties, geometry - one or both must be specified
    #      dictionaries of keys and values to be changed; they don't need to be complete;
    #      they will be merged here with the synced dictionary before sending to the server

    #  EXAMPLES:
    #  (assuming sts is a SartopoSession object)
    
    #  1. move a marker
    #    sts.editFeature(className='Marker',title='t',geometry={'coordinates':[-120,39,0,0]})

    #  2. change assignment status to INPROGRESS
    #    sts.editFeature(className='Assignment',letter='AB',properties={'status':'INPROGRESS'})

    #  3. change assignment number
    #    sts.editFeature(className='Assignment',letter='AB',properties={'number':'111'})

    def editFeature(self,
            id=None,
            className=None,
            title=None,
            letter=None,
            properties=None,
            geometry=None):

        logging.info('editFeature called')
        # PART 1: determine the exact id of the feature to be edited
        if id is None:
            # first, validate the arguments and adjust as needed
            if className is None:
                logging.error(' ClassName was not specified.')
                return False
            if letter is not None:
                if className != 'Assignment':
                    logging.warning(' Letter was specified, but className was specified as other than Assignment.  ClassName Assignment will be used.')
                className='Assignment'
            if title is None and letter is None:
                logging.error(' Either Title or Letter must be specified.')
                return False
            if title is not None and letter is not None:
                logging.warning(' Both Title and Letter were specified.  Only one or the other can be used for the search.  Using Letter, in case the rest of the feature title has changed.')
                title=None
            if title is not None:
                ltKey='title'
                ltVal=title
            else:
                ltKey='letter'
                ltVal=letter

            # validation complete; first search based on letter/title, then, if needed, filter based on className if specified
            
            # it's probably quicker to filter by letter/title first, since that should only return a very small number of hits,
            #   as opposed to filtering by className first, which could return a large number of hits

            features=[f for f in self.mapData['state']['features'] if f['properties'].get(ltKey,None)==ltVal and f['properties']['class'].lower()==className.lower()]
                
            if len(features)==0:
                logging.warning(' no feature matched class='+str(className)+' title='+str(title)+' letter='+str(letter))
                return False
            if len(features)>1:
                logging.warning(' more than one feature matched class='+str(className)+' title='+str(title)+' letter='+str(letter))
                return False
            feature=features[0]
            logging.info(' feature found: '+str(feature))

        else:
            logging.info(' id specified: '+id)
            features=[f for f in self.mapData['state']['features'] if f['id']==id]
            # logging.info(json.dumps(self.mapData,indent=3))
            if len(features)==1:
                feature=features[0]
                className=feature['properties']['class']
            else:
                logging.info('  no match!')
                return False

        # PART 2: merge the properties and/or geometry dictionaries, and send the request
        
        # the outgoing request when changing an assignment letter is as follows:
        # URL: ...../<mapID>/<className>/<id>
        # type: POST
        # json: {
        #   "type":"Feature",
        #   "id":"3c8e72a2-4ea6-433d-b547-37e23472065b",
        #   "properties":{
        #       "number":"",
        #       "letter":"AX",
        #       ...
        #       "class":"Assignment"
        #   }
        # }

        propToWrite=None
        if properties is not None:
            keys=properties.keys()
            propToWrite=feature['properties']
            for key in keys:
                propToWrite[key]=properties[key]
            # write the correct title for assignments, since sartopo does not internally recalcualte it
            if className.lower()=='assignment':
                propToWrite['title']=propToWrite['letter']+' '+propToWrite['number'].strip()

        geomToWrite=None
        if geometry is not None:
            if isinstance(geometry,dict) and 'coordinates' in geometry.keys():
                geometry['size']=len(geometry['coordinates'])
            # logging.info('geometry specified (size was recalculated if needed):\n'+json.dumps(geometry))
            geomToWrite=feature['geometry']
            for key in geometry.keys():
                geomToWrite[key]=geometry[key]
        
        j={'type':'Feature','id':feature['id']}
        if propToWrite is not None:
            j['properties']=propToWrite
        if geomToWrite is not None:
            j['geometry']=geomToWrite

        return self.sendRequest('post',className,j,id=feature['id'],returnJson='ID')

    # removeDuplicatePoints - walk a list of points - if a given point is
    #   very close to the previous point, delete it (<0.00001 degrees)

    def removeDuplicatePoints(self,points):
        logging.info('removeDuplicatePoints called')
        ls=LineString(points)
        logging.info('is_valid:'+str(ls.is_valid))
        logging.info('is_simple:'+str(ls.is_simple))
        out=[points[0]]
        for i in range(1,len(points)):
            dx=points[i][0]-points[i-1][0]
            dy=points[i][1]-points[i-1][1]
            logging.info('   '+str(i)+' : dx='+str(dx)+' dy='+str(dy))
            if abs(dx)>0.0005 or abs(dy)>0.0005:
                out.append(points[i])
        logging.info('\n     '+str(len(points))+' points: '+str(points)+'\n --> '+str(len(out))+' points: '+str(out))
        return out

    # getUsedSuffixList - get a list of integers of all used suffixes for the
    #   specified base title
    #   ex: if features exist in the cache with titles 'a','a:1','a:3','a:stuff','other'
    #   then getUsedSuffixList('a') should return [1,3]
    def getUsedSuffixList(self,base):
        # build list of all titles (or letters as appropriate) from the cache
        #  try 'letter' first; if not found, use 'title'; default to 'NO-TITLE'
        # logging.info('getUsedSuffixList called: base='+str(base))
        allTitles=[]
        for f in self.mapData['state']['features']:
            title='NO-TITLE'
            p=f.get('properties')
            if p:
                title=p.get('letter')
                if not title:
                    title=p.get('title')
            if title: # title could be None at this point
                allTitles.append(title)
        # logging.info('  allTitles='+str(allTitles))
        # extract the list of used suffixes
        suffixStrings=[x.split(':')[-1] for x in allTitles if x.startswith(base+':')]
        rval=[int(x) for x in suffixStrings if x.isnumeric()] # only positive integers, as integers
        logging.info('getUsedSuffixList: base='+str(base)+'  rval='+str(rval))
        return rval

    # getNextAvailableSuffix - get the next available suffix given a list of used titles; limit at 100
    def getNextAvailableSuffix(self,usedSuffixList):
        keepLooking=True
        suffix=1
        while keepLooking and suffix<100:
            if suffix not in usedSuffixList:
                keepLooking=False
            else:
                suffix+=1
        return suffix

    # removeSpurs - self-intersecting polygons can be caused by single-point
    #   'spurs': a,b,c,d,c,e,f  where c,d,c is the spur.  Change a sequence
    #   like this to a,b,c,e,f.
    def removeSpurs(self,points):
        # logging.info('removeSpurs called')
        # ls=LineString(points)
        # logging.info('is_valid:'+str(ls.is_valid))
        # logging.info('is_simple:'+str(ls.is_simple))
        if len(points)>3:
            out=points[0:2]
            for i in range(2,len(points)):
                if points[i][0:2]!=points[i-1][0:2]: # skip this point if it is the same as the previous point
                    if points[i][0:2]!=points[i-2][0:2]:
                        out.append(points[i])
                    else:
                        logging.info('spur removed at '+str(points[i-1]))
                        out.pop() # delete last vertex
                    # logging.info('\n --> '+str(len(out))+' points: '+str(out))
        else:
            # logging.info('\n      feature has less than three points; no spur removal attempted.')
            out=points
        # if len(points)!=len(out):
        #     logging.info('spur(s) were removed from the shape:\n    '+str(len(points))+' points: '+str(points)+'\n --> '+str(len(out))+' points: '+str(out))
        return out

    # cut - this method should accomodate the following operations:
    #   - remove a notch from a polygon, using a polygon
    #   - slice a polygon, using a polygon
    #   - slice a polygon, using a line
    #   - slice a line, using a polygon
    #   - slice a line, using a line
    #  the arguments (target, cutter) can be name (string), id (string), or feature (json)

    def cut(self,target,cutter,deleteCutter=True,useResultNameSuffix=True):
        if isinstance(target,str): # if string, find feature by name; if id, find feature by id
            targetStr=target
            if len(target)==36: # id
                targetShape=self.getFeature(id=target)
            else:
                targetShape=self.getFeature(title=target,featureClassExcludeList=['Folder','OperationalPeriod'])
        else:
            targetShape=target
            targetStr='NO TITLE'
            if isinstance(targetShape,dict):
                targetStr=targetShape.get('title','NO TITLE')
        if not targetShape:
            logging.warning('Target shape '+targetStr+' not found; operation aborted.')
            return False

        tg=targetShape['geometry']
        targetType=tg['type']
        if targetType=='Polygon':
            tgc=tg['coordinates'][0]
            tgc=self.removeSpurs(tgc)
            targetGeom=Polygon(tgc) # Shapely object
        elif targetType=='LineString':
            tgc=tg['coordinates']
            tgc=self.removeSpurs(tgc)
            targetGeom=LineString(tgc) # Shapely object
        else:
            logging.error('cut: unhandled target '+targetStr+' geometry type: '+targetType)
            return False
        logging.info('targetGeom:'+str(targetGeom))

        if isinstance(cutter,str): # if string, find feature by name; if id, find feature by id
            cutterStr=cutter
            if len(cutter)==36: # id
                cutterShape=self.getFeature(id=cutter)
            else:
                cutterShape=self.getFeature(title=cutter,featureClassExcludeList=['Folder','OperationalPeriod'])
        else:
            cutterShape=cutter
            cutterStr='NO TITLE'
            if isinstance(cutterShape,dict):
                cutterStr=cutterShape.get('title','NO TITLE')
        if not cutterShape:
            logging.warning('Cutter shape '+cutterStr+' not found; operation aborted.')
            return False

        logging.info('cut: target='+targetStr+'  cutter='+cutterStr)

        cg=cutterShape['geometry']
        cutterType=cg['type']
        if cutterType=='Polygon':
            cgc=cg['coordinates'][0]
            cgc=self.removeSpurs(cgc)
            cutterGeom=Polygon(cgc) # Shapely object
        elif cutterType=='LineString':
            cgc=cg['coordinates']
            cgc=self.removeSpurs(cgc)
            cutterGeom=LineString(cgc) # Shapely object
        else:
            logging.error('cut: unhandled cutter geometry type: '+cutterType)
            return False
        logging.info('cutterGeom:'+str(cutterGeom))

        if not cutterGeom.intersects(targetGeom):
            logging.warning(targetShape['properties']['title']+','+cutterShape['properties']['title']+': features do not intersect; no operation performed')
            return False

        #  shapely.ops.split only works if the second geometry completely splits the first;
        #   instead, use the simple boolean object.difference (same as overloaded '-' operator)
        if targetType=='Polygon' and cutterType=='LineString':
            result=split(targetGeom,cutterGeom)
        else:
            result=targetGeom-cutterGeom
        logging.info('cut result:'+str(result))

        # preserve target properties when adding new features
        tp=targetShape['properties']
        tc=tp['class'] # Shape or Assignment
        tfid=tp.get('folderId',None)

        # collect resulting feature ids to return as the return value
        rids=[]

        # use the unsiffixed name as the base (everything before colon-followed-by-integer)
        #  so that a cut of a:2 would produce a:3 rather than a:2:1
        if tc=='Assignment':
            base=tp['letter']
        else:
            base=tp['title']
        # accomodate base names that include colon
        baseParse=base.split(':')
        if len(baseParse)>1 and baseParse[-1].isnumeric():
            base=':'.join(baseParse[:-1])
        usedSuffixList=self.getUsedSuffixList(base)

        if isinstance(result,GeometryCollection): # polygons, linestrings, or both
            try:
                result=MultiPolygon(result)
            except:
                try:
                    result=MultiLineString(result)
                except:
                    logging.error('cut: resulting GeometryCollection could not be converted to MultiPolygon or MultiLineString.  Operation aborted.')
                    return False
        if isinstance(result,Polygon):
            rids.append(self.editFeature(id=targetShape['id'],geometry={'coordinates':[list(result.exterior.coords)]}))
            if rids==[]:
                logging.warning('cut: target shape not found; operation aborted.')
                return False
        elif isinstance(result,MultiPolygon):
            rids.append(self.editFeature(id=targetShape['id'],geometry={'coordinates':[list(result[0].exterior.coords)]}))
            if rids==[]:
                logging.warning('cut: target shape not found; operation aborted.')
                return False
            for r in result[1:]:
                if tc=='Shape':
                    title=tp['title']
                    if useResultNameSuffix:
                        suffix=self.getNextAvailableSuffix(usedSuffixList)
                        title=base+':'+str(suffix)
                        usedSuffixList.append(suffix)
                    rids.append(self.addPolygon(list(r.exterior.coords),
                        title=title,
                        stroke=tp['stroke'],
                        fill=tp['fill'],
                        strokeOpacity=tp['stroke-opacity'],
                        strokeWidth=tp['stroke-width'],
                        fillOpacity=tp['fill-opacity'],
                        description=tp['description'],
                        folderId=tfid,
                        gpstype=tp['gpstype']))
                elif tc=='Assignment':
                    letter=tp['letter']
                    if useResultNameSuffix:
                        suffix=self.getNextAvailableSuffix(usedSuffixList)
                        letter=base+':'+str(suffix)
                        usedSuffixList.append(suffix)
                    rids.append(self.addAreaAssignment(list(r.exterior.coords),
                        number=tp['number'],
                        letter=letter,
                        opId=tp.get('operationalPeriodId',''),
                        folderId=tp.get('folderId',None), # empty string will create an unnamed folder!
                        resourceType=tp.get('resourceType',''),
                        teamSize=tp.get('teamSize',0),
                        priority=tp.get('priority',''),
                        responsivePOD=tp.get('responsivePOD',''),
                        unresponsivePOD=tp.get('unresponsivePOD',''),
                        cluePOD=tp.get('cluePOD',''),
                        description=tp.get('description',''),
                        previousEfforts=tp.get('previousEfforts',''),
                        transportation=tp.get('transportation',''),
                        timeAllocated=tp.get('timeAllocated',0),
                        primaryFrequency=tp.get('primaryFrequency',''),
                        secondaryFrequency=tp.get('secondaryFrequency',''),
                        preparedBy=tp.get('preparedBy',''),
                        gpstype=tp.get('gpstype',''),
                        status=tp.get('status','')))
                else:
                    logging.warning('cut: target feature class was neither Shape nor Assigment; operation aborted.')
                    return False
        elif isinstance(result,LineString):
            rids.append(self.editFeature(id=targetShape['id'],geometry={'coordinates':list(result.coords)}))
            if rids==[]:
                logging.warning('cut: target shape not found; operation aborted.')
                return False
        elif isinstance(result,MultiLineString):
            rids.append(self.editFeature(id=targetShape['id'],geometry={'coordinates':list(result[0].coords)}))
            if rids==[]:
                logging.warning('cut: target shape not found; operation aborted.')
                return False
            for r in result[1:]:
                if tc=='Shape':
                    title=tp['title']
                    if useResultNameSuffix:
                        suffix=self.getNextAvailableSuffix(usedSuffixList)
                        title+=':'+str(suffix)
                        usedSuffixList.append(suffix)
                    rids.append(self.addLine(list(r.coords),
                        title=title,
                        color=tp['stroke'],
                        opacity=tp['stroke-opacity'],
                        width=tp['stroke-width'],
                        pattern=tp['pattern'],
                        description=tp['description'],
                        folderId=tfid,
                        gpstype=tp['gpstype']))
                elif tc=='Assignment':
                    letter=tp['letter']
                    if useResultNameSuffix:
                        suffix=self.getNextAvailableSuffix(usedSuffixList)
                        letter+=':'+str(suffix)
                        usedSuffixList.append(suffix)
                    rids.append(self.addLineAssignment(list(r.coords),
                        number=tp['number'],
                        letter=letter,
                        opId=tp.get('operationalPeriodId',''),
                        folderId=tp.get('folderId',None), # empty string will create an unnamed folder!
                        resourceType=tp.get('resourceType',''),
                        teamSize=tp.get('teamSize',0),
                        priority=tp.get('priority',''),
                        responsivePOD=tp.get('responsivePOD',''),
                        unresponsivePOD=tp.get('unresponsivePOD',''),
                        cluePOD=tp.get('cluePOD',''),
                        description=tp.get('description',''),
                        previousEfforts=tp.get('previousEfforts',''),
                        transportation=tp.get('transportation',''),
                        timeAllocated=tp.get('timeAllocated',0),
                        primaryFrequency=tp.get('primaryFrequency',''),
                        secondaryFrequency=tp.get('secondaryFrequency',''),
                        preparedBy=tp.get('preparedBy',''),
                        gpstype=tp.get('gpstype',''),
                        status=tp.get('status','')))
                else:
                    logging.error('cut: target feature class was neither Shape nor Assigment; operation aborted.')
                    return False
        if deleteCutter:
            self.delFeature(id=cutterShape['id'],fClass=cutterShape['properties']['class'])

        return rids # resulting feature IDs

    # expand - expand target polygon to include the area of p2 polygon

    def expand(self,target,p2,deleteP2=True):
        if isinstance(target,str): # if string, find feature by name; if id, find feature by id
            targetStr=target
            if len(target)==36: # id
                targetShape=self.getFeature(id=target)
            else:
                targetShape=self.getFeature(title=target,featureClassExcludeList=['Folder','OperationalPeriod'])
        else:
            targetShape=target
            targetStr='NO TITLE'
            if isinstance(targetShape,dict):
                targetStr=targetShape.get('title','NO TITLE')
        if not targetShape:
            logging.warning('Target shape '+targetStr+' not found; operation aborted.')
            return False
        
        tg=targetShape['geometry']
        tgc=tg['coordinates'][0]
        tgc=self.removeSpurs(tgc)
        targetType=tg['type']
        if targetType=='Polygon':
            targetGeom=Polygon(tgc) # Shapely object
        else:
            logging.warning('expand: target feature '+targetStr+' is not a polygon: '+targetType)
            return False
        logging.info('targetGeom:'+str(targetGeom))

        if isinstance(p2,str): # if string, find feature by name; if id, find feature by id
            p2Str=p2
            if len(p2)==36: # id
                p2Shape=self.getFeature(id=p2)
            else:
                p2Shape=self.getFeature(title=p2,featureClassExcludeList=['Folder','OperationalPeriod'])
        else:
            p2Shape=p2
            p2Str='NO TITLE'
            if isinstance(p2Shape,dict):
                p2Str=p2Shape.get('title','NO TITLE')
        if not p2Shape:
            logging.warning('expand: second polygon '+p2Str+' not found; operation aborted.')
            return False

        logging.info('expand: target='+targetStr+'  p2='+p2Str)
        
        cg=p2Shape['geometry']
        cgc=cg['coordinates'][0]
        cgc=self.removeSpurs(cgc)
        p2Type=cg['type']
        if p2Type=='Polygon':
            p2Geom=Polygon(cgc) # Shapely object
        else:
            logging.warning('expand: p2 feature '+p2Str+' is not a polygon: '+p2Type)
            return False
        logging.info('p2Geom:'+str(p2Geom))

        if not p2Geom.intersects(targetGeom):
            logging.warning(targetShape['properties']['title']+','+p2Shape['properties']['title']+': features do not intersect; no operation performed')
            return False

        result=targetGeom|p2Geom
        logging.info('expand result:'+str(result))

        if not self.editFeature(id=targetShape['id'],geometry={'coordinates':[list(result.exterior.coords)]}):
            logging.warning('expand: target shape not found; operation aborted.')
            return False

        if deleteP2:
            self.delFeature(id=p2Shape['id'],fClass=p2Shape['properties']['class'])

        return True # success

    def buffer2(self,boundaryGeom,beyond):
        a=boundaryGeom.buffer(0) # split bowties into separate polygons
        merged=unary_union(a)
        return merged.buffer(beyond)

    # intersection2(targetGeom,boundaryGeom)
    # we want a function that can take the place of shapely.ops.intersection
    #  when the target is a LineString and the boundary is a Polygon,
    #  which will preserve complex (is_simple=False) lines i.e. with internal crossovers

    # walk thru the points (except fot the last point) in the target shape(line):
    #    A = current point, B = next point
    #  A and B both inside boundary?  --> append A to output coord list
    #  A inside, B outside --> append A; append point at instersection of this segment with boundary; don't append B
    #  A outside, B inside --> append B; append point at intersection of this segment with boundary; don't append A
    #  A outside, B outside --> don't append either point; instead, append the intersection as a new line segment

    def intersection2(self,targetGeom,boundaryGeom):
        outLines=[]
        targetCoords=targetGeom.coords
        nextInsidePointStartsNewLine=True
        for i in range(len(targetCoords)-1):
            ac=targetCoords[i]
            bc=targetCoords[i+1]
            ap=Point(ac)
            bp=Point(bc)
            a_in=ap.within(boundaryGeom)
            b_in=bp.within(boundaryGeom)
            if a_in and b_in:
                if nextInsidePointStartsNewLine:
                    outLines.append([])
                    nextInsidePointStartsNewLine=False
                outLines[-1].append(ac)
            elif a_in and not b_in:
                abl=LineString([ap,bp])
                mp=abl.intersection(boundaryGeom.exterior)
                if nextInsidePointStartsNewLine:
                    outLines.append([])
                    nextInsidePointStartsNewLine=False
                outLines[-1].append(ac)
                outLines[-1].append(list(mp.coords)[0])
                nextInsidePointStartsNewLine=True
            elif b_in and not a_in:
                abl=LineString([ap,bp])
                mp=abl.intersection(boundaryGeom.exterior)
                nextInsidePointStartsNewLine=True
                if nextInsidePointStartsNewLine:
                    outLines.append([])
                    nextInsidePointStartsNewLine=False
                # the midpoint will be the first point of a new line
                outLines[-1].append(list(mp.coords)[0])
            else: # neither endpoint is inside the boundary: save the portion within the boundary, if any
                abl=LineString([ap,bp])
                mp=abl.intersection(boundaryGeom.exterior)
                # the result will be a single disjoint line segment inside the boundary,
                #  with both vertices touching the boundary;
                # the result is a multipoint, which has no .coords attribute
                #  see https://stackoverflow.com/a/51060918
                # (or LineString Empty if none of the segment is inside the boundary)
                if mp.geom_type=='MultiPoint' and not mp.is_empty:
                    mpcoords=[(p.x,p.y) for p in mp]
                    nextInsidePointStartsNewLine=True
                    outLines.append(mpcoords)

        # don't forget to check the last vertex!
        fc=targetCoords[-1]
        fp=Point(fc)
        f_in=fp.within(boundaryGeom)
        if f_in:
            outLines[-1].append(fc)

        # return the Shapely object(s)
        if len(outLines)>1:
            rval=MultiLineString(outLines)
        elif len(outLines)==1:
            rval=LineString(outLines[0])
        else:
            rval=None
        return rval


    # getBounds - return the bounding box (minx,miny,maxx,maxy), oversized by 'pad',
    #               that bounds the listed objects

    def getBounds(self,objectList,padDeg=0.0001,padPct=None):
        rval=[9e12,9e12,-9e12,-9e12]
        for obj in objectList:
            if isinstance(obj,str): # if string, find feature by name; if id, find feature by id
                objStr=obj
                if len(obj)==36: # id
                    objShape=self.getFeature(id=obj)
                else:
                    objShape=self.getFeature(title=obj,featureClassExcludeList=['Folder','OperationalPeriod'])
            else:
                objShape=obj
                objStr='NO TITLE'
                if isinstance(objShape,dict):
                    objStr=objShape.get('title','NO TITLE')
            if not objShape:
                logging.warning('Object shape '+objStr+' not found; operation aborted.')
                return False
            og=objShape['geometry']
            objType=og['type']
            # logging.info('geometry:'+json.dumps(og,indent=3))
            if objType=='Polygon':
                ogc=og['coordinates'][0]
                ogc=self.removeSpurs(ogc)
                objGeom=Polygon(self.twoify(ogc)) # Shapely object
            elif objType=='LineString':
                ogc=og['coordinates']
                ogc=self.removeSpurs(ogc)
                objGeom=LineString(self.twoify(ogc)) # Shapely object
            elif objType=='Point':
                ogc=og['coordinates'][0:2]
                objGeom=Point(self.twoify(ogc)) # Shapely object
            else:
                logging.warning('crop: feature '+objStr+' is not a polygon or line or point: '+objType)
                return False
            bbox=objGeom.bounds
            rval=[min(bbox[0],rval[0]),min(bbox[1],rval[1]),max(bbox[2],rval[2]),max(bbox[3],rval[3])]
        if not padPct:
            pad=padDeg
        else:
            if padPct<1: # if specified as a ratio
                padPct=padPct*100
            pad=max(abs(rval[2]-rval[0]),abs(rval[3]-rval[1]))*padPct*0.01
        rval=[rval[0]-pad,rval[1]-pad,rval[2]+pad,rval[3]+pad]
        return rval

    # twoify - turn four-element-vertex-data into two-element-vertex-data so that
    #  the shapely functions can operate on it
    def twoify(self,points):
        if not isinstance(points,list):
            return points
        if isinstance(points[0],list): # the arg is a list of points
            return [p[0:2] for p in points]
        else: # the arg is just one point
            return points[0:2]

    # fourify - try to use four-element-vertex data from original data; called by
    #  geometry operations during resulting shape creation / editing
    def fourify(self,points,origPoints):
        # no use trying to fourify if the orig points list is not all four-element points
        if len(origPoints[0])!=4 or len(origPoints[-1])!=4:
            return points
        # make sure both are lists of lists, since points may initially be a list of tuples
        if isinstance(points[0],tuple):
            points=list(map(list,points))
        # logging.info('fourify called:\npoints='+str(points)+'\norigPoints='+str(origPoints))
        if len(points[0])==4 and len(points[-1])==4: # it's already a four-element list
            return points
        # logging.info('fourify: '+str(len(points))+' points: '+str(points[0:3])+' ... '+str(points[-3:]))
        # logging.info('orig: '+str(len(origPoints))+' points: '+str(origPoints[0:3])+' ... '+str(origPoints[-3:]))
        for i in range(len(points)):
            found=False
            for j in range(len(origPoints)):
                if origPoints[j][0:2]==points[i][0:2]:
                    points[i]=origPoints[j]
                    found=True
                    break
            # generated endpoints (possibly first and/or last point after crop) won't have timestamps;
            #  for the new first point, use the timestamp from the original first point;
            #  for the new last point, use the timestamp from the original last point
            if not found:
                if i==0:
                    points[i]=points[i][0:2]+[0,origPoints[0][3]]
                elif i==len(points)-1:
                    points[i]=points[i][0:2]+[0,origPoints[-1][3]]
                else:
                    logging.error('Fourify - could not find a matching point, not at beginning or end of new line:')
                    logging.info('not found: '+str(len(points))+' points:  points['+str(i)+']='+str(points[i]))
        return points

    # crop - remove portions of a line or polygon that are outside a boundary polygon;
    #          grow the specified boundary polygon by the specified distance before cropping

    def crop(self,target,boundary,beyond=0.0001,deleteBoundary=False,useResultNameSuffix=False,drawSizedBoundary=False,noDraw=False):
        if isinstance(target,str): # if string, find feature by name; if id, find feature by id
            targetStr=target
            if len(target)==36: # id
                targetShape=self.getFeature(id=target)
            else:
                targetShape=self.getFeature(title=target,featureClassExcludeList=['Folder','OperationalPeriod'])
        else:
            targetShape=target
            targetStr='NO TITLE'
            if isinstance(targetShape,dict):
                targetStr=targetShape.get('title','NO TITLE')
        if not targetShape:
            logging.warning('Target shape '+targetStr+' not found; operation aborted.')
            return False

        tg=targetShape['geometry']
        tgc_orig=None
        targetType=tg['type']
        if targetType=='Polygon':
            tgc=tg['coordinates'][0]
            tgc=self.removeSpurs(tgc)
            targetGeom=Polygon(tgc) # Shapely object
        elif targetType=='LineString':
            tgc_orig=tg['coordinates']
            tgc=self.twoify(tgc_orig)
            # logging.info('tgc before ('+str(len(tgc))+' points):'+str(tgc))
            tgc=self.removeSpurs(tgc)
            # logging.info('tgc after ('+str(len(tgc))+' points):'+str(tgc))
            targetGeom=LineString(tgc)
        else:
            logging.warning('crop: target feature '+targetStr+' is not a polygon or line: '+targetType)
            return False
            
        if isinstance(boundary,str): # if string, find feature by name; if id, find feature by id
            boundaryStr=boundary
            if len(boundary)==36: # id
                boundaryShape=self.getFeature(id=boundary)
            else:
                boundaryShape=self.getFeature(title=boundary,featureClassExcludeList=['Folder','OperationalPeriod'])
        else:
            boundaryShape=boundary
            boundaryStr='NO TITLE'
            if isinstance(boundaryShape,dict):
                boundaryStr=boundaryShape.get('title','NO TITLE')
        if not boundaryShape:
            logging.warning('crop: boundary shape '+boundaryStr+' not found; operation aborted.')
            return False

        logging.info('crop: target='+targetStr+'  boundary='+boundaryStr)

        cg=boundaryShape['geometry']
        boundaryType=cg['type']
        if boundaryType=='Polygon':
            cgc=cg['coordinates'][0]
            boundaryGeom=self.buffer2(Polygon(cgc),beyond)
        elif boundaryType=='LineString':
            cgc=self.twoify(cg['coordinates'])
            boundaryGeom=LineString(cgc).buffer(beyond)
        else:
            logging.warning('crop: boundary feature '+boundaryStr+' is not a polygon or line: '+boundaryType)
            return False
        # logging.info('crop: boundaryGeom:'+str(boundaryGeom))
        if drawSizedBoundary:
            tp=targetShape['properties']
            self.addPolygon(list(boundaryGeom.exterior.coords),
                title='sizedCropBoundary',
                stroke=tp['stroke'],
                fill=tp['fill'],
                strokeOpacity=tp['stroke-opacity'],
                strokeWidth=tp['stroke-width'],
                fillOpacity=tp['fill-opacity'],
                description=tp['description'],
                gpstype=tp['gpstype'])

        if not boundaryGeom.intersects(targetGeom):
            logging.warning(targetShape['properties']['title']+','+boundaryShape['properties']['title']+': features do not intersect; no operation performed')
            return False

        # if target is a line, and boundary is a polygon, use intersection2; see notes above
        if isinstance(targetGeom,LineString) and isinstance(boundaryGeom,Polygon):
            result=self.intersection2(targetGeom,boundaryGeom)
        else:
            result=targetGeom&boundaryGeom # could be MultiPolygon or MultiLinestring or GeometryCollection
        # logging.info('crop targetGeom:'+str(targetGeom))
        # logging.info('crop boundaryGeom:'+str(boundaryGeom))
        # logging.info('crop result:'+str(result))

        # if specified, only return the coordinate list(s) instead of editing / adding map features
        if noDraw:
            # return a list of line segments with points as lists rather than tuples; a.k.a. a list of lists of lists
            if isinstance(result,LineString):
                return [list(map(list,result.coords))]
            elif isinstance(result,MultiLineString):
                return [list(map(list,ls.coords)) for ls in result]
            else:
                logging.error('Unexpected noDraw crop result type '+str(result.__class__.__name__))
                return False

        # preserve target properties when adding new features
        tp=targetShape['properties']
        tc=tp['class'] # Shape or Assignment
        tfid=tp.get('folderId',None)

        # use the unsiffixed name as the base (everything before colon-followed-by-integer)
        #  so that a cut of a:2 would produce a:3 rather than a:2:1
        if tc=='Assignment':
            base=tp['letter']
        else:
            base=tp['title']
        # accomodate base names that include colon
        baseParse=base.split(':')
        if len(baseParse)>1 and baseParse[-1].isnumeric():
            base=':'.join(baseParse[:-1])
        usedSuffixList=self.getUsedSuffixList(base)

        # collect resulting feature ids to return as the return value
        rids=[]

        if isinstance(result,GeometryCollection): # apparently this will only be the case for polygons
            try:
                result=MultiPolygon(result)
            except:
                try:
                    result=MultiLineString(result)
                except:
                    logging.error('crop: resulting GeometryCollection could not be converted to MultiPolygon or MultiLineString.  Operation aborted.')
                    return False
        if isinstance(result,Polygon):
            rids.append(self.editFeature(id=targetShape['id'],geometry={'coordinates':[list(result.exterior.coords)]}))
            if rids==[]:
                logging.warning('crop: target shape not found; operation aborted.')
                return False
        elif isinstance(result,MultiPolygon):
            rids.append(self.editFeature(id=targetShape['id'],geometry={'coordinates':[list(result[0].exterior.coords)]}))
            if rids==[]:
                logging.warning('crop: target shape not found; operation aborted.')
                return False
            for r in result[1:]:
                if tc=='Shape':
                    title=tp['title']
                    if useResultNameSuffix:
                        suffix=self.getNextAvailableSuffix(usedSuffixList)
                        title=base+':'+str(suffix)
                        usedSuffixList.append(suffix)
                    rids.append(self.addPolygon(list(r.exterior.coords),
                        title=title,
                        stroke=tp['stroke'],
                        fill=tp['fill'],
                        strokeOpacity=tp['stroke-opacity'],
                        strokeWidth=tp['stroke-width'],
                        fillOpacity=tp['fill-opacity'],
                        description=tp['description'],
                        folderId=tfid,
                        gpstype=tp['gpstype']))
                elif tc=='Assignment':
                    letter=tp['letter']
                    if useResultNameSuffix:
                        suffix=self.getNextAvailableSuffix(usedSuffixList)
                        letter=base+':'+str(suffix)
                        usedSuffixList.append(suffix)
                    rids.append(self.addAreaAssignment(list(r.exterior.coords),
                        number=tp['number'],
                        letter=letter,
                        opId=tp.get('operationalPeriodId',''),
                        folderId=tp.get('folderId',None), # empty string will create an unnamed folder!
                        resourceType=tp.get('resourceType',''),
                        teamSize=tp.get('teamSize',0),
                        priority=tp.get('priority',''),
                        responsivePOD=tp.get('responsivePOD',''),
                        unresponsivePOD=tp.get('unresponsivePOD',''),
                        cluePOD=tp.get('cluePOD',''),
                        description=tp.get('description',''),
                        previousEfforts=tp.get('previousEfforts',''),
                        transportation=tp.get('transportation',''),
                        timeAllocated=tp.get('timeAllocated',0),
                        primaryFrequency=tp.get('primaryFrequency',''),
                        secondaryFrequency=tp.get('secondaryFrequency',''),
                        preparedBy=tp.get('preparedBy',''),
                        gpstype=tp.get('gpstype',''),
                        status=tp.get('status','')))
                else:
                    logging.warning('crop: target feature class was neither Shape nor Assigment')
        elif isinstance(result,LineString):
            # logging.info('adding shape to result list')
            four=self.fourify(list(result.coords),tgc_orig)
            # logging.info('four:'+str(four))
            rids.append(self.editFeature(id=targetShape['id'],geometry={'coordinates':four}))
            if rids==[]:
                logging.warning('crop: target shape not found; operation aborted.')
                return False
        elif isinstance(result,MultiLineString):
            rids.append(self.editFeature(id=targetShape['id'],geometry={'coordinates':list(result[0].coords)}))
            if rids==[]:
                logging.warning('crop: target shape not found; operation aborted.')
                return False
            for r in result[1:]:
                if tc=='Shape':
                    title=tp['title']
                    if useResultNameSuffix:
                        title=title+':'+str(suffix)
                    rids.append(self.addLine(list(r.coords),
                        title=title,
                        color=tp['stroke'],
                        opacity=tp['stroke-opacity'],
                        width=tp['stroke-width'],
                        pattern=tp['pattern'],
                        description=tp['description'],
                        folderId=tfid,
                        gpstype=tp['gpstype']))
                elif tc=='Assignment':
                    letter=tp['letter']
                    if useResultNameSuffix:
                        letter=letter+':'+str(suffix)
                    rids.append(self.addLineAssignment(list(r.coords),
                        number=tp['number'],
                        letter=letter,
                        opId=tp.get('operationalPeriodId',''),
                        folderId=tp.get('folderId',None), # empty string will create an unnamed folder!
                        resourceType=tp.get('resourceType',''),
                        teamSize=tp.get('teamSize',0),
                        priority=tp.get('priority',''),
                        responsivePOD=tp.get('responsivePOD',''),
                        unresponsivePOD=tp.get('unresponsivePOD',''),
                        cluePOD=tp.get('cluePOD',''),
                        description=tp.get('description',''),
                        previousEfforts=tp.get('previousEfforts',''),
                        transportation=tp.get('transportation',''),
                        timeAllocated=tp.get('timeAllocated',0),
                        primaryFrequency=tp.get('primaryFrequency',''),
                        secondaryFrequency=tp.get('secondaryFrequency',''),
                        preparedBy=tp.get('preparedBy',''),
                        gpstype=tp.get('gpstype',''),
                        status=tp.get('status','')))
                else:
                    logging.warning('crop: target feature class was neither Shape nor Assigment')
                    return False

        if deleteBoundary:
            self.delFeature(id=boundaryShape['id'],fClass=boundaryShape['properties']['class'])

        return rids # resulting feature IDs

        
def insertBeforeExt(fn,ins):
    if '.' in fn:
        lastSlashIndex=-1
        lastBackSlashIndex=-1
        if '/' in fn:
            lastSlashIndex=fn.rindex('/')
        if '\\' in fn:
            lastBackSlashIndex=fn.rindex('\\')
        lastSepIndex=max(0,lastBackSlashIndex,lastSlashIndex)
        try:
            lastDotIndex=fn.rindex('.',lastSepIndex)
            return fn[:lastDotIndex]+ins+fn[lastDotIndex:]
        except:
            pass
    return fn+ins


# print by default; let the caller change this if needed
# (note, caller would need to clear all handlers first,
#   per stackoverflow.com/questions/12158048)
logging.basicConfig(
    level=logging.INFO,
    datefmt='%H:%M:%S',
    format='%(asctime)s [%(module)s:%(lineno)d:%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# handle uncaught exceptions at the top level or in a thread;
#  deal with the fact that sys.excepthook and threading.excepthook use different arguments
#   sys.excepthook wants a 3-tuple; threading.excepthook wants an instance of
#   _thread._ExceptHookArgs, which provides a 4-namedtuple
def handle_exception(*args):
    if len(args)==1:
        a=args[0]
        [exc_type,exc_value,exc_traceback,thread]=[a.exc_type,a.exc_value,a.exc_traceback,a.thread]
    else:
        [exc_type,exc_value,exc_traceback]=args
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    prefix='Uncaught exception:' # not in a thread
    try:
        if thread and thread.__class__.__name__=='Thread':
            prefix='Uncaught exception in '+thread.name+':' # in a thread
    except UnboundLocalError:
        pass
    logging.critical(prefix, exc_info=(exc_type, exc_value, exc_traceback))
sys.excepthook = handle_exception
threading.excepthook = handle_exception

# pare down json for logging messages to reduce log size and clutter
def jsonForLog(orig):
    rval=copy.deepcopy(orig)
    try:
        ok=orig.keys()
        wrapped=False
        if len(ok)==1 and 'json' in ok:
            wrapped=True
            rval=json.loads(rval['json'])
        gc=rval['geometry']['coordinates']
        if isinstance(gc[0][0],list): # list of segments
            segCount=len(gc)
            suffix=''
            if segCount>1:
                suffix='s'
            countStr=str(segCount)+' segment'+suffix+' ('
            for seg in gc:
                countStr+=str(len(seg))+','
            countStr=countStr.rstrip(',')
            countStr+=' points)'
            rval['geometry']['coordinates']=countStr
        else:
            suffix=''
            if len(gc)>1:
                suffix='s'
            rval['geometry']['coordinates']=str(len(gc))+' point'+suffix
        if wrapped:
            rval={'json':json.dumps(rval)}
    except:
        pass
    return str(rval)
