#!/usr/bin/env python3
"""
OnePay — Secret Generator
Generate cryptographically secure secrets for environment variables.

Usage:
    python generate_secrets.py

This will output three different secrets that you can copy into your .env file.
Each secret is 64 hex characters (256 bits of entropy).
"""
import secrets


def generate_secret(name: str) -> str:
    """Generate a cryptographically secure 256-bit secret."""
    return secrets.token_hex(32)


def main():
    print("=" * 70)
    print("OnePay Secret Generator")
    print("=" * 70)
    print()
    print("Copy these values into your .env file:")
    print()
    print(f"SECRET_KEY={generate_secret('SECRET_KEY')}")
    print(f"HMAC_SECRET={generate_secret('HMAC_SECRET')}")
    print(f"WEBHOOK_SECRET={generate_secret('WEBHOOK_SECRET')}")
    print()
    print("=" * 70)
    print("IMPORTANT:")
    print("- Use DIFFERENT secrets for dev, staging, and production")
    print("- Never commit .env files to version control")
    print("- Store production secrets in a secure vault (AWS Secrets Manager, etc.)")
    print("- Rotate secrets periodically (every 90 days recommended)")
    print("=" * 70)


if __name__ == "__main__":
    main()
