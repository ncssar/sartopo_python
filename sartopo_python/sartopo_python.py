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
#
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
from threading import Timer

class SartopoSession():
    def __init__(self,
            domainAndPort='localhost:8080',
            mapID=None,
            configpath=None,
            account=None,
            id=None,
            key=None,
            sync=True,
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
        self.propUpdateCallback=propUpdateCallback
        self.geometryUpdateCallback=geometryUpdateCallback
        self.newObjectCallback=newObjectCallback
        self.deletedObjectCallback=deletedObjectCallback
        self.syncInterval=5
        self.lastSuccessfulSyncTimestamp=0
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
                        return -1
                    config=configparser.ConfigParser()
                    config.read(self.configpath)
                    if self.account not in config.sections():
                        logging.error("specified account '"+self.account+"' has no entry in config file '"+self.configpath+"'.")
                        return -1
                    section=config[self.account]
                    id=section.get("id",None)
                    key=section.get("key",None)
                    if id is None or key is None:
                        logging.error("account entry '"+self.account+"' in config file '"+self.configpath+"' is not complete:\n  it must specify id and key.")
                        return -1
                else:
                    logging.error("specified config file '"+self.configpath+"' does not exist.")
                    return -1

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
                return -1
            if self.key is None:
                logging.error("sartopo session is invalid: 'key' must be specified for online maps")
                return -1

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
            r=self.s.get(url,timeout=2)
        except:
            logging.error("no response from first get request; aborting; should get a response of 400 at this point for api v0")
        else:
            logging.info("response code = "+str(r.status_code))
            if r.status_code==200:
                # now validate the mapID, since the initial test doesn't care about mapID
                mapUrl="http://"+self.domainAndPort+"/m/"+self.mapID
                try:
                    r=self.s.get(mapUrl,timeout=8)
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
                    r=self.s.get(url,timeout=2)
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
                            r=self.s.get(url,timeout=2)
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
            
    def doSync(self):
        if self.sync: # check here since sync could have been disabled since last sync
            # Use a 'since' value of a half second prior to the previous response timestamp;
            #  this is what sartopo currently does.

            # Keys under 'result':
            # 1 - 'ids' will only exist on first sync or after a deletion, so, if 'ids' exists
            #     then just use it to replace the entire cached 'ids', and also do cleanup later
            #     by deleting any state->features from the cache whose 'id' value is not in 'ids'
            # 2 - state->features is an array of changed existing objects, and the array will
            #     have complete data for 'geometry', 'id', 'type', and 'properties', so, for each
            #     item in state->features, just replace the entire existing cached feature of
            #     the same id

            logging.info('Sending sartopo "since" request...')
            rj=self.getFeatures(since=str(max(0,self.lastSuccessfulSyncTimestamp-500)))
            # logging.debug(json.dumps(rj,indent=3))
            if rj['status']=='ok':
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

                # 3 - cleanup
                self.mapIDs=sum(self.mapData['ids'].values(),[])
                mapSFIDs=[f['id'] for f in self.mapData['state']['features']]
                for i in range(len(mapSFIDs)):
                    if mapSFIDs[i] not in self.mapIDs:
                        prop=self.mapData['state']['features'][i]['properties']
                        logging.info('  Deleting '+str(prop['class'])+':'+str(prop['title']))
                        if self.deletedObjectCallback:
                            self.deletedObjectCallback(mapSFIDs[i],self.mapData['state']['features'][i])
                        del self.mapData['state']['features'][i]
        
                if self.syncDumpFile:
                    with open(self.syncDumpFile,"w") as f:
                        f.write(json.dumps(self.mapData,indent=3))

                if self.sync:
                    syncTimer=Timer(self.syncInterval,self.doSync)
                    syncTimer.start()
            else:
                logging.error('Sartopo sync failed!')

    def stop(self):
        logging.info('Sartopo syncing terminated.')
        self.sync=False

    def start(self):
        self.sync=True
        logging.info('Sartopo syncing initiated.')
        self.doSync()

    def sendRequest(self,type,apiUrlEnd,j,id="",returnJson=None):
        if self.apiVersion<0:
            logging.error("sartopo session is invalid; request aborted: type="+str(type)+" apiUrlEnd="+str(apiUrlEnd))
            return -1
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
        # logging.info("sending "+str(type)+" to "+url)
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
            r=self.s.post(url,data=params,timeout=2)
        elif type=="get": # no need for json in GET; sending null JSON causes downstream error
#             logging.info("SENDING GET to '"+url+"':")
            r=self.s.get(url,timeout=2)
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
            r=self.s.delete(url,params=params,timeout=2)   ## use params for query vs data for body data
            # logging.info("URL:"+str(url))
            # logging.info("Ris:"+str(r))
        else:
            logging.error("Unrecognized request type:"+str(type))
            return -1
#         logging.info("response code = "+str(r.status_code))
#         logging.info("response:")
#         try:
#             logging.info(json.dumps(r.json(),indent=3))
#         except:
#             logging.info(r.text)
        if returnJson:
            try:
                rj=r.json()
            except:
                logging.error("response had no decodable json")
                return -1
            else:
                if returnJson=="ID":
                    id=None
                    if 'result' in rj and 'id' in rj['result']:
                        id=rj['result']['id']
                    elif 'id' in rj:
                        id=rj['id']
                    elif not rj['result']['state']['features']:  # response if no new info
                        return 0
                    elif 'result' in rj and 'id' in rj['result']['state']['features'][0]:
                        id=rj['result']['state']['features'][0]['id']
                    else:
                        logging.info("No valid ID was returned from the request:")
                        logging.info(json.dumps(rj,indent=3))
                    return id
                if returnJson=="ALL":
                    return rj
        
    def addFolder(self,
            label="New Folder",
            queue=False):
        j={}
        j['properties']={}
        j['properties']['title']=label
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
            queue=False):
        j={}
        jp={}
        jg={}
        jp['class']='Marker'
        jp['updated']=0
        jp['marker-color']=color
        jp['marker-symbol']=symbol
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
            folderId=None,
            existingId=None,
            queue=False):
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
        jg['type']='LineString'
        jg['coordinates']=points
        j['properties']=jp
        j['geometry']=jg
        if existingId is not None:
            j['id']=existingId
        # logging.info("sending json: "+json.dumps(j,indent=3))
        return self.sendRequest("post","Shape",j,id=existingId,returnJson="ID")

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
            jp['operationalPeriod']=opId
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
            jp['operationalPeriod']=opId
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

    def flush(self):
        self.sendRequest('post','api/v0/map/[MAPID]/save',self.queue)
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
        # logging.info("In delete:"+objType+":"+str(existingId))
        ###return self.sendRequest("delete","since/0",None,id=str(existingId),returnJson="ALL")
        return self.sendRequest("delete",objType,None,id=str(existingId),returnJson="ALL")

    def getFeatures(self,featureClass=None,since=0):
        rj=self.sendRequest('get','since/'+str(since),None,returnJson='ALL')
        if featureClass is None:
            return rj # if no feature class is specified, return the entire json response
        else:
            rval=[]
            if 'result' in rj and 'state' in rj['result'] and 'features' in rj['result']['state']:
                features=rj['result']['state']['features']
                for feature in features:
#                     logging.info('FEATURE:'+str(feature))
#                     id=feature['id']
                    prop=feature['properties']
                    if prop['class']==featureClass:
                        rval.append(feature) # return the entire json object
#                         rval.append([id,prop]) # return all properties
                        
            return rval

logging.basicConfig(stream=sys.stdout,level=logging.INFO) # print by default; let the caller change this if needed
