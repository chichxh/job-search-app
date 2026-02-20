from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

AllowedExtraParamValue = str | int | bool | list[str | int] | None


class HHImportRequest(BaseModel):
    text: str = Field(min_length=1, max_length=255)
    area: Optional[int] = None
    schedule: Optional[str] = Field(default=None, max_length=50)
    experience: Optional[str] = Field(default=None, max_length=50)
    salary_from: Optional[int] = Field(default=None, ge=0)
    salary_to: Optional[int] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, max_length=10)
    per_page: int = Field(default=20, ge=1, le=100)
    pages_limit: int = Field(default=3, ge=1, le=20)
    fetch_details: bool = True
    extra_params: dict[str, AllowedExtraParamValue] | None = None

    @field_validator("extra_params")
    @classmethod
    def validate_extra_params(cls, value: dict[str, AllowedExtraParamValue] | None) -> dict[str, AllowedExtraParamValue] | None:
        if value is None:
            return value

        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("extra_params keys must be strings")

            if item is None or isinstance(item, (str, int, bool)):
                continue

            if isinstance(item, list):
                if not all(isinstance(entry, (str, int)) for entry in item):
                    raise ValueError("extra_params list values must contain only strings or integers")
                continue

            raise ValueError("extra_params supports only str|int|bool|list[str|int]|None values")

        return value


class HHImportTaskResponse(BaseModel):
    task_id: str
