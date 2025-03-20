# Django SNS View

A drop in configurable django view that is used to subscribe and process AWS SNS messages.

## Installation

```bash
pip install django-sns-view
```

## Default Django Settings

```python
SNS_CERT_DOMAIN_REGEX = r"sns.[a-z0-9\-]+.amazonaws.com$" # Regex to match on cert domain
SNS_VERIFY_CERTIFICATE = True # Whether to verify signature against certificate
```

## SNSEndpoint Attributes

```python
message_type_header = 'HTTP_X_AMZ_SNS_MESSAGE_TYPE'
topic_type_header = 'HTTP_X_AMZ_SNS_TOPIC_ARN'
allowed_message_types = ['Notification', 'SubscriptionConfirmation', 'UnsubscribeConfirmation']
cert_domain_settings_key = 'SNS_CERT_DOMAIN_REGEX'
sns_verify_settings_key = 'SNS_VERIFY_CERTIFICATE'
topic_settings_key = '' # If you would like to subscribe this endpoint to only certain topics, create a setting containing a list of topics that are allowed.
```

## Usage

```python
from django_sns_view.views import SNSEndpoint

class MySNSView(SNSEndpoint):
    # Can override SNSEndpoint attributes outlined above

    def handle_message(self, message, payload):
        # Process the message
```
