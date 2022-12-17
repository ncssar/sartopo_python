from sartopo_python import SartopoSession
import logging
import sys
# from shapely.geometry import LineString,Polygon,Point,MultiLineString,MultiPolygon,GeometryCollection
# from shapely.ops import split,linemerge

# To redefine basicConfig, per stackoverflow.com/questions/12158048
# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('test2.log','w'),
        logging.StreamHandler(sys.stdout)
    ]
)

def pucb(*args):
    print("pucb called with args "+str(args))

def gucb(*args):
    print("gucb called with args "+str(args))

def nocb(*args):
    print("nocb called with args "+str(args))

def docb(*args):
    print("docb called with args "+str(args))

print('startup')

# logging.basicConfig(stream=sys.stdout,level=logging.INFO)

sts=SartopoSession('localhost:8080','0BC')
# sts=SartopoSession('sartopo.com','HB0U',
#         configpath='../../sts.ini',
#         account='caver456@gmail.com',
#         sync=False,
#         syncDumpFile='../../HB0U.txt')
#         # propUpdateCallback=pucb,
#         # geometryUpdateCallback=gucb,
#         # newObjectCallback=nocb,
#         # deletedObjectCallback=docb)

# timeout=0.001
timeout=None
testFolder=sts.addFolder('testFolder',timeout=timeout)
testMarker=sts.addMarker(39,-120,'testMarker',timeout=timeout)
testLine=sts.addLine([[-120.1,39.1],[-120.2,39.2]],'testLine',timeout=timeout)
testPolygon=sts.addPolygon([[-120.05,39.05],[-120.15,39.05],[-120.15,39.15],[-120.05,39.15]],'testPolygon',timeout=timeout)
testLineAssignment=sts.addLineAssignment([[-120.3,39.3],[-120.4,39.4]],101,'AA',timeout=timeout)
testAreaAssignment=sts.addAreaAssignment([[-120.05,39.45],[-120.15,39.45],[-120.15,39.55],[-120.05,39.55]],102,timeout=timeout)
testAppTrack=sts.addAppTrack([[-120.2,39],[-120.25,39]],'testAppTrack',timeout=timeout)
# r=sts.crop('c1','c2')
# print('crop return value:'+str(r))

# sts.cut('c1','c2',deleteCutter=False,crop=True)

# sts.cut('c3','c4')

# sts.crop('a16','b16')

# sts.crop('c1','c2')
# sts.crop('c3','c2')
# sts.crop('c4','c2')
# sts.crop('c5','c2')
# sts.crop('c6','c2')
# sts.crop('c7','c2')

# targetShape=sts.getFeatures(title='c1')[0]
# tg=targetShape['geometry']
# targetType=tg['type']
# if targetType=='Polygon':
#     tgc=tg['coordinates'][0]
#     targetGeom=Polygon(tgc) # Shapely object
# elif targetType=='LineString':
#     tgc=tg['coordinates']
#     targetGeom=LineString(tgc)

# cutterShape=sts.getFeatures(title='c2')[0]
# cg=cutterShape['geometry']
# cutterType=cg['type']
# if cutterType=='Polygon':
#     cgc=cg['coordinates'][0]
#     cutterGeom=Polygon(cgc) # Shapely object
# elif cutterType=='LineString':
#     cgc=cg['coordinates']
#     cutterGeom=LineString(cgc)

# outCoords=[]
# # for point in targetGeom.coords:
# for point in tgc:
#     if Point(point).within(cutterGeom):
#         outCoords.append(point)

# intersects2(targetGeom,cutterGeom)
# we want a function that can take the place of shapely.ops.intersection
#  when the target is a LineString and the cutter is a Polygon,
#  which will preserve complex (is_simple=False) lines i.e. with internal crossovers

# walk thru the points (except fot the last point) in the target shape(line):
#    A = current point, B = next point
#  A and B both inside cutter?  --> append A to output coord list
#  A inside, B outside --> append A; append point at instersection of this segment with cutter; don't append B
#  A outside, B inside --> append B; append point at intersection of this segment with cutter; don't append A
#  A outside, B outside --> don't append either

# def intersects2(targetGeom,cutterGeom):
#     outLines=[]
#     targetCoords=targetGeom.coords
#     nextInsidePointStartsNewLine=True
#     for i in range(len(targetCoords)-1):
#         ac=targetCoords[i]
#         bc=targetCoords[i+1]
#         ap=Point(ac)
#         bp=Point(bc)
#         a_in=ap.within(cutterGeom)
#         b_in=bp.within(cutterGeom)
#         print(str(i)+':')
#         print("   A="+str(ac)+'  within:'+str(a_in))
#         print("   B="+str(bc)+'  within:'+str(b_in))
#         if a_in and b_in:
#             if nextInsidePointStartsNewLine:
#                 outLines.append([])
#                 nextInsidePointStartsNewLine=False
#             outLines[-1].append(ac)
#         elif a_in and not b_in:
#             abl=LineString([ap,bp])
#             mp=abl.intersection(cutterGeom.exterior)
#             print('   midpoint intersection with crop shape:'+str(mp))
#             if nextInsidePointStartsNewLine:
#                 outLines.append([])
#                 nextInsidePointStartsNewLine=False
#             outLines[-1].append(ac)
#             outLines[-1].append(list(mp.coords)[0])
#             nextInsidePointStartsNewLine=True
#         elif b_in and not a_in:
#             abl=LineString([ap,bp])
#             mp=abl.intersection(cutterGeom.exterior)
#             print('   midpoint intersection with crop shape:'+str(mp))
#             nextInsidePointStartsNewLine=True
#             if nextInsidePointStartsNewLine:
#                 outLines.append([])
#                 nextInsidePointStartsNewLine=False
#             # the midpoint will be the first point of a new line
#             outLines[-1].append(list(mp.coords)[0])
#     print('outLines:'+str(outLines))
#     if len(outLines)>1:
#         rval=MultiLineString(outLines)
#     else:
#         rval=LineString(outLines)
#     print('rval:'+str(rval))
#     return rval

# r=intersects2(targetGeom,cutterGeom)
# sts.editObject(id=targetShape['id'],geometry={'coordinates':list(r[0].coords)})
# for i in range(1,len(r)):
#     sts.addLine(list(r[i].coords),title='c1:'+str(i))

# print(' target is valid:'+str(targetGeom.is_valid))
# print('target is simple:'+str(targetGeom.is_simple))
# print('orig:'+str(tgc))
# print(' out:'+str(outCoords))
# outGeom=LineString(outCoords)
# print(' output is valid:'+str(outGeom.is_valid))
# print('output is simple:'+str(outGeom.is_simple))
# r=sts.editObject(id=targetShape['id'],geometry={'coordinates':list(outGeom.coords)})
# # print('r:'+str(r))

