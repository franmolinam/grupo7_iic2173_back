import pytest
from unittest.mock import MagicMock, patch, call
import json
import uuid
from datetime import datetime, timezone
from src.rabbitmq.utils import fibonacci_retry
from src.rabbitmq.publisher import publicar_mensaje
from src.rabbitmq.auditor import enviar_reporte_auditor
from src.rabbitmq.consumer import validar_mensaje

# TESTS UTILIDADES

# test para verificar que si tiene éxito al primer intento no reintenta
def test_fibonacci_retry_success_first_try():
    mock_func = MagicMock(return_value="ok")
    decorated = fibonacci_retry(max_retries=3)(mock_func)
    result = decorated()
    assert result == "ok"
    assert mock_func.call_count == 1

# test para función que falla 2 veces y luego tiene éxito
def test_fibonacci_retry_success_after_retries():
    mock_func = MagicMock(side_effect=[Exception("fallo"), Exception("fallo"), "ok"])
    decorated = fibonacci_retry(max_retries=3)(mock_func)
    with patch("time.sleep"):  # evitar esperas reales
        result = decorated()
    assert result == "ok"
    assert mock_func.call_count == 3

# test para función que siempre falla lanza excepción después de max_retries
def test_fibonacci_retry_raises_after_max_retries():
    mock_func = MagicMock(side_effect=Exception("fallo permanente"))
    mock_func.__name__ = "mock_func"  # fix
    decorated = fibonacci_retry(max_retries=3)(mock_func)
    with patch("time.sleep"):
        with pytest.raises(Exception, match="fallo permanente"):
            decorated()
    assert mock_func.call_count == 3

# test para ver q el decorador preserva el nombre de la función original
def test_fibonacci_retry_preserves_function_name():
    def mi_funcion():
        pass
    decorated = fibonacci_retry(max_retries=3)(mi_funcion)
    assert decorated.__name__ == "mi_funcion"


# TESTS PUBLISHER

# test para ver que publicar_mensaje llama a basic_publish con los parámetros correctos
def test_publicar_mensaje_success():
    mock_channel = MagicMock()
    mensaje = {"type": "ack", "msgId": str(uuid.uuid4())}

    result = publicar_mensaje(mock_channel, "fulfillment.x", "central", mensaje)

    assert result == True
    mock_channel.basic_publish.assert_called_once_with(
        exchange="fulfillment.x",
        routing_key="central",
        body=json.dumps(mensaje),
        mandatory=True
    )

# test para ver que publicar_mensaje reintenta si basic_publish falla
def test_publicar_mensaje_retries_on_failure():
    mock_channel = MagicMock()
    mock_channel.basic_publish.side_effect = [Exception("fallo"), None]
    mensaje = {"type": "test"}

    with patch("time.sleep"):
        result = publicar_mensaje(mock_channel, "fulfillment.x", "central", mensaje)

    assert mock_channel.basic_publish.call_count == 2


# TESTS AUDITOR

# test para ver que enviar_reporte_auditor envía reporte tipo 'received' a central
def test_auditor_received():
    mock_channel = MagicMock()
    package_id = str(uuid.uuid4())

    with patch("src.rabbitmq.auditor.publicar_mensaje") as mock_pub:
        enviar_reporte_auditor(mock_channel, package_id, "received")
        mock_pub.assert_called_once()
        args = mock_pub.call_args
        mensaje = args[1]["message_dict"] if args[1] else args[0][3]
        assert mensaje["type"] == "received"
        assert mensaje["pkgId"] == package_id

# test para verificar que enviar_reporte_auditor envía reporte tipo 'expired'
def test_auditor_expired():
    mock_channel = MagicMock()
    package_id = str(uuid.uuid4())

    with patch("src.rabbitmq.auditor.publicar_mensaje") as mock_pub:
        enviar_reporte_auditor(mock_channel, package_id, "expired")
        args = mock_pub.call_args
        mensaje = args[1]["message_dict"] if args[1] else args[0][3]
        assert mensaje["type"] == "expired"

# test para verificar que enviar_reporte_auditor incluye nextCityId para tipo 'transit'
def test_auditor_transit_includes_next_city():
    mock_channel = MagicMock()
    package_id = str(uuid.uuid4())

    with patch("src.rabbitmq.auditor.publicar_mensaje") as mock_pub:
        enviar_reporte_auditor(mock_channel, package_id, "transit", next_city_id="HGW")
        args = mock_pub.call_args
        mensaje = args[1]["message_dict"] if args[1] else args[0][3]
        assert mensaje["type"] == "transit"
        assert mensaje["data"]["nextCityId"] == "HGW"

# test para verificar que enviar_reporte_auditor incluye nextCityId para tipo 'transit-redirect'
def test_auditor_transit_redirect_includes_next_city():
    mock_channel = MagicMock()
    package_id = str(uuid.uuid4())

    with patch("src.rabbitmq.auditor.publicar_mensaje") as mock_pub:
        enviar_reporte_auditor(mock_channel, package_id, "transit-redirect", next_city_id="COR")
        args = mock_pub.call_args
        mensaje = args[1]["message_dict"] if args[1] else args[0][3]
        assert mensaje["data"]["nextCityId"] == "COR"

# test para verificar que enviar_reporte_auditor siempre envía a la central
def test_auditor_sends_to_central():
    mock_channel = MagicMock()

    with patch("src.rabbitmq.auditor.publicar_mensaje") as mock_pub:
        enviar_reporte_auditor(mock_channel, "pkg-123", "received")
        args = mock_pub.call_args
        routing_key = args[1]["routing_key"] if args[1] else args[0][2]
        assert routing_key == "central"


# TESTS CONSUMER (callback)

# test para verificar que el mensaje con todos los campos requeridos es válido
def test_validar_mensaje_valido():
    mensaje = {
        "idpk": str(uuid.uuid4()),
        "msgId": str(uuid.uuid4()),
        "type": "package-transit",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    assert validar_mensaje(mensaje) == True

# test para verificar que el mensaje sin campo requerido no es válido
def test_validar_mensaje_falta_campo():
    mensaje = {
        "msgId": str(uuid.uuid4()),
        "type": "package-transit",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    assert validar_mensaje(mensaje) == False

# test para verificar que el mensaje vacío no es válido
def test_validar_mensaje_vacio():
    assert validar_mensaje({}) == False

# test para verificar que los 4 campos requeridos son necesarios
def test_validar_mensaje_todos_los_campos():
    campos = ["idpk", "msgId", "type", "timestamp"]
    mensaje_completo = {c: "valor" for c in campos}
    for campo in campos:
        incompleto = {k: v for k, v in mensaje_completo.items() if k != campo}
        assert validar_mensaje(incompleto) == False