import pytest
from unittest.mock import MagicMock, patch, call
import json
import uuid
from datetime import datetime, timezone

# --- Tests de utils (fibonacci_retry) ---

from src.rabbitmq.utils import fibonacci_retry

def test_fibonacci_retry_success_first_try():
    """Función que tiene éxito al primer intento no reintenta."""
    mock_func = MagicMock(return_value="ok")
    decorated = fibonacci_retry(max_retries=3)(mock_func)
    result = decorated()
    assert result == "ok"
    assert mock_func.call_count == 1


def test_fibonacci_retry_success_after_retries():
    """Función que falla 2 veces y luego tiene éxito."""
    mock_func = MagicMock(side_effect=[Exception("fallo"), Exception("fallo"), "ok"])
    decorated = fibonacci_retry(max_retries=3)(mock_func)
    with patch("time.sleep"):  # evitar esperas reales
        result = decorated()
    assert result == "ok"
    assert mock_func.call_count == 3


def test_fibonacci_retry_raises_after_max_retries():
    """Función que siempre falla lanza excepción después de max_retries."""
    mock_func = MagicMock(side_effect=Exception("fallo permanente"))
    mock_func.__name__ = "mock_func"  # fix
    decorated = fibonacci_retry(max_retries=3)(mock_func)
    with patch("time.sleep"):
        with pytest.raises(Exception, match="fallo permanente"):
            decorated()
    assert mock_func.call_count == 3


def test_fibonacci_retry_preserves_function_name():
    """El decorador preserva el nombre de la función original."""
    def mi_funcion():
        pass
    decorated = fibonacci_retry(max_retries=3)(mi_funcion)
    assert decorated.__name__ == "mi_funcion"


# --- Tests de publisher ---

from src.rabbitmq.publisher import publicar_mensaje

def test_publicar_mensaje_success():
    """publicar_mensaje llama a basic_publish con los parámetros correctos."""
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


def test_publicar_mensaje_retries_on_failure():
    """publicar_mensaje reintenta si basic_publish falla."""
    mock_channel = MagicMock()
    mock_channel.basic_publish.side_effect = [Exception("fallo"), None]
    mensaje = {"type": "test"}

    with patch("time.sleep"):
        result = publicar_mensaje(mock_channel, "fulfillment.x", "central", mensaje)

    assert mock_channel.basic_publish.call_count == 2


# --- Tests de auditor ---

from src.rabbitmq.auditor import enviar_reporte_auditor

def test_auditor_received():
    """enviar_reporte_auditor envía reporte tipo 'received' a central."""
    mock_channel = MagicMock()
    package_id = str(uuid.uuid4())

    with patch("src.rabbitmq.auditor.publicar_mensaje") as mock_pub:
        enviar_reporte_auditor(mock_channel, package_id, "received")
        mock_pub.assert_called_once()
        args = mock_pub.call_args
        mensaje = args[1]["message_dict"] if args[1] else args[0][3]
        assert mensaje["type"] == "received"
        assert mensaje["pkgId"] == package_id


def test_auditor_expired():
    """enviar_reporte_auditor envía reporte tipo 'expired'."""
    mock_channel = MagicMock()
    package_id = str(uuid.uuid4())

    with patch("src.rabbitmq.auditor.publicar_mensaje") as mock_pub:
        enviar_reporte_auditor(mock_channel, package_id, "expired")
        args = mock_pub.call_args
        mensaje = args[1]["message_dict"] if args[1] else args[0][3]
        assert mensaje["type"] == "expired"


def test_auditor_transit_includes_next_city():
    """enviar_reporte_auditor incluye nextCityId para tipo 'transit'."""
    mock_channel = MagicMock()
    package_id = str(uuid.uuid4())

    with patch("src.rabbitmq.auditor.publicar_mensaje") as mock_pub:
        enviar_reporte_auditor(mock_channel, package_id, "transit", next_city_id="HGW")
        args = mock_pub.call_args
        mensaje = args[1]["message_dict"] if args[1] else args[0][3]
        assert mensaje["type"] == "transit"
        assert mensaje["data"]["nextCityId"] == "HGW"


def test_auditor_transit_redirect_includes_next_city():
    """enviar_reporte_auditor incluye nextCityId para tipo 'transit-redirect'."""
    mock_channel = MagicMock()
    package_id = str(uuid.uuid4())

    with patch("src.rabbitmq.auditor.publicar_mensaje") as mock_pub:
        enviar_reporte_auditor(mock_channel, package_id, "transit-redirect", next_city_id="COR")
        args = mock_pub.call_args
        mensaje = args[1]["message_dict"] if args[1] else args[0][3]
        assert mensaje["data"]["nextCityId"] == "COR"


def test_auditor_sends_to_central():
    """enviar_reporte_auditor siempre envía a la central."""
    mock_channel = MagicMock()

    with patch("src.rabbitmq.auditor.publicar_mensaje") as mock_pub:
        enviar_reporte_auditor(mock_channel, "pkg-123", "received")
        args = mock_pub.call_args
        routing_key = args[1]["routing_key"] if args[1] else args[0][2]
        assert routing_key == "central"


# --- Tests de consumer (callback) ---

from src.rabbitmq.consumer import validar_mensaje

def test_validar_mensaje_valido():
    """Mensaje con todos los campos requeridos es válido."""
    mensaje = {
        "idpk": str(uuid.uuid4()),
        "msgId": str(uuid.uuid4()),
        "type": "package-transit",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    assert validar_mensaje(mensaje) == True


def test_validar_mensaje_falta_campo():
    """Mensaje sin campo requerido no es válido."""
    mensaje = {
        "msgId": str(uuid.uuid4()),
        "type": "package-transit",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    assert validar_mensaje(mensaje) == False


def test_validar_mensaje_vacio():
    """Mensaje vacío no es válido."""
    assert validar_mensaje({}) == False


def test_validar_mensaje_todos_los_campos():
    """Verifica que los 4 campos requeridos son necesarios."""
    campos = ["idpk", "msgId", "type", "timestamp"]
    mensaje_completo = {c: "valor" for c in campos}
    for campo in campos:
        incompleto = {k: v for k, v in mensaje_completo.items() if k != campo}
        assert validar_mensaje(incompleto) == False