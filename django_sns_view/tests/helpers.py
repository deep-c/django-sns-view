import os

from django.test import TestCase
from django.conf import settings

from django_sns_view.tests.test_data.notifications import SNS_NOTIFICATION, SNS_NOTIFICATION_NO_SUBJECT, SNS_SUBSCRIPTION_NOTIFICATION


DIRNAME, _ = os.path.split(os.path.abspath(__file__))


class SNSBaseTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(SNSBaseTest, cls).setUpClass()
        cls.old_topics = getattr(settings, '', None)
        cls.sns_notification = SNS_NOTIFICATION
        cls.sns_notification_no_subject = SNS_NOTIFICATION_NO_SUBJECT
        cls.sns_confirmation = SNS_SUBSCRIPTION_NOTIFICATION
        cls.keyfileobj = open(DIRNAME + ('/test_data/example.pem'))
        cls.pemfile = cls.keyfileobj.read()

        settings.SNS_STORY_TOPIC_ARN = [
            'arn:aws:sns:us-west-2:123456789012:MyTopic'
        ]

    @classmethod
    def tearDownClass(cls):
        if cls.old_topics is not None:
            settings.SNS_STORY_TOPIC_ARN = cls.old_topics
