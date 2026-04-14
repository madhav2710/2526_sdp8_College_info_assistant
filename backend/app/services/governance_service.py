import logging
from typing import Any, Optional

from fastapi import HTTPException

from app.core.database import get_service_client
from app.schemas.admin import (
    AdminCreateRequest,
    AdminStatusUpdateRequest,
    AdminUpdateRequest,
)
from app.schemas.college import CollegeCreateRequest, CollegeUpdateRequest

logger = logging.getLogger(__name__)


def normalize_sort_order(sort_order: Optional[str], default: str = "desc") -> str:
    if not sort_order:
        return default
    value = sort_order.lower()
    return value if value in {"asc", "desc"} else default


def normalize_status_filter(status: Optional[str]) -> Optional[str]:
    if not status:
        return None
    return status.strip().lower().replace(" ", "_")


def normalize_search_term(search: Optional[str]) -> Optional[str]:
    if not search:
        return None
    value = search.strip()
    return value or None


def _extract_count(response: Any) -> int:
    return response.count or len(response.data or [])


def _map_governance_error(action: str, exc: Exception) -> HTTPException:
    message = str(exc)
    if isinstance(exc, HTTPException):
        return exc
    if "colleges_name_key" in message:
        return HTTPException(
            status_code=400, detail="A college with this name already exists"
        )
    if "colleges_code_key" in message:
        return HTTPException(
            status_code=400, detail="A college with this code already exists"
        )
    if "colleges_domain_key" in message:
        return HTTPException(
            status_code=400, detail="A college with this domain already exists"
        )
    logger.exception("Failed to %s", action)
    return HTTPException(status_code=500, detail=f"Failed to {action}")


def _raise_governance_server_error(
    action: str,
    exc: Exception,
    *,
    detail: Optional[str] = None,
    status_code: int = 500,
) -> None:
    logger.exception("Failed to %s", action)
    raise HTTPException(
        status_code=status_code,
        detail=detail or f"Failed to {action}",
    ) from exc


def _get_college_name_map(client: Any, college_ids: set[str]) -> dict[str, str]:
    if not college_ids:
        return {}

    college_map: dict[str, str] = {}
    for college in (
        client.table("colleges")
        .select("id, name")
        .in_("id", list(college_ids))
        .execute()
        .data
        or []
    ):
        college_map[college["id"]] = college["name"]
    return college_map


def _get_user_email_map(client: Any, user_ids: set[str]) -> dict[str, str]:
    if not user_ids:
        return {}

    email_map: dict[str, str] = {}
    for user in (
        client.table("users").select("id, email").in_("id", list(user_ids)).execute().data
        or []
    ):
        email_map[user["id"]] = user.get("email") or ""
    return email_map


def _build_admin_payload(
    admin: dict[str, Any],
    *,
    college_name: Optional[str],
    email: str = "",
) -> dict[str, Any]:
    return {
        "id": admin["id"],
        "name": admin.get("full_name") or "Unnamed Admin",
        "email": email,
        "college_id": admin.get("college_id"),
        "college": college_name or "Unassigned",
        "status": admin.get("status") or "active",
        "joined": admin.get("created_at"),
    }


def _rollback_created_auth_user(client: Any, user_id: str) -> None:
    try:
        client.auth.admin.delete_user(user_id)
        logger.info("Rolled back auth user %s after admin creation failure", user_id)
    except Exception as rollback_exc:  # noqa: BLE001
        logger.exception(
            "Failed to rollback auth user %s after admin creation failure",
            user_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to create admin and rollback auth user",
        ) from rollback_exc


def get_superadmin_dashboard_stats() -> dict[str, int]:
    try:
        client = get_service_client()
        total_colleges = _extract_count(
            client.table("colleges").select("id", count="exact").execute()
        )
        total_admins = _extract_count(
            client.table("profiles")
            .select("id", count="exact")
            .eq("role", "college_admin")
            .execute()
        )
        total_docs = _extract_count(
            client.table("documents").select("id", count="exact").execute()
        )
        total_queries = _extract_count(
            client.table("messages")
            .select("id", count="exact")
            .eq("role", "user")
            .execute()
        )
        return {
            "colleges": total_colleges,
            "totalAdmins": total_admins,
            "totalDocs": total_docs,
            "totalQueries": total_queries,
            "activeNodes": 12,
        }
    except Exception as exc:  # noqa: BLE001
        _raise_governance_server_error("retrieve superadmin stats", exc)


