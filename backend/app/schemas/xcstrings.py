from pydantic import BaseModel


class ImportOptions(BaseModel):
    conflict: str = "skip"  # "skip" | "overwrite"
