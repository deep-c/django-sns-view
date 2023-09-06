"""Base SNS View"""
import json
import logging
import re

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.generic import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings

from django_sns_view.utils import confirm_subscription, verify_notification


logger = logging.getLogger(__name__)
DEFAULT_ALLOWED_MESSAGE_TYPES = [
    'Notification', 'SubscriptionConfirmation', 'UnsubscribeConfirmation']


class SNSEndpoint(View):
    message_type_header = 'HTTP_X_AMZ_SNS_MESSAGE_TYPE'
    topic_type_header = 'HTTP_X_AMZ_SNS_TOPIC_ARN'
    allowed_message_types = DEFAULT_ALLOWED_MESSAGE_TYPES
    cert_domain_settings_key = 'SNS_CERT_DOMAIN_REGEX'
    sns_verify_settings_key = 'SNS_VERIFY_CERTIFICATE'
    topic_settings_key = ''

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super(SNSEndpoint, self).dispatch(*args, **kwargs)

    def handle_message(self, message, notification):
        """
        Process the SNS message.
        """
        raise NotImplementedError

    def should_confirm_subscription(self, payload):
        """
        Determine if the subscription should be confirmed.
        By default, we confirm all subscriptions.
        If settings has an AWS_ACCOUNT_ID key, we only confirm subscriptions from that account.

        This behavior can be overridden by subclassing and overriding this method.
        """
        if hasattr(settings, 'AWS_ACCOUNT_ID'):
            arn = payload['TopicArn'].split(':')[4]
            if  arn == settings.AWS_ACCOUNT_ID:
                return True
            else:
                logger.warning("Recieved subscription confirmation from account %s, but only accepting from account %s", arn, settings.AWS_ACCOUNT_ID)
                return False
        return True

    def post(self, request):
        """
        Validate and handle an SNS message.
        """
        # Check the topic if specified by a settings key
        if hasattr(settings, self.topic_settings_key):
            if self.topic_type_header not in request.META:
                return HttpResponseBadRequest('No TopicArn Header')

            # Check to see if the topic is in the settings
            if (not request.META[self.topic_type_header]
                    in getattr(settings, self.topic_settings_key)):
                return HttpResponseBadRequest('Bad Topic')

        if isinstance(request.body, str):
            # requests return str in python 2.7
            request_body = request.body
        else:
            # and return bytes in python 3.4
            request_body = request.body.decode()

        try:
            payload = json.loads(request_body)
        except ValueError:
            logger.error(
                'Notification Not Valid JSON: {}'.format(request.body))
            return HttpResponseBadRequest('Not Valid JSON')

        # Confirm that the signing certificate is hosted on a correct domain
        # AWS by default uses sns.{region}.amazonaws.com
        domain = urlparse(payload['SigningCertURL']).netloc
        pattern = getattr(
            settings, self.cert_domain_settings_key, r"sns.[a-z0-9\-]+.amazonaws.com$"
        )
        if not re.search(pattern, domain):
            logger.warning(
                'Improper Certificate Location %s', payload['SigningCertURL'])
            return HttpResponseBadRequest('Improper Certificate Location')

        # Verify that the notification is signed by Amazon
        if (getattr(settings, self.sns_verify_settings_key, True)
                and not verify_notification(payload)):
            logger.error('Verification Failure %s', )
            return HttpResponseBadRequest('Improper Signature')

        if not self.message_type_header in request.META:
            logger.error(
                'HTTP_X_AMZ_SNS_MESSAGE_TYPE not found in request.META')
            return HttpResponseBadRequest('HTTP_X_AMZ_SNS_MESSAGE_TYPE not set')

        message_type = request.META[self.message_type_header]

        if not message_type in self.allowed_message_types:
            logger.warning('Notification Type Not Known %s', message_type)
            return HttpResponseBadRequest('Invalid Notification Type')

        if message_type == 'SubscriptionConfirmation':
            if not self.should_confirm_subscription(payload):
                return HttpResponseBadRequest("Subscription Denied")
            return confirm_subscription(payload)
        elif message_type == 'UnsubscribeConfirmation':
            # Don't handle unsubscribe notification here, just remove
            # this endpoint from AWS console. Return 200 status
            # so redelivery of this message doesnt occur.
            logger.info('UnsubscribeConfirmation Not Handled')
            return HttpResponse('UnsubscribeConfirmation Not Handled')

        message = payload.get('Message')

        logger.info('SNS Notification received', extra=dict(
            message_type=message_type,
            sns_payload=request.body,
            payload_message=message,
        ))

        self.handle_message(message, payload)

        return HttpResponse('OK')