def get_superadmin_college_directory(
    search: Optional[str] = None,
) -> dict[str, list[dict]]:
    try:
        client = get_service_client()
        query = client.table("colleges").select(
            "id, name, code, domain, description, logo_url, is_active, created_at"
        )
        search_term = normalize_search_term(search)
        if search_term:
            query = query.ilike("name", f"%{search_term}%")

        colleges = query.execute().data or []
        result = []
        for college in colleges:
            admin_count = 0
            try:
                admin_count = _extract_count(
                    client.table("profiles")
                    .select("id", count="exact")
                    .eq("role", "college_admin")
                    .eq("college_id", college["id"])
                    .execute()
                )
            except Exception:
                admin_count = 0

            result.append(
                {
                    "id": college["id"],
                    "name": college["name"],
                    "code": college.get("code"),
                    "domain": college.get("domain"),
                    "description": college.get("description"),
                    "admin_count": admin_count,
                }
            )

        return {"colleges": result}
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, HTTPException):
            raise exc
        _raise_governance_server_error("retrieve colleges", exc)


def get_superadmin_college_record(college_id: str) -> dict[str, Any]:
    try:
        client = get_service_client()
        response = (
            client.table("colleges")
            .select("id, name, code, domain, description, logo_url, is_active, created_at")
            .eq("id", college_id)
            .limit(1)
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="College not found")

        college = response.data[0]
        admin_count = 0
        try:
            admin_count = _extract_count(
                client.table("profiles")
                .select("id", count="exact")
                .eq("role", "college_admin")
                .eq("college_id", college_id)
                .execute()
            )
        except Exception:  # noqa: BLE001
            admin_count = 0

        return {
            "id": college["id"],
            "name": college["name"],
            "code": college.get("code"),
            "domain": college.get("domain"),
            "description": college.get("description"),
            "logo_url": college.get("logo_url"),
            "is_active": college.get("is_active", True),
            "admin_count": admin_count,
            "created_at": college.get("created_at"),
        }
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, HTTPException):
            raise exc
        _raise_governance_server_error("retrieve college", exc)


def create_superadmin_college_record(request: CollegeCreateRequest) -> dict[str, Any]:
    try:
        client = get_service_client()
        data = request.dict()
        for key in ["domain", "description", "logo_url"]:
            if data.get(key) is not None:
                data[key] = data[key].strip() or None

        response = client.table("colleges").insert(data).execute()
        college = (response.data or [None])[0]
        if not college:
            raise HTTPException(status_code=500, detail="Failed to create college")

        return {
            "id": college["id"],
            "name": college["name"],
            "code": college.get("code"),
            "domain": college.get("domain"),
            "description": college.get("description"),
            "logo_url": college.get("logo_url"),
            "is_active": college.get("is_active", True),
        }
    except Exception as exc:  # noqa: BLE001
        raise _map_governance_error("create college", exc) from exc


def update_superadmin_college_record(
    college_id: str, request: CollegeUpdateRequest
) -> dict[str, str]:
    try:
        client = get_service_client()
        updates = {
            key: value for key, value in request.dict().items() if value is not None
        }
        for key in ["domain", "description", "logo_url"]:
            if key in updates:
                updates[key] = updates[key].strip() or None

        if not updates:
            return {"status": "no_changes"}

        response = (
            client.table("colleges").update(updates).eq("id", college_id).execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="College not found")

        return {"status": "success"}
    except Exception as exc:  # noqa: BLE001
        raise _map_governance_error("update college", exc) from exc


def delete_superadmin_college_record(college_id: str) -> dict[str, str]:
    try:
        client = get_service_client()
        response = client.table("colleges").delete().eq("id", college_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="College not found")
        return {"status": "success"}
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, HTTPException):
            raise exc
        _raise_governance_server_error("delete college", exc)


