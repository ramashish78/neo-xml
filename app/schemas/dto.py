from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("value is not a valid email address")
        return value


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UserCreate(BaseModel):
    email: str
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    roles: list[str] = Field(min_length=1)
    workspace_ids: list[str] = []

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("value is not a valid email address")
        return value


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    roles: list[str] | None = None
    workspace_ids: list[str] | None = None
    status: Literal["active", "disabled"] | None = None


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    status: Literal["active", "archived"] | None = None
    schema_file_id: str | None = None
    brex_file_id: str | None = None
    ste_file_id: str | None = None


class DataModuleCreate(BaseModel):
    workspace_id: str
    dmc: str | None = None
    title: str = Field(min_length=1, max_length=300)
    type: str = Field(default="descriptive", min_length=1, max_length=40)
    language: str = Field(default="en", min_length=1, max_length=10)
    applicability: str | None = Field(default=None, max_length=500)
    xml_content: str | None = None
    file_id: str | None = None
    graphic_ids: list[str] = []

    @model_validator(mode="after")
    def one_source(self):
        if bool(self.xml_content) == bool(self.file_id):
            raise ValueError("Provide xml_content or file_id")
        return self


class DataModulePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    type: str | None = Field(default=None, min_length=1, max_length=40)
    language: str | None = Field(default=None, min_length=1, max_length=10)
    applicability: str | None = Field(default=None, max_length=500)
    graphic_ids: list[str] | None = None
    xml_content: str | None = None


class RevisionCreate(BaseModel):
    xml_content: str | None = None
    file_id: str | None = None
    comment: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def one_source(self):
        if bool(self.xml_content) == bool(self.file_id):
            raise ValueError("Provide xml_content or file_id")
        return self


class ReviewCreate(BaseModel):
    object_id: str
    object_type: Literal["data_module"] = "data_module"
    assigned_to: str
    due_date: datetime | None = None


class CommentCreate(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    location: str | None = Field(default=None, max_length=200)


class ReviewDecision(BaseModel):
    decision: Literal["approve", "changes_requested"]
    comment: str | None = Field(default=None, max_length=4000)


class TrackChangeCreate(BaseModel):
    revision_id: str
    change_type: Literal["insert", "delete", "modify"]
    location: str = Field(min_length=1, max_length=200)
    original_text: str | None = None
    new_text: str | None = None


class PublicationCreate(BaseModel):
    workspace_id: str
    pm_code: str | None = None
    title: str = Field(min_length=1, max_length=300)
    data_module_ids: list[str] = Field(min_length=1)


class PublicationPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    data_module_ids: list[str] | None = None


class TransformRequest(BaseModel):
    publication_id: str
    scenario: Literal["web", "pdf", "ietp"]


class DmrlEntry(BaseModel):
    dmc: str
    title: str | None = None


class DmrlCreate(BaseModel):
    workspace_id: str
    code: str | None = None
    title: str = Field(min_length=1, max_length=300)
    entries: list[DmrlEntry] = Field(min_length=1)


class DdnCreate(BaseModel):
    workspace_id: str
    code: str | None = None
    title: str = Field(min_length=1, max_length=300)
    dmrl_id: str
    recipient: str = Field(min_length=1, max_length=200)
