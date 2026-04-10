// Refund Management JavaScript

document.addEventListener('DOMContentLoaded', () => {
    const refundForm = document.getElementById('refundForm');
    if (refundForm) {
        refundForm.addEventListener('submit', handleRefundSubmit);
    }
});

async function handleRefundSubmit(event) {
    event.preventDefault();
    
    const txRef = document.getElementById('txRef').value;
    const amount = document.getElementById('amount').value;
    const reason = document.getElementById('reason').value;
    
    const submitBtn = event.target.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = 'Processing...';
    
    try {
        const response = await fetch('/refunds/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': '{{ csrf_token }}'
            },
            body: JSON.stringify({
                tx_ref: txRef,
                amount: amount,
                reason: reason
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(`Refund initiated successfully!\n\nReference: ${data.refund_reference}\nStatus: ${data.status}`);
            refundForm.reset();
            window.location.reload();
        } else {
            alert('Error: ' + data.message);
        }
    } catch (error) {
        console.error('Failed to initiate refund:', error);
        alert('Failed to initiate refund. Please try again.');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
    }
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        const btn = event.target;
        const originalText = btn.textContent;
        btn.textContent = 'check';
        setTimeout(() => {
            btn.textContent = originalText;
        }, 1000);
    });
}
