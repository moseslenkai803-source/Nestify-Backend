import logging
import time

from app.core.runtime_config import validate_runtime_configuration
from app.services.email_outbox_worker import EmailOutboxWorker
from app.services.email_service import EmailService


POLL_INTERVAL_SECONDS = 2

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    validate_runtime_configuration()
    EmailService.validate_configuration()
    worker = EmailOutboxWorker()
    logger.info("Email outbox worker started")

    try:
        while True:
            try:
                processed = worker.process_one()

                if not processed:
                    time.sleep(POLL_INTERVAL_SECONDS)

            except Exception:
                # Keep transient database or polling failures from
                # terminating the worker or causing a tight retry loop.
                logger.exception("Email outbox polling failed")
                time.sleep(POLL_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        logger.info("Email outbox worker stopped")


if __name__ == "__main__":
    main()
