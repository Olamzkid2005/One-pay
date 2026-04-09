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

    def test_valid_public_url(self):
        """Valid public URL should pass validation."""
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = self._mock_dns_response('8.8.8.8')
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://example.com/logo.png")

            assert is_valid is True
            assert ip == '8.8.8.8'
            assert error is None

    def test_valid_http_url(self):
        """HTTP URLs should be allowed (HTTPS enforcement is application-level)."""
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = self._mock_dns_response('1.1.1.1')
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("http://example.com/image.jpg")

            assert is_valid is True
            assert ip == '1.1.1.1'
            assert error is None

    def test_private_ip_10_0_0_0(self):
        """Private IP 10.0.0.0/8 should be blocked."""
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = self._mock_dns_response('10.0.0.1')
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://internal.example.com")

            assert is_valid is False
            assert ip is None
            assert error is not None

    def test_private_ip_172_16_0_0(self):
        """Private IP 172.16.0.0/12 should be blocked."""
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = self._mock_dns_response('172.16.5.10')
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://internal.example.com")

            assert is_valid is False
            assert ip is None
            assert error is not None

    def test_private_ip_192_168_0_0(self):
        """Private IP 192.168.0.0/16 should be blocked."""
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = self._mock_dns_response('192.168.1.100')
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://router.local")

            assert is_valid is False
            assert ip is None
            assert error is not None

    def test_loopback_127_0_0_1(self):
        """Loopback address 127.0.0.1 should be blocked."""
        with patch('socket.gethostbyname', return_value='127.0.0.1'):
            is_valid, ip, error = validate_url_for_ssrf("https://localhost")

            assert is_valid is False
            assert ip is None
            assert error is not None

    def test_loopback_127_0_0_2(self):
        """Any 127.0.0.0/8 address should be blocked."""
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = self._mock_dns_response('127.0.0.2')
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://localhost.localdomain")

            assert is_valid is False
            assert ip is None
            assert error is not None

    def test_link_local_169_254(self):
        """Link-local address 169.254.0.0/16 should be blocked."""
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = self._mock_dns_response('169.254.1.1')
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://link-local.example.com")

            assert is_valid is False
            assert ip is None
            assert error is not None

    def test_aws_metadata_endpoint(self):
        """AWS metadata endpoint 169.254.169.254 should be explicitly blocked."""
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = self._mock_dns_response('169.254.169.254')
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://metadata.aws.internal")

            assert is_valid is False
            assert ip is None
            assert error is not None

    def test_multicast_224_0_0_0(self):
        """Multicast address 224.0.0.0/4 should be blocked."""
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = self._mock_dns_response('224.0.0.1')
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://multicast.example.com")

            assert is_valid is False
            assert ip is None
            assert error is not None

    def test_reserved_240_0_0_0(self):
        """Reserved address 240.0.0.0/4 should be blocked."""
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = self._mock_dns_response('240.0.0.1')
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://reserved.example.com")

            assert is_valid is False
            assert ip is None
            assert error is not None

    def test_current_network_0_0_0_0(self):
        """Current network 0.0.0.0/8 should be blocked."""
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = self._mock_dns_response('0.0.0.1')
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://zero.example.com")

            assert is_valid is False
            assert ip is None
            assert error is not None

    def test_ipv6_loopback(self):
        """IPv6 loopback ::1 should be blocked."""
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = self._mock_dns_response('::1')
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://localhost6")

            assert is_valid is False
            assert ip is None
            assert error is not None

    def test_dns_resolution_failure(self):
        """DNS resolution failure should be handled gracefully."""
        with patch('socket.gethostbyname', side_effect=socket.gaierror("Name or service not known")):
            is_valid, ip, error = validate_url_for_ssrf("https://nonexistent.invalid")

            assert is_valid is False
            assert ip is None
            assert error is not None

    def test_invalid_scheme_ftp(self):
        """FTP URLs should be rejected."""
        is_valid, ip, error = validate_url_for_ssrf("ftp://example.com/file.txt")

        assert is_valid is False
        assert ip is None
        assert "HTTP or HTTPS" in error

    def test_invalid_scheme_javascript(self):
        """JavaScript URLs should be rejected."""
        is_valid, ip, error = validate_url_for_ssrf("javascript:alert(1)")

        assert is_valid is False
        assert ip is None
        assert "HTTP or HTTPS" in error

    def test_invalid_scheme_data(self):
        """Data URLs should be rejected."""
        is_valid, ip, error = validate_url_for_ssrf("data:text/html,<script>alert(1)</script>")

        assert is_valid is False
        assert ip is None
        assert "HTTP or HTTPS" in error

    def test_missing_hostname(self):
        """URL without hostname should be rejected."""
        is_valid, ip, error = validate_url_for_ssrf("https://")

        assert is_valid is False
        assert ip is None
        assert "valid hostname" in error

    def test_empty_url(self):
        """Empty URL should be rejected."""
        is_valid, ip, error = validate_url_for_ssrf("")

        assert is_valid is False
        assert ip is None
        assert error is not None

    def test_url_with_port(self):
        """URL with port should be validated correctly."""
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = self._mock_dns_response('93.184.216.34')
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://example.com:8443/logo.png")

            assert is_valid is True
            assert ip == '93.184.216.34'
            assert error is None

    def test_url_with_path_and_query(self):
        """URL with path and query parameters should be validated correctly."""
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = self._mock_dns_response('1.2.3.4')
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://cdn.example.com/images/logo.png?v=123")

            assert is_valid is True
            assert ip == '1.2.3.4'
            assert error is None


