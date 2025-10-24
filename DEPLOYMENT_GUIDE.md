# 🚀 Production Deployment Guide

## ✅ Pre-Deployment Checklist

All fixes have been applied and tested locally:
- ✅ React import fixed (no crashes)
- ✅ Email credentials secured (environment variables)
- ✅ Exchange rate fallback removed (real data only)
- ✅ Dependencies updated (yfinance 0.2.65)
- ✅ Pandas deprecation warnings fixed
- ✅ Health check endpoint added (`/health`)
- ✅ Port configuration simplified
- ✅ All tests passing locally

---

## 🌐 Deploying to Render

### Step 1: Update Environment Variables

Go to your Render dashboard and add/update these environment variables:

**Required Variables:**
```
SENDER_EMAIL=menypeled@gmail.com
SENDER_PASSWORD=your-gmail-app-password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
ENVIRONMENT=production
DEBUG=False
```

**Firebase Variables (if using):**
```
FIREBASE_DATABASE_URL=https://sn-stock-monitor-default-rtdb.europe-west1.firebasedatabase.app/
FIREBASE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
```

### Step 2: Deploy the Code

**Option A: Automatic Deployment (Recommended)**
```bash
# Commit all changes
git add .
git commit -m "Applied security fixes and improvements"
git push origin main
```

Render will automatically detect the push and deploy.

**Option B: Manual Deployment**
1. Go to Render Dashboard
2. Select your service: `sn-stock-monitor`
3. Click "Manual Deploy" → "Deploy latest commit"

### Step 3: Verify Deployment

Once deployed, test these endpoints:

1. **Health Check:**
   ```bash
   curl https://now-stock-monitor.onrender.com/health
   ```
   Expected: `{"status": "healthy", ...}`

2. **Main Dashboard:**
   ```
   https://now-stock-monitor.onrender.com/
   ```

3. **API Status:**
   ```bash
   curl https://now-stock-monitor.onrender.com/api/status
   ```

4. **Best to Sell:**
   ```
   https://now-stock-monitor.onrender.com/best-to-sell
   ```

### Step 4: Monitor Logs

Check Render logs for any errors:
1. Go to Render Dashboard
2. Select your service
3. Click "Logs" tab
4. Look for:
   - ✅ "Starting Flask app on port..."
   - ✅ "Firebase initialized: True"
   - ✅ No error messages

---

## 🔍 Health Check Endpoint

The new `/health` endpoint provides service status:

```json
{
  "status": "healthy",
  "timestamp": "2025-10-24T13:51:09.522852",
  "services": {
    "stock_api": "healthy",
    "exchange_api": "healthy",
    "firebase": "healthy",
    "flask": "healthy"
  },
  "version": "2.0.0"
}
```

**Status Codes:**
- `200` - All services healthy
- `503` - One or more services degraded

**Use Cases:**
- Render health checks
- Monitoring services (UptimeRobot, Pingdom)
- CI/CD pipeline verification
- Manual service verification

---

## 📊 What Changed in This Deployment

### Code Improvements:
1. **Fixed React Import** - Added missing `WindowAllYearsLineCharts` import
2. **Secured Credentials** - Moved email credentials to environment variables
3. **Real Data Only** - Removed fallback to simulated exchange rates
4. **Updated Dependencies** - yfinance 0.2.37 → 0.2.65
5. **Fixed Pandas Warnings** - Updated deprecated Series indexing
6. **Added Health Check** - New `/health` endpoint for monitoring
7. **Simplified Port Logic** - Clear priority order for port selection

### Breaking Changes:
- **Email alerts require environment variables** - Set `SENDER_PASSWORD` or alerts will be disabled
- **Exchange rate failures raise exceptions** - No more fallback to default rate (3.42)

---

## 🧪 Post-Deployment Testing

### 1. Test Main Features:
- [ ] Stock price fetching (NOW ticker)
- [ ] Exchange rate fetching (USD/ILS)
- [ ] Profitability calculations
- [ ] Email alerts (if configured)
- [ ] All web pages load

### 2. Test API Endpoints:
- [ ] `GET /api/status` - Returns current stock data
- [ ] `POST /api/refresh` - Refreshes stock data
- [ ] `GET /health` - Returns service health
- [ ] `GET /best-to-sell` - Sell analysis page
- [ ] `GET /best-to-buy-sp` - Buy analysis page

### 3. Verify Security:
- [ ] No hardcoded credentials in logs
- [ ] Environment variables loaded correctly
- [ ] HTTPS working (Render provides SSL)

---

## 🔧 Troubleshooting

### Issue: Email alerts not working
**Solution:** Verify `SENDER_PASSWORD` environment variable is set correctly in Render dashboard

### Issue: Exchange rate API failing
**Check:** 
- Health endpoint shows exchange_api status
- Frankfurter API is accessible
- No rate limiting issues

### Issue: Firebase connection failed
**Solution:** 
- Verify `FIREBASE_DATABASE_URL` is set
- Check `FIREBASE_SERVICE_ACCOUNT_JSON` is valid JSON
- Ensure Firebase project is active

### Issue: App won't start
**Check:**
- Render build logs for errors
- Python version compatibility (3.7+)
- All dependencies installed correctly

---

## 📈 Monitoring Recommendations

### Set Up Health Check Monitoring:
1. **UptimeRobot** (Free):
   - Monitor: `https://now-stock-monitor.onrender.com/health`
   - Interval: 5 minutes
   - Alert on: Status code != 200

2. **Render Built-in**:
   - Render automatically monitors your service
   - Check "Events" tab for deployment history

### Set Up Alerts:
- Email notifications for downtime
- Slack/Discord webhooks for critical errors
- Log aggregation (optional)

---

## 🎯 Success Criteria

Your deployment is successful when:
- ✅ Health endpoint returns 200 status
- ✅ All services show "healthy" status
- ✅ Main dashboard loads without errors
- ✅ Stock data updates in real-time
- ✅ Exchange rates fetch successfully
- ✅ No errors in Render logs
- ✅ Email alerts working (if configured)

---

## 📞 Support

If you encounter issues:
1. Check Render logs first
2. Test health endpoint
3. Verify environment variables
4. Review this deployment guide
5. Check `FIXES_APPLIED.md` for recent changes

---

## 🔄 Rollback Plan

If deployment fails:
1. Go to Render Dashboard
2. Click "Rollback" to previous deployment
3. Investigate issues locally
4. Fix and redeploy

---

**Current Version:** 2.0.0  
**Last Updated:** October 24, 2025  
**Deployment Status:** Ready for Production ✅
