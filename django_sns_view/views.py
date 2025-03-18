import logging
import re

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
import pydantic_core

from .types import (
    Notification,
    SNSPayload,
    SubscriptionConfirmation,
    UnsubscribeConfirmation,
)
from .utils import confirm_subscription, verify_notification

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class SNSEndpoint(View):
    topic_type_header: str = "HTTP_X_AMZ_SNS_TOPIC_ARN"
    cert_domain_settings_key: str = "SNS_CERT_DOMAIN_REGEX"
    sns_verify_settings_key: str = "SNS_VERIFY_CERTIFICATE"
    topic_settings_key: str = ""

    def handle_message(self, message: str, notification: Notification) -> None:
        """
        Process the SNS message.
        """
        raise NotImplementedError

    def post(self, request: HttpRequest) -> HttpResponse:
        """
        Validate and handle an SNS message.
        """
        # Check the topic if specified by a settings key
        topic_allowlist = self.get_topic_allowlist()
        if topic_allowlist is not None:
            if self.topic_type_header not in request.META:
                return HttpResponseBadRequest("No TopicArn Header")

            # Check to see if the topic is in the settings
            if request.META[self.topic_type_header] not in topic_allowlist:
                return HttpResponseBadRequest("Bad Topic")

        # Parse and validate the request body
        try:
            payload = SNSPayload.model_validate_json(request.body).root
        except pydantic_core.ValidationError:
            logger.exception("Invalid payload")
            return HttpResponseBadRequest("Invalid payload")

        # Confirm that the signing certificate is hosted on a correct domain
        # AWS by default uses sns.{region}.amazonaws.com
        pattern = self.get_cert_domain_pattern()
        if not payload.SigningCertURL.host or not re.search(
            pattern, payload.SigningCertURL.host
        ):
            logger.warning(
                "Improper Certificate Location %s",
                payload.SigningCertURL,
            )
            return HttpResponseBadRequest("Improper Certificate Location")

        # Verify that the notification is signed by Amazon
        if self.get_cert_verification_enabled() and not verify_notification(payload):
            logger.error("Cert verification failed")
            return HttpResponseBadRequest("Improper Signature")

        # Handle subscription confirmations
        if isinstance(payload, SubscriptionConfirmation):
            return confirm_subscription(payload)

        # Handle unsubscribe confirmations
        if isinstance(payload, UnsubscribeConfirmation):
            # Don't handle unsubscribe notification here, just remove
            # this endpoint from AWS console. Return 200 status
            # so redelivery of this message doesnt occur.
            logger.info("UnsubscribeConfirmation Not Handled")
            return HttpResponse("UnsubscribeConfirmation Not Handled")

        message = payload.Message
        logger.info(
            "SNS Notification received",
            extra=dict(
                message_type=payload.Type,
                sns_payload=request.body,
                payload_message=payload,
            ),
        )
        self.handle_message(message, payload)
        return HttpResponse("OK")

    def get_topic_allowlist(self) -> list[str] | None:
        return getattr(settings, self.topic_settings_key, None)

    def get_cert_domain_pattern(self) -> str:
        return getattr(
            settings,
            self.cert_domain_settings_key,
            r"sns.[a-z0-9\-]+.amazonaws.com$",
        )

    def get_cert_verification_enabled(self) -> bool:
        return getattr(
            settings,
            self.sns_verify_settings_key,
            True,
        )
