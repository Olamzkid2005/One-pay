#!/usr/bin/env python3
"""
End-to-end test for QR code functionality in OnePay
"""

import requests
import json
import time

BASE_URL = "http://localhost:5000"

def test_qr_integration():
    print("Testing QR Code Integration")
    print("=" * 40)
    
    session = requests.Session()
    
    # Test 1: Check if main page loads
    try:
        response = session.get(BASE_URL)
        print(f"Main page loads: {response.status_code}")
    except Exception as e:
        print(f"Main page error: {e}")
        return
    
    # Test 2: Check if QR code service is working
    try:
        from services.qr_code import qr_service
        
        # Generate test QR codes
        payment_qr = qr_service.generate_payment_qr(
            payment_url=f"{BASE_URL}/pay/TEST-QR-123",
            amount="5000.00",
            description="QR Test Payment"
        )
        
        print(f"Payment QR code generated ({len(payment_qr)} chars)")
        
        va_qr = qr_service.generate_virtual_account_qr(
            account_number="9876543210",
            bank_name="Test Bank",
            account_name="QR Test Account",
            amount="5000.00"
        )
        
        print(f"Virtual account QR code generated ({len(va_qr)} chars)")
        
    except Exception as e:
        print(f"QR service error: {e}")
    
    # Test 3: Check database has QR columns
    try:
        from database import get_db
        from sqlalchemy import text
        
        with get_db() as db:
            result = db.execute(text("PRAGMA table_info(transactions)"))
            columns = [row[1] for row in result]
            
            qr_columns = ['qr_code_payment_url', 'qr_code_virtual_account']
            missing = [col for col in qr_columns if col not in columns]
            
            if not missing:
                print("Database QR columns exist")
            else:
                print(f"Missing QR columns: {missing}")
                
    except Exception as e:
        print(f"Database check error: {e}")
    
    print("\n" + "=" * 40)
    print("QR Integration Test Complete!")
    print("\nNext Steps:")
    print("1. Open http://localhost:5000 in browser")
    print("2. Register/login to merchant account")
    print("3. Create a payment link")
    print("4. Check for 'QR Codes Generated' section")
    print("5. Click 'View Payment Page' to see QR codes")
    print("6. Verify QR codes are scannable")

if __name__ == "__main__":
    test_qr_integration()
