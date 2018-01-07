.. image:: https://travis-ci.org/deep-c/django-sns-view.svg?branch=master
    :target: https://travis-ci.org/deep-c/django-sns-view
    
================
Django SNS View
================

A drop in configurable django view that is used to subscribe and process AWS SNS messages. 

Installation
------------

.. code-block:: python

   pip install django-sns-view


Default Django Settings
----------------------
.. code-block:: python

  SNS_CERT_DOMAIN_REGEX = r"sns.[a-z0-9\-]+.amazonaws.com$" # Regex to match on cert domain
  SNS_VERIFY_CERTIFICATE = True # Whether to verify signature against certificate

SNSEndpoint Attributes
----------------------
.. code-block:: python

    message_type_header = 'HTTP_X_AMZ_SNS_MESSAGE_TYPE'
    topic_type_header = 'HTTP_X_AMZ_SNS_TOPIC_ARN'
    allowed_message_types = ['Notification', 'SubscriptionConfirmation', 'UnsubscribeConfirmation']
    cert_domain_settings_key = 'SNS_CERT_DOMAIN_REGEX'
    sns_verify_settings_key = 'SNS_VERIFY_CERTIFICATE'
    topic_settings_key = '' # If you would like to subscribe this endpoint only certain topics, create a setting containing a list of topics that are allowed.  

Usage
-----------
.. code-block:: python

   from django-sns-view.views import SNSEndpoint

    class MySNSView(SNSEndpoint):
       # Can override SNSEndpoint attributes outlined above

       def handle_message(message, payload):
           # Process the message
