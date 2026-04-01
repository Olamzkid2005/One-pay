"""API Key management endpoints"""
from flask import Blueprint, request, jsonify
from core.auth import current_user_id
from core.responses import unauthenticated
from database import get_db
from models.api_key import APIKey

api_keys_bp = Blueprint("api_keys", __name__)


@api_keys_bp.route("/api-keys", methods=["GET"])
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


@api_keys_bp.route("/api-keys", methods=["POST"])
def create_api_key():
    """Generate a new API key for the authenticated user"""
    user_id = current_user_id()
    if not user_id:
        return unauthenticated()
    
    data = request.get_json(silent=True) or {}
    name = data.get('name', '')
    
    with get_db() as db:
        from core.api_auth import generate_api_key, hash_api_key
        
        # Generate key
        key = generate_api_key()
        key_hash = hash_api_key(key)
        key_prefix = key[:20]
        
        # Create record
        api_key = APIKey(
            user_id=user_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=name
        )
        db.add(api_key)
        db.flush()
        
        # Return full key (only time it's shown)
        result = api_key.to_dict()
        result['api_key'] = key
        
        return jsonify({"success": True, "api_key": result})


@api_keys_bp.route("/api-keys/<int:key_id>", methods=["DELETE"])
def revoke_api_key(key_id):
    """Revoke (deactivate) an API key"""
    from core.responses import error
    
    user_id = current_user_id()
    if not user_id:
        return unauthenticated()
    
    with get_db() as db:
        api_key = db.query(APIKey).filter(
            APIKey.id == key_id,
            APIKey.user_id == user_id
        ).first()
        
        if not api_key:
            return error("API key not found", "NOT_FOUND", 404)
        
        api_key.is_active = False
        db.flush()
        
        return jsonify({"success": True, "message": "API key revoked"})
