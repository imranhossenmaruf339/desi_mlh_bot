# 🏷️ Invisible Tagall System - Implementation Guide

## Overview

The Invisible Tagall system allows group admins to mention all members in a group without creating visible spam or mention lists. It uses Zero-Width Non-Joiner (ZWNJ) characters combined with HTML hyperlink mentions for maximum compatibility and invisibility.

---

## Quick Start

### Basic Usage

```bash
# Tag all members
/tagall

# Tag with a message
/tagall Check the pinned announcement!

# Stop ongoing tagging
/stoptag

# View tagging progress
/taggingstatus

# Get help
/taghelp
```

---

## Features

### 1. Invisible Mentions 👻
- Uses Zero-Width Non-Joiner character (U+200C)
- Combined with HTML `<a href='tg://user?id=UID'>` hyperlinks
- **Result**: Message appears clean while notifying all members
- No visible @ mentions or ID lists in the message

### 2. Batch Processing 📦
- Splits members into configurable batches (default: 5 members per message)
- Prevents Telegram API rate limiting
- **Benefit**: Can tag 500+ member groups safely
- Each batch includes progress tracking

### 3. Custom Messages 💬
- Admin can include a message with the tag
- Message appears before invisible mentions
- HTML formatting supported
- **Use Case**: Announcements, reminders, urgent messages

### 4. Session Management 📋
- Each tagging operation is tracked as a session
- Sessions stored in MongoDB with full details
- Can cancel ongoing tagging with `/stoptag`
- View progress with `/taggingstatus`

### 5. Error Handling & Retries 🔄
- Automatic retry for failed batches (default: 3 retries)
- Detailed error reporting
- Success rate calculation
- Logging of all operations

### 6. Admin Configuration ⚙️
- Super admins can customize batch behavior
- View tagging history and statistics
- Monitor performance

---

## Commands

### For Group Admins

#### `/tagall [message]`
Tag all group members with optional message.

**Usage:**
```
/tagall                                    # No message
/tagall Important announcement!            # With message
/tagall Don't forget: Meeting at 5 PM      # With details
```

**Output:**
```
🔄 Fetching group members...
👥 Found 150 members
🏷️ Starting tagging process

[Progress updates every batch...]

✅ Tagging Complete
Total Members: 150
Tagged: 148
Failed: 2
Success Rate: 98.7%
```

#### `/stoptag` or `/cancel`
Stop the ongoing tagging operation immediately.

**Output:**
```
⏹️ Tagging Stopped
Tagged: 45/150
```

#### `/taggingstatus`
View current tagging progress.

**Output:**
```
📊 Tagging Status
Status: 🔄 In Progress
Admin: John
Members: 250
Progress: 3/50 batches
```

#### `/taghelp`
Display help information about tagging commands.

---

### For Super Admin (Private Chat)

#### `/tagconfig batchsize <number>`
Set the number of members per batch.

```bash
/tagconfig batchsize 5      # Default: 5 members per message
/tagconfig batchsize 10     # Faster but higher API risk
/tagconfig batchsize 3      # Slower but safer
```

**Recommendation:**
- `3-5`: Very safe, slower (recommended for first time)
- `5-10`: Safe, moderate speed (recommended)
- `10+`: Fast but risky (use with caution)

#### `/tagconfig delay <seconds>`
Set the delay between batches.

```bash
/tagconfig delay 1.5       # Default: 1.5 seconds
/tagconfig delay 2.0       # Safer, prevents rate limiting
/tagconfig delay 0.5       # Faster but risky
```

**Recommendation:**
- `1.5+`: Safe (recommended)
- `0.5-1.5`: Moderate risk
- `<0.5`: Very risky

#### `/tagconfig retries <number>`
Set the maximum retries per batch.

```bash
/tagconfig retries 3       # Default: 3 attempts
/tagconfig retries 5       # More reliable
/tagconfig retries 1       # Faster but less reliable
```

#### `/taghistory [limit]`
View tagging history.

```bash
/taghistory              # Last 20 sessions
/taghistory 50           # Last 50 sessions
/taghistory -1234567890  # For specific group
```

**Output:**
```
📝 Tagging History (Last 10)

1. Group: -1001234567890
   👤 Admin: John
   👥 Members: 150 → ✅ 148 (98.7%)
   📅 15 Jan 2024 10:30

2. Group: -1001234567890
   👤 Admin: Jane
   👥 Members: 200 → ✅ 195 (97.5%)
   📅 14 Jan 2024 15:45
```

---

## Administration

### Permissions

- ✅ **Who Can Use `/tagall`**: Group admins only
- ✅ **Bot Requirement**: Bot must be a group admin
- ✅ **Who Can Configure**: Super admin only (ADMIN_ID in config.py)

### Error Messages

**"❌ Admin Only"**
- User is not a group admin
- Solution: Make user a group admin

**"❌ Bot Permission Error"**
- Bot is not a group admin
- Solution: Give bot admin permissions

**"⚠️ Tagging Already in Progress"**
- Another tagging session is active
- Solution: Wait or use `/stoptag`

**"❌ No members found"**
- Group has no non-bot members
- Solution: Check group member list

### Monitoring

**Real-time Progress**
- Use `/taggingstatus` to see current progress
- Updates show batches completed and members tagged

**Session Details**
- Each session stored in MongoDB
- Includes: admin name, member count, success rate, timestamp
- Useful for auditing and analytics

---

## Technical Details

### How It Works

1. **User runs `/tagall` command**
   ```
   Admin types: /tagall Check the pinned message!
   ```

2. **Bot fetches group members**
   ```
   Retrieves all non-bot members (max 500)
   ```

3. **Create session**
   ```
   Store in MongoDB: admin_id, member_count, custom_msg
   Add to in-memory session tracker
   ```

4. **Split into batches**
   ```
   Example: 150 members with batchsize=5
   → 30 batches of 5 members each
   ```

5. **Processing each batch**
   ```
   For each batch:
     - Build invisible mentions using ZWNJ
     - Add custom message if provided
     - Send message to group
     - Wait for batch_delay seconds
     - Handle errors and retries
   ```

6. **Session cleanup**
   ```
   Update MongoDB with final stats
   Remove from in-memory tracker
   Log completion event
   ```

### ZWNJ + Hyperlink Mention

**Formula:**
```
{ZWNJ}<a href='tg://user?id={USER_ID}'>​</a>
```

**Breakdown:**
- `{ZWNJ}` = Zero-Width Non-Joiner character (U+200C)
- `<a href='tg://user?id={USER_ID}'>` = Telegram user profile link
- `​` = Zero-Width Space (invisible space)
- **Result**: Invisible text that notifies when touched

**Why This Works:**
1. ZWNJ makes text invisible
2. HTML link ensures notification is sent
3. Telegram recognizes the user ID link
4. User gets notification without seeing the mention

### Database Schema

```javascript
{
  "session_id": "ChatId_AdminId_Timestamp",
  "chat_id": -1001234567890,                    // Group chat ID
  "admin_id": 123456789,                        // Admin user ID
  "admin_name": "John Doe",                     // Admin's first name
  "members_count": 250,                         // Total members found
  "custom_msg": "Check announcement",           // Optional message
  "created_at": ISODate("2024-01-15T10:30:00"),
  "completed_at": ISODate("2024-01-15T10:35:00"),
  "status": "completed",                        // active, completed, failed
  "tagged_count": 248,                          // Successfully tagged
  "failed_count": 2,                            // Failed attempts
  "success_rate": 99.2                          // Percentage
}
```

### In-Memory Session Tracking

```python
_tagging_sessions: dict[int, dict] = {
  -1001234567890: {
    "user_id": 123456789,
    "message_id": 999,
    "cancel": False,
    "session_id": "ChatId_AdminId_1234567890",
    "members_count": 250,
    "admin_name": "John",
    "custom_msg": "Important update!",
    "started_at": datetime.utcnow(),
  }
}
```

---

## Configuration

### Default Settings

```python
BATCH_SIZE = 5              # Members per message
BATCH_DELAY = 1.5           # Seconds between batches
MAX_RETRIES = 3             # Retries per batch
MAX_MEMBERS = 500           # Maximum members to fetch
```

### Recommended Settings

**Safe Mode (Default)**
```
batchsize = 5
delay = 1.5
retries = 3
```
Use for: Learning, testing, important groups

**Balanced Mode**
```
batchsize = 8
delay = 1.2
retries = 3
```
Use for: Regular use, most groups

**Fast Mode**
```
batchsize = 10
delay = 1.0
retries = 2
```
Use for: Small groups, when speed matters

---

## Performance

### Speed Analysis

Tagging 150 members:

| Batch Size | Batches | Min Time | With Delay |
|-----------|---------|----------|-----------|
| 3 | 50 | 50s | 75s |
| 5 | 30 | 30s | 45s |
| 10 | 15 | 15s | 22.5s |

### Rate Limits

