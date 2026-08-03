from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .memory import MemoryStore


@dataclass(slots=True)
class WorkspacePermission:
    role: str = "viewer"
    project_permissions: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class User:
    id: str
    name: str
    email: str
    role: str = "member"
    organizations: list[str] = field(default_factory=list)
    workspaces: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Organization:
    id: str
    name: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass(slots=True)
class Workspace:
    id: str
    name: str
    organization_id: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass(slots=True)
class Project:
    id: str
    name: str
    workspace_id: str
    permissions: dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class UserManager:
    """Manages users and their memberships."""

    def __init__(self, memory_store: Optional[MemoryStore] = None) -> None:
        self.memory_store = memory_store
        self._users: dict[str, User] = {}
        self._audit_log: list[dict[str, Any]] = []

    def _get_memory(self) -> MemoryStore:
        if self.memory_store is None:
            self.memory_store = MemoryStore(Path("~/.zaya_ai_operations_agent/workspaces.json").expanduser())
        return self.memory_store

    def create_user(self, user: User) -> User:
        self._users[user.id] = user
        self._persist()
        self._audit("create_user", user.id, "created")
        return user

    def get_user(self, user_id: str) -> Optional[User]:
        if user_id in self._users:
            return self._users[user_id]
        stored = self._get_memory().get("users", [])
        for entry in stored:
            if entry.get("id") == user_id:
                self._users[user_id] = User(**entry)
                return self._users[user_id]
        return None

    def list_users(self) -> list[User]:
        stored = self._get_memory().get("users", [])
        self._users = {entry["id"]: User(**entry) for entry in stored}
        return list(self._users.values())

    def _persist(self) -> None:
        memory = self._get_memory()
        memory.set("users", [asdict(user) for user in self._users.values()])

    def _audit(self, action: str, subject: str, details: str) -> None:
        self._audit_log.append({"action": action, "subject": subject, "details": details, "executed_at": datetime.now().isoformat()})

    def audit_log(self) -> list[dict[str, Any]]:
        return list(self._audit_log)


class WorkspaceManager:
    """Manages organizations, workspaces, and projects with role inheritance."""

    def __init__(self, memory_store: Optional[MemoryStore] = None) -> None:
        self.memory_store = memory_store
        self._organizations: dict[str, Organization] = {}
        self._workspaces: dict[str, Workspace] = {}
        self._projects: dict[str, Project] = {}
        self._audit_log: list[dict[str, Any]] = []

    def _get_memory(self) -> MemoryStore:
        if self.memory_store is None:
            self.memory_store = MemoryStore(Path("~/.zaya_ai_operations_agent/workspaces.json").expanduser())
        return self.memory_store

    def create_organization(self, organization: Organization) -> Organization:
        self._organizations[organization.id] = organization
        self._persist()
        self._audit("create_organization", organization.id, "created")
        return organization

    def list_organizations(self) -> list[Organization]:
        stored = self._get_memory().get("organizations", [])
        self._organizations = {entry["id"]: Organization(**entry) for entry in stored}
        return list(self._organizations.values())

    def create_workspace(self, workspace: Workspace) -> Workspace:
        self._workspaces[workspace.id] = workspace
        self._persist()
        self._audit("create_workspace", workspace.id, "created")
        return workspace

    def list_workspaces(self) -> list[Workspace]:
        stored = self._get_memory().get("workspaces", [])
        self._workspaces = {entry["id"]: Workspace(**entry) for entry in stored}
        return list(self._workspaces.values())

    def create_project(self, project: Project) -> Project:
        self._projects[project.id] = project
        self._persist()
        self._audit("create_project", project.id, "created")
        return project

    def list_projects(self) -> list[Project]:
        stored = self._get_memory().get("projects", [])
        self._projects = {entry["id"]: Project(**entry) for entry in stored}
        return list(self._projects.values())

    def has_project_permission(self, user_role: str, project: Project, permission: str) -> bool:
        role_hierarchy = {"viewer": 0, "member": 1, "admin": 2, "owner": 3}
        effective_role = role_hierarchy.get(user_role, 0)
        project_role = role_hierarchy.get(project.permissions.get("default", "viewer"), 0)
        return effective_role >= project_role or project.permissions.get(permission) == "allow"

    def _persist(self) -> None:
        memory = self._get_memory()
        memory.set("organizations", [asdict(org) for org in self._organizations.values()])
        memory.set("workspaces", [asdict(ws) for ws in self._workspaces.values()])
        memory.set("projects", [asdict(project) for project in self._projects.values()])

    def _audit(self, action: str, subject: str, details: str) -> None:
        self._audit_log.append({"action": action, "subject": subject, "details": details, "executed_at": datetime.now().isoformat()})

    def audit_log(self) -> list[dict[str, Any]]:
        return list(self._audit_log)
