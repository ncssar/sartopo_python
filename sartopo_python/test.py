from sartopo_python import SartopoSession

def pucb(*args):
    print("pucb called with args "+str(args))

def gucb(*args):
    print("gucb called with args "+str(args))

def nocb(*args):
    print("nocb called with args "+str(args))

def docb(*args):
    print("docb called with args "+str(args))

print('startup')

# sts=SartopoSession('localhost:8080','FAB')
sts=SartopoSession('sartopo.com','HB0U',
        configpath='../../sts.ini',
        account='caver456@gmail.com',
        syncDumpFile='../../HB0U.txt',
        propUpdateCallback=pucb,
        geometryUpdateCallback=gucb,
        newObjectCallback=nocb,
        deletedObjectCallback=docb)




# print('adding folder')
# fid=sts.addFolder('MyFolder')
# print('adding marker: stuff')
# stuffID=sts.addMarker(39,-120,'stuff')
# time.sleep(15)
# sts.editMarkerDescription('abc',stuffID)

# print('adding marker: myStuff')
# myStuffID=sts.addMarker(39.01,-120.01,'myStuff',folderId=fid)
# print('getting markers')
# r=sts.getFeatures('Marker')
# print('r:'+str(r))
# print('\nmoving the marker after a pause:'+myStuffID)
# time.sleep(30)
# print('moving marker: myStuff')
# sts.moveMarker(39.02,-120.02,existingId=myStuffID)
# # sts.addMarker(39.02,-120.02,'myStuff',existingId=myStuffID)
# print('\ndeleting "stuff" after a pause:')
# time.sleep(15)
# print('deleting marker: stuff')
# sts.delMarker(stuffID)
# print('done')

# j={}
# id='64acc33f-464d-47d0-9b5c-37f2aee81044'
# sts.editAreaAssignmentNumber('123',existingId=id)
# j['id']=id
# j['properties']={}
# j['properties']['number']='111'
# sts.sendRequest('post','assignment',j,id=id,returnJson='ID')