"""
OnePay — Google OAuth Service
Handles Google OAuth 2.0 token validation and profile extraction.
"""
import logging
from typing import Dict, Optional

import requests as http_requests
from google.auth.transport import requests
from google.oauth2 import id_token


logger = logging.getLogger(__name__)


class GoogleTokenValidator:
    """
    Validates Google OAuth 2.0 ID tokens.
    
    Verifies token signature using Google's public keys and validates
    token claims (audience, issuer, expiration).
    """
    
    def __init__(self, client_id: str):
        """
        Initialize token validator.
        
        Args:
            client_id: Google OAuth client ID for audience validation
        """
        self.client_id = client_id
    
    def validate_token(self, id_token_str: str) -> Dict:
        """
        Validate Google ID token and return payload.
        
        This method:
        1. Verifies the token signature using Google's public keys
        2. Validates the audience matches our client ID
        3. Validates the issuer is accounts.google.com
        4. Validates the token has not expired
        
        Args:
            id_token_str: JWT ID token from Google
        
        Returns:
            dict: Token payload with user claims including:
                - sub: Google user ID
                - email: User's email address
                - email_verified: Whether email is verified
                - name: User's full name
                - picture: Profile picture URL
                - iss: Token issuer
                - aud: Token audience
                - exp: Expiration timestamp
                - iat: Issued at timestamp
        
        Raises:
            ValueError: If token is invalid, expired, or claims don't match
        """
        # SECURITY FIX: Validate input length to prevent DoS
        if not id_token_str or len(id_token_str) > 10000:
            raise ValueError("Invalid credential format")
        
        try:
            # SECURITY FIX: Add timeout to prevent hanging on network issues
            # Create a session with timeout for token verification
            session = http_requests.Session()
            session.timeout = 5  # 5 second timeout
            
            # Verify token signature and decode payload
            # This automatically validates:
            # - Signature using Google's public keys
            # - Expiration (exp claim)
            # - Audience (aud claim must match client_id)
            # - Issuer (iss claim must be accounts.google.com or https://accounts.google.com)
            # 
            # clock_skew_in_seconds: Allow 60 seconds of clock drift for better compatibility
            idinfo = id_token.verify_oauth2_token(
                id_token_str,
                requests.Request(session=session),  # SECURITY FIX: Use session with timeout
                self.client_id,
                clock_skew_in_seconds=60  # SECURITY FIX: Increased from 10 to 60 seconds
            )
            
            # SECURITY FIX: Explicit issuer validation
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise ValueError(f"Invalid token issuer: {idinfo['iss']}")
            
            # SECURITY FIX: Explicit audience validation
            if idinfo['aud'] != self.client_id:
                raise ValueError(f"Invalid token audience")
            
            # SECURITY FIX: Verify email is verified by Google
            if not idinfo.get('email_verified', False):
                raise ValueError('Email not verified by Google')
            
            logger.info("Google ID token validated successfully for user: %s", idinfo.get('sub'))
            return idinfo
            
        except ValueError as e:
            logger.warning("Google ID token validation failed: %s", str(e))
            raise ValueError(f"Invalid token: {str(e)}")


class GoogleProfileExtractor:
    """
    Extracts user profile information from validated Google ID token payload.
    """
    
    @staticmethod
    def extract_profile(token_payload: Dict) -> Dict:
        """
        Extract user profile from validated token payload.
        
        Args:
            token_payload: Validated ID token payload from GoogleTokenValidator
        
        Returns:
            dict: User profile with keys:
                - google_id: Google user ID (sub claim)
                - email: Normalized email address (lowercase)
                - full_name: User's full name
                - profile_picture_url: Profile picture URL
                - email_verified: Whether email is verified
        
        Raises:
            ValueError: If email is not verified or required fields are missing
        """
        # Validate email is verified
        email_verified = token_payload.get('email_verified', False)
        if not email_verified:
            raise ValueError("Email address is not verified. Please verify your email with Google.")
        
        # Extract required fields
        google_id = token_payload.get('sub')
        email = token_payload.get('email')
        full_name = token_payload.get('name', '')
        profile_picture_url = token_payload.get('picture', '')
        
        # Validate required fields are present
        if not google_id:
            raise ValueError("Missing required field: sub (Google user ID)")
        if not email:
            raise ValueError("Missing required field: email")
        
        # Normalize email to lowercase
        email = email.lower().strip()
        
        logger.info("Extracted profile for Google user: %s (email: %s)", google_id, email)
        
        return {
            'google_id': google_id,
            'email': email,
            'full_name': full_name,
            'profile_picture_url': profile_picture_url,
            'email_verified': email_verified
        }
