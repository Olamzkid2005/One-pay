"""API Key management endpoints"""
from flask import Blueprint, request, jsonify
from core.auth import current_user_id
from core.responses import unauthenticated
from database import get_db
from models.api_key import APIKey

api_keys_bp = Blueprint("api_keys", __name__)


@api_keys_bp.route("/api/api-keys", methods=["GET"])
def list_api_keys():
    """List all API keys for the authenticated user"""
    user_id = current_user_id()
    if not user_id:
        return unauthenticated()
    
    with get_db() as db:
        keys = db.query(APIKey).filter(APIKey.user_id == user_id).all()
        return jsonify({
            "success": True,
            "api_keys": [k.to_dict() for k in keys]
        })
