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
from threading import Thread

from shapely.geometry import LineString,Point,Polygon,MultiLineString,MultiPolygon,GeometryCollection
from shapely.ops import split
    
class SartopoSession():
    def __init__(self,
            domainAndPort='localhost:8080',
            mapID=None,
            configpath=None,
            account=None,
            id=None,
            key=None,
            sync=True,
            syncInterval=5,
            syncTimeout=10,
            syncDumpFile=None,
            propUpdateCallback=None,
            geometryUpdateCallback=None,
            newObjectCallback=None,
            deletedObjectCallback=None):
        self.s=requests.session()
        self.apiVersion=-1
        if not mapID or not isinstance(mapID,str) or len(mapID)<3:
            logging.error('ERROR: you must specify a three-or-more-character sartopo map ID string (end of the URL) when opening a SartopoSession object.')
            return None
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
        self.sync=sync
        self.syncTimeout=syncTimeout
        self.syncPause=False
        self.propUpdateCallback=propUpdateCallback
        self.geometryUpdateCallback=geometryUpdateCallback
        self.newObjectCallback=newObjectCallback
        self.deletedObjectCallback=deletedObjectCallback
        self.syncInterval=syncInterval
        self.lastSuccessfulSyncTimestamp=0 # the server's integer milliseconds 'sincce' request completion time
        self.lastSuccessfulSyncTSLocal=0 # this object's integer milliseconds sync completion time
        self.syncDumpFile=syncDumpFile
        self.setupSession()
        
    def setupSession(self):
        if 'sartopo.com' in self.domainAndPort.lower():
            id=None
            key=None
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
                    if id is None or key is None:
                        logging.error("account entry '"+self.account+"' in config file '"+self.configpath+"' is not complete:\n  it must specify id and key.")
                        return False
                else:
                    logging.error("specified config file '"+self.configpath+"' does not exist.")
                    return False

            # now allow values specified in constructor to override config file values
            if self.id is not None:
                id=self.id
            if self.key is not None:
                key=self.key
            # finally, save them back as parameters of this object
            self.id=id
            self.key=key

            if self.id is None:
                logging.error("sartopo session is invalid: 'id' must be specified for online maps")
                return False
            if self.key is None:
                logging.error("sartopo session is invalid: 'key' must be specified for online maps")
                return False

        # by default, do not assume any sartopo session is running;
        # send a GET request to http://localhost:8080/api/v1/map/
        #  response code 200 = new API
        #  otherwise:
        #    send a GET request to http://localhost:8080/rest/
        #     response code 200 = old API
        
        self.apiUrlMid="/invalid/"
        url="http://"+self.domainAndPort+"/api/v1/map/"
        logging.info("searching for API v1: sending get to "+url)
        try:
            r=self.s.get(url,timeout=10)
        except:
            logging.error("no response from first get request; aborting; should get a response of 400 at this point for api v0")
        else:
            logging.info("response code = "+str(r.status_code))
            if r.status_code==200:
                # now validate the mapID, since the initial test doesn't care about mapID
                mapUrl="http://"+self.domainAndPort+"/m/"+self.mapID
                try:
                    r=self.s.get(mapUrl,timeout=10)
                except:
                    logging.error("API version 1 detected, but the get request timed out so the mapID is not valid: "+mapUrl)
                else:
                    if r.status_code==200:
                        # now we know the API is valid and the mapID is valid
                        self.apiVersion=1
                        self.apiUrlMid="/api/v1/map/[MAPID]/"
                    else:
                        logging.error("API version 1 detected, but the map-specific URL returned a code of "+str(r.status_code)+" so this session is not valid.")
            else:
                url="http://"+self.domainAndPort+"/rest/marker/"
                logging.info("searching for API v0: sending get to "+url)
                try:
                    r=self.s.get(url,timeout=10)
                except:
                    logging.info("no response from second get request")
                else:
                    logging.info("response code = "+str(r.status_code))
                    if r.status_code==200:
                        self.apiVersion=0
                        self.apiUrlMid="/rest/"
                        # for v0, send a get to the map URL to authenticate the session
                        url="http://"+self.domainAndPort+"/m/"+self.mapID
                        logging.info("sending API v0 authentication request to url "+url)
                        try:
                            r=self.s.get(url,timeout=10)
                        except:
                            logging.info("no response during authentication for API v0")
                        else:
                            logging.info("response code = "+str(r.status_code))
                            if r.status_code==200:
                                logging.info("API v0 session is now authenticated")
        logging.info("API version:"+str(self.apiVersion))
        # sync needs to be done here instead of in the caller, so that
        #  edit functions can have access to the full json
        if self.sync:
            self.start()
        else: # do an initial since(0) even if sync is false
            self.doSync()
            
    def doSync(self):
        self.syncing=True

        # Keys under 'result':
        # 1 - 'ids' will only exist on first sync or after a deletion, so, if 'ids' exists
        #     then just use it to replace the entire cached 'ids', and also do cleanup later
        #     by deleting any state->features from the cache whose 'id' value is not in 'ids'
        # 2 - state->features is an array of changed existing objects, and the array will
        #     have complete data for 'geometry', 'id', 'type', and 'properties', so, for each
        #     item in state->features, just replace the entire existing cached feature of
        #     the same id

        logging.info('Sending sartopo "since" request...')
        rj=self.sendRequest('get','since/'+str(max(0,self.lastSuccessfulSyncTimestamp-500)),None,returnJson='ALL',timeout=self.syncTimeout)
        if rj and rj['status']=='ok':
            if self.syncDumpFile:
                with open(self.insertBeforeExt(self.syncDumpFile,'.since'+str(self.lastSuccessfulSyncTimestamp)),"w") as f:
                    f.write(json.dumps(rj,indent=3))
            # response timestamp is an integer number of milliseconds; equivalent to
            # int(time.time()*1000))
            self.lastSuccessfulSyncTimestamp=rj['result']['timestamp']
            logging.info('Successful sartopo sync: timestamp='+str(self.lastSuccessfulSyncTimestamp))
            rjr=rj['result']
            rjrsf=rjr['state']['features']
            
            # 1 - if 'ids' exists, use it verbatim; cleanup happens later
            if 'ids' in rjr.keys():
                self.mapData['ids']=rjr['ids']
                logging.info('  Updating "ids"')
            
            # 2 - update existing features
            if len(rjrsf)>0:
                logging.info(json.dumps(rj,indent=3))
                for f in rjrsf:
                    rjrfid=f['id']
                    prop=f['properties']
                    title=str(prop.get('title',None))
                    featureClass=str(prop['class'])
                    # 2a - if id already exists, replace it
                    processed=False
                    for i in range(len(self.mapData['state']['features'])):
                        if self.mapData['state']['features'][i]['id']==rjrfid:
                            # don't simply overwrite the entire feature entry:
                            #  - if only geometry was changed, indicated by properties['nop']=true,
                            #    then leave properties alone and just overwrite geometry;
                            #  - if only properties were changed, geometry will not be in the response,
                            #    so leave geometry alone
                            #  SO:
                            #  - if f->prop->title exists, replace the entire prop dict
                            #  - if f->geometry exists, replace the entire geometry dict
                            if 'title' in prop.keys():
                                logging.info('  Updating properties for '+featureClass+':'+title)
                                self.mapData['state']['features'][i]['properties']=prop
                                if self.propUpdateCallback:
                                    self.propUpdateCallback(rjrfid,prop)
                            if title=='None':
                                title=self.mapData['state']['features'][i]['properties']['title']
                            if 'geometry' in f.keys():
                                logging.info('  Updating geometry for '+featureClass+':'+title)
                                self.mapData['state']['features'][i]['geometry']=f['geometry']
                                if self.geometryUpdateCallback:
                                    self.geometryUpdateCallback(rjrfid,f['geometry'])
                            processed=True
                            break
                    # 2b - otherwise, create it - and add to ids so it doesn't get cleaned
                    if not processed:
                        logging.info('  Adding '+featureClass+':'+title)
                        self.mapData['state']['features'].append(f)
                        if self.newObjectCallback:
                            self.newObjectCallback(f)
                        if f['id'] not in self.mapData['ids'][prop['class']]:
                            self.mapData['ids'][prop['class']].append(f['id'])

            # 3 - cleanup - ids will be part of the response whenever object(s) were added or deleted
            self.mapIDs=sum(self.mapData['ids'].values(),[])
            mapSFIDs=[f['id'] for f in self.mapData['state']['features']]

            logging.debug('\nself.mapIDs:'+str(self.mapIDs))
            logging.debug('\n   mapSFIDs:'+str(mapSFIDs))
            for i in range(len(mapSFIDs)):
                if mapSFIDs[i] not in self.mapIDs:
                    prop=self.mapData['state']['features'][i]['properties']
                    logging.info('  Deleting '+str(prop['class'])+':'+str(prop['title']))
                    logging.info('     [ id='+mapSFIDs[i]+' ]')
                    if self.deletedObjectCallback:
                        self.deletedObjectCallback(mapSFIDs[i],self.mapData['state']['features'][i])
                    del self.mapData['state']['features'][i]
    
            if self.syncDumpFile:
                with open(self.insertBeforeExt(self.syncDumpFile,'.cache'+str(self.lastSuccessfulSyncTimestamp)),"w") as f:
                    f.write('sync cleanup:')
                    f.write('  mapIDs='+str(self.mapIDs)+'\n\n')
                    f.write('  mapSFIDs='+str(mapSFIDs)+'\n\n')
                    f.write(json.dumps(self.mapData,indent=3))

            self.syncing=False
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
        self.syncing=False

    # refresh - update the cache (self.mapData) by calling doSync once;
    #   only relevant if sync is off; if the latest refresh is within the sync interval value (even when sync is off),
    #   then don't do a refresh unless forceImmediate is True
    #  since doSync() would be called from this thread, it is always blocking
    def refresh(self,blocking=False,forceImmediate=False):
        d=int(time.time()*1000)-self.lastSuccessfulSyncTSLocal # integer ms since last completed sync
        logging.info('  refresh requested: '+str(d)+'ms since last completed sync')
        if d>(self.syncInterval*1000):
            logging.info('    this is longer than the syncInterval: syncing now')
            self.doSync()
        else:
            logging.info('    this is shorter than the syncInterval')
            if forceImmediate:
                logging.info('    but forceImmedate is specified: syncing now')
                self.doSync()
            else:
                logging.info('    and forceImmediate is not specified: not syncing now')

    def stop(self):
        logging.info('Sartopo syncing terminated.')
        self.sync=False

    def __del__(self):
        logging.info('SartopoSession instance deleted.')
        if self.sync:
            self.stop()

    def start(self):
        self.sync=True
        logging.info('Sartopo syncing initiated.')
        Thread(target=self._syncLoop).start()

    # _syncLoop - should only be called from self.start(), which calls _syncLoop in a new thread.
    #  This is just a loop that calls doSync.  To prevent an endless loop, doSync must be
    #  able to terminate the thread if the main thread has ended; also note that any other
    #  code can end sync by setting self.sync to False.  This allows doSync to be
    #  iterative rather than recursive (which would eventually hit recursion limit issues),
    #  and it allows the blocking sleep call to happen here instead of inside doSync.
    def _syncLoop(self):
        while self.sync:
            while self.syncPause:
                logging.info('  sync is paused - sleeping for one second')
                time.sleep(1)
            self.doSync()
            if self.sync: # don't bother with the sleep if sync is no longer True
                time.sleep(self.syncInterval)

    def sendRequest(self,type,apiUrlEnd,j,id="",returnJson=None,timeout=None):
        timeout=timeout or self.syncTimeout
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
        url="http://"+self.domainAndPort+mid+apiUrlEnd
        logging.info("sending "+str(type)+" to "+url)
        self.syncPause=True
        if type=="post":
            params={}
            params["json"]=json.dumps(j)
            if "sartopo.com" in self.domainAndPort.lower():
                expires=int(time.time()*1000)+120000 # 2 minutes from current time, in milliseconds
                data="POST "+mid+apiUrlEnd+"\n"+str(expires)+"\n"+json.dumps(j)
                # logging.info("pre-hashed data:"+data)                
                token=hmac.new(base64.b64decode(self.key),data.encode(),'sha256').digest()
                token=base64.b64encode(token).decode()
                # logging.info("hashed data:"+str(token))
                params["id"]=self.id
                params["expires"]=expires
                params["signature"]=token
            logging.info("SENDING POST to '"+url+"':")
            logging.info(json.dumps(params,indent=3))
            r=self.s.post(url,data=params,timeout=timeout)
        elif type=="get": # no need for json in GET; sending null JSON causes downstream error
