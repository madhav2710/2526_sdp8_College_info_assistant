from fastapi import APIRouter

from app import legacy_main as legacy

router = APIRouter()
router.add_api_route("/config/status", legacy.get_config_status, methods=["GET"])
router.add_api_route("/config/validate", legacy.validate_config, methods=["POST"])
router.add_api_route("/system/health", legacy.get_system_health, methods=["GET"])
router.add_api_route(
    "/system/health/reset",
    legacy.reset_system_health,
    methods=["POST"],
)
router.add_api_route("/public/colleges", legacy.list_public_colleges, methods=["GET"])
router.add_api_route("/", legacy.root, methods=["GET"])
router.add_api_route("/student/{student_id}", legacy.get_student, methods=["GET"])
