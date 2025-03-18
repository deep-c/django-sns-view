from typing import Literal, Optional
import uuid

import pydantic


class BaseSNSPayload(pydantic.BaseModel):
    MessageId: uuid.UUID
    TopicArn: str
    Message: str
    # This must be left as a string and not parsed into datetime so that
    # signature calculation still works
    Timestamp: str
    SignatureVersion: str
    Signature: pydantic.Base64Bytes
    SigningCertURL: pydantic.HttpUrl


class SubscriptionConfirmation(BaseSNSPayload):
    Type: Literal["SubscriptionConfirmation"]
    Token: str
    SubscribeURL: pydantic.HttpUrl


class UnsubscribeConfirmation(BaseSNSPayload):
    Type: Literal["UnsubscribeConfirmation"]
    Token: str
    SubscribeURL: pydantic.HttpUrl


class Notification(BaseSNSPayload):
    Type: Literal["Notification"]
    Subject: Optional[str] = None
    UnsubscribeURL: pydantic.HttpUrl


type AnySNSPayload = SubscriptionConfirmation | UnsubscribeConfirmation | Notification


class SNSPayload(pydantic.RootModel[AnySNSPayload]):
    root: AnySNSPayload = pydantic.Field(discriminator="Type")
