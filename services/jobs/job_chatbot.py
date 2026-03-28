"""
Handles Naukri's chatbot-based easy apply drawer.

Flow after clicking Apply:
  1. Chatbot drawer opens with a question
  2. Answer each question (text input or clickable chip)
  3. Repeat until "Thank you for your response" appears
  4. Return True — caller marks the job as applied

Pre-configured answers live at the top of this file.
Update ANSWERS or CHIP_ANSWERS when new question types appear.
"""

import logging
import time

from playwright.sync_api import Page

from core.utils import human_type
from services.locators.naukri_locators import ChatbotLocators

logger = logging.getLogger(__name__)

MAX_QUESTIONS   = 20    # safety cap — stop after this many exchanges
ANSWER_DELAY    = 0.8   # seconds between typing and clicking send
WAIT_NEXT_Q     = 3     # seconds to wait for next bot message after answering

# ── Pre-configured answers ─────────────────────────────────────────────────────
# Keys are lowercase substrings matched against the bot's question text.
# Order matters — more specific keys should come first.

TEXT_ANSWERS: dict[str, str] = {
    # Experience
    "years of experience":          "2",
    "total experience":             "2",
    "how many years":               "2",
    "experience do you have":       "2",
    "years experience":             "2",

    # Portfolio / links
    "portfolio":                    "https://romeshjain.netlify.app/",
    "website":                      "https://romeshjain.netlify.app/",
    "profile link":                 "https://romeshjain.netlify.app/",
    "personal website":             "https://romeshjain.netlify.app/",
    "github":                       "https://github.com/RomeshJain7",

    # Notice period
    "notice period":                "30",
    "serving notice":               "No",

    # Salary
    "current ctc":                  "5",
    "current salary":               "5",
    "current package":              "5",
    "expected ctc":                 "8",
    "expected salary":              "8",
    "expected package":             "8",

    # Location
    "current location":             "Indore",
    "preferred location":           "Remote",

    # Miscellaneous
    "gender":                       "Male",
    "highest qualification":        "B.Tech",
    "degree":                       "B.Tech",
}

# For chip / button questions — matched the same way, value is the chip text to click.
CHIP_ANSWERS: dict[str, str] = {
    "relocate":                     "Yes",
    "relocation":                   "Yes",
    "work from office":             "Yes",
    "hybrid":                       "Yes",
    "immediate joiner":             "No",
    "fresher":                      "No",
    "currently employed":           "Yes",
}


class JobChatbot:
    def __init__(self, page: Page):
        self.page = page

    # ── Public ────────────────────────────────────────────────────────────────

    def handle(self) -> bool:
        """Drive the chatbot from open drawer to 'Thank you' confirmation.

        Returns True if application was submitted, False if something went wrong.
        """
        # Wait for drawer to open
        try:
            self.page.wait_for_selector(ChatbotLocators.DRAWER, timeout=8000)
        except Exception:
            logger.warning("Chatbot drawer did not open")
            return False

        logger.info("Chatbot drawer opened — starting Q&A")
        prev_msg_count = 0

        for turn in range(MAX_QUESTIONS):
            # Wait for a new bot message
            new_msg_count = self._wait_for_new_message(prev_msg_count)
            if new_msg_count == prev_msg_count:
                logger.warning("No new bot message after turn %d — stopping", turn)
                break

            prev_msg_count = new_msg_count

            # Read the latest question
            question = self._get_last_question()
            logger.info("Bot: %s", question[:120])

            # Check for success
            if ChatbotLocators.SUCCESS_TEXT.lower() in question.lower():
                logger.info("Chatbot complete — 'Thank you' received")
                time.sleep(1.5)
                return True

            # Try chip answer first, then text input
            answered = self._try_chip_answer(question) or self._try_text_answer(question)

            if not answered:
                logger.warning("No answer found for: '%s' — skipping question", question[:80])
                # Try to submit whatever is in the text field anyway
                self._click_send()

        logger.warning("Reached max turns (%d) without completion", MAX_QUESTIONS)
        return False

    # ── Private ───────────────────────────────────────────────────────────────

    def _wait_for_new_message(self, prev_count: int, timeout: int = 10) -> int:
        """Wait until a new bot message appears. Returns new count."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            count = self.page.locator(ChatbotLocators.ALL_BOT_MSGS).count()
            if count > prev_count:
                time.sleep(0.5)   # let message fully render
                return count
            time.sleep(0.4)
        return prev_count

    def _get_last_question(self) -> str:
        try:
            el = self.page.locator(ChatbotLocators.LAST_BOT_MSG).last
            return el.inner_text().strip()
        except Exception:
            return ""

    def _try_chip_answer(self, question: str) -> bool:
        """Click a chip option if the question matches a CHIP_ANSWERS key."""
        q = question.lower()
        answer_text = None
        for keyword, answer in CHIP_ANSWERS.items():
            if keyword in q:
                answer_text = answer
                break

        if not answer_text:
            return False

        for selector in ChatbotLocators.CHIP_OPTIONS:
            chips = self.page.locator(selector)
            count = chips.count()
            for i in range(count):
                chip = chips.nth(i)
                try:
                    text = chip.inner_text().strip().lower()
                    if text == answer_text.lower():
                        chip.click()
                        logger.info("Chip answer: '%s'", answer_text)
                        time.sleep(ANSWER_DELAY)
                        return True
                except Exception:
                    continue

        # Chips exist but exact match not found — click first visible chip
        for selector in ChatbotLocators.CHIP_OPTIONS:
            chip = self.page.locator(selector).first
            if chip.count() and chip.is_visible():
                chip.click()
                logger.info("Chip fallback: clicked first available option")
                time.sleep(ANSWER_DELAY)
                return True

        return False

    def _try_text_answer(self, question: str) -> bool:
        """Type an answer into the text field if the question matches TEXT_ANSWERS."""
        q = question.lower()
        answer_text = None
        for keyword, answer in TEXT_ANSWERS.items():
            if keyword in q:
                answer_text = answer
                break

        # Fallback: if text input is available and no match, type "2" as a safe default
        text_field = self.page.locator(ChatbotLocators.TEXT_INPUT).first
        if not text_field.count() or not text_field.is_visible():
            return False

        if not answer_text:
            logger.warning("No text answer for '%s' — typing default '2'", question[:60])
            answer_text = "2"

        # Clear existing content and type answer with human rhythm
        text_field.evaluate("el => el.innerText = ''")
        human_type(self.page, text_field, answer_text)
        logger.info("Text answer: '%s'", answer_text)
        time.sleep(ANSWER_DELAY)

        return self._click_send()

    def _click_send(self) -> bool:
        """Click the Send/Save button. Returns True if clicked."""
        try:
            btn = self.page.locator(ChatbotLocators.SEND_BTN).first
            if btn.count() and btn.is_visible():
                btn.click()
                time.sleep(WAIT_NEXT_Q)
                return True
        except Exception as e:
            logger.debug("Send click failed: %s", e)
        return False
