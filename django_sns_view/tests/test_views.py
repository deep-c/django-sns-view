from copy import deepcopy
from unittest.mock import MagicMock, patch
import json

from django.conf import settings
from django.http import HttpResponse, HttpResponseNotAllowed
from django.test import RequestFactory
from django.test.utils import override_settings

from ..types import Notification
from ..views import SNSEndpoint
from .helpers import SNSBaseTest
from .test_data.notifications import SNS_NOTIFICATION


@override_settings(SNS_VERIFY_CERTIFICATE=False)
class SNSEndpointTestCase(SNSBaseTest):
    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.request = self.factory.post("/")
        self.endpoint = SNSEndpoint.as_view()
        self.request.META["HTTP_X_AMZ_SNS_TOPIC_ARN"] = settings.SNS_STORY_TOPIC_ARN[0]  # type:ignore[misc]
        self.request.META["HTTP_X_AMZ_SNS_MESSAGE_TYPE"] = "Notification"

    def test_non_post_httpnotallowed(self) -> None:
        """
        Test that GET requests to the endpoint return a
        HttpResponseNotAllowed
        """
        request = self.factory.get("/")
        response = self.endpoint(request)
        self.assertIsInstance(response, HttpResponseNotAllowed)

    @patch.object(
        SNSEndpoint,
        "handle_message",
        lambda _, message, notification: HttpResponse("OK"),
    )
    def test_success(self) -> None:
        """Test a successful request"""
        self.request._body = self.sns_notification.model_dump_json().encode()
        response = self.endpoint(self.request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.content.decode("ascii"),  # type:ignore[attr-defined]
            "OK",
        )

    @override_settings(
        SNS_TEST_TOPIC_ARN=["arn:aws:sns:us-west-2:123456789012:MyTopic"]
    )
    @patch.object(SNSEndpoint, "topic_settings_key", "SNS_TEST_TOPIC_ARN")
    def test_no_topic_header(self) -> None:
        """Test the results if the request does not have a topic header"""
        request = self.factory.post("/")
        request.META["HTTP_X_AMZ_SNS_MESSAGE_TYPE"] = "Notification"
        request._body = self.sns_notification.model_dump_json().encode()
        response = self.endpoint(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.content.decode("ascii"),  # type:ignore[attr-defined]
            "No TopicArn Header",
        )

    @override_settings(SNS_TEST_TOPIC_ARN=["Diddly Doo"])
    @patch.object(SNSEndpoint, "topic_settings_key", "SNS_TEST_TOPIC_ARN")
    def test_bad_topic(self) -> None:
        """Test the response if the topic does not match the settings"""
        self.request._body = self.sns_notification.model_dump_json().encode()
        response = self.endpoint(self.request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.content.decode("ascii"),  # type:ignore[attr-defined]
            "Bad Topic",
        )

    def test_invalid_notification_json(self) -> None:
        """Test if the notification does not have a JSON body"""
        self.request._body = b"This Is Not JSON"
        response = self.endpoint(self.request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.content.decode("ascii"),  # type:ignore[attr-defined]
            "Invalid payload",
        )

    def test_bad_certificate_url(self) -> None:
        """Test an unknown certificate hostname"""
        notification = deepcopy(SNS_NOTIFICATION)
        notification["SigningCertURL"] = "https://baddomain.com/cert.pem"
        self.request._body = json.dumps(notification).encode()
        response = self.endpoint(self.request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.content.decode("ascii"),  # type:ignore[attr-defined]
            "Improper Certificate Location",
        )

    @patch("django_sns_view.views.confirm_subscription")
    def test_confirm_subscription_called(self, mock: MagicMock) -> None:
        """
        Test that confirm_subscription is called when sns
        sends a SubscriptionConfirmation notification
        """
        mock.return_value = "Confirmed"
        self.request.META["HTTP_X_AMZ_SNS_MESSAGE_TYPE"] = "SubscriptionConfirmation"
        self.request._body = self.sns_confirmation.model_dump_json().encode()
        response = self.endpoint(self.request)
        self.assertTrue(mock.called)
        self.assertEqual(response, "Confirmed")

    def test_unsubscribe_confirmation_not_handled(self) -> None:
        """Test that an unsubscribe notification is properly ignored"""
        self.request.META["HTTP_X_AMZ_SNS_MESSAGE_TYPE"] = "UnsubscribeConfirmation"
        self.request._body = self.sns_unsubscribe.model_dump_json().encode()
        response = self.endpoint(self.request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.content.decode("ascii"),  # type:ignore[attr-defined]
            "UnsubscribeConfirmation Not Handled",
        )

    @patch.object(SNSEndpoint, "handle_message")
    def test_handle_message_sucessfully_called(self, mock: MagicMock) -> None:
        """
        Test that the handle message method is called successfully,
        and that it has the right arguments passed.
        """
        mock.return_value = True
        self.request._body = self.sns_notification.model_dump_json().encode()
        response = self.endpoint(self.request)
        mock.assert_called_once_with(
            SNS_NOTIFICATION.get("Message"),
            Notification.model_validate(SNS_NOTIFICATION),
        )
        self.assertEqual(response.status_code, 200)
