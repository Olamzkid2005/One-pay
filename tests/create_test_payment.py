"""
Create a test payment link with QR codes for manual verification
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database import get_db
from models.transaction import Transaction
from models.user import User
from services.qr_code import qr_service
from services.security import generate_tx_reference, generate_hash_token, generate_expiration_time
from decimal import Decimal

def create_test_payment():
    """Create a test payment with QR codes"""
    app = create_app()
    
    with app.app_context():
        with get_db() as db:
            # Get or create test user
            user = db.query(User).filter(User.username == "testuser").first()
            if not user:
                print("Creating test user...")
                user = User(username="testuser", email="test@example.com")
                user.set_password("TestPassword123!")
                db.add(user)
                db.flush()
                db.refresh(user)
                print(f"✅ Created user: {user.username}")
            else:
                print(f"✅ Using existing user: {user.username}")
            
            # Create transaction
            tx_ref = generate_tx_reference()
            amount = Decimal("2500.00")
            expires_at = generate_expiration_time()
            hash_token = generate_hash_token(tx_ref, amount, expires_at)
            
            tx = Transaction(
                tx_ref=tx_ref,
                user_id=user.id,
                amount=amount,
                currency="NGN",
                description="Test Payment with QR Codes",
                customer_email="customer@example.com",
                hash_token=hash_token,
                expires_at=expires_at,
            )
            
            db.add(tx)
            db.flush()
            db.refresh(tx)
            
            # Generate payment URL
            payment_url = f"http://localhost:5000/pay/{tx_ref}"
            
            print(f"\n{'='*60}")
            print(f"✅ Payment link created successfully!")
            print(f"{'='*60}")
            print(f"\n📋 Transaction Details:")
            print(f"   Reference: {tx_ref}")
            print(f"   Amount: ₦{amount:,.2f}")
            print(f"   Description: {tx.description}")
            
            print(f"\n🌐 Test URL:")
            print(f"   {payment_url}")
            
            print(f"\n💡 To test QR code feature:")
            print(f"   1. Open the URL above")
            print(f"   2. Click the 'QR Code' button")
            print(f"   3. QR code should appear")
            print(f"   4. Click 'Bank Transfer' to switch back")
            
            return tx_ref

if __name__ == '__main__':
    try:
        tx_ref = create_test_payment()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Failed to create test payment: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
