# 🔐 Security Setup Guide

## Important Security Updates

We've moved all sensitive credentials to environment variables for better security. Follow this guide to set up your environment properly.

## Local Development Setup

### 1. Create a `.env` file

Copy the example file and fill in your actual credentials:

```bash
cp .env.example .env
```

### 2. Configure Email Credentials

Edit `.env` and add your Gmail credentials:

```bash
SENDER_EMAIL=menypeled@gmail.com
SENDER_PASSWORD=your-gmail-app-password-here
```

**How to get a Gmail App Password:**
1. Go to your Google Account settings
2. Navigate to Security → 2-Step Verification
3. Scroll down to "App passwords"
4. Generate a new app password for "Mail"
5. Copy the 16-character password (without spaces)

### 3. Set Firebase Credentials (if using Firebase)

Add your Firebase configuration to `.env`:

```bash
FIREBASE_DATABASE_URL=https://sn-stock-monitor-default-rtdb.europe-west1.firebasedatabase.app/
```

For local development, you can also use the JSON file approach (already configured).

## Production Deployment (Render/Netlify)

### Setting Environment Variables on Render:

1. Go to your Render dashboard
2. Select your web service
3. Navigate to "Environment" tab
4. Add the following variables:

```
SENDER_EMAIL=menypeled@gmail.com
SENDER_PASSWORD=your-gmail-app-password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
ENVIRONMENT=production
DEBUG=False
FIREBASE_DATABASE_URL=https://your-project.firebaseio.com
FIREBASE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
```

### Setting Environment Variables on Netlify:

1. Go to Site settings → Build & deploy → Environment
2. Add the same variables as above

## Testing Your Setup

Run the application locally to test:

```bash
python3 sn_stock_monitor.py
```

If email credentials are not set, you'll see a warning but the app will still run (email alerts will be disabled).

## Security Best Practices

✅ **DO:**
- Keep `.env` file local (never commit it)
- Use environment variables for all secrets
- Rotate passwords regularly
- Use app-specific passwords for Gmail

❌ **DON'T:**
- Commit `.env` to version control
- Share credentials in code or messages
- Use your main Gmail password (use app password)
- Hardcode any sensitive data

## Troubleshooting

**Email alerts not working?**
- Check that `SENDER_PASSWORD` is set correctly
- Verify Gmail app password is valid
- Check console for error messages

**App won't start?**
- Ensure all required environment variables are set
- Check Python version (3.7+ required)
- Verify all dependencies are installed

## Changes Made

### What Changed:
1. ✅ Email credentials moved to environment variables
2. ✅ Added graceful fallback if email not configured
3. ✅ Created `.env.example` template
4. ✅ Updated security documentation

### Migration from Old Code:
If you were using hardcoded credentials before, they will no longer work. You **must** set the environment variables as described above.
