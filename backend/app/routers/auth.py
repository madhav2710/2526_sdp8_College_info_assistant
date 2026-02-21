from fastapi import APIRouter

from app import legacy_main as legacy

router = APIRouter()
router.add_api_route("/auth/signup", legacy.signup, methods=["POST"])
router.add_api_route("/auth/login", legacy.login, methods=["POST"])
