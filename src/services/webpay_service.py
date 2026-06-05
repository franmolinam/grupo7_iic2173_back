import os
from transbank.webpay.webpay_plus.transaction import Transaction
from transbank.common.options import WebpayOptions
from transbank.common.integration_type import IntegrationType

# En ambiente de pruebas siempre se usan estas credenciales de integración
COMMERCE_CODE = "597055555532"
API_KEY = "579B532A7440BB0C9079DED94D31EA1615BACEB56610332264630D42D0A36B1C"

def get_transaction() -> Transaction:
    return Transaction(
        WebpayOptions(COMMERCE_CODE, API_KEY, IntegrationType.TEST)
    )


# para crear una transacción en webpay.
# Devuelve token + url.
# payment_id se usa como buy_order para identificar el pago.
def create_transaction(payment_id: str, amount: int, return_url: str) -> dict:
    tx = get_transaction()
    response = tx.create(
        buy_order=payment_id,
        session_id=payment_id,
        amount=amount,
        return_url=return_url,
    )
    return {
        "token": response.token,
        "url": response.url,
    }

# Para confirmar una transacción con Webpay usando el token.
# Devuelve los datos de la transacción confirmada.
def commit_transaction(token: str) -> dict:
    tx = get_transaction()
    response = tx.commit(token)
    return {
        "response_code": response.response_code,
        "authorization_code": response.authorization_code,
        "amount": response.amount,
        "transaction_date": response.transaction_date,
        "status": response.status,
    }