"""Output contract: exactly one valid label per row (README 12.1, 17)."""

from pydantic import BaseModel, Field


class Prediction(BaseModel):
    row_id: int = Field(ge=1)
    invoice_number: str = Field(min_length=1)
    voucher_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    needs_review: bool = False
    top_k: list = Field(default_factory=list)
    evidence: list = Field(default_factory=list)

    def model_post_init(self, _context) -> None:
        from .labels import LABEL_NAMES

        if self.voucher_type not in LABEL_NAMES:
            raise ValueError("unknown voucher_type: " + self.voucher_type)
