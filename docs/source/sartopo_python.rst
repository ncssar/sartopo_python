:tocdepth: 3

sartopo\_python module
======================
.. see https://stackoverflow.com/a/48682589/3577105 for categorization technique
.. currentmodule:: sartopo_python

.. autoclass:: SartopoSession

.. omitting class name from automethod calls, when the section headers are unindented,
..   causes these failures, but, the headers need to be unindented for the TOC to recognize them:
.. WARNING: don't know which module to import for autodocumenting 'openMap' (try placing a "module" or "currentmodule" directive in the document, or giving an explicit module name)

.. **Session setup methods**
.. -------------------------

.. automethod:: SartopoSession.openMap

**Account data access methods**
-------------------------------
These methods may be called from a mapless session.

   .. automethod:: SartopoSession.getAccountData
   .. automethod:: SartopoSession.getMapList
   .. automethod:: SartopoSession.getAllMapLists
   .. automethod:: SartopoSession.getMapTitle
   .. automethod:: SartopoSession.getGroupAccountTitles

**Feature creation methods**
----------------------------

   .. automethod:: SartopoSession.addFolder
   .. automethod:: SartopoSession.addMarker
   .. automethod:: SartopoSession.addLine
   .. automethod:: SartopoSession.addPolygon
   .. automethod:: SartopoSession.addLineAssignment
   .. automethod:: SartopoSession.addAreaAssignment
   .. automethod:: SartopoSession.addAppTrack
   .. automethod:: SartopoSession.flush

**Feature query methods**
-------------------------

   .. automethod:: SartopoSession.getFeature
   .. automethod:: SartopoSession.getFeatures
      
**Feature editing methods**
---------------------------
   
   .. automethod:: SartopoSession.editFeature
   .. automethod:: SartopoSession.moveMarker
   .. automethod:: SartopoSession.editMarkerDescription

**Feature deletion methods**
----------------------------

   .. automethod:: SartopoSession.delFeature
   .. automethod:: SartopoSession.delFeatures
   .. automethod:: SartopoSession.delMarker
   .. automethod:: SartopoSession.delMarkers

**Geometry operation methods**
------------------------------

   .. automethod:: SartopoSession.cut
   .. automethod:: SartopoSession.expand
   .. automethod:: SartopoSession.crop
   .. automethod:: SartopoSession.buffer2
   .. automethod:: SartopoSession.intersection2
   .. automethod:: SartopoSession.getBounds

**Internal data management methods**
------------------------------------

   .. automethod:: SartopoSession._setupSession
   .. automethod:: SartopoSession._sendUserdata
   .. automethod:: SartopoSession._doSync
   .. automethod:: SartopoSession._refresh
   .. automethod:: SartopoSession.__del__
   .. automethod:: SartopoSession._start
   .. automethod:: SartopoSession._stop
   .. automethod:: SartopoSession._pause
   .. automethod:: SartopoSession._resume
   .. automethod:: SartopoSession._syncLoop
   .. automethod:: SartopoSession._sendRequest
   .. automethod:: SartopoSession._delAsync

**Internal helper methods**
---------------------------

   .. automethod:: SartopoSession._caseMatch
   .. automethod:: SartopoSession._twoify
   .. automethod:: SartopoSession._fourify
   .. automethod:: SartopoSession._removeDuplicatePoints
   .. automethod:: SartopoSession._removeSpurs
   .. automethod:: SartopoSession._getUsedSuffixList
   .. automethod:: SartopoSession._getNextAvailableSuffix
   .. automethod:: SartopoSession._getToken

   .. :members:
   .. :undoc-members:
   .. :show-inheritance:

.. Module contents
.. ---------------

.. .. automodule:: sartopo_python
..    :members:
..    :undoc-members:
..    :show-inheritance:
