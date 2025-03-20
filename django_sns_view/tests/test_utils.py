from unittest.mock import MagicMock, Mock, patch

from cryptography import x509
from django.conf import settings
from requests.exceptions import HTTPError
import pydantic

from ..utils import confirm_subscription, get_x509_cert, verify_notification
from .helpers import SNSBaseTest


class VerificationTest(SNSBaseTest):
    @patch("django_sns_view.utils.requests.get")
    def test_get_x509_cert(self, mock: MagicMock) -> None:
        """Test the get_pemfile util"""
        responsemock = Mock()
        mock.return_value = responsemock
        responsemock.text = self.pemfile
        result = get_x509_cert("http://www.fakeurl.com")

        mock.assert_called_with("http://www.fakeurl.com")
        self.assertIsInstance(result, x509.Certificate)

    @patch("django_sns_view.utils.requests.get")
    def test_bad_keyfile(self, mock: MagicMock) -> None:
        """Test a non-valid keyfile"""
        responsemock = Mock()
        responsemock.read.return_value = "Not A Certificate"
        mock.return_value = responsemock

        with self.assertRaises(ValueError) as context_manager:
            get_x509_cert("http://www.fakeurl.com")

        the_exception = context_manager.exception
        self.assertTrue(the_exception.args[0].startswith("Unable to load PEM file"))

    @patch("django_sns_view.utils.get_x509_cert")
    def test_verify_notification_with_subject(self, mock: MagicMock) -> None:
        """Test the verification of a valid notification with Subject"""
        mock.return_value = self.x509_cert
        result = verify_notification(self.sns_notification)
        self.assertTrue(result)

    @patch("django_sns_view.utils.get_x509_cert")
    def test_verify_notification_no_subject(self, mock: MagicMock) -> None:
        """Test the verification of a valid notification without Subject"""
        mock.return_value = self.x509_cert
        result = verify_notification(self.sns_notification_no_subject)
        self.assertTrue(result)


class ConfirmSubscriptionTest(SNSBaseTest):
    @patch("django_sns_view.utils.requests.get")
    def test_successful_confirm_subscription(self, mock: MagicMock) -> None:
        """Test a successful subscription confirmation"""
        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.status_code = 200

        mock.return_value = mock_resp

        response = confirm_subscription(self.sns_confirmation)

        mock.assert_called_with(str(self.sns_confirmation.SubscribeURL))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("ascii"), "OK")

    @patch("django_sns_view.utils.requests.get")
    def test_fail_confirm_subscription(self, mock: MagicMock) -> None:
        """Test a successful subscription confirmation"""
        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.raise_for_status.side_effect = HTTPError("site is down")
        mock_resp.status_code = 503
        mock.return_value = mock_resp

        self.assertRaises(HTTPError, confirm_subscription, self.sns_confirmation)
        mock.assert_called_with(str(self.sns_confirmation.SubscribeURL))

    def test_bad_url(self) -> None:
        """Test to make sure an invalid URL isn't requested"""
        old_setting = getattr(settings, "SNS_SUBSCRIBE_DOMAIN_REGEX", None)
        settings.SNS_SUBSCRIBE_DOMAIN_REGEX = r"sns.[a-z0-9\-]+.amazonaws.com$"
        notification = self.sns_confirmation.model_copy()
        notification.SubscribeURL = pydantic.HttpUrl("http://anon.amazonaws.com")
        result = confirm_subscription(notification)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content.decode("ascii"), "Improper Subscription Domain")

        if old_setting is not None:
            settings.SNS_SUBSCRIBE_DOMAIN_REGEX = old_setting
