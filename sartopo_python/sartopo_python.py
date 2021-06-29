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
#  6-15-21    TMG        add geometry operations cut, expand, crop
#  6-27-21    TMG        stop sync when main thread terminates (fix #19)
#  6-28-21    TMG        remove spurs to fix self-intersecting polygons (fix #20)
#  6-29-21    TMG        return gracefully if shapes do not intersect (fix #21)
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
import threading
from threading import Thread

from shapely.geometry import LineString,Polygon,MultiLineString,MultiPolygon,GeometryCollection
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
            syncTimeout=2,
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
        self.propUpdateCallback=propUpdateCallback
        self.geometryUpdateCallback=geometryUpdateCallback
        self.newObjectCallback=newObjectCallback
        self.deletedObjectCallback=deletedObjectCallback
        self.syncInterval=syncInterval
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
            rj=self.getFeatures(since=str(max(0,self.lastSuccessfulSyncTimestamp-500)),timeout=self.syncTimeout)
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
                    if threading.main_thread().is_alive():
                        time.sleep(self.syncInterval)
                        self.doSync()
                    else:
                        logging.info('Main thread has ended; sync is stopping...')

            else:
                logging.error('Sartopo sync failed!')

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
        Thread(target=self.doSync).start()

    def sendRequest(self,type,apiUrlEnd,j,id="",returnJson=None,timeout=2):
        if self.apiVersion<0:
            logging.error("sendRequest: sartopo session is invalid; request aborted: type="+str(type)+" apiUrlEnd="+str(apiUrlEnd))
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
            logging.debug("SENDING POST to '"+url+"':")
            logging.debug(json.dumps(params,indent=3))
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
                logging.error("sendRequest: response had no decodable json")
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
                        logging.info("sendRequest: No valid ID was returned from the request:")
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
            update=0,
            queue=False):
        j={}
        jp={}
        jg={}
        jp['class']='Marker'
        jp['updated']=update
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
            gpstype='TRACK',
            folderId=None,
            existingId=None,
            queue=False,
            timeout=2):
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

    def getFeatures(self,
            featureClass=None,
            title=None,
            id=None,
            featureClassExcludeList=[],
            allowMultiTitleMatch=False,
            since=0,
            timeout=2):
        rj=self.sendRequest('get','since/'+str(since),None,returnJson='ALL',timeout=timeout)
        if featureClass is None and title is None and id is None:
            return rj # if no feature class or title or id is specified, return the entire json response
        else:
            titleMatchCount=0
            rval=[]
            if 'result' in rj and 'state' in rj['result'] and 'features' in rj['result']['state']:
                features=rj['result']['state']['features']
                for feature in features:
                    if feature['id']==id:
                        rval.append(feature)
                        break
                    prop=feature['properties']
                    cls=prop['class']
                    if featureClass is None and cls not in featureClassExcludeList:
                        if prop['title']==title:
                            titleMatchCount+=1
                            rval.append(feature)
                    else:
                        if cls==featureClass:
                            if title is None:
                                rval.append(feature)
                            else:
                                if prop['title']==title:
                                    titleMatchCount+=1
                                    rval.append(feature) # return the entire json object
            if len(rval)==0:
                logging.info('getFeatures: No features matching the specified criteria.')
            if titleMatchCount>1:
                if allowMultiTitleMatch:
                    return rval
                else:
                    logging.error('getFeatures: More than one feature matches the specified title.')
                    return False
            else:
                return rval

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
                return -1
            if letter is not None:
                if className is not 'Assignment':
                    logging.warning('Letter was specified, but className was specified as other than Assignment.  ClassName Assignment will be used.')
                className='Assignment'
            if title is None and letter is None:
                logging.error('Either Title or Letter must be specified.')
                return -1
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
                return -1
            if len(features)>1:
                logging.error('more than one feature matched class='+str(className)+' title='+str(title)+' letter='+str(letter))
                return -1
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
                return -1

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
                    out.pop() # delete last vertex
                # logging.info('\n --> '+str(len(out))+' points: '+str(out))
        else:
            # logging.info('\n      object has less than three points; no spur removal attempted.')
            out=points
        if len(points)!=len(out):
            logging.info('spur(s) were removed from the shape:\n    '+str(len(points))+' points: '+str(points)+'\n --> '+str(len(out))+' points: '+str(out))
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
            if len(target)==36: # id
                targetShape=self.getFeatures(id=target)[0]
            else:
                targetShape=self.getFeatures(title=target,featureClassExcludeList=['Folder','OperationalPeriod'])[0]
        else:
            targetShape=target
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
            logging.error('cut: unhandled target geometry type: '+targetType)
            return False
        logging.debug('targetGeom:'+str(targetGeom))

        if isinstance(cutter,str):
            if len(cutter)==36: # id
                cutterShape=self.getFeatures(id=cutter)[0]
            else:
                cutterShape=self.getFeatures(title=cutter,featureClassExcludeList=['Folder','OperationalPeriod'])[0]
        else:
            cutterShape=cutter # if string, find object by name; if id, find object by id
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
        logging.debug('cutterGeom:'+str(cutterGeom))

        if not cutterGeom.intersects(targetGeom):
            logging.info(targetShape['properties']['title']+','+cutterShape['properties']['title']+': objects do not intersect; no operation performed')
            return False

        #  shapely.ops.split only works if the second geometry completely splits the first;
        #   instead, use the simple boolean object.difference (same as overloaded '-' operator)
        if targetType=='Polygon' and cutterType=='LineString':
            result=split(targetGeom,cutterGeom)
        else:
            result=targetGeom-cutterGeom
        logging.debug('cut result:'+str(result))

        # preserve target properties when adding new features
        tp=targetShape['properties']
        tc=tp['class'] # Shape or Assignment
        tfid=tp.get('folderId',None)

        if isinstance(result,GeometryCollection): # apparently this will only be the case for polygons
            result=MultiPolygon(result)
        if isinstance(result,Polygon):
            self.editObject(id=targetShape['id'],geometry={'coordinates':[list(result.exterior.coords)]})
        elif isinstance(result,MultiPolygon):
            self.editObject(id=targetShape['id'],geometry={'coordinates':[list(result[0].exterior.coords)]})
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
                    logging.error('cut: target object class was neither Shape nor Assigment')
        elif isinstance(result,LineString):
            self.editObject(id=targetShape['id'],geometry={'coordinates':list(result.coords)})
        elif isinstance(result,MultiLineString):
            self.editObject(id=targetShape['id'],geometry={'coordinates':list(result[0].coords)})
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
                    logging.error('cut: target object class was neither Shape nor Assigment')
        if deleteCutter:
            self.delObject(cutterShape['properties']['class'],existingId=cutterShape['id'])

    # expand - expand target polygon to include the area of p2 polygon

    def expand(self,target,p2,deleteP2=True):
        if isinstance(target,str): # if string, find object by name; if id, find object by id
            if len(target)==36: # id
                targetShape=self.getFeatures(id=target)[0]
            else:
                targetShape=self.getFeatures(title=target,featureClassExcludeList=['Folder','OperationalPeriod'])[0]
        else:
            targetShape=target
        tg=targetShape['geometry']
        tgc=tg['coordinates'][0]
        tgc=self.removeSpurs(tgc)
        targetType=tg['type']
        if targetType=='Polygon':
            targetGeom=Polygon(tgc) # Shapely object
        else:
            logging.error('expand: target object is not a polygon: '+targetType)
        logging.debug('targetGeom:'+str(targetGeom))

        if isinstance(p2,str):
            if len(p2)==36: # id
                p2Shape=self.getFeatures(id=p2)[0]
            else:
                p2Shape=self.getFeatures(title=p2,featureClassExcludeList=['Folder','OperationalPeriod'])[0]
        else:
            p2Shape=p2 # if string, find object by name; if id, find object by id
        cg=p2Shape['geometry']
        cgc=cg['coordinates'][0]
        cgc=self.removeSpurs(cgc)
        p2Type=cg['type']
        if p2Type=='Polygon':
            p2Geom=Polygon(cgc) # Shapely object
        else:
            logging.error('expand: p2 object is not a polygon: '+p2Type)
        logging.debug('p2Geom:'+str(p2Geom))

        if not p2Geom.intersects(targetGeom):
            logging.info(targetShape['properties']['title']+','+p2Shape['properties']['title']+': objects do not intersect; no operation performed')
            return False

        result=targetGeom|p2Geom
        logging.debug('expand result:'+str(result))

        self.editObject(id=targetShape['id'],geometry={'coordinates':[list(result.exterior.coords)]})

        if deleteP2:
            self.delObject(p2Shape['properties']['class'],existingId=p2Shape['id'])

    # crop - remove portions of a line or polygon that are outside a boundary polygon;
    #          grow the specified boundary polygon by the specified distance before cropping

    def crop(self,target,boundary,beyond=0.0001,deleteBoundary=False):
        if isinstance(target,str): # if string, find object by name; if id, find object by id
            if len(target)==36: # id
                targetShape=self.getFeatures(id=target)[0]
            else:
                targetShape=self.getFeatures(title=target,featureClassExcludeList=['Folder','OperationalPeriod'])[0]
        else:
            targetShape=target
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
            logging.error('crop: target object is not a polygon or line: '+targetType)
            
        if isinstance(boundary,str):
            if len(boundary)==36: # id
                boundaryShape=self.getFeatures(id=boundary)[0]
            else:
                boundaryShape=self.getFeatures(title=boundary,featureClassExcludeList=['Folder','OperationalPeriod'])[0]
        else:
            boundaryShape=boundary # if string, find object by name; if id, find object by id
        cg=boundaryShape['geometry']
        boundaryType=cg['type']
        if boundaryType=='Polygon':
            cgc=cg['coordinates'][0]
            gcg=self.removeSpurs(cgc)
            boundaryGeom=Polygon(cgc).buffer(beyond) # Shapely object
        else:
            logging.error('crop: boundary object is not a polygon: '+boundaryType)
        logging.debug('crop: boundaryGeom:'+str(boundaryGeom))

        if not boundaryGeom.intersects(targetGeom):
            logging.info(targetShape['properties']['title']+','+boundaryShape['properties']['title']+': objects do not intersect; no operation performed')
            return False

        result=targetGeom&boundaryGeom # could be MultiPolygon or MultiLinestring or GeometryCollection
        logging.debug('crop result:'+str(result))

        # preserve target properties when adding new features
        tp=targetShape['properties']
        tc=tp['class'] # Shape or Assignment
        tfid=tp.get('folderId',None)

        if isinstance(result,GeometryCollection): # apparently this will only be the case for polygons
            result=MultiPolygon(result)
        if isinstance(result,Polygon):
            self.editObject(id=targetShape['id'],geometry={'coordinates':[list(result.exterior.coords)]})
        elif isinstance(result,MultiPolygon):
            self.editObject(id=targetShape['id'],geometry={'coordinates':[list(result[0].exterior.coords)]})
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
                    logging.error('crop: target object class was neither Shape nor Assigment')
        elif isinstance(result,LineString):
            self.editObject(id=targetShape['id'],geometry={'coordinates':list(result.coords)})
        elif isinstance(result,MultiLineString):
            self.editObject(id=targetShape['id'],geometry={'coordinates':list(result[0].coords)})
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
                    logging.error('crop: target object class was neither Shape nor Assigment')

        if deleteBoundary:
            self.delObject(boundaryShape['properties']['class'],existingId=boundaryShape['id'])

logging.basicConfig(stream=sys.stdout,level=logging.INFO) # print by default; let the caller change this if needed
