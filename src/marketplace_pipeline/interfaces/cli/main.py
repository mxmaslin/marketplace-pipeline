from __future__ import annotations

import logging
import sys

from marketplace_pipeline.domain.exceptions import ProxyQuotaExhaustedError
from marketplace_pipeline.infrastructure.composition.container import Container
from marketplace_pipeline.infrastructure.config.settings import get_settings


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)

    try:
        container = Container(settings)
        container.validate_proxy_prerequisites()
        result = container.run_pipeline_use_case().execute()
    except ProxyQuotaExhaustedError as exc:
        logging.error("%s", exc)
        return 1
    except Exception:
        logging.exception("Pipeline failed")
        return 1

    collection = result.collection_result
    print(
        f"Done: collected={collection.collected_count}, "
        f"classified={len(result.enriched_products)}, "
        f"crm_tasks={len(result.crm_tasks)}"
    )
    if result.output_path:
        print(f"Output: {result.output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
