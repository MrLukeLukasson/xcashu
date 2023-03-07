import json
import base64

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from cashu.core.base import TokenV2
from cashu.core.settings import LIGHTNING
from cashu.core.helpers import sum_proofs

from xcashu.server.ledger import ledger


class EcashHeaderMiddleware(BaseHTTPMiddleware):
    """
    Middleware that checks the HTTP headers for ecash
    """

    async def dispatch(self, request, call_next):
        if is_payment_required(request.url.path):
            # check whether valid ecash was provided in header
            token = get_payment_token(request)
            required_amount = get_required_amount(request.url.path)
            if not token:
                return await payment_information(get_invoice_amount(request))

            error = await handle_payment(token, required_amount)
            if error:
                return error

        return await call_next(request)


def is_payment_required(path: str) -> bool:
    """
    Check whether the path requires ecash
    """
    return get_required_amount(path) > 0


def get_required_amount(path: str) -> int:
    """
    Get the required amount for the path
    """
    # TODO: get paid paths and required amount from config
    # all requests to /cashu/* are not checked for ecash
    if path.startswith("/paid/"):
        return 1
    return 0


def get_payment_token(request) -> str:
    """
    Get the payment token from the request
    """
    # TODO: get header from config?
    # TODO: a more "generic" way could be to introduce a "Payment" header
    # and then expect a value "Cashu <payment token>"
    # Example:
    # ```
    # HTTP POST /paid/endpoint
    # Payment: Cashu <payment token>
    # ```
    # Similar to how the `Authorization` header works in HTTP
    # (Example: `Authorization: Bearer <token>`)
    return request.headers.get("X-Cashu")


def get_invoice_amount(request) -> int:
    """
    Get the invoice amount from the request or fallback to 1000
    """
    return int(request.headers.get("X-Cashu-Inv-Amnt", "1000"))


async def payment_information(required_amount, amount=1000):
    """
    Return payment information.

    If LIGHTNING is True, the payment information is a BOLT11 invoice with the
    specified `amount`.
    """
    if LIGHTNING:
        payment_request, payment_hash = await ledger.request_mint(amount)
    else:
        payment_request = f"payment_request: {amount} sats"
        payment_hash = "payment_hash"
    return JSONResponse(
        {
            "detail": "This endpoint requires a X-Cashu ecash header. "
                      f"Costs per request: {required_amount} sats",
            "pr": payment_request,
            "hash": payment_hash,
            "mint": "http://localhost:8000/cashu",
        },
        status_code=402,
    )


async def handle_payment(token, required_amount):
    """
    Handle the payment token.

    Returns None if the payment was successful, otherwise a JSONResponse with
    the error message and status code.
    """
    tokenv2 = TokenV2.parse_obj(json.loads(base64.urlsafe_b64decode(token)))
    proofs = tokenv2.proofs
    total_provided = sum_proofs(proofs)
    if total_provided != required_amount:
        return JSONResponse(
            {
                "detail": "Insufficient amount provided. "
                          f"Costs per request: {required_amount} sats",
            },
            # TODO: use 402 instead of 400? IMHO, 400 could be argued since a
            # payment is provided, just not enough?
            status_code=400
        )

    await ledger._set_proofs_pending(proofs)
    try:
        await ledger._verify_proofs(proofs)
        await ledger._invalidate_proofs(proofs)
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=402)
    finally:
        # delete proofs from pending list
        await ledger._unset_proofs_pending(proofs)
    return None
