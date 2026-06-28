from __future__ import annotations

import time
from datetime import datetime
from typing import Callable

import httpx
import structlog
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import Settings
from filters import filter_slots
from models import AppointmentSlot, MonitorResult
from notifier import IST, TelegramNotifier
from parser import AppointmentParseError, detect_anti_bot, parse_slots_from_html
from storage import NotifiedSlotStore


LOGGER = structlog.get_logger(__name__)


class SuperhealthMonitor:
    def __init__(
        self,
        settings: Settings,
        notifier: TelegramNotifier,
        store: NotifiedSlotStore,
    ) -> None:
        self.settings = settings
        self.notifier = notifier
        self.store = store

    def run_forever(self) -> None:
        while True:
            self.run_once()
            time.sleep(self.settings.check_interval_seconds)

    def run_once(self) -> MonitorResult:
        started_at = datetime.now(IST)
        timer_start = time.perf_counter()
        LOGGER.info("monitor_started", start_time=started_at.isoformat())

        slots_found = 0
        matching_slots_found = 0
        notifications_sent = 0
        source = "http"

        try:
            html, source = self._fetch_html_with_fallback()
            slots, source = self._parse_slots_with_fallback(html, source)
            matching_slots = filter_slots(slots, self.settings.slot_filter)
            slots_found = len(slots)
            matching_slots_found = len(matching_slots)

            LOGGER.info(
                "slots_parsed",
                slots_found=slots_found,
                matching_slots_found=matching_slots_found,
                slot_filter=self.settings.slot_filter.description,
                source=source,
            )

            for slot in matching_slots:
                if self.store.has_notified(slot):
                    LOGGER.info("duplicate_slot_skipped", slot_key=slot.notification_key)
                    continue

                detected_at = datetime.now(IST)
                self.notifier.send_slot_alert(slot, detected_at)
                if not self.settings.dry_run:
                    self.store.mark_notified(slot, detected_at)
                    notifications_sent += 1

        except AppointmentParseError as exc:
            LOGGER.error("parse_failed", error=str(exc), exc_info=True)
        except RetryError as exc:
            LOGGER.error("fetch_retry_exhausted", error=str(exc), exc_info=True)
        except Exception as exc:
            LOGGER.error("monitor_failed", error=str(exc), exc_info=True)

        return self._result(
            started_at,
            timer_start,
            slots_found,
            matching_slots_found,
            notifications_sent,
            source,
        )

    def _fetch_html_with_fallback(self) -> tuple[str, str]:
        try:
            return self._fetch_http(), "http"
        except Exception as exc:
            LOGGER.warning("http_fetch_failed", error=str(exc), exc_info=True)
            if not self.settings.use_playwright_fallback:
                raise
            return self._fetch_playwright(), "playwright"

    def _fetch_http(self) -> str:
        fetch = self._retryable(self._fetch_http_once)
        return fetch()

    def _fetch_http_once(self) -> str:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        with httpx.Client(timeout=self.settings.request_timeout_seconds, follow_redirects=True) as client:
            response = client.get(self.settings.appointment_url, headers=headers)
            response.raise_for_status()
            return response.text

    def _parse_slots_with_fallback(
        self,
        html: str,
        source: str,
    ) -> tuple[list[AppointmentSlot], str]:
        if detect_anti_bot(html):
            LOGGER.warning("anti_bot_detected", source=source)
            return [], source

        try:
            return (
                parse_slots_from_html(
                    html,
                    self.settings.doctor_name,
                    self.settings.appointment_url,
                    self.settings.doctor_slug,
                ),
                source,
            )
        except AppointmentParseError as exc:
            if source != "http" or not self.settings.use_playwright_fallback:
                raise

            LOGGER.warning(
                "http_parse_failed_trying_playwright",
                error=str(exc),
                exc_info=True,
            )
            playwright_html = self._fetch_playwright()
            if detect_anti_bot(playwright_html):
                LOGGER.warning("anti_bot_detected", source="playwright")
                return [], "playwright"
            return (
                parse_slots_from_html(
                    playwright_html,
                    self.settings.doctor_name,
                    self.settings.appointment_url,
                    self.settings.doctor_slug,
                ),
                "playwright",
            )

    def _fetch_playwright(self) -> str:
        fetch = self._retryable(self._fetch_playwright_once)
        return fetch()

    def _fetch_playwright_once(self) -> str:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright fallback requested but playwright is not installed."
            ) from exc

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.settings.headless)
            try:
                page = browser.new_page()
                page.goto(
                    self.settings.appointment_url,
                    wait_until="domcontentloaded",
                    timeout=int(self.settings.request_timeout_seconds * 1000),
                )
                try:
                    page.wait_for_load_state(
                        "networkidle",
                        timeout=int(self.settings.request_timeout_seconds * 1000),
                    )
                except PlaywrightTimeoutError:
                    LOGGER.warning("playwright_networkidle_timeout")
                page.wait_for_timeout(1500)
                return page.content()
            finally:
                browser.close()

    def _retryable(self, function: Callable[[], str]) -> Callable[[], str]:
        return retry(
            retry=retry_if_exception_type(
                (
                    httpx.HTTPError,
                    RuntimeError,
                    TimeoutError,
                )
            ),
            wait=wait_exponential(
                multiplier=self.settings.retry_base_seconds,
                min=self.settings.retry_base_seconds,
                max=30,
            ),
            stop=stop_after_attempt(self.settings.max_retries),
            reraise=True,
            before_sleep=lambda retry_state: LOGGER.warning(
                "retrying_transient_failure",
                attempt=retry_state.attempt_number,
                error=str(retry_state.outcome.exception())
                if retry_state.outcome
                else None,
            ),
        )(function)

    @staticmethod
    def _result(
        started_at: datetime,
        timer_start: float,
        slots_found: int,
        matching_slots_found: int,
        notifications_sent: int,
        source: str,
    ) -> MonitorResult:
        ended_at = datetime.now(IST)
        response_time_ms = int((time.perf_counter() - timer_start) * 1000)
        LOGGER.info(
            "monitor_finished",
            start_time=started_at.isoformat(),
            end_time=ended_at.isoformat(),
            slots_found=slots_found,
            matching_slots_found=matching_slots_found,
            notifications_sent=notifications_sent,
            response_time_ms=response_time_ms,
            source=source,
        )
        return MonitorResult(
            slots_found=slots_found,
            matching_slots_found=matching_slots_found,
            notifications_sent=notifications_sent,
            response_time_ms=response_time_ms,
            source=source,
        )
