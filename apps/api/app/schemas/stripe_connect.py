from pydantic import BaseModel


class StripeConnectOnboardResponse(BaseModel):
    onboarding_url: str
    stripe_connect_account_id: str
    onboarding_required: bool
