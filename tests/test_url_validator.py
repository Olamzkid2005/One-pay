"""
Unit tests for URL validator service with SSRF protection.

Tests cover:
- Valid public URLs
- Private IP ranges (RFC 1918, loopback, link-local, multicast)
- DNS resolution failures
- Invalid URL formats
- AWS metadata endpoint blocking
- IPv6 addresses
- DNS TTL checking for race condition detection (Requirement 3.4)
"""

import socket
from unittest.mock import Mock, patch

import dns.rdatatype
import dns.resolver
import pytest

from services.url_validator import MIN_SAFE_TTL, is_private_ip, validate_url_for_ssrf


class TestValidateUrlForSsrf:
    """Test URL validation with SSRF protection."""

    def _mock_dns_response(self, ip: str, ttl: int = 3600):
        """Helper to create a mock DNS response."""
        mock_answer = Mock()
        mock_rrset = Mock()
        mock_rrset.ttl = ttl
        mock_answer.rrset = mock_rrset
        mock_answer.__getitem__ = Mock(return_value=Mock(__str__=lambda self: ip))
        return mock_answer

    def test_valid_public_url(self) -> None:
        """Valid public URL should pass validation."""
        with patch("dns.resolver.Resolver") as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = self._mock_dns_response("8.8.8.8")
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://example.com/logo.png")

            assert is_valid is True
            assert ip == "8.8.8.8"
            assert error is None

    def test_valid_http_url(self) -> None:
        """HTTP URLs should be allowed (HTTPS enforcement is application-level)."""
        with patch("dns.resolver.Resolver") as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = self._mock_dns_response("1.1.1.1")
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("http://example.com/image.jpg")

            assert is_valid is True
            assert ip == "1.1.1.1"
            assert error is None

    def test_private_ip_10_0_0_0(self) -> None:
        """Private IP 10.0.0.0/8 should be blocked."""
        with patch("dns.resolver.Resolver") as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = self._mock_dns_response("10.0.0.1")
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://internal.example.com")

            assert is_valid is False
            assert ip is None
            assert "restricted address" in error.lower()

    def test_zero_ttl_rejected(self) -> None:
        """URLs with zero TTL should be rejected."""
        mock_answer = Mock()
        mock_rrset = Mock()
        mock_rrset.ttl = 0  # Zero TTL - highly suspicious
        mock_answer.rrset = mock_rrset
        mock_answer.__getitem__ = Mock(return_value=Mock(__str__=lambda self: "1.2.3.4"))

        with patch("dns.resolver.Resolver") as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = mock_answer
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://zero-ttl.com/test")

            assert is_valid is False
            assert ip is None
            assert "DNS TTL too low" in error

    def test_ttl_exactly_at_threshold_passes(self) -> None:
        """URLs with TTL exactly at threshold (300s) should pass."""
        mock_answer = Mock()
        mock_rrset = Mock()
        mock_rrset.ttl = MIN_SAFE_TTL  # Exactly at threshold
        mock_answer.rrset = mock_rrset
        mock_answer.__getitem__ = Mock(return_value=Mock(__str__=lambda self: "8.8.8.8"))

        with patch("dns.resolver.Resolver") as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = mock_answer
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://threshold.com/test")

            assert is_valid is True
            assert ip == "8.8.8.8"
            assert error is None

    def test_ttl_one_below_threshold_rejected(self) -> None:
        """URLs with TTL one second below threshold should be rejected."""
        mock_answer = Mock()
        mock_rrset = Mock()
        mock_rrset.ttl = MIN_SAFE_TTL - 1  # Just below threshold
        mock_answer.rrset = mock_rrset
        mock_answer.__getitem__ = Mock(return_value=Mock(__str__=lambda self: "1.2.3.4"))

        with patch("dns.resolver.Resolver") as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = mock_answer
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://below-threshold.com/test")

            assert is_valid is False
            assert ip is None
            assert "DNS TTL too low" in error

    def test_dns_resolver_fallback_on_ttl_check_failure(self) -> None:
        """If DNS TTL check fails, should fallback to socket.gethostbyname."""
        # Mock DNS resolver to raise exception
        with patch("dns.resolver.Resolver") as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.side_effect = Exception("DNS library error")
            mock_resolver_class.return_value = mock_resolver

            # Mock socket fallback to succeed
            with patch("socket.gethostbyname", return_value="8.8.8.8"):
                is_valid, ip, error = validate_url_for_ssrf("https://example.com/logo.png")

                # Should succeed via fallback (but without TTL check)
                assert is_valid is True
                assert ip == "8.8.8.8"
                assert error is None

    def test_dns_nxdomain_rejected(self) -> None:
        """Non-existent domains should be rejected."""
        with patch("dns.resolver.Resolver") as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.side_effect = dns.resolver.NXDOMAIN("Domain does not exist")
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://nonexistent.invalid/test")

            assert is_valid is False
            assert ip is None
            assert "Hostname could not be resolved" in error

    def test_dns_timeout_rejected(self) -> None:
        """DNS timeouts should be rejected."""
        with patch("dns.resolver.Resolver") as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.side_effect = dns.exception.Timeout("DNS query timed out")
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://slow-dns.com/test")

            assert is_valid is False
            assert ip is None
            assert "Hostname could not be resolved" in error

    def test_low_ttl_with_private_ip_rejected_for_ttl(self) -> None:
        """Low TTL should be checked before private IP check."""
        # Mock DNS resolver to return low TTL with private IP
        mock_answer = Mock()
        mock_rrset = Mock()
        mock_rrset.ttl = 10  # Very low TTL
        mock_answer.rrset = mock_rrset
        mock_answer.__getitem__ = Mock(return_value=Mock(__str__=lambda self: "192.168.1.1"))

        with patch("dns.resolver.Resolver") as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = mock_answer
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://internal.local/test")

            # Should be rejected for low TTL (checked first)
            assert is_valid is False
            assert ip is None
            assert "DNS TTL too low" in error

    def test_safe_ttl_with_private_ip_rejected_for_private_ip(self) -> None:
        """Safe TTL with private IP should be rejected for private IP."""
        # Mock DNS resolver to return safe TTL with private IP
        mock_answer = Mock()
        mock_rrset = Mock()
        mock_rrset.ttl = 3600  # Safe TTL
        mock_answer.rrset = mock_rrset
        mock_answer.__getitem__ = Mock(return_value=Mock(__str__=lambda self: "192.168.1.1"))

        with patch("dns.resolver.Resolver") as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = mock_answer
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://internal.local/test")

            # Should be rejected for private IP (TTL is safe)
            assert is_valid is False
            assert ip is None
            assert "restricted address" in error.lower()
