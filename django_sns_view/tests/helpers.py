import os

from cryptography import x509
from django.conf import settings
from django.test import TestCase, override_settings

from ..types import Notification, SubscriptionConfirmation, UnsubscribeConfirmation
from .test_data.notifications import (
    SNS_NOTIFICATION,
    SNS_NOTIFICATION_NO_SUBJECT,
    SNS_SUBSCRIPTION_NOTIFICATION,
    SNS_UNSUBSCRIBE_NOTIFICATION,
)

DIRNAME, _ = os.path.split(os.path.abspath(__file__))


@override_settings(SNS_STORY_TOPIC_ARN=["arn:aws:sns:us-west-2:123456789012:MyTopic"])
class SNSBaseTest(TestCase):
    old_topics = getattr(settings, "", None)

    sns_notification = Notification.model_validate(SNS_NOTIFICATION)
    sns_notification_no_subject = Notification.model_validate(
        SNS_NOTIFICATION_NO_SUBJECT
    )
    sns_confirmation = SubscriptionConfirmation.model_validate(
        SNS_SUBSCRIPTION_NOTIFICATION
    )
    sns_unsubscribe = UnsubscribeConfirmation.model_validate(
        SNS_UNSUBSCRIBE_NOTIFICATION
    )

    keyfileobj = open(DIRNAME + ("/test_data/example.pem"))
    pemfile = keyfileobj.read().encode()
    x509_cert = x509.load_pem_x509_certificate(pemfile)
