from copy import deepcopy
from mock import patch, Mock
from requests.exceptions import HTTPError

from django.conf import settings

from django_sns_view.utils import get_pemfile, verify_notification, confirm_subscription
from django_sns_view.tests.test_data.notifications import SNS_SUBSCRIPTION_NOTIFICATION
from django_sns_view.tests.helpers import SNSBaseTest


class VerificationTest(SNSBaseTest):
    @patch('django_sns_view.utils.requests.get')
    def test_get_pemfile(self, mock):
        """Test the get_pemfile util"""
        responsemock = Mock()
        mock.return_value = responsemock
        responsemock.text = self.pemfile
        result = get_pemfile('http://www.fakeurl.com')

        mock.assert_called_with('http://www.fakeurl.com')
        self.assertEqual(result, self.pemfile)

    @patch('django_sns_view.utils.requests.get')
    def test_bad_keyfile(self, mock):
        """Test a non-valid keyfile"""
        responsemock = Mock()
        responsemock.read.return_value = 'Not A Certificate'
        mock.return_value = responsemock

        with self.assertRaises(ValueError) as context_manager:
            get_pemfile('http://www.fakeurl.com')

        the_exception = context_manager.exception
        self.assertEqual(the_exception.args[0], 'Invalid Certificate File')

    @patch('django_sns_view.utils.get_pemfile')
    def test_verify_notification_with_subject(self, mock):
        """Test the verification of a valid notification with Subject"""
        mock.return_value = self.pemfile
        result = verify_notification(self.sns_notification)
        self.assertTrue(result)

    @patch('django_sns_view.utils.get_pemfile')
    def test_verify_notification_no_subject(self, mock):
        """Test the verification of a valid notification without Subject"""
        mock.return_value = self.pemfile
        result = verify_notification(self.sns_notification_no_subject)
        self.assertTrue(result)


class ConfirmSubscriptionTest(SNSBaseTest):
    @patch('django_sns_view.utils.requests.get')
    def test_successful_confirm_subscription(self, mock):
        """Test a successful subscription confirmation"""
        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.status_code = 200

        mock.return_value = mock_resp

        response = confirm_subscription(self.sns_confirmation)

        mock.assert_called_with(self.sns_confirmation['SubscribeURL'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode('ascii'), 'OK')

    @patch('django_sns_view.utils.requests.get')
    def test_fail_confirm_subscription(self, mock):
        """Test a successful subscription confirmation"""
        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.raise_for_status.side_effect = HTTPError("site is down")
        mock_resp.status_code = 503
        mock.return_value = mock_resp

        self.assertRaises(HTTPError, confirm_subscription,
                          self.sns_confirmation)
        mock.assert_called_with(self.sns_confirmation['SubscribeURL'])

    def test_bad_url(self):
        """Test to make sure an invalid URL isn't requested"""
        old_setting = getattr(settings, 'SNS_SUBSCRIBE_DOMAIN_REGEX', None)
        settings.SNS_SUBSCRIBE_DOMAIN_REGEX = \
            r"sns.[a-z0-9\-]+.amazonaws.com$"
        notification = deepcopy(SNS_SUBSCRIPTION_NOTIFICATION)
        notification['SubscribeURL'] = 'http://anon.amazonaws.com'
        result = confirm_subscription(notification)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(
            result.content.decode('ascii'), 'Improper Subscription Domain')

        if old_setting is not None:
            settings.SNS_SUBSCRIBE_DOMAIN_REGEX = old_setting
