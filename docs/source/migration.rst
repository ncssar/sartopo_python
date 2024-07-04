Migration
==========================================

There are two categories of migration that you might be concerned with:

1. sartopo_python is changing names to caltopo_python
-----------------------------------------------------

This module began as 'sartopo_python'.  There are several reasons for chaning the module name, including:

- most of the features in this module are not SAR-specific
- sartopo.com is now effectively the same as caltopo.com; the only difference is the 'SAR' vs. 'Recreation' mode setting for each map
- caltopo.com has much broader name recognition than sartopo.com outside of the SAR community
- CalTopo is the name of the app; there is no 'SARTopo app'
- the name of the downloadble server is CalTopo Desktop (formerly SARTopo Offline or CalTopo Offline); there is no 'SARTopo Desktop'

caltopo_python 1.0.x will be identical to sartopo_python 2.0.x.

sartopo_python will not receive any updates after 2.0.x.  That is, there will be no sartopo_python 2.1.0.
Patches / bug fixes to 1.0 / 2.0 will be applied to both packages, but,
minor and major version updates will only be applied to caltopo_python.

We suggest that you change to caltopo_python as soon as possible.  If you are just getting started with sartopo_python, we suggest that you use caltopo_python instead.

*How do I migrate from sartopo_python to caltopo_python?*

1. pip install caltopo_python
2. import caltopo_python instead of import sartopo_python
3. create an instance of CaltopoSession instead of SartopoSession

There is no change to class method names or signatures.  The class name is the only difference.

2. migrating to sartopo_python 2.0.0 from an earlier version
------------------------------------------------------------

(or, migrating to caltopo_python 1.0.0 from an earlier version of sartopo_python)

Some class method names and signatures have changed from earlier versions.

Several method names now start with an underscore, to indicate that they are not likely to be needed directly
in your downstream code.  These 'internal' data management and helper methods are normally only called internally
by other class methods.

They can still be called from your downstream code if there is a specific need, as long as you are fully aware
of their impacts on internal class data - especially the local cache and the threaded queueing operations.

These previously-non-underscored methods from the latest PyPi version (1.1.2) are now 'internal' (e.g. .setupSession is now ._setupSession):

- ._setupSession, ._sendRequest

In addition, these previously-non-underscored methods from more recent versions of source code are now 'internal':

- ._sendUserdata, ._doSync, ._refresh, ._start, ._stop, ._pause, ._resume, ._buffer2, ._intersection2, ._caseMatch, ._twoify, ._fourify, ._removeDuplicatePoints, ._removeSpurs, ._getUsedSuffixList, ._getNextAvailableSuffix, ._getToken

In general, the changes from the latest PyPi version (1.1.2) are extensive enough that documenting
the differences would not be any more helpful than looking in the Class Reference.

Changes from more recent versions of source code mainly involve method signatures (argument names, types, and sequences).

In either case, migrating your code from previous versions may be a fair amount of work, but the new feature set and
forward compatibility should be a good payoff.  Use the Examples section of the main page,
and the Class Reference, as your guides.