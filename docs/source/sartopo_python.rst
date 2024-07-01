:tocdepth: 3

sartopo\_python module
======================

This module provides one main class: SartopoSession.  Class methods are categorized and documented below.

Downstream code should create and use one instance of this class.

An exception class is also defined, STSException, which could be thrown during initialization but is not documented here.

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
These methods may be called from either a mapless or a map-associated session.

   .. automethod:: SartopoSession.getAccountData
   .. automethod:: SartopoSession.getMapList
   .. automethod:: SartopoSession.getAllMapLists
   .. automethod:: SartopoSession.getMapTitle
   .. automethod:: SartopoSession.getGroupAccountTitles

**Feature creation methods**
----------------------------

Most of these feature creation methods can be used to edit an existing feature,
by specifying the existingId argument.  .editFeature is a convenience method
that calls the appropriate .add... method with existingId specified.

   .. automethod:: SartopoSession.addFolder
   .. automethod:: SartopoSession.addMarker
   .. automethod:: SartopoSession.addLine
   .. automethod:: SartopoSession.addPolygon
   .. automethod:: SartopoSession.addOperationalPeriod
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
These methods are typically only called internally, from other class methods.  They can be called from downstream code if needed, with caution.

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
These methods are typically only called internally, from other class methods.  They can be called from downstream code if needed, with caution.

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