#             logging.info("SENDING GET to '"+url+"':")
            r=self.s.get(url,timeout=timeout)
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
            # logging.info("SENDING DELETE to '"+url+"':")
            # logging.info(json.dumps(params,indent=3))
            # logging.info("Key:"+str(self.key))
            r=self.s.delete(url,params=params,timeout=timeout)   ## use params for query vs data for body data
            # logging.info("URL:"+str(url))
            # logging.info("Ris:"+str(r))
        else:
            logging.error("sendRequest: Unrecognized request type:"+str(type))
            self.syncPause=False
            return False
#         logging.info("response code = "+str(r.status_code))
#         logging.info("response:")
#         try:
#             logging.info(json.dumps(r.json(),indent=3))
#         except:
#             logging.info(r.text)
        if returnJson:
            logging.info('response:'+str(r))
            try:
                rj=r.json()
            except:
                logging.error("sendRequest: response had no decodable json")
                self.syncPause=False
                return False
            else:
                logging.info('rj:'+str(rj))
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
            return self.sendRequest("post","folder",j,returnJson="ID")
    
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
            return self.sendRequest('post','marker',j,id=existingId,returnJson='ID')

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
            return self.sendRequest("post","Shape",j,id=existingId,returnJson="ID",timeout=timeout)

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
            timeAllocated='',
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
            return self.sendRequest('post','Shape',j,id=existingId,returnJson='ID')

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
            timeAllocated='',
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

    def delMarker(self,existingId=""):
        self.delObject("marker",existingId=existingId)

    def delObject(self,objType,existingId=""):
        return self.sendRequest("delete",objType,None,id=str(existingId),returnJson="ALL")

    # getFeatures - attempts to get data from the local cache (self.madData); refreshes and tries again if necessary
    #   determining if a refresh is necessary:
    #   - if the requested feature/s is/are not in the cache, and it has been longer than syncInterval since the last refresh,
    #      then do a new refresh; otherwise return [False]
    #   - if the requested feature/s IS/ARE in the cache, do we need to do a refresh anyway?  Only if forceRefresh is True.
    def getFeatures(self,
            featureClass=None,
            title=None,
            id=None,
            featureClassExcludeList=[],
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
            for feature in features:
                if feature['id']==id:
                    rval.append(feature)
                    break
                prop=feature['properties']
                c=prop['class']
                if featureClass is None and c not in featureClassExcludeList:
                    if prop['title']==title:
                        titleMatchCount+=1
                        rval.append(feature)
                else:
                    if c==featureClass:
                        if title is None:
                            rval.append(feature)
                        else:
                            if prop['title']==title:
                                titleMatchCount+=1
                                rval.append(feature) # return the entire json object
            if len(rval)==0:
                # question: do we want to try a refresh and try one more time?
                logging.info('getFeatures: No features match the specified criteria.')
                return [False]
            if titleMatchCount>1:
                if allowMultiTitleMatch:
                    return rval
                else:
                    logging.error('getFeatures: More than one feature matches the specified title.')
                    return [False]
            else:
                return rval

    # getFeature - same interface as getFeatures, expecting only one result;
    #   if the number of results is not exactly one, return with an error
    def getFeature(self,
            featureClass=None,
            title=None,
            id=None,
            featureClassExcludeList=[],
            allowMultiTitleMatch=False,
            since=0,
            timeout=False):
        r=self.getFeatures(
            featureClass=featureClass,
            title=title,
            id=id,
            featureClassExcludeList=featureClassExcludeList,
            allowMultiTitleMatch=allowMultiTitleMatch,
            since=since,
            timeout=timeout)
        if isinstance(r,list):
            if len(r)==1:
                return r[0]
            elif len(r)<1:
                logging.error('getFeature: no match')
                return -1
            else:
                logging.error('getFeature: more than one match')
                logging.info(str(r))
                return -1
        else:
            logging.error('getFeature: return from getFeatures was not a list: '+str(r))

    # editObject(id=None,className=None,title=None,letter=None,properties=None,geometry=None)
    # edit any properties and/or geometry of specified map object

    #   - id, className, title, letter - used to identify the object to be edited;
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
    #    sts.editObject(className='Marker',title='t',geometry={'coordinates':[-120,39,0,0]})

    #  2. change assignment status to INPROGRESS
    #    sts.editObject(className='Assignment',letter='AB',properties={'status':'INPROGRESS'})

    #  3. change assignment number
    #    sts.editObject(className='Assignment',letter='AB',properties={'number':'111'})

    def editObject(self,
            id=None,
            className=None,
            title=None,
            letter=None,
            properties=None,
            geometry=None):

        # PART 1: determine the exact id of the object to be edited
        if id is None:
            # first, validate the arguments and adjust as needed
            if className is None:
                logging.error('ClassName was not specified.')
                return False
            if letter is not None:
                if className is not 'Assignment':
                    logging.warning('Letter was specified, but className was specified as other than Assignment.  ClassName Assignment will be used.')
                className='Assignment'
            if title is None and letter is None:
                logging.error('Either Title or Letter must be specified.')
                return False
            if title is not None and letter is not None:
                logging.warning('Both Title and Letter were specified.  Only one or the other can be used for the search.  Using Letter, in case the rest of the object title has changed.')
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
                logging.error('no feature matched class='+str(className)+' title='+str(title)+' letter='+str(letter))
                return False
            if len(features)>1:
                logging.error('more than one feature matched class='+str(className)+' title='+str(title)+' letter='+str(letter))
                return False
            feature=features[0]
            logging.info('feature found: '+str(feature))

        else:
            logging.info('id specified: '+id)
            features=[f for f in self.mapData['state']['features'] if f['id']==id]
            # logging.info(json.dumps(self.mapData,indent=3))
            if len(features)==1:
                feature=features[0]
                className=feature['properties']['class']
            else:
                logging.info('no match!')
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
                if points[i]!=points[i-2]:
                    out.append(points[i])
                else:
                    logging.info('spur removed at '+str(points[i-1]))
                    out.pop() # delete last vertex
                # logging.info('\n --> '+str(len(out))+' points: '+str(out))
        else:
            # logging.info('\n      object has less than three points; no spur removal attempted.')
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

    def cut(self,target,cutter,deleteCutter=True):
        if isinstance(target,str): # if string, find object by name; if id, find object by id
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
            logging.error('Target shape '+targetStr+' not found; operation aborted.')
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

        if isinstance(cutter,str): # if string, find object by name; if id, find object by id
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
            logging.error('Cutter shape '+cutterStr+' not found; operation aborted.')
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
            logging.error(targetShape['properties']['title']+','+cutterShape['properties']['title']+': objects do not intersect; no operation performed')
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
            if not self.editObject(id=targetShape['id'],geometry={'coordinates':[list(result.exterior.coords)]}):
                logging.error('cut: target shape not found; operation aborted.')
                return False
        elif isinstance(result,MultiPolygon):
            if not self.editObject(id=targetShape['id'],geometry={'coordinates':[list(result[0].exterior.coords)]}):
                logging.error('cut: target shape not found; operation aborted.')
                return False
            suffix=0
            for r in result[1:]:
                suffix+=1
                if tc=='Shape':
                    self.addPolygon(list(r.exterior.coords),
                        title=tp['title']+':'+str(suffix),
                        stroke=tp['stroke'],
                        fill=tp['fill'],
                        strokeOpacity=tp['stroke-opacity'],
                        strokeWidth=tp['stroke-width'],
                        fillOpacity=tp['fill-opacity'],
                        description=tp['description'],
                        folderId=tfid,
                        gpstype=tp['gpstype'])
                elif tc=='Assignment':
                    self.addAreaAssignment(list(r.exterior.coords),
                        number=tp['number'],
                        letter=tp['letter']+':'+str(suffix),
                        opId=tp.get('operationalPeriodId',None),
                        folderId=tp.get('folderId',None),
                        resourceType=tp['resourceType'],
                        teamSize=tp['teamSize'],
                        priority=tp['priority'],
                        responsivePOD=tp['responsivePOD'],
                        unresponsivePOD=tp['unresponsivePOD'],
                        cluePOD=tp['cluePOD'],
                        description=tp['description'],
                        previousEfforts=tp['previousEfforts'],
                        transportation=tp['transportation'],
                        timeAllocated=tp['timeAllocated'],
                        primaryFrequency=tp['primaryFrequency'],
                        secondaryFrequency=tp['secondaryFrequency'],
                        preparedBy=tp['preparedBy'],
                        gpstype=tp['gpstype'],
                        status=tp['status'])
                else:
                    logging.error('cut: target object class was neither Shape nor Assigment; operation aborted.')
                    return False
        elif isinstance(result,LineString):
            if not self.editObject(id=targetShape['id'],geometry={'coordinates':list(result.coords)}):
                logging.error('cut: target shape not found; operation aborted.')
                return False
        elif isinstance(result,MultiLineString):
            if not self.editObject(id=targetShape['id'],geometry={'coordinates':list(result[0].coords)}):
                logging.error('cut: target shape not found; operation aborted.')
                return False
            suffix=0
            for r in result[1:]:
                suffix+=1
                if tc=='Shape':
                    self.addLine(list(r.coords),
                        title=tp['title']+':'+str(suffix),
                        color=tp['stroke'],
                        opacity=tp['stroke-opacity'],
                        width=tp['stroke-width'],
                        pattern=tp['pattern'],
                        description=tp['description'],
                        folderId=tfid,
                        gpstype=tp['gpstype'])
                elif tc=='Assignment':
                    self.addLineAssignment(list(r.coords),
                        number=tp['number'],
                        letter=tp['letter']+':'+str(suffix),
                        opId=tp.get('operationalPeriodId',None),
                        folderId=tp.get('folderId',None),
                        resourceType=tp['resourceType'],
                        teamSize=tp['teamSize'],
                        priority=tp['priority'],
                        responsivePOD=tp['responsivePOD'],
                        unresponsivePOD=tp['unresponsivePOD'],
                        cluePOD=tp['cluePOD'],
                        description=tp['description'],
                        previousEfforts=tp['previousEfforts'],
                        transportation=tp['transportation'],
                        timeAllocated=tp['timeAllocated'],
                        primaryFrequency=tp['primaryFrequency'],
                        secondaryFrequency=tp['secondaryFrequency'],
                        preparedBy=tp['preparedBy'],
                        gpstype=tp['gpstype'],
                        status=tp['status'])
                else:
                    logging.error('cut: target object class was neither Shape nor Assigment; operation aborted.')
                    return False
        if deleteCutter:
            self.delObject(cutterShape['properties']['class'],existingId=cutterShape['id'])

    # expand - expand target polygon to include the area of p2 polygon

    def expand(self,target,p2,deleteP2=True):
        if isinstance(target,str): # if string, find object by name; if id, find object by id
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
            logging.error('Target shape '+targetStr+' not found; operation aborted.')
            return False
        
        tg=targetShape['geometry']
        tgc=tg['coordinates'][0]
        tgc=self.removeSpurs(tgc)
        targetType=tg['type']
        if targetType=='Polygon':
            targetGeom=Polygon(tgc) # Shapely object
        else:
            logging.error('expand: target object '+targetStr+' is not a polygon: '+targetType)
            return False
        logging.info('targetGeom:'+str(targetGeom))

        if isinstance(p2,str): # if string, find object by name; if id, find object by id
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
            logging.error('expand: second polygon '+p2Str+' not found; operation aborted.')
            return False

        logging.info('expand: target='+targetStr+'  p2='+p2Str)
        
        cg=p2Shape['geometry']
        cgc=cg['coordinates'][0]
        cgc=self.removeSpurs(cgc)
        p2Type=cg['type']
        if p2Type=='Polygon':
            p2Geom=Polygon(cgc) # Shapely object
        else:
            logging.error('expand: p2 object '+p2Str+' is not a polygon: '+p2Type)
            return False
        logging.info('p2Geom:'+str(p2Geom))

        if not p2Geom.intersects(targetGeom):
            logging.error(targetShape['properties']['title']+','+p2Shape['properties']['title']+': objects do not intersect; no operation performed')
            return False

        result=targetGeom|p2Geom
        logging.info('expand result:'+str(result))

        if not self.editObject(id=targetShape['id'],geometry={'coordinates':[list(result.exterior.coords)]}):
            logging.error('expand: target shape not found; operation aborted.')
            return False

        if deleteP2:
            self.delObject(p2Shape['properties']['class'],existingId=p2Shape['id'])

    # intersection2(targetGeom,boundaryGeom)
    # we want a function that can take the place of shapely.ops.intersection
    #  when the target is a LineString and the boundary is a Polygon,
    #  which will preserve complex (is_simple=False) lines i.e. with internal crossovers

    # walk thru the points (except fot the last point) in the target shape(line):
    #    A = current point, B = next point
    #  A and B both inside boundary?  --> append A to output coord list
    #  A inside, B outside --> append A; append point at instersection of this segment with boundary; don't append B
    #  A outside, B inside --> append B; append point at intersection of this segment with boundary; don't append A
    #  A outside, B outside --> don't append either

    # known issue: straight segments that are 'clipped' by the boundary corner,
    #  i.e. A and B are both outside, but a portion of the AB segment is inside,
    #  will be omitted from the result, since only the drawn vertices are checked.

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

        # don't forget to check the last vertex!
        fc=targetCoords[-1]
        fp=Point(fc)
        f_in=fp.within(boundaryGeom)
        if f_in:
            outLines[-1].append(fc)

        # return the Shapely object(s)
        if len(outLines)>1:
            rval=MultiLineString(outLines)
        else:
            rval=LineString(outLines[0])
        return rval


    # crop - remove portions of a line or polygon that are outside a boundary polygon;
    #          grow the specified boundary polygon by the specified distance before cropping

    def crop(self,target,boundary,beyond=0.0001,deleteBoundary=False):
        if isinstance(target,str): # if string, find object by name; if id, find object by id
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
            logging.error('Target shape '+targetStr+' not found; operation aborted.')
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
            targetGeom=LineString(tgc)
        else:
            logging.error('crop: target object '+targetStr+' is not a polygon or line: '+targetType)
            return False
            
        if isinstance(boundary,str): # if string, find object by name; if id, find object by id
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
            logging.error('crop: boundary shape '+boundaryStr+' not found; operation aborted.')
            return False

        logging.info('crop: target='+targetStr+'  boundary='+boundaryStr)

        cg=boundaryShape['geometry']
        boundaryType=cg['type']
        if boundaryType=='Polygon':
            cgc=cg['coordinates'][0]
            cgc=self.removeSpurs(cgc)
            boundaryGeom=Polygon(cgc).buffer(beyond) # Shapely object
        else:
            logging.error('crop: boundary object '+boundaryStr+' is not a polygon: '+boundaryType)
            return False
        logging.info('crop: boundaryGeom:'+str(boundaryGeom))

        if not boundaryGeom.intersects(targetGeom):
            logging.error(targetShape['properties']['title']+','+boundaryShape['properties']['title']+': objects do not intersect; no operation performed')
            return False

        # if target is a line, and boundary is a polygon, use intersection2; see notes above
        if isinstance(targetGeom,LineString) and isinstance(boundaryGeom,Polygon):
            result=self.intersection2(targetGeom,boundaryGeom)
        else:
            result=targetGeom&boundaryGeom # could be MultiPolygon or MultiLinestring or GeometryCollection
        logging.info('crop result:'+str(result))

        # preserve target properties when adding new features
        tp=targetShape['properties']
        tc=tp['class'] # Shape or Assignment
        tfid=tp.get('folderId',None)

        # collect resulting object ids to return as the return value
        rids=[]

        if isinstance(result,GeometryCollection): # apparently this will only be the case for polygons
            result=MultiPolygon(result)
        if isinstance(result,Polygon):
            rids.append(self.editObject(id=targetShape['id'],geometry={'coordinates':[list(result.exterior.coords)]}))
            if rids==[]:
                logging.error('cut: target shape not found; operation aborted.')
                return False
        elif isinstance(result,MultiPolygon):
            rids.append(self.editObject(id=targetShape['id'],geometry={'coordinates':[list(result[0].exterior.coords)]}))
            if rids==[]:
                logging.error('cut: target shape not found; operation aborted.')
                return False
            suffix=0
            for r in result[1:]:
                suffix+=1
                if tc=='Shape':
                    rids.append(self.addPolygon(list(r.exterior.coords),
                        title=tp['title']+':'+str(suffix),
                        stroke=tp['stroke'],
                        fill=tp['fill'],
                        strokeOpacity=tp['stroke-opacity'],
                        strokeWidth=tp['stroke-width'],
                        fillOpacity=tp['fill-opacity'],
                        description=tp['description'],
                        folderId=tfid,
                        gpstype=tp['gpstype']))
                elif tc=='Assignment':
                    rids.append(self.addAreaAssignment(list(r.exterior.coords),
                        number=tp['number'],
                        letter=tp['letter']+':'+str(suffix),
                        opId=tp.get('operationalPeriodId',None),
                        folderId=tp.get('folderId',None),
                        resourceType=tp['resourceType'],
                        teamSize=tp['teamSize'],
                        priority=tp['priority'],
                        responsivePOD=tp['responsivePOD'],
                        unresponsivePOD=tp['unresponsivePOD'],
                        cluePOD=tp['cluePOD'],
                        description=tp['description'],
                        previousEfforts=tp['previousEfforts'],
                        transportation=tp['transportation'],
                        timeAllocated=tp['timeAllocated'],
                        primaryFrequency=tp['primaryFrequency'],
                        secondaryFrequency=tp['secondaryFrequency'],
                        preparedBy=tp['preparedBy'],
                        gpstype=tp['gpstype'],
                        status=tp['status']))
                else:
                    logging.error('crop: target object class was neither Shape nor Assigment')
        elif isinstance(result,LineString):
            rids.append(self.editObject(id=targetShape['id'],geometry={'coordinates':list(result.coords)}))
            if rids==[]:
                logging.error('crop: target shape not found; operation aborted.')
                return False
        elif isinstance(result,MultiLineString):
            rids.append(self.editObject(id=targetShape['id'],geometry={'coordinates':list(result[0].coords)}))
            if rids==[]:
                logging.error('crop: target shape not found; operation aborted.')
                return False
            suffix=0
            for r in result[1:]:
                suffix+=1
                if tc=='Shape':
                    rids.append(self.addLine(list(r.coords),
                        title=tp['title']+':'+str(suffix),
                        color=tp['stroke'],
                        opacity=tp['stroke-opacity'],
                        width=tp['stroke-width'],
                        pattern=tp['pattern'],
                        description=tp['description'],
                        folderId=tfid,
                        gpstype=tp['gpstype']))
                elif tc=='Assignment':
                    rids.append(self.addLineAssignment(list(r.coords),
                        number=tp['number'],
                        letter=tp['letter']+':'+str(suffix),
                        opId=tp.get('operationalPeriodId',None),
                        folderId=tp.get('folderId',None),
                        resourceType=tp['resourceType'],
                        teamSize=tp['teamSize'],
                        priority=tp['priority'],
                        responsivePOD=tp['responsivePOD'],
                        unresponsivePOD=tp['unresponsivePOD'],
                        cluePOD=tp['cluePOD'],
                        description=tp['description'],
                        previousEfforts=tp['previousEfforts'],
                        transportation=tp['transportation'],
                        timeAllocated=tp['timeAllocated'],
                        primaryFrequency=tp['primaryFrequency'],
                        secondaryFrequency=tp['secondaryFrequency'],
                        preparedBy=tp['preparedBy'],
                        gpstype=tp['gpstype'],
                        status=tp['status']))
                else:
                    logging.error('crop: target object class was neither Shape nor Assigment')
                    return False

        if deleteBoundary:
            self.delObject(boundaryShape['properties']['class'],existingId=boundaryShape['id'])

        return rids # resulting object IDs

        
    def insertBeforeExt(self,fn,ins):
        if '.' in fn:
            lastSlashIndex=-1
            lastBackSlashIndex=-1
            if '/' in fn:
                lastSlashIndex=fn.rindex('/')
            if '\\' in fn:
                lastBackSlashIndex=fn.rindex('\\')
            lastSepIndex=max(lastBackSlashIndex,lastSlashIndex)
            try:
                lastDotIndex=fn.rindex('.',lastSepIndex)
                return fn[:lastDotIndex]+ins+fn[lastDotIndex:]
            except:
                pass
        return fn+ins

logging.basicConfig(stream=sys.stdout,level=logging.INFO) # print by default; let the caller change this if needed
