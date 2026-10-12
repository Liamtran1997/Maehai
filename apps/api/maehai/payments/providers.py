"""Payment providers sit behind small interfaces so they can be swapped without touching order code."""
from dataclasses import dataclass
from typing import Protocol


@dataclass
class SlipResult:
    """ok=True: auto-approve. ok=False: auto-reject. ok=None: a person must look at the slip."""

    ok: bool | None
    detail: str = ""


class SlipVerifier(Protocol):
    def verify(self, payment) -> SlipResult: ...


class ManualReview:
    """Default: every slip waits for staff. Replace with a SlipOK/EasySlip adapter once API keys exist."""

    def verify(self, payment) -> SlipResult:
        return SlipResult(ok=None, detail="manual review")
