"""
Integration tests for URL validator service demonstrating real-world usage.

These tests show how the URL validator should be integrated with HTTP requests
to prevent SSRF attacks via DNS rebinding (TOCTOU vulnerabilities).
"""

from unittest.mock import Mock, patch

import dns.resolver
import pytest
import requests

from services.url_validator import validate_url_for_ssrf


class TestUrlValidatorIntegration:
    """Integration tests showing proper usage of URL validator."""

    def _mock_dns_response(self, ip: str, ttl: int = 3600):
        """Helper to create a mock DNS response."""
        mock_answer = Mock()
        mock_rrset = Mock()
        mock_rrset.ttl = ttl
        mock_answer.rrset = mock_rrset
        mock_answer.__getitem__ = Mock(return_value=Mock(__str__=lambda self: ip))
        return mock_answer

    def test_safe_http_request_pattern(self) -> None:
        """
        Demonstrate the correct pattern for making HTTP requests with SSRF protection.

        The resolved IP should be used directly in the request URL, with the original
        hostname passed in the Host header to prevent DNS rebinding attacks.
        """
        logo_url = "https://cdn.example.com/logo.png"

        # Step 1: Validate URL and get resolved IP
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = self._mock_dns_response('93.184.216.34')
            mock_resolver_class.return_value = mock_resolver

            is_valid, resolved_ip, error = validate_url_for_ssrf(logo_url)

        assert is_valid is True
        assert resolved_ip == '93.184.216.34'

        # Step 2: Make HTTP request using resolved IP with Host header
        # This prevents DNS rebinding attacks (TOCTOU)
        from urllib.parse import urlparse
        parsed = urlparse(logo_url)

        # Construct URL with IP instead of hostname
        safe_url = f"{parsed.scheme}://{resolved_ip}{parsed.path}"

        # Mock the HTTP request
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {'Content-Type': 'image/png'}
            mock_get.return_value = mock_response

            # Make request with Host header set to original hostname
            response = requests.get(
                safe_url,
                headers={'Host': parsed.hostname},
                timeout=5,
                verify=True  # Always verify SSL certificates
            )

            # Verify the request was made correctly
            mock_get.assert_called_once_with(
                safe_url,
                headers={'Host': parsed.hostname},
                timeout=5,
                verify=True
            )

            assert response.status_code == 200

    def test_reject_private_ip_before_request(self) -> None:
        """
        Demonstrate that private IPs are rejected BEFORE making HTTP requests.

        This prevents SSRF attacks where an attacker tries to access internal
        resources like AWS metadata endpoints, internal APIs, or local services.
        """
        malicious_url = "https://internal.company.local/secret-data"

        # Attacker's DNS server resolves to private IP
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = self._mock_dns_response('10.0.0.5')
            mock_resolver_class.return_value = mock_resolver

            is_valid, resolved_ip, error = validate_url_for_ssrf(malicious_url)

        # Validation fails - no HTTP request should be made
        assert is_valid is False
        assert resolved_ip is None
        assert "The URL resolves to a restricted address" in error

        # Application should NOT proceed with HTTP request
        # This prevents SSRF attack

    def test_dns_rebinding_attack_prevention(self) -> None:
        """
        Demonstrate prevention of DNS rebinding attacks (TOCTOU).

        In a DNS rebinding attack:
        1. First DNS lookup returns public IP (passes validation)
        2. Attacker changes DNS to private IP
        3. HTTP request resolves DNS again, gets private IP
        4. SSRF attack succeeds

        Our solution: Use the resolved IP directly in HTTP request.
        """
        attack_url = "https://attacker.com/rebind"

        # First DNS lookup returns public IP with safe TTL
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = self._mock_dns_response('1.2.3.4', ttl=3600)
            mock_resolver_class.return_value = mock_resolver

            is_valid, resolved_ip, error = validate_url_for_ssrf(attack_url)

        assert is_valid is True
        assert resolved_ip == '1.2.3.4'

        # Attacker changes DNS to point to private IP (e.g., 169.254.169.254)
        # But we use the ALREADY RESOLVED IP in the HTTP request
        # So the attack fails - we never do a second DNS lookup

        from urllib.parse import urlparse
        parsed = urlparse(attack_url)
        safe_url = f"{parsed.scheme}://{resolved_ip}{parsed.path}"

        # The HTTP request uses 1.2.3.4 (the validated IP)
        # NOT attacker.com (which now resolves to 169.254.169.254)
        assert '1.2.3.4' in safe_url
        assert 'attacker.com' not in safe_url

    def test_aws_metadata_endpoint_attack_prevention(self) -> None:
        """
        Demonstrate prevention of AWS metadata endpoint SSRF attack.

        Common SSRF target: http://169.254.169.254/latest/meta-data/
        This endpoint provides AWS credentials and sensitive instance data.
        """
        # Attacker tries to access AWS metadata endpoint
        attack_url = "https://metadata.aws.internal/latest/meta-data/iam/security-credentials/"

        # DNS resolves to AWS metadata IP
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = self._mock_dns_response('169.254.169.254')
            mock_resolver_class.return_value = mock_resolver

            is_valid, resolved_ip, error = validate_url_for_ssrf(attack_url)

        # Attack is blocked with specific error message
        assert is_valid is False
        assert resolved_ip is None
        assert "The URL resolves to a restricted address" in error

        # No HTTP request should be made - credentials are safe

    def test_localhost_bypass_attempt_prevention(self) -> None:
        """
        Demonstrate prevention of localhost bypass attempts.

        Attackers may try various localhost representations:
        - localhost
        - 127.0.0.1
        - 127.0.0.2 (also loopback)
        - 0.0.0.0
        """
        localhost_variants = [
            ("https://localhost/admin", "127.0.0.1"),
            ("https://local.test/api", "127.0.0.2"),
            ("https://zero.test/internal", "0.0.0.0"),  # nosec B104
        ]

        for url, resolved_ip in localhost_variants:
            with patch('dns.resolver.Resolver') as mock_resolver_class:
                mock_resolver = Mock()
                mock_resolver.resolve.return_value = self._mock_dns_response(resolved_ip)
                mock_resolver_class.return_value = mock_resolver

                is_valid, ip, error = validate_url_for_ssrf(url)

            assert is_valid is False
            assert ip is None
            assert "The URL resolves to a restricted address" in error

    def test_error_handling_for_dns_failures(self) -> None:
        """
        Demonstrate proper error handling for DNS resolution failures.

        DNS failures should be treated as validation failures to prevent
        potential attacks using DNS timeouts or errors.
        """
        invalid_url = "https://nonexistent.invalid.tld/logo.png"

        # DNS resolution fails
        with patch('socket.gethostbyname', side_effect=Exception("DNS timeout")):
            is_valid, resolved_ip, error = validate_url_for_ssrf(invalid_url)

        # Validation fails - fail closed for security
        assert is_valid is False
        assert resolved_ip is None
        assert error is not None

        # Application should show user-friendly error
        # "Logo URL is not accessible" or similar
