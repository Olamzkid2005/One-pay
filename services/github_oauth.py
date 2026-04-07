import logging
import requests
from typing import Dict, Optional
from urllib.parse import urlencode
from config import Config

logger = logging.getLogger(__name__)


class GitHubOAuthService:
    @staticmethod
    def get_auth_url() -> str:
        client_id = Config.GITHUB_CLIENT_ID
        redirect_uri = Config.GITHUB_REDIRECT_URI
        params = urlencode(
            {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "scope": "user:email",
            }
        )
        return f"https://github.com/login/oauth/authorize?{params}"

    @staticmethod
    def exchange_code_for_token(code: str) -> str:
        client_id = Config.GITHUB_CLIENT_ID
        client_secret = Config.GITHUB_CLIENT_SECRET

        response = requests.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={"client_id": client_id, "client_secret": client_secret, "code": code},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise ValueError(data.get("error_description", "Invalid token response"))

        return data["access_token"]

    @staticmethod
    def get_user_profile(access_token: str) -> Dict:
        headers = {
            "Authorization": f"token {access_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        # 1. Get user Profile
        user_resp = requests.get(
            "https://api.github.com/user", headers=headers, timeout=10
        )
        user_resp.raise_for_status()
        user_data = user_resp.json()

        # 2. Get user Emails (since public email might be empty)
        email = None
        emails_resp = requests.get(
            "https://api.github.com/user/emails", headers=headers, timeout=10
        )
        if emails_resp.status_code == 200:
            emails = emails_resp.json()
            # find primary, verified email
            for em in emails:
                if em.get("primary") and em.get("verified"):
                    email = em.get("email")
                    break

            if not email and emails:  # fallback to any verified
                for em in emails:
                    if em.get("verified"):
                        email = em.get("email")
                        break

        if not email:
            email = user_data.get("email")

        if not email:
            raise ValueError("Profile has no verified email address.")

        return {
            "github_id": str(user_data["id"]),
            "email": email,
            "full_name": user_data.get("name") or user_data.get("login"),
            "profile_picture_url": user_data.get("avatar_url"),
        }
