"""Input sanitisation and prompt injection filtering utilities.

This module provides classes and functions for detecting and sanitising potential prompt
injection attempts in user input, as well as general input cleaning for AI and web applications.
It includes filters recommended by OWASP for handling untrusted input in AI systems.

Typical usage example:
    filter = PromptInjectionFilter()
    is_injection, reason = filter.detect_injection(user_text)
    safe_text = filter.sanitize_input(user_text)
"""

import re

from survey_assist_utils.logging import get_logger

logger = get_logger(__name__, level="INFO")

MIN_WORD_LEN = 3


class PromptInjectionFilter:
    """Detect and sanitize potential prompt injection attempts in user input.
    This class is reccomended by OWASP for handling untrusted input in AI applications.
    See:
    https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html.
    """

    def __init__(self):
        self.dangerous_patterns = [
            r"ignore\s+(all\s+)?previous\s+instructions?",
            r"you\s+are\s+now\s+(in\s+)?developer\s+mode",
            r"system\s+override",
            r"reveal\s+prompt",
            r"override\s+instructions",
        ]

        # Fuzzy matching for typoglycemia attacks
        self.fuzzy_patterns = [
            "ignore",
            "bypass",
            "override",
            "reveal",
            "delete",
            "system",
        ]

    def detect_injection(self, text: str | None) -> tuple[bool, str | None]:
        """Return (is_injection_detected, reason)."""
        text = "" if text is None else text

        # Standard pattern matching
        for pattern in self.dangerous_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                reason = f"Matched dangerous regex pattern: {pattern}"
                return True, reason

        # Fuzzy matching
        words = re.findall(r"\b\w+\b", text.lower())
        for word in words:
            for pattern in self.fuzzy_patterns:
                if self._is_similar_word(word, pattern):
                    reason = f"Fuzzy match: input word '{word}' similar to '{pattern}'"
                    return True, reason

        return False, None

    def _is_similar_word(self, word: str | None, target: str) -> bool:
        """Check if word is a typoglycemia variant of target."""
        if word is None:
            return False

        if len(word) != len(target) or len(word) < MIN_WORD_LEN:
            return False
        return (
            word[0] == target[0]
            and word[-1] == target[-1]
            and sorted(word[1:-1]) == sorted(target[1:-1])
        )

    def sanitize_input(self, text: str | None, *, max_len: int = 500) -> str:
        """Sanitize user input by removing dangerous patterns
        and normalizing whitespace.
        """
        if text is None:
            return ""

        # 1) Normalize
        text = re.sub(r"\s+", " ", text)  # collapse whitespace
        text = re.sub(r"(.)\1{3,}", r"\1", text)  # squash excessive repeats

        # Find earliest dangerous regex match
        earliest = None
        for pat in self.dangerous_patterns:
            m = re.search(pat, text, flags=re.IGNORECASE)
            if m:
                start = m.start()
                earliest = start if earliest is None else min(earliest, start)

        # Cut everything from the first trigger onward
        if earliest is not None:
            text = text[:earliest].rstrip()
            # Add FILTERED to the cut
            text += " FILTERED CONTENT REMOVED"

        # Final cap length
        return text[:max_len]


class SafeInputFilter(PromptInjectionFilter):
    """A safe input filter that extends the PromptInjectionFilter to include
    additional sanitization steps for general user input.
    """

    # ruff: noqa: RUF001
    SAFE_CHARS_PATTERN = re.compile(r"[^A-Za-zÀ-ÿ0-9\s.,!?;:'\"()\-\–—£€%&]")

    SMART_QUOTE_MAP = str.maketrans(
        {
            "’": "'",
            "‘": "'",
            "“": '"',
            "”": '"',
        }
    )

    # ruff: enable: RUF001
    def sanitize_input(self, text: str | None, *, max_len: int = 500) -> str:
        if text is None:
            return ""
        original_text = text
        # Normalize spaces and repetition
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"(.)\1{3,}", r"\1", text)

        # Replace smart quotes with standard quotes
        text = text.translate(self.SMART_QUOTE_MAP)

        # Remove control/invisible characters
        text = re.sub(r"[\x00-\x1F\x7F-\x9F\u200B-\u200D\uFEFF]", "", text)

        # Remove unsafe special characters
        text = re.sub(self.SAFE_CHARS_PATTERN, "", text)

        # Log any changes made
        if text != original_text:
            logger.info("Input sanitized by SafeInputFilter.")

        # Cap length
        return text[:max_len]