def get_superadmin_admin_directory(
    search: Optional[str] = None,
) -> dict[str, list[dict]]:
    try:
        client = get_service_client()
        admins = (
            client.table("profiles")
            .select("id, college_id, full_name, role, created_at, status")
            .eq("role", "college_admin")
            .execute()
            .data
            or []
        )

        college_ids = {
            admin["college_id"] for admin in admins if admin.get("college_id")
        }
        college_map = _get_college_name_map(client, college_ids)
        email_map = _get_user_email_map(client, {admin["id"] for admin in admins})

        admin_list = []
        for admin in admins:
            admin_list.append(
                _build_admin_payload(
                    admin,
                    college_name=college_map.get(admin.get("college_id")),
                    email=email_map.get(admin["id"], ""),
                )
            )

        search_term = normalize_search_term(search)
        if search_term:
            lowered = search_term.lower()
            admin_list = [
                admin
                for admin in admin_list
                if lowered in admin["name"].lower()
                or lowered in (admin["email"] or "").lower()
                or lowered in (admin["college"] or "").lower()
            ]

        return {"admins": admin_list}
    except Exception as exc:  # noqa: BLE001
        _raise_governance_server_error("retrieve admins", exc)


def get_superadmin_admin_record(admin_id: str) -> dict[str, Any]:
    try:
        client = get_service_client()
        response = (
            client.table("profiles")
            .select("id, college_id, full_name, role, created_at, status")
            .eq("id", admin_id)
            .eq("role", "college_admin")
            .limit(1)
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="Admin not found")

        admin = response.data[0]
        college_map = _get_college_name_map(
            client,
            {admin["college_id"]} if admin.get("college_id") else set(),
        )
        email_map = _get_user_email_map(client, {admin_id})
        return _build_admin_payload(
            admin,
            college_name=college_map.get(admin.get("college_id")),
            email=email_map.get(admin_id, ""),
        )
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, HTTPException):
            raise exc
        _raise_governance_server_error("retrieve admin", exc)


def create_superadmin_admin_account(request: AdminCreateRequest) -> dict[str, str]:
    client: Any = None
    user_id: Optional[str] = None
    rollback_required = False
    try:
        client = get_service_client()
        try:
            auth_response = client.auth.admin.create_user(
                {
                    "email": request.email,
                    "password": request.password,
                    "email_confirm": True,
                }
            )
            user = getattr(auth_response, "user", None) or getattr(
                auth_response, "data", {}
            ).get("user")
            if not user:
                raise HTTPException(
                    status_code=500, detail="Failed to create auth user"
                )

            raw_user_id = getattr(user, "id", None)
            if raw_user_id is None and isinstance(user, dict):
                raw_user_id = user.get("id")
            if raw_user_id is None:
                raise HTTPException(
                    status_code=500, detail="Auth user record is missing an id"
                )
            user_id = str(raw_user_id)
            rollback_required = True
        except Exception as exc:  # noqa: BLE001
            if isinstance(exc, HTTPException):
                raise exc
            message = str(exc)
            duplicate_markers = [
                "User already registered",
                "email_already_in_use",
                "A user with this email address has already been registered",
            ]
            if any(marker in message for marker in duplicate_markers):
                raise HTTPException(
                    status_code=400, detail="An account with this email already exists"
                )
            _raise_governance_server_error("create auth user", exc)

        client.table("profiles").upsert(
            {
                "id": user_id,
                "full_name": request.name,
                "role": "college_admin",
                "college_id": request.college_id,
                "status": "active",
            }
        ).execute()

        try:
            client.table("users").upsert(
                {"id": user_id, "email": request.email},
                on_conflict="id",
            ).execute()
        except Exception:  # noqa: BLE001
            logger.warning("Failed to sync compatibility users row for %s", user_id)

        client.table("admins").upsert(
            {
                "user_id": user_id,
                "college_id": request.college_id,
                "is_super_admin": False,
            },
            on_conflict="user_id,college_id",
        ).execute()
        rollback_required = False

        return {
            "id": user_id,
            "name": request.name,
            "email": request.email,
            "college_id": request.college_id,
            "status": "active",
        }
    except Exception as exc:  # noqa: BLE001
        if rollback_required and user_id:
            _rollback_created_auth_user(client, user_id)
        if isinstance(exc, HTTPException):
            raise exc
        _raise_governance_server_error("create admin", exc)