class TestIsPrivateIp:
    """Test private IP detection helper function."""

    def test_public_ip_8_8_8_8(self):
        """Google DNS should be detected as public."""
        assert is_private_ip("8.8.8.8") is False

    def test_public_ip_1_1_1_1(self):
        """Cloudflare DNS should be detected as public."""
        assert is_private_ip("1.1.1.1") is False

    def test_private_ip_10_0_0_1(self):
        """10.0.0.1 should be detected as private."""
        assert is_private_ip("10.0.0.1") is True

    def test_private_ip_172_16_0_1(self):
        """172.16.0.1 should be detected as private."""
        assert is_private_ip("172.16.0.1") is True

    def test_private_ip_192_168_1_1(self):
        """192.168.1.1 should be detected as private."""
        assert is_private_ip("192.168.1.1") is True

    def test_loopback_127_0_0_1(self):
        """127.0.0.1 should be detected as private."""
        assert is_private_ip("127.0.0.1") is True

    def test_link_local_169_254_1_1(self):
        """169.254.1.1 should be detected as private."""
        assert is_private_ip("169.254.1.1") is True

    def test_multicast_224_0_0_1(self):
        """224.0.0.1 should be detected as private."""
        assert is_private_ip("224.0.0.1") is True

    def test_invalid_ip_string(self):
        """Invalid IP string should be treated as private (fail closed)."""
        assert is_private_ip("not-an-ip") is True

    def test_empty_string(self):
        """Empty string should be treated as private (fail closed)."""
        assert is_private_ip("") is True

    def test_ipv6_loopback(self):
        """IPv6 loopback ::1 should be detected as private."""
        assert is_private_ip("::1") is True

    def test_ipv6_link_local(self):
        """IPv6 link-local fe80:: should be detected as private."""
        assert is_private_ip("fe80::1") is True

    def test_ipv6_unique_local(self):
        """IPv6 unique local fc00:: should be detected as private."""
        assert is_private_ip("fc00::1") is True

    def test_ipv6_public(self):
        """Public IPv6 address should be detected as public."""
        assert is_private_ip("2001:4860:4860::8888") is False



