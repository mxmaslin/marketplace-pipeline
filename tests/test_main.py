from unittest.mock import patch

from marketplace_pipeline.interfaces.cli.main import main


def test_main_success() -> None:
    with patch("marketplace_pipeline.interfaces.cli.main.Container") as container_cls:
        use_case = container_cls.return_value.run_pipeline_use_case.return_value
        use_case.execute.return_value.collection_result.collected_count = 10
        use_case.execute.return_value.enriched_products = [1, 2]
        use_case.execute.return_value.crm_tasks = [1]
        use_case.execute.return_value.output_path = None
        assert main() == 0


def test_main_failure() -> None:
    with patch("marketplace_pipeline.interfaces.cli.main.Container") as container_cls:
        container_cls.return_value.run_pipeline_use_case.return_value.execute.side_effect = (
            RuntimeError("boom")
        )
        assert main() == 1
