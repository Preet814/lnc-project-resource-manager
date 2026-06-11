"""Admin engineer-profile API request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from prm.domain.enums import ProficiencyLevel, ResourceWorkStatus, SkillCategory


class CreateEmployeeRequest(BaseModel):
    user_id: int
    full_name: str = Field(min_length=1)
    email: str = Field(min_length=1)
    department: str = Field(min_length=1)
    designation: str = Field(min_length=1)


class UpdateEmployeeRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1)
    email: str | None = Field(default=None, min_length=1)
    department: str | None = Field(default=None, min_length=1)
    designation: str | None = Field(default=None, min_length=1)


class AssignManagerRequest(BaseModel):
    engineer_user_id: int
    manager_user_id: int


class EmployeeResponse(BaseModel):
    id: int
    manager_id: int | None
    full_name: str
    email: str
    department: str
    designation: str
    work_status: ResourceWorkStatus
    is_active: bool
    current_utilisation_percent: int
    created_at: datetime


class EngineerSummaryResponse(BaseModel):
    id: int
    full_name: str
    department: str
    designation: str
    work_status: ResourceWorkStatus
    is_active: bool


class EngineerListResponse(BaseModel):
    engineers: list[EngineerSummaryResponse]
    total: int
    allocated_count: int
    bench_count: int


class AddUserSkillRequest(BaseModel):
    skill_name: str = Field(min_length=1)
    category: SkillCategory
    proficiency: ProficiencyLevel


class UpdateUserSkillRequest(BaseModel):
    proficiency: ProficiencyLevel


class UserSkillResponse(BaseModel):
    user_skill_id: int
    skill_id: int
    skill_name: str
    category: SkillCategory
    proficiency: ProficiencyLevel
    assigned_at: datetime


class UserSkillListResponse(BaseModel):
    skills: list[UserSkillResponse]
