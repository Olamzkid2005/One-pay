"""
Generate API key for VoicePay integration.

This script creates a dedicated API key for VoicePay to authenticate
with OnePay's payment link creation and status check endpoints.

Usage:
    python scripts/generate_voicepay_api_key.py --email voicepay@example.com --name "VoicePay Integration"
"""
import argparse
import sys

from database import get_db
from models.api_key import APIKey
from models.user import User


def generate_voicepay_api_key(email: str, name: str) -> str:
    """
    Generate API key for VoicePay user.

    Args:
        email: Email address for VoicePay user account
        name: Descriptive name for the API key

    Returns:
        Generated API key string
    """
    with get_db() as db:
        # Check if user exists
        user = db.query(User).filter(User.email == email).first()

        if not user:
            print(f"Error: User with email {email} not found")
            print("Please create the user account first")
            sys.exit(1)

        # Generate API key
        api_key_obj = APIKey.generate(
            db=db,
            user_id=user.id,
            name=name,
            rate_limit_override=100  # 100 requests/minute for VoicePay
        )

        print("\n✅ VoicePay API Key Generated Successfully")
        print("━" * 60)
        print(f"User: {user.email}")
        print(f"Name: {name}")
        print(f"API Key: {api_key_obj.key}")
        print("Rate Limit: 100 requests/minute")
        print("━" * 60)
        print("\n⚠️  IMPORTANT: Save this API key securely!")
        print("Add to VoicePay's .env file:")
        print(f"ONEPAY_API_KEY={api_key_obj.key}")
        print("\nThis key will not be shown again.\n")

        return api_key_obj.key


def main():
    parser = argparse.ArgumentParser(
        description="Generate API key for VoicePay integration"
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Email address for VoicePay user account"
    )
    parser.add_argument(
        "--name",
        default="VoicePay Integration",
        help="Descriptive name for the API key"
    )

    args = parser.parse_args()
    generate_voicepay_api_key(args.email, args.name)


if __name__ == "__main__":
    main()
