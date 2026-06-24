from unittest.mock import MagicMock, patch

from marketplace_pipeline.domain.exceptions import ProxyQuotaExhaustedError
from marketplace_pipeline.domain.services.proxy_prerequisites import (
    ProxyPrerequisites,
    validate_proxy_prerequisites,
)
from marketplace_pipeline.interfaces.cli.main import main


def test_main_success() -> None:
    with patch("marketplace_pipeline.interfaces.cli.main.Container") as container_cls:
        result = MagicMock()
        result.collection_result.collected_count = 10
        result.enriched_products = [1, 2]
        result.crm_tasks = [1]
        result.output_path = None
        container_cls.return_value.run_pipeline_use_case.return_value.execute.return_value = (
            result
        )
        assert main() == 0


def test_main_failure() -> None:
    with patch("marketplace_pipeline.interfaces.cli.main.Container") as container_cls:
        container_cls.return_value.run_pipeline_use_case.return_value.execute.side_effect = (
            RuntimeError("boom")
        )
        assert main() == 1


def test_main_proxy_quota_exhausted() -> None:
    with patch("marketplace_pipeline.interfaces.cli.main.Container") as container_cls:
        container_cls.return_value.validate_proxy_prerequisites.side_effect = (
            ProxyQuotaExhaustedError("PROXY_MARKET traffic exhausted")
        )
        assert main() == 1


def test_validate_proxy_prerequisites_skips_without_proxy_list() -> None:
    checker = MagicMock()
    validate_proxy_prerequisites(
        ProxyPrerequisites(mock_parser=False, ozon_proxy_list="", proxy_market_api_key="k"),
        quota_checker=checker,
    )
    checker.check_quota_available.assert_not_called()


def test_validate_proxy_prerequisites_skips_without_checker() -> None:
    validate_proxy_prerequisites(
        ProxyPrerequisites(
            mock_parser=False,
            ozon_proxy_list="http://user:pass@host:10000",
            proxy_market_api_key="k",
        ),
        quota_checker=None,
    )
