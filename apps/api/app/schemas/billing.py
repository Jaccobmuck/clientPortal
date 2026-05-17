from pydantic import BaseModel


class BillingCheckoutResponse(BaseModel):
    checkout_url: str


class BillingPortalResponse(BaseModel):
    portal_url: str