def update_superadmin_admin_account(
    admin_id: str, request: AdminUpdateRequest
) -> dict[str, str]:
    try:
        client = get_service_client()
        updates = {}
        if request.name is not None:
            updates["full_name"] = request.name
        if request.college_id is not None:
            updates["college_id"] = request.college_id

        if updates:
            client.table("profiles").update(updates).eq("id", admin_id).execute()

        return {"status": "success"}
    except Exception as exc:  # noqa: BLE001
        _raise_governance_server_error("update admin", exc)


def delete_superadmin_admin_account(admin_id: str) -> dict[str, str]:
    try:
        client = get_service_client()
        client.auth.admin.delete_user(admin_id)
        try:
            client.table("profiles").delete().eq("id", admin_id).execute()
            client.table("users").delete().eq("id", admin_id).execute()
            client.table("admins").delete().eq("user_id", admin_id).execute()
        except Exception:  # noqa: BLE001
            logger.warning(
                "Auth user %s deleted successfully; leftover relational cleanup may be required",
                admin_id,
            )
        return {"status": "success"}
    except Exception as exc:  # noqa: BLE001
        _raise_governance_server_error("delete admin", exc)


def toggle_superadmin_admin_account_status(
    admin_id: str, request: AdminStatusUpdateRequest
) -> dict[str, str]:
    try:
        client = get_service_client()
        client.table("profiles").update({"status": request.status}).eq(
            "id", admin_id
        ).execute()
        return {"status": "success"}
    except Exception as exc:  # noqa: BLE001
        _raise_governance_server_error("update admin status", exc)


def get_superadmin_document_groups(
    search: Optional[str] = None,
) -> dict[str, list[dict]]:
    try:
        client = get_service_client()
        documents = (
            client.table("documents")
            .select(
                "id, filename, file_type, file_size, college_id, uploaded_by, created_at"
            )
            .execute()
            .data
            or []
        )
        if not documents:
            return {"groups": []}

        college_ids = {
            document["college_id"]
            for document in documents
            if document.get("college_id")
        }
        uploader_ids = {
            document["uploaded_by"]
            for document in documents
            if document.get("uploaded_by")
        }

        college_map: dict[str, str] = {}
        if college_ids:
            for college in (
                client.table("colleges")
                .select("id, name")
                .in_("id", list(college_ids))
                .execute()
                .data
                or []
            ):
                college_map[college["id"]] = college["name"]

        uploader_map: dict[str, str] = {}
        if uploader_ids:
            for profile in (
                client.table("profiles")
                .select("id, full_name")
                .in_("id", list(uploader_ids))
                .execute()
                .data
                or []
            ):
                uploader_map[profile["id"]] = (
                    profile.get("full_name") or "Unknown Admin"
                )

        groups_map: dict[tuple[Optional[str], Optional[str]], dict[str, Any]] = {}
        for document in documents:
            college_id = document.get("college_id")
            uploader_id = document.get("uploaded_by")
            key = (college_id, uploader_id)
            if key not in groups_map:
                groups_map[key] = {
                    "college": college_map.get(college_id, "Unknown College"),
                    "admin_name": uploader_map.get(uploader_id, "Unknown Admin"),
                    "total_documents": 0,
                    "documents": [],
                }

            groups_map[key]["documents"].append(
                {
                    "id": document["id"],
                    "name": document["filename"],
                    "uploaded_at": document.get("created_at"),
                    "type": (document.get("file_type") or "").upper(),
                    "size": f"{document.get('file_size', 0)} bytes"
                    if document.get("file_size") is not None
                    else "",
                }
            )
            groups_map[key]["total_documents"] += 1

        groups = list(groups_map.values())
        search_term = normalize_search_term(search)
        if search_term:
            lowered = search_term.lower()
            filtered_groups = []
            for group in groups:
                if (
                    lowered in group["college"].lower()
                    or lowered in group["admin_name"].lower()
                ):
                    filtered_groups.append(group)
                    continue

                matching_documents = [
                    document
                    for document in group["documents"]
                    if lowered in document["name"].lower()
                ]
                if matching_documents:
                    filtered_groups.append(
                        {
                            **group,
                            "documents": matching_documents,
                            "total_documents": len(matching_documents),
                        }
                    )
            groups = filtered_groups

        return {"groups": groups}
    except Exception as exc:  # noqa: BLE001
        _raise_governance_server_error("retrieve documents", exc)
