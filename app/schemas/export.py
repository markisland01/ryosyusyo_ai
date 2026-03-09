from pydantic import BaseModel


class ExportRequest(BaseModel):
    video_id: int
    format: str = "generic"  # generic, yayoi, freee, moneyforward
    encoding: str = "utf-8-sig"  # utf-8-sig or shift_jis