class TestDnsRebindingRaceConditionDetection:
    """Test DNS TTL checking for race condition detection (Requirement 3.4)."""

    def test_safe_ttl_passes_validation(self):
        """URLs with safe TTL (>= 300s) should pass validation."""
        # Mock DNS resolver to return safe TTL
        mock_answer = Mock()
        mock_rrset = Mock()
        mock_rrset.ttl = 3600  # 1 hour - safe
        mock_answer.rrset = mock_rrset
        mock_answer.__getitem__ = Mock(return_value=Mock(__str__=lambda self: '8.8.8.8'))

        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = mock_answer
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://example.com/logo.png")

            assert is_valid is True
            assert ip == '8.8.8.8'
            assert error is None

    def test_low_ttl_rejected(self):
        """URLs with low TTL (< 300s) should be rejected as suspicious."""
        # Mock DNS resolver to return suspiciously low TTL
        mock_answer = Mock()
        mock_rrset = Mock()
        mock_rrset.ttl = 60  # 1 minute - suspicious
        mock_answer.rrset = mock_rrset
        mock_answer.__getitem__ = Mock(return_value=Mock(__str__=lambda self: '1.2.3.4'))

        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = mock_answer
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://attacker.com/rebind")

            assert is_valid is False
            assert ip is None
            assert "The URL could not be validated" in error

    def test_zero_ttl_rejected(self):
        """URLs with zero TTL should be rejected."""
        mock_answer = Mock()
        mock_rrset = Mock()
        mock_rrset.ttl = 0  # Zero TTL - highly suspicious
        mock_answer.rrset = mock_rrset
        mock_answer.__getitem__ = Mock(return_value=Mock(__str__=lambda self: '1.2.3.4'))

        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = mock_answer
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://zero-ttl.com/test")

            assert is_valid is False
            assert ip is None
            assert "The URL could not be validated" in error

    def test_ttl_exactly_at_threshold_passes(self):
        """URLs with TTL exactly at threshold (300s) should pass."""
        mock_answer = Mock()
        mock_rrset = Mock()
        mock_rrset.ttl = MIN_SAFE_TTL  # Exactly at threshold
        mock_answer.rrset = mock_rrset
        mock_answer.__getitem__ = Mock(return_value=Mock(__str__=lambda self: '8.8.8.8'))

        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = mock_answer
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://threshold.com/test")

            assert is_valid is True
            assert ip == '8.8.8.8'
            assert error is None

    def test_ttl_one_below_threshold_rejected(self):
        """URLs with TTL one second below threshold should be rejected."""
        mock_answer = Mock()
        mock_rrset = Mock()
        mock_rrset.ttl = MIN_SAFE_TTL - 1  # Just below threshold
        mock_answer.rrset = mock_rrset
        mock_answer.__getitem__ = Mock(return_value=Mock(__str__=lambda self: '1.2.3.4'))

        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = mock_answer
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://below-threshold.com/test")

            assert is_valid is False
            assert ip is None
            assert "The URL could not be validated" in error

    def test_dns_resolver_fallback_on_ttl_check_failure(self):
        """If DNS TTL check fails, should fallback to socket.gethostbyname."""
        # Mock DNS resolver to raise exception
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.side_effect = Exception("DNS library error")
            mock_resolver_class.return_value = mock_resolver

            # Mock socket fallback to succeed
            with patch('socket.gethostbyname', return_value='8.8.8.8'):
                is_valid, ip, error = validate_url_for_ssrf("https://example.com/logo.png")

                # Should succeed via fallback (but without TTL check)
                assert is_valid is True
                assert ip == '8.8.8.8'
                assert error is None

    def test_dns_nxdomain_rejected(self):
        """Non-existent domains should be rejected."""
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.side_effect = dns.resolver.NXDOMAIN("Domain does not exist")
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://nonexistent.invalid/test")

            assert is_valid is False
            assert ip is None
            assert "The URL hostname could not be resolved" in error

    def test_dns_timeout_rejected(self):
        """DNS timeouts should be rejected."""
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.side_effect = dns.exception.Timeout("DNS query timed out")
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://slow-dns.com/test")

            assert is_valid is False
            assert ip is None
            assert "DNS resolution timed out" in error

    def test_low_ttl_with_private_ip_rejected_for_ttl(self):
        """Low TTL should be checked before private IP check."""
        # Mock DNS resolver to return low TTL with private IP
        mock_answer = Mock()
        mock_rrset = Mock()
        mock_rrset.ttl = 10  # Very low TTL
        mock_answer.rrset = mock_rrset
        mock_answer.__getitem__ = Mock(return_value=Mock(__str__=lambda self: '192.168.1.1'))

        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = mock_answer
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://internal.local/test")

            # Should be rejected for low TTL (checked first)
            assert is_valid is False
            assert ip is None
            assert "The URL could not be validated" in error

    def test_safe_ttl_with_private_ip_rejected_for_private_ip(self):
        """Safe TTL with private IP should be rejected for private IP."""
        # Mock DNS resolver to return safe TTL with private IP
        mock_answer = Mock()
        mock_rrset = Mock()
        mock_rrset.ttl = 3600  # Safe TTL
        mock_answer.rrset = mock_rrset
        mock_answer.__getitem__ = Mock(return_value=Mock(__str__=lambda self: '192.168.1.1'))

        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = mock_answer
            mock_resolver_class.return_value = mock_resolver

            is_valid, ip, error = validate_url_for_ssrf("https://internal.local/test")

            # Should be rejected for private IP (TTL is safe)
            assert is_valid is False
            assert ip is None
            assert "The URL resolves to a restricted address" in error
