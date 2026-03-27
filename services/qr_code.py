"""
OnePay — QR Code Service
Generates QR codes for payment links and virtual accounts.
"""
import base64
import io
import logging
from typing import Optional

import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer

from config import Config

logger = logging.getLogger(__name__)


class QRCodeService:
    """Service for generating QR codes for OnePay payment links."""
    
    def __init__(self):
        self.default_box_size = 10
        self.default_border = 4
        self.default_fill_color = "black"
        self.default_back_color = "white"
    
    def generate_payment_qr(
        self,
        payment_url: str,
        amount: Optional[str] = None,
        description: Optional[str] = None,
        include_logo: bool = False,
        style: str = "standard"
    ) -> str:
        """
        Generate QR code for payment link.
        
        Args:
            payment_url: The payment URL to encode
            amount: Optional amount to include in QR data
            description: Optional description to include
            include_logo: Whether to include OnePay logo (future feature)
            style: QR code style ('standard', 'rounded')
            
        Returns:
            Base64-encoded PNG image data URI
        """
        try:
            # Enhanced QR data with payment information
            qr_data = self._build_payment_data(payment_url, amount, description)
            
            # Configure QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=self.default_box_size,
                border=self.default_border,
            )
            
            qr.add_data(qr_data)
            qr.make(fit=True)
            
            # Create image with style
            if style == "rounded":
                img = qr.make_image(
                    fill_color=self.default_fill_color,
                    back_color=self.default_back_color,
                    image_factory=StyledPilImage,
                    module_drawer=RoundedModuleDrawer()
                )
            else:
                img = qr.make_image(
                    fill_color=self.default_fill_color,
                    back_color=self.default_back_color
                )
            
            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG', optimize=True)
            buffer.seek(0)
            
            img_base64 = base64.b64encode(buffer.getvalue()).decode()
            data_uri = f"data:image/png;base64,{img_base64}"
            
            logger.debug("QR code generated successfully for payment URL")
            return data_uri
            
        except Exception as e:
            logger.error("Failed to generate QR code: %s", e)
            raise
    
    def generate_virtual_account_qr(
        self,
        account_number: str,
        bank_name: str,
        account_name: str,
        amount: Optional[str] = None
    ) -> str:
        """
        Generate QR code for virtual account payment.
        
        Args:
            account_number: Virtual account number
            bank_name: Bank name
            account_name: Account holder name
            amount: Optional payment amount
            
        Returns:
            Base64-encoded PNG image data URI
        """
        try:
            # Build transfer instruction data
            qr_data = self._build_transfer_data(
                account_number, bank_name, account_name, amount
            )
            
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=self.default_box_size,
                border=self.default_border,
            )
            
            qr.add_data(qr_data)
            qr.make(fit=True)
            
            img = qr.make_image(
                fill_color=self.default_fill_color,
                back_color=self.default_back_color,
                image_factory=StyledPilImage,
                module_drawer=RoundedModuleDrawer()
            )
            
            buffer = io.BytesIO()
            img.save(buffer, format='PNG', optimize=True)
            buffer.seek(0)
            
            img_base64 = base64.b64encode(buffer.getvalue()).decode()
            data_uri = f"data:image/png;base64,{img_base64}"
            
            logger.debug("QR code generated successfully for virtual account")
            return data_uri
            
        except Exception as e:
            logger.error("Failed to generate virtual account QR code: %s", e)
            raise
    
    def _build_payment_data(
        self,
        payment_url: str,
        amount: Optional[str] = None,
        description: Optional[str] = None
    ) -> str:
        """Build QR data payload for payment link."""
        data_parts = [payment_url]
        
        if amount:
            data_parts.append(f"amount:{amount}")
        
        if description:
            data_parts.append(f"desc:{description}")
        
        data_parts.append("provider:OnePay")
        
        return "|".join(data_parts)
    
    def _build_transfer_data(
        self,
        account_number: str,
        bank_name: str,
        account_name: str,
        amount: Optional[str] = None
    ) -> str:
        """Build QR data payload for bank transfer."""
        # Nigerian bank transfer format
        data_parts = [
            f"acc:{account_number}",
            f"bank:{bank_name}",
            f"name:{account_name}"
        ]
        
        if amount:
            data_parts.append(f"amount:{amount}")
        
        data_parts.append("provider:OnePay")
        
        return "|".join(data_parts)


# Global instance
qr_service = QRCodeService()
