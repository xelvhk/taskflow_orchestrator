from dataclasses import dataclass


class RetryableTaskError(Exception):
    """Raised when a task can be retried."""


class NonRetryableTaskError(Exception):
    """Raised when retrying would not help."""


@dataclass
class SummarizationAdapter:
    max_words: int = 24

    def summarize(self, text: str) -> dict[str, str | int]:
        normalized = " ".join(text.split())
        if "__retry__" in normalized:
            raise RetryableTaskError("Mock retry trigger found in text.")
        if "__fail__" in normalized:
            raise NonRetryableTaskError("Mock non-retryable failure trigger found in text.")

        words = normalized.split()
        summary = " ".join(words[: self.max_words])
        if len(words) > self.max_words:
            summary += "..."
        return {
            "summary": summary,
            "input_words": len(words),
            "summary_words": len(summary.split()),
        }
