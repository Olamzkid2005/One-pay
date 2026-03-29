# Gmail Email Setup Guide for OnePay

## Step-by-Step Instructions

### 1. Enable 2-Factor Authentication (Required)

1. Go to your Google Account: https://myaccount.google.com/security
2. Find "2-Step Verification" section
3. Click "Get Started" and follow the prompts
4. Complete the setup (you'll need your phone)

### 2. Generate App Password

1. Go to: https://myaccount.google.com/apppasswords
   - Or search "App Passwords" in your Google Account settings
2. You may need to sign in again
3. Under "Select app" choose **Mail**
4. Under "Select device" choose **Windows Computer** (or "Other" and name it "OnePay")
5. Click **Generate**
6. Google will show you a 16-character password like: `abcd efgh ijkl mnop`
7. **Copy this password** - you won't see it again!

### 3. Update Your .env File

Open your `.env` file and update these lines:

```env
# Email Configuration
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=abcdefghijklmnop
MAIL_FROM=your-email@gmail.com
```

**Replace:**
- `your-email@gmail.com` with your actual Gmail address
- `abcdefghijklmnop` with the 16-character app password (remove spaces)

**Example:**
```env
MAIL_USERNAME=john.doe@gmail.com
MAIL_PASSWORD=xyzw1234abcd5678
MAIL_FROM=john.doe@gmail.com
```

### 4. Test the Configuration

After updating `.env`, run the test script:

```bash
python test_email_config.py
```

This will:
- Verify your SMTP credentials
- Send a test email to yourself
- Confirm the email service is working

### 5. Restart Your Application

After confirming the test works:

```bash
# Stop your app if running (Ctrl+C)
# Then restart it
python app.py
```

### 6. Test Invoice Email

1. Go to your OnePay dashboard
2. Navigate to Invoices page
3. Find an unpaid invoice with a customer email
4. Click "Resend Invoice"
5. Check the customer's email inbox

## Troubleshooting

### "Username and Password not accepted"
- Make sure you're using the **App Password**, not your regular Gmail password
- Remove any spaces from the app password
- Verify 2FA is enabled on your Google account

### "SMTP connection failed"
- Check your internet connection
- Verify `MAIL_PORT=587` and `MAIL_USE_TLS=true`
- Some networks block port 587 - try port 465 with `MAIL_USE_SSL=true`

### "Daily sending limit exceeded"
- Gmail free accounts: 500 emails/day
- Wait 24 hours or upgrade to Google Workspace

### Email goes to spam
- Ask recipients to mark as "Not Spam"
- Consider using a custom domain with Google Workspace
- Or upgrade to SendGrid for better deliverability

## Security Notes

- **Never commit your `.env` file to git** (it's already in `.gitignore`)
- App passwords are safer than your main password
- You can revoke app passwords anytime at https://myaccount.google.com/apppasswords
- Each app password is unique - don't reuse them

## Gmail Limits

- **Free Gmail**: 500 emails/day
- **Google Workspace**: 2,000 emails/day
- Limits reset at midnight Pacific Time

## Next Steps

Once email is working:
1. Test with a real invoice
2. Check email formatting and PDF attachment
3. Verify payment links work in the email
4. Consider upgrading to SendGrid if you need more volume

## Support

If you encounter issues:
1. Check the application logs for error messages
2. Verify your `.env` configuration
3. Test with the `test_email_config.py` script
4. Review the troubleshooting section above
