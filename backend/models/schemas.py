"""All Pydantic models/schemas — extracted verbatim from the original server.py."""
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Union, Dict, Any
from datetime import date


class UserRole:
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    RESOURCE = "resource"
    CONTRACTOR = "contractor"
    CLIENT = "client"


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str = UserRole.RESOURCE
    resource_id: Optional[str] = None
    must_change_password: bool = True
    allowed_project_ids: List[str] = []


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    resource_id: Optional[str] = None
    must_change_password: Optional[bool] = False
    allowed_project_ids: List[str] = []


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenWithUser(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


class ResourceCreate(BaseModel):
    name: str
    role: str
    standard_capacity: int = 100
    avatar_url: Optional[str] = None


class ResourceUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    standard_capacity: Optional[int] = None
    avatar_url: Optional[str] = None


class ResourceResponse(BaseModel):
    id: str
    name: str
    role: str
    standard_capacity: int
    avatar_url: Optional[str] = None


class ProjectStatus:
    ACTIVE = "Active"
    PIPELINE = "Pipeline"
    COMPLETED = "Completed"


class ProjectCreate(BaseModel):
    name: str
    client_name: str
    main_contact_name: Optional[str] = None
    main_contact_email: Optional[str] = None
    main_contact_phone: Optional[str] = None
    main_contact_role: Optional[str] = None
    status: str
    start_date: date
    end_date: date
    is_draft: bool = False
    budgeted_hours: Optional[float] = None
    phases: Optional[List[dict]] = None
    project_lead_id: Optional[str] = None
    google_drive_url: Optional[str] = None
    project_objective: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    client_name: Optional[str] = None
    main_contact_name: Optional[str] = None
    main_contact_email: Optional[str] = None
    main_contact_phone: Optional[str] = None
    main_contact_role: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    phases: Optional[List[dict]] = None
    is_draft: Optional[bool] = None
    status_summary: Optional[str] = None
    status_summary_updated_at: Optional[str] = None
    budgeted_hours: Optional[float] = None
    project_lead_id: Optional[str] = None
    google_drive_url: Optional[str] = None
    project_objective: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    client_name: str
    main_contact_name: Optional[str] = None
    main_contact_email: Optional[str] = None
    main_contact_phone: Optional[str] = None
    main_contact_role: Optional[str] = None
    status: str
    start_date: str
    end_date: str
    phases: Optional[List[dict]] = None
    created_at: Optional[str] = None
    is_draft: Optional[bool] = False
    status_summary: Optional[str] = None
    status_summary_updated_at: Optional[str] = None
    budgeted_hours: Optional[float] = None
    actual_hours: Optional[float] = 0.0
    health: Optional[str] = None
    schedule_status: Optional[str] = None
    actual_progress: Optional[int] = None
    project_lead_id: Optional[str] = None
    project_lead_name: Optional[str] = None
    google_drive_url: Optional[str] = None
    project_objective: Optional[str] = None
    wbs_summary: Optional[dict] = None  # NEW (FIX #2): WBS summary


SCHEDULE_STATUS_OPTIONS = ["On Track", "Delayed", "Ahead of Schedule", "At Risk"]
HEALTH_STATUS_OPTIONS = ["Green", "Amber", "Red"]


class StatusUpdateCreate(BaseModel):
    project_id: str
    health: str = "Green"
    schedule_status: str = "On Track"
    actual_progress: Optional[int] = None
    accomplishments: Optional[str] = None
    blockers: Optional[str] = None
    next_steps: Optional[str] = None
    notes: Optional[str] = None
    new_risks: Optional[List[Dict[str, Any]]] = None


class StatusUpdateResponse(BaseModel):
    id: str
    project_id: str
    updated_by: str
    updated_by_name: Optional[str] = None
    update_date: str
    health: str
    schedule_status: str
    actual_progress: int
    accomplishments: Optional[str] = None
    blockers: Optional[Union[str, list]] = None
    next_steps: Optional[str] = None
    notes: Optional[str] = None
    ai_generated_summary: Optional[str] = None
    progress_summary: Optional[str] = None
    next_week_plan: Optional[str] = None
    week_start_date: Optional[str] = None
    created_at: str
    edited_by: Optional[str] = None
    edited_at: Optional[str] = None


class StatusUpdateEdit(BaseModel):
    health: Optional[str] = None
    schedule_status: Optional[str] = None
    actual_progress: Optional[int] = None
    accomplishments: Optional[str] = None
    blockers: Optional[str] = None
    next_steps: Optional[str] = None
    notes: Optional[str] = None


ALLOCATION_ROLES = [
    "Project Lead",
    "Developer",
    "Designer",
    "QA Engineer",
    "Consultant",
    "Analyst",
    "Support",
    "Architect",
    "Product Manager",
]


class PhaseAllocation(BaseModel):
    """Phase-specific allocation percentage for a resource."""
    phase_id: str
    percentage: Optional[int] = None
    hours: Optional[int] = None


class AllocationCreate(BaseModel):
    resource_id: str
    project_id: str
    start_date: date
    end_date: date
    percentage: Optional[int] = None
    hours: Optional[int] = None
    allocation_type: str = "percentage"
    role: Optional[str] = None
    actual_percentage: Optional[int] = None
    confirmation_status: str = "Pending"
    phase_names: Optional[List[str]] = None
    phase_allocations: Optional[List[PhaseAllocation]] = []  # NEW: Per-phase allocations


class AllocationUpdate(BaseModel):
    resource_id: Optional[str] = None
    project_id: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    percentage: Optional[int] = None
    hours: Optional[int] = None
    allocation_type: Optional[str] = None
    role: Optional[str] = None
    actual_percentage: Optional[int] = None
    confirmation_status: Optional[str] = None
    phase_names: Optional[List[str]] = None
    phase_allocations: Optional[List[dict]] = None  # NEW: Per-phase allocations


class AllocationResponse(BaseModel):
    id: str
    resource_id: str
    project_id: str
    start_date: str
    end_date: str
    percentage: int
    hours: Optional[int] = None
    allocation_type: Optional[str] = "percentage"
    role: Optional[str] = None
    actual_percentage: Optional[int] = None
    confirmation_status: Optional[str] = "Pending"
    resource_name: Optional[str] = None
    resource_role: Optional[str] = None
    project_name: Optional[str] = None
    client_name: Optional[str] = None
    phase_allocations: Optional[List[dict]] = []  # NEW: Per-phase allocations


class RiskCreate(BaseModel):
    description: str
    impact: str
    probability: str
    mitigation: Optional[str] = None
    status: Optional[str] = "Active"
    category: Optional[str] = "Risk"
    impact_areas: Optional[List[str]] = None
    skip_ai_polish: Optional[bool] = False


class RiskUpdate(BaseModel):
    description: Optional[str] = None
    impact: Optional[str] = None
    probability: Optional[str] = None
    mitigation: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    impact_areas: Optional[List[str]] = None
    skip_ai_polish: Optional[bool] = False


class RiskResponse(BaseModel):
    id: str
    project_id: str
    description: str
    impact: str
    probability: str
    mitigation: Optional[str] = None
    status: Optional[str] = "Active"
    category: Optional[str] = "Risk"
    impact_areas: Optional[List[str]] = None
    ai_polished: Optional[bool] = False
    source_status_update_id: Optional[str] = None
    created_at: Optional[str] = None


class BulkRiskCreate(BaseModel):
    project_id: str
    risks: List[RiskCreate]


class LeaveCreate(BaseModel):
    resource_id: str
    start_date: date
    end_date: date
    type: str
    notes: Optional[str] = None


class LeaveUpdate(BaseModel):
    resource_id: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    type: Optional[str] = None
    notes: Optional[str] = None


class LeaveResponse(BaseModel):
    id: str
    resource_id: str
    start_date: str
    end_date: str
    type: str
    notes: Optional[str] = None


class HolidayCreate(BaseModel):
    name: str
    date: date
    description: Optional[str] = None


class HolidayResponse(BaseModel):
    id: str
    name: str
    date: str
    description: Optional[str] = None


class AICommandRequest(BaseModel):
    query: str
    provider: Optional[str] = None
    api_key: Optional[str] = None


class AICommandResponse(BaseModel):
    intent: str
    entities: dict
    confidence: float
    natural_language: str
    provider_used: Optional[str] = None


class ProjectWizardCreate(BaseModel):
    name: str
    client_name: str
    main_contact_name: Optional[str] = None
    main_contact_email: Optional[str] = None
    main_contact_phone: Optional[str] = None
    main_contact_role: Optional[str] = None
    status: str
    start_date: date
    end_date: date
    is_draft: bool = False
    budgeted_hours: Optional[float] = None
    project_lead_id: Optional[str] = None
    google_drive_url: Optional[str] = None
    project_objective: Optional[str] = None
    phases: List[dict] = []
    allocations: List[dict]
    risks: List[dict]


class TimesheetCreate(BaseModel):
    resource_id: str
    project_id: str
    phase_id: Optional[str] = None
    week_start_date: date
    week_end_date: date
    planned_hours: float
    actual_hours: float
    notes: Optional[str] = None
    status: str = "Draft"
    task_id: Optional[str] = None
    task_name: Optional[str] = None


class TimesheetUpdate(BaseModel):
    actual_hours: Optional[float] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    task_id: Optional[str] = None
    task_name: Optional[str] = None


class TimesheetResponse(BaseModel):
    id: str
    resource_id: str
    project_id: str
    phase_id: Optional[str] = None
    week_start_date: str
    week_end_date: str
    planned_hours: float
    actual_hours: float
    variance_hours: float
    variance_percentage: float
    notes: Optional[str] = None
    status: str
    auto_filled: bool
    modified_by_user: bool
    submitted_at: Optional[str] = None
    created_at: str
    task_id: Optional[str] = None
    task_name: Optional[str] = None


# ============================================================
# WBS (Work Breakdown Structure) Models
# ============================================================

class WBSTaskStatus:
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    ON_HOLD = "on_hold"
    BLOCKED = "blocked"


class WBSTaskPriority:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WBSTaskCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    phase_id: Optional[str] = None
    phase_name: Optional[str] = None
    parent_id: Optional[str] = None
    assigned_to: Optional[str] = None
    status: Optional[str] = "todo"
    priority: Optional[str] = "medium"
    estimated_hours: Optional[float] = 0
    actual_hours: Optional[float] = 0
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    order: Optional[int] = 0
    dependencies: Optional[List[str]] = []
    labels: Optional[List[str]] = []
    # Milestone fields
    is_milestone: Optional[bool] = False
    milestone_date: Optional[str] = None


class WBSTaskUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    phase_id: Optional[str] = None
    phase_name: Optional[str] = None
    parent_id: Optional[str] = None
    assigned_to: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    order: Optional[int] = None
    dependencies: Optional[List[str]] = None
    labels: Optional[List[str]] = None
    # Milestone fields
    is_milestone: Optional[bool] = None
    milestone_date: Optional[str] = None
    milestone_completed: Optional[bool] = None


class WBSTaskResponse(BaseModel):
    id: str
    project_id: str
    name: str
    description: Optional[str] = ""
    phase_id: Optional[str] = None
    phase_name: Optional[str] = None
    parent_id: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_to_name: Optional[str] = None
    status: str = "todo"
    priority: str = "medium"
    estimated_hours: Optional[float] = 0
    actual_hours: Optional[float] = 0
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    # Baseline (planned) dates — snapshot of the committed schedule.
    # Set explicitly by a PM via the "Set Baseline" action; preserved when
    # start_date/end_date are later revised, so schedule slip is traceable.
    baseline_start_date: Optional[str] = None
    baseline_end_date: Optional[str] = None
    order: int = 0
    dependencies: List[str] = []
    labels: List[str] = []
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    children: Optional[List[dict]] = []
    # Milestone fields
    is_milestone: Optional[bool] = False
    milestone_date: Optional[str] = None
    milestone_completed: Optional[bool] = False


class AIGenerateWBSRequest(BaseModel):
    project_id: str
    additional_context: Optional[str] = ""
    include_subtasks: Optional[bool] = True
    depth: Optional[int] = 2
    complexity: Optional[str] = "standard"
    primary_deliverables: Optional[str] = ""
    start_date: Optional[str] = None
    provider: Optional[str] = None
    api_key: Optional[str] = None


class SaveGeneratedWBSRequest(BaseModel):
    project_id: str
    tasks: List[dict]
    start_date: Optional[str] = None


class AvatarUpdate(BaseModel):
    avatar_url: str


class RescheduleProjectRequest(BaseModel):
    weeks_to_shift: int
    shift_direction: str = "forward"


class MoveResourceRequest(BaseModel):
    resource_id: str
    source_project_id: str
    target_project_id: str
    new_percentage: Optional[int] = None
    new_start_date: Optional[str] = None
    new_end_date: Optional[str] = None


class BulkSummaryUpdate(BaseModel):
    project_ids: List[str]


class CreateProjectFullRequest(BaseModel):
    name: str
    client_name: str
    status: str = "Active"
    start_date: str
    end_date: str
    budgeted_hours: Optional[float] = None
    phases: Optional[List[dict]] = None


class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None


class NotificationCreate(BaseModel):
    user_id: str
    type: str
    title: str
    message: str
    related_id: Optional[str] = None
    priority: str = "normal"


class NotificationResponse(BaseModel):
    id: str
    user_id: str
    type: str
    title: str
    message: str
    related_id: Optional[str] = None
    priority: str = "normal"
    read: bool = False
    created_at: Optional[str] = None


class ClientUserCreate(BaseModel):
    email: EmailStr
    password: str
    company_name: str = ""
    allowed_project_ids: List[str] = []


class ClientUserUpdate(BaseModel):
    company_name: Optional[str] = None
    allowed_project_ids: Optional[List[str]] = None
    password: Optional[str] = None


class ClientUserResponse(BaseModel):
    id: str
    email: str
    company_name: Optional[str] = ""
    allowed_project_ids: List[str] = []
    must_change_password: Optional[bool] = False
    projects: Optional[List[dict]] = []


# ============================================================
# Budget Allocation Validation Schemas
# ============================================================

class AllocationValidateRequest(BaseModel):
    project_id: str
    resource_id: str
    start_date: date
    end_date: date
    percentage: Optional[int] = None
    hours: Optional[int] = None
    allocation_type: str = "percentage"
    exclude_allocation_id: Optional[str] = None  # for edits, exclude the current one


# ============================================================
# Report Link (Magic Link) Schemas
# ============================================================

class ReportLinkCreate(BaseModel):
    project_id: str
    recipient_email: EmailStr
    report_type: str = "project_status"  # or "wbs"
    report_period: str = "whole_project"  # or "this_week", "last_month", etc.


class ReportLinkResponse(BaseModel):
    id: str
    project_id: str
    token: str
    report_type: str
    report_period: str
    created_at: str
    expires_at: str
    created_by: str
    recipient_email: str
    is_active: bool
    view_count: int
    last_viewed_at: Optional[str] = None
    magic_link: str  # Full URL


class VerifyCodeRequest(BaseModel):
    verification_code: str


# ============================================================
# WBS Comments Schemas
# ============================================================

class WBSCommentCreate(BaseModel):
    content: str
    mentions: Optional[List[str]] = []  # list of user emails mentioned

class WBSCommentUpdate(BaseModel):
    content: str

class WBSCommentResponse(BaseModel):
    id: str
    task_id: str
    project_id: str
    author_email: str
    author_name: Optional[str] = None
    content: str
    mentions: List[str] = []
    is_edited: bool = False
    created_at: str
    updated_at: Optional[str] = None


# ============================================================
# AI Learning & Guidance
# ============================================================

class AIInstructionCreate(BaseModel):
    scope: str = "global"  # "global" or "project"
    project_id: Optional[str] = None
    category: str = "all"  # "all", "risk_polish", "status_summary", "wbs_generation", "reschedule", "chat"
    instructions: str
    
class AIInstructionUpdate(BaseModel):
    instructions: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None

class AIInstructionResponse(BaseModel):
    id: str
    scope: str
    project_id: Optional[str] = None
    category: str
    instructions: str
    is_active: bool = True
    created_by: str
    created_at: str
    updated_at: Optional[str] = None

class AIFeedbackCreate(BaseModel):
    feature: str  # "risk_polish", "status_summary", "wbs_generation", "reschedule", "chat", "budget_analysis"
    project_id: Optional[str] = None
    rating: str  # "thumbs_up" or "thumbs_down"
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    feedback_text: Optional[str] = None

class AIFeedbackResponse(BaseModel):
    id: str
    feature: str
    project_id: Optional[str] = None
    rating: str
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    feedback_text: Optional[str] = None
    user_email: str
    created_at: str
