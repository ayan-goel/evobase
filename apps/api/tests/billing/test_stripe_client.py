from types import SimpleNamespace

from app.billing import stripe_client


def test_create_subscription_expands_confirmation_secret_and_payment_intent():
    captured_kwargs = {}

    class FakeSubscriptionApi:
        @staticmethod
        def create(**kwargs):
            captured_kwargs.update(kwargs)
            return {"id": "sub_test"}

    fake_stripe = SimpleNamespace(Subscription=FakeSubscriptionApi)

    original_get_stripe = stripe_client._get_stripe
    stripe_client._get_stripe = lambda: fake_stripe
    try:
        result = stripe_client.create_subscription("cus_test", "hobby")
    finally:
        stripe_client._get_stripe = original_get_stripe

    assert result == {"id": "sub_test"}
    assert captured_kwargs["expand"] == [
        "latest_invoice.confirmation_secret",
        "latest_invoice.payment_intent",
    ]


def test_get_client_secret_from_subscription_prefers_confirmation_secret():
    subscription = SimpleNamespace(
        id="sub_test",
        latest_invoice=SimpleNamespace(
            id="in_test",
            confirmation_secret=SimpleNamespace(client_secret="cs_confirm"),
        ),
    )

    assert stripe_client.get_client_secret_from_subscription(subscription) == "cs_confirm"


def test_get_client_secret_from_subscription_falls_back_to_payment_intent():
    subscription = SimpleNamespace(
        id="sub_test",
        latest_invoice=SimpleNamespace(
            id="in_test",
            payment_intent=SimpleNamespace(client_secret="cs_payment_intent"),
        ),
    )

    assert stripe_client.get_client_secret_from_subscription(subscription) == "cs_payment_intent"


def test_get_client_secret_from_subscription_handles_removed_payment_intent_attribute():
    class InvoiceWithRemovedPaymentIntent:
        id = "in_test"
        status = "open"
        confirmation_secret = None

        @property
        def payment_intent(self):
            raise AttributeError("payment_intent is removed")

    subscription = SimpleNamespace(
        id="sub_test",
        latest_invoice=InvoiceWithRemovedPaymentIntent(),
    )

    assert stripe_client.get_client_secret_from_subscription(subscription) is None
