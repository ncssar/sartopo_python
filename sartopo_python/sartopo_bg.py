from sartopo_python import SartopoSession

# open a session on the target map first, since nocb definition checks for it
sts2=SartopoSession('localhost:8080','0SD',sync=False)

def nocb(f):
    p=f['properties']
    c=p['class']
    t=p.get('title','')
    id=f['id']
    if c=='Assignment':
        sts2.addFolder(t)
    elif c=='Shape':
        for folder in sts2.getFeatures('Folder',timeout=10):
            if folder['properties']['title']==t:
                sts2.addLine(f['geometry']['coordinates'],title=t,folderId=folder['id'],timeout=10)
                # sts2.editObject(id=id,properties={'folderId':folder['id']})


sts1=SartopoSession('localhost:8080','V80',
    newObjectCallback=nocb,
    syncTimeout=10)





