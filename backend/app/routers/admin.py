from fastapi import APIRouter

from app import legacy_main as legacy

router = APIRouter()
router.add_api_route("/admin/upload", legacy.upload_document, methods=["POST"])
router.add_api_route("/admin/documents", legacy.get_documents, methods=["GET"])
router.add_api_route("/admin/query-history", legacy.get_query_history, methods=["GET"])
router.add_api_route(
    "/admin/trigger-rag-processing",
    legacy.trigger_manual_rag_processing,
    methods=["POST"],
)
