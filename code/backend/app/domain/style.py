from typing import Literal

from pydantic import BaseModel, Field, RootModel


BuiltinStyle = Literal["realism", "suspense", "romance", "comedy", "short_drama"]


class BuiltinStyleSource(BaseModel):
    kind: Literal["builtin"]
    builtin_style: BuiltinStyle


class CustomTextStyleSource(BaseModel):
    kind: Literal["custom_text"]
    style_text: str = Field(min_length=1)


class ReferenceScriptsStyleSource(BaseModel):
    kind: Literal["reference_scripts"]
    reference_file_ids: list[str] = Field(min_length=1, max_length=3)


StyleSource = BuiltinStyleSource | CustomTextStyleSource | ReferenceScriptsStyleSource


class StyleSourceEnvelope(RootModel[StyleSource]):
    root: StyleSource

