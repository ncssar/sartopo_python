:tocdepth: 1

Credentials
===========

To activate online requests, you need to determine these values:

- account ID (6 characters)
- credential ID (12 characters)
- public key (44 characters)

You can place these values in the configuration file, or you can specify them as arguments during session initialization.
See examples at the bottom of this page.

This section only refers to your CalTopo account credentials - it does not refer to your external account provider credentials
(Google, Yahoo, MSN, Apple, etc.).  **This module does not need credentials for your external account provider.**

Your CalTopo account may have multiple sets of credentials.  These show up in the 'Credentials' section at the bottom
of the 'Your Account' dialog.

To open the 'Your Account' dialog, sign in to caltopo.com then click your login ID name, to the right of
'Your Data' near the top right of the web interface.  Don't worry if no credentials are listed yet.

Each credential has a 'credential ID' (the 12-character code shown in the Credentials table),
and a 'public key', which takes a bit more work to find.

Currently, the public key is most easily determined during the process of creating a new credential.

To create a new credential and to determine its credential ID and public key, follow these steps (based on the README at |sme-sartopo-mapsrv_link|):

1. Open a web page to caltopo.com.  Make sure you are signed in to your account:
   you should see your user name or login name at the top right, to the right of 'Your Data'.

2. In a separate browser tab, go to |activation-link|.
   This should show a web page similar to |activation-image_link| from the |desktop-installation_link| instructions.  Don't click Sync Account yet.

3. Open the developer console of your browser and start monitoring network traffic.
   For Chrome, use F12 to open Chrome DevTools; network traffic logging should be on when you open DevTools,
   as indicated by a red square-in-circle near the top left, which would stop monitoring network traffic
   when clicked.

4. Type 'sartopo_python' or a similar name for 'Your device will be synced as'.  The exact name is not important,
   but can help you keep track of credentials in case you have several.  Afterwards, the name you enter here will
   show up in the Credentials section of the Your Account dialog as above.

5. Check the checkbox and click Sync Account.  (This should load an error page, which is OK.)

6. In the network traffic monitor, you will see many requests.  After a few seconds, you can stop or pause
   network traffic monitoring to make sure the important entry does not get scrolled away as more new traffic happens.

7. In the first few requests, at the top of the list, you should see a request similar to::
   
      finish-activate?code=........&name=......

   Write down or copy the 8-character value after 'code=' from that request.  This is not the value to put in the
   configuration file; you will use it in the next step.

8.  In a new browser tab, go to::
   
      caltopo.com/api/v1/activate?code=<code>

   replacing <code> with the 8-character code from the previous step.

9.  This should load a page that looks like the following (possibly all compressed into one line):

.. code-block:: json

 {
   "code": "XXXXXXXXXXX",
   "account": {
     "id": "ABC123",
     "type": "Feature",
     "properties": {
       "subscriptionExpires": 1554760038,
       "subscriptionType": "pro-1",
       "subscriptionRenew": true,
       "subscriptionStatus": "active",
       "title": "......@example",
       "class": "UserAccount",
       "updated": 1554760038,
       "email": "......@example.com"
     }
   },
   "key": "xXXXXxXXXXXXXXXxxxXXXXxXxXXXXXXXXXXXX="
 }

10. Enter the 12-character 'code' value as 'id' in the configuration file.  Enter the 44-character value of 'key'
    as 'key' in the configuration file.  Enter the 6-character 'id' value as 'accountId' in the configuration file::

	# sartopo_python config file
	# This file contains credentials used to send API map requests
	#  to sartopo.com.  Protect and do not distribute these credentials.
	[joe@example.com]
	id=XXXXXXXXXXXX
	key=xXXXXxXXXXXXXXXxxxXXXXxXxXXXXXXXXXXXX=
	accountId=ABC123

   Alternately, any of these can be specified as arguments when initializing the session, which will override values
   from the configuration file (if any):

.. code-block:: python

	# to use the config file: specify filename and account name
	sts=SartopoSession('sartopo.com',
		configpath='../../sts.ini',
		account='joe@gmail.com')

	# to use arguments instead of the config file:
	sts=SartopoSession('sartopo.com',
		id='XXXXXXXXXXXX',
		key='xXXXXxXXXXXXXXXxxxXXXXxXxXXXXXXXXXXXX=',
		accountId='ABC123')

	# to use the config file, but use arguments to override values from the config file:
	sts=SartopoSession('sartopo.com',
		configpath='../../sts.ini',
		account='joe@gmail.com',
		id='XXXXXXXXXXXX',
		key='xXXXXxXXXXXXXXXxxxXXXXxXxXXXXXXXXXXXX=',
		accountId='ABC123')

.. |activation-link| raw:: html

	<a href="https://caltopo.com/app/activate/offline?redirect=localhost" target="_blank">https://caltopo.com/app/activate/offline?redirect=localhost</a>

.. |activation-image_link| raw:: html
	
	<a href="https://training.caltopo.com/user/pages/all_users/12.%20desktop/run-program-5.png" target="_blank">the one used during CalTopo Desktop activation</a>

.. |desktop-installation_link| raw:: html

	<a href="https://training.caltopo.com/all_users/desktop" target="_blank">CalTopo Desktop Installation</a>

.. |sme-sartopo-mapsrv_link| raw:: html

   <a href="https://github.com/elliottshane/sme-sartopo-mapsrv" target="_blank">https://github.com/elliottshane/sme-sartopo-mapsrv</a>