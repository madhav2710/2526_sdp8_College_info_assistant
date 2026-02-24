from fastapi import APIRouter

from app import legacy_main as legacy

router = APIRouter()
router.add_api_route("/user/profile", legacy.get_user_profile, methods=["GET"])
router.add_api_route("/user/set-college", legacy.set_user_college, methods=["POST"])
