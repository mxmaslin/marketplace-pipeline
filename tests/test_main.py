from unittest.mock import MagicMock, patch

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
