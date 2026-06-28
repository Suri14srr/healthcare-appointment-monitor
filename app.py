from __future__ import annotations

import structlog

from config import load_settings
from logging_config import configure_logging
from monitor import SuperhealthMonitor
from notifier import TelegramNotifier
from storage import NotifiedSlotStore


def main() -> None:
    settings = load_settings()
    configure_logging(settings.logs_dir, settings.log_level)
    logger = structlog.get_logger(__name__)

    try:
        settings.validate()
    except ValueError as exc:
        logger.error("configuration_invalid", error=str(exc))
        raise SystemExit(2) from exc

    monitor = SuperhealthMonitor(
        settings=settings,
        notifier=TelegramNotifier(
            bot_token=settings.telegram_bot_token,
            chat_id=settings.telegram_chat_id,
            dry_run=settings.dry_run,
        ),
        store=NotifiedSlotStore(settings.notified_slots_file),
    )

    if settings.run_once:
        monitor.run_once()
    else:
        monitor.run_forever()


if __name__ == "__main__":
    main()