Telegram API limits:
- **Message sending**: ~30 messages/second (conservative)
- **With batch_delay = 1.5s**: Max 42 batches/minute = 210 members/minute
- **With batch_delay = 2.0s**: Max 30 batches/minute = 150 members/minute

**Recommendation**: Use `delay >= 1.5s` for safety

### Error Recovery

- **Batch fails**: Automatic retry (up to 3 times)
- **Network timeout**: Retry with exponential backoff
- **Rate limit hit**: Increases delay for subsequent batches
- **Member removed**: Skips and counts as success (already left)

---

## Use Cases

### 1. Important Announcements
```
/tagall 🚨 URGENT: All members please read the pinned message immediately!
```

### 2. Event Reminders
```
/tagall 📅 Reminder: Group event starts in 2 hours at the location in pinned message!
```

### 3. Policy Updates
```
/tagall ⚠️ New group rules have been added. Check pinned message for details.
```

### 4. Emergency Alerts
```
/tagall 🚨 EMERGENCY: See pinned message for important update.
```

### 5. Community Polls
```
/tagall 🗳️ Important poll: Vote in our pinned message. Your opinion matters!
```

---

## Troubleshooting

### Issue: "Bot Permission Error"

**Cause**: Bot is not a group admin

**Solution**:
1. Open group settings
2. Find the bot in member list
3. Tap the bot name
4. Select "Promote to Admin"
5. Grant "Can Manage Chat" permission

### Issue: "Tagging Already in Progress"

**Cause**: Another tagging session is running

**Solution**:
- Wait for it to complete, OR
- Use `/stoptag` to cancel

### Issue: Tagging Takes Too Long

**Cause**: Batch size too small or delay too large

**Solution**:
```bash
/tagconfig batchsize 10    # Increase batch size
/tagconfig delay 1.0       # Decrease delay
```
⚠️ But this increases risk of rate limiting

### Issue: "Failed" Count Too High

**Cause**: Batch size too large causing rate limiting

**Solution**:
```bash
/tagconfig batchsize 3     # Decrease batch size
/tagconfig delay 2.0       # Increase delay
/tagconfig retries 5       # Increase retries
```

### Issue: Members Not Notified

**Cause**: Possible reasons:
- Bot not admin
- Members have notifications disabled
- Batch failed after retries
- Member left group during tagging

**Solution**:
1. Check bot admin status
2. Verify member notification settings
3. Check `/taghistory` for failed count
4. Retry with `/tagall`

---

## Security & Safety

### Protections Implemented

✅ **Admin-Only Access**
- Only group admins can use `/tagall`
- Super admin required for configuration

✅ **Role-Based Permissions**
- Bot must be group admin
- Validates permissions before proceeding

✅ **Audit Logging**
- All sessions stored in MongoDB
- Complete history available
- Admin can review all tagging events

✅ **Rate Limit Safety**
- Configurable delays between batches
- Prevents Telegram API blocking
- Automatic backoff on failures

✅ **Error Protection**
- Try-catch blocks for all API calls
- Graceful failure handling
- Detailed error messages

✅ **Session Management**
- One session per group at a time
- Prevents duplicate tagging
- Easy cancellation with `/stoptag`

---

## Advanced Usage

### Scripting Tagalls

**Automated Announcements:**

```python
# Example: Tag at specific time
schedule.every().day.at("18:00").do(lambda: trigger_tagall(
    chat_id=-1001234567890,
    message="Daily reminder: Check announcements!"
))
```

### Batch Configuration via API

**Update settings programmatically:**

```python
await db["bot_settings"].update_one(
    {"key": "tagall_config"},
    {"$set": {
        "value.batch_size": 10,
        "value.batch_delay": 1.5,
        "value.max_retries": 3
    }},
    upsert=True
)
```

---

## Future Enhancements

- [ ] Scheduled tagging at specific times
- [ ] Tag specific roles/permissions
- [ ] Mention with timeout (timed notifications)
- [ ] Group-specific batch configurations
- [ ] Web dashboard for tagging analytics
- [ ] Reaction-based member filtering
- [ ] Tagging cooldown per admin
- [ ] Smart rate limit detection

---

## Support & Troubleshooting

For issues:
1. Check `/taghelp` in the group
2. Review error message carefully
3. Check logs for detailed error info
4. Contact super admin if needed

---

**Version:** 1.0.0
**Handler File:** handlers/tagger.py
**Lines of Code:** 500+
**Compatibility:** Python 3.8+, Pyrogram 2.0+, MongoDB 4.0+
