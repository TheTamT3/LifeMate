import pytest

from lifemate.vllm import VLLMConfig, validate_loopback_url


def test_loopback_endpoint_is_accepted():
    assert validate_loopback_url("http://127.0.0.1:8000/v1") == "http://127.0.0.1:8000/v1"
    assert validate_loopback_url("http://localhost:9000/v1") == "http://localhost:9000/v1"


def test_remote_endpoint_is_rejected():
    with pytest.raises(ValueError, match="loopback"):
        validate_loopback_url("https://api.example.com/v1")


def test_vllm_config_defaults():
    config = VLLMConfig()
    assert config.base_url == "http://127.0.0.1:8000/v1"
    assert config.model_name == "qwen3-4b"
    assert config.max_steps == 8
