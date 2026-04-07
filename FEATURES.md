# 🤖 Group Settings & Automation Features

This document describes the new core features added to the DESI MLH Bot for enhanced group management and automation.

## Overview

Six major features have been implemented to give admins comprehensive control over their groups:

1. **Granular Group Settings** - Toggle features on/off per group
2. **Auto-Reaction System** - Automatic reactions to messages
3. **Custom Buttons** - Inline buttons in bot messages
4. **Keyword-Based Auto-Reply** - Trigger responses to specific keywords
5. **Auto-Approve Join Requests** - Automatically approve new members
6. **Configuration Management** - Persistent storage in MongoDB

---

## 1. Granular Group Settings ⚙️

### Overview
Admins can toggle features on/off for their specific group.

### Available Features
- `video` - Enable/disable `/video` command
- `welcome` - Enable/disable welcome messages
- `filters` - Enable/disable word filters
- `antiflood` - Enable/disable flood protection
- `nightmode` - EnaEnablesable nightmode
- `auto_reactions` - Enable/disable auto-reactions
- `keyword_reply` - Enable/disable keyword-based replies

### Commands

#### In Group
```
/group              → Open group settings menu
/groupinfo          → View current settings info
```

#### For Super Admins (Private)
```
/grouplist          → List all groups using the bot
/groupinfo <chat_id> → Get info about a specific group
/togglegroupfeature <chat_id> <feature> → Toggle a feature
/resetgroup <chat_id> → Reset all group settings
```

### Usage Example

1. **In your group**, type `/group` as an admin
2. A menu appears with options:
   - ⚙️ Features - Toggle each feature
   - 📝 Keywords - Manage keyword triggers
   - 😂 Reactions - Configure auto-reactions
   - 🔘 Buttons - Setup custom buttons
   - ✅ Auto-Approve - Enable auto-approvals
   - 📋 Info - View current configuration

---

## 2. Auto-Reaction System 😂

### Overview
The bot automatically reacts to messages with emoji when enabled.

### Database Collection
- **Collection:** `auto_reactions`
- **Fields:**
  ```
  {
    "chat_id": -1001234567890,
    "reactions": ["😂", "😍", "🔥", "⭐"],
    "enabled": true,
    "updated_at": "2024-01-15T10:30:00"
  }
  ```

### Commands

#### In Group
```
/setreactions emoji1 emoji2 emoji3...
```

**Example:**
```
/setreactions 😂 😍 🔥 ⭐
```

### How It Works
1. Admin sets reaction emojis for the group
2. When any message is sent in the group:
   - Bot checks if `auto_reactions` feature is enabled
   - Bot retrieves the emoji list for that group
   - Bot reacts with the first emoji

### Enable/Disable
- Via `/group` → Reactions → Toggle
- Reactions are disabled by default for new groups

---

## 3. Keyword-Based Auto-Reply 🔑

### Overview
When users mention specific keywords, the bot automatically replies with a pre-configured message.

### Database Collection
- **Collection:** `keyword_triggers`
- **Fields:**
  ```
  {
    "chat_id": -1001234567890,
    "keyword": "hello",
    "response": "Hey there! 👋 How can I help?",
    "created_at": "2024-01-15T10:30:00"
  }
  ```

### Commands

#### In Group
```
/addkeyword <keyword> <response>    → Add a keyword trigger
/delkeyword <keyword>                → Delete a keyword
/keywords                            → List all keywords
```

**Examples:**
```
/addkeyword hello Hey there! 👋
/addkeyword rules Check the pinned message for rules
```

### How It Works
1. Admin adds a keyword and response
2. When a message containing the keyword is posted:
   - Bot finds the keyword trigger
   - Bot replies with the configured response
   - The bot quotes the original message

### Enable/Disable
- Via `/group` → Keywords → Info
- Keyword reply feature disabled by default

### Important Notes
- Keyword matching is case-insensitive
- One keyword per entry (no multi-word phrase matching currently)
- Response supports HTML formatting

---

## 4. Custom Buttons 🔘

### Overview
Admins can attach custom inline buttons to bot messages.

### Database Collection
- **Collection:** `group_buttons`
- **Fields:**
  ```
  {
    "chat_id": -1001234567890,
    "name": "video_buttons",
    "buttons": [
      {
        "text": "Join Channel",
        "url": "https://t.me/mychannel"
      },
      {
        "text": "Buy Premium",
        "url": "https://t.me/bot?start=premium"
      }
    ],
    "updated_at": "2024-01-15T10:30:00"
  }
  ```

### Commands

#### In Group
```
/setbuttons         → Start custom buttons setup
/attachbuttons <name> → Attach buttons to next message
```

### How It Works
1. Admin uses `/setbuttons` to see the format
2. Buttons are set in the format: `[Button Text|URL]`
3. Multiple buttons are supported (up to 10)
4. Buttons are automatically added when bot sends messages

### Button Format
```
[Visit Site|https://example.com] [Join Channel|https://t.me/channel]
```

---

## 5. Auto-Approve Join Requests ✅

### Overview
When enabled, the bot automatically approves new join requests in the group.

### Database Collections
- **Collection:** `auto_approve_logs`
- **Fields:**
  ```
  {
    "chat_id": -1001234567890,
    "user_id": 123456789,
    "username": "john_doe",
    "first_name": "John",
    "approved_at": "2024-01-15T10:30:00"
  }
  ```

### Commands

#### In Group
```
/autoapprove        → Toggle auto-approve for the group
```

### How It Works
1. Admin enables auto-approve via `/group` → Auto-Approve
2. When a user sends a join request:
   - Bot automatically approves the request
   - User receives a confirmation message
   - Entry is logged in `auto_approve_logs`
   - Admin receives log event

### Features
- ✅ **Auto-Approve:** Join requests are instantly approved
- ✅ **Confirmation:** User gets a DM confirming approval
- ✅ **Logging:** All approvals are logged with timestamps
- ✅ **Admin Notification:** Admin receives approval logs

### Disable Auto-Approve
If you need to disable it:
```
/group → Auto-Approve → Disable
```

---

## 6. Configuration Management 🗄️

### Database Schema

#### group_settings Collection
```javascript
{
  "chat_id": -1001234567890,
  "features": {
    "video": true,
    "welcome": true,
    "filters": true,
    "antiflood": true,
    "nightmode": false,
    "auto_reactions": false,
    "keyword_reply": false
  },
  "auto_approve": false,
  "log_channel": null,
  "created_at": "2024-01-15T10:30:00",
  "updated_at": "2024-01-15T10:30:00"
}
```

#### auto_reactions Collection
```javascript
{
  "chat_id": -1001234567890,
  "reactions": ["😂", "😍", "🔥"],
  "enabled": true,
  "updated_at": "2024-01-15T10:30:00"
}
```

#### keyword_triggers Collection
```javascript
{
  "chat_id": -1001234567890,
  "keyword": "hello",
  "response": "Hey there! 👋",
  "created_at": "2024-01-15T10:30:00"
}
```

#### auto_approve_logs Collection
```javascript
{
  "chat_id": -1001234567890,
  "user_id": 123456789,
  "username": "john_doe",
  "first_name": "John",
  "approved_at": "2024-01-15T10:30:00"
}
```

#### group_buttons Collection
```javascript
{
  "chat_id": -1001234567890,
  "name": "default",
  "buttons": [
    {
      "text": "Get Video",
      "url": "https://t.me/bot?start=video"
    }
  ],
  "updated_at": "2024-01-15T10:30:00"
}
```

---

## Architecture

### Handler Organization
- **handlers/group_settings.py** - Main group settings manager
  - `/group` command and menu
  - Callback query handlers for settings
  - Keyword triggers logic
  - Auto-reactions logic
  - Auto-approve logic

- **handlers/groups.py** - Enhanced with feature checks
  - Video command now checks if feature is enabled
  - Group tracking and management
  - Join request monitoring

- **handlers/admin.py** - Admin management tools
  - `/grouplist` - List all groups
  - `/groupinfo` - Get group details
  - `/togglegroupfeature` - Toggle features per group
  - `/resetgroup` - Reset group configuration

### Data Flow

```
User Message in Group
    ↓
Check if keyword matches (if enabled)
    ↓
If match → Send auto-reply
    ↓
Apply auto-reactions (if enabled)
    ↓
Process other handlers normally
```

---

## Usage Guide

### For Group Admins

#### Setup Initial Settings
1. Add bot to group and give it admin permissions
2. Use `/group` to open settings menu
3. Configure features as needed
4. Add keywords if you want auto-reply
5. Set auto-reactions for engagement

#### Manage Keywords
```
# Add: /addkeyword help Type /help for commands
# Remove: /delkeyword help
# List: /keywords
```

#### Enable Auto-Reactions
```
/setreactions 😂 😍 🔥 ⭐
# Up to 10 emojis supported
```

#### Auto-Approve Members
```
/autoapprove  # Toggle on/off
```

### For Super Admin

#### View All Groups
```
/grouplist
```

#### Check Specific Group
```
/groupinfo -1001234567890
```

#### Toggle Feature for Specific Group
```
/togglegroupfeature -1001234567890 video
```

#### Reset Group Configuration
```
/resetgroup -1001234567890
```

---

## Troubleshooting

### Issue: Auto-reactions not working
- ✅ Check if feature is enabled via `/group`
- ✅ Verify emojis were set with `/setreactions`
- ✅ Check bot has permission to add reactions

### Issue: Keywords not triggering
- ✅ Check if `keyword_reply` feature is enabled
- ✅ Verify keyword was added with `/addkeyword`
- ✅ Note: Matching is case-insensitive but requires the exact word

### Issue: Auto-approve not working
- ✅ Check if enabled with `/autoapprove`
- ✅ Verify bot has `can_invite_users` permission
- ✅ Check MongoDB `auto_approve_logs` collection for errors

### Issue: Custom buttons not showing
- ✅ Check if buttons were properly configured
- ✅ Verify button format is correct
- ✅ Use `/setbuttons` to view correct format

---

## Performance Notes

- ✅ All settings are cached in MongoDB
- ✅ Feature toggles are checked per-message
- ✅ Keyword matching uses simple string search (O(n))
- ✅ Auto-reactions react with first emoji only
- ✅ Suitable for groups with 1000+ members

---

## Future Enhancements

- [ ] Multi-word keyword phrase support
- [ ] Regex pattern matching for keywords
- [ ] Multiple reactions per message (round-robin)
- [ ] Scheduled messages with custom buttons
- [ ] Message filtering by role/permission
- [ ] Analytics dashboard for group activity
- [ ] Custom emoji reactions based on user roles
- [ ] Keyword cooldown periods

---

## Files Modified

1. **config.py** - Added new database collections
2. **handlers/group_settings.py** - New main handler (350+ lines)
3. **handlers/groups.py** - Enhanced with feature checks
4. **handlers/admin.py** - Added group management commands
5. **handlers/__init__.py** - Imported new handler
6. **main.py** - Imported new handler module

---

## Testing Checklist

- [x] All syntax validated
- [x] All imports correct
- [ ] Test /group command in test group
- [ ] Test feature toggles
- [ ] Test keyword triggers
- [ ] Test auto-reactions
- [ ] Test auto-approve
- [ ] Test admin commands

---

## 7. Invisible Tagall System 🏷️

### Overview
Admins can mention all group members invisibly using Zero-Width Non-Joiner (ZWNJ) characters. Messages appear clean without showing mentions, but all members are notified.

### Database Collection
- **Collection:** `tagall_sessions`
- **Fields:**
  ```
  {
    "session_id": "chat_id_admin_timestamp",
    "chat_id": -1001234567890,
    "admin_id": 123456789,
    "admin_name": "Admin Name",
    "members_count": 250,
    "custom_msg": "Check pinned message!",
    "created_at": "2024-01-15T10:30:00",
    "status": "completed",
    "tagged_count": 245,
    "failed_count": 5
  }
  ```

### Commands

#### In Group
```
/tagall [message]      → Tag all members with optional message
/stoptag or /cancel    → Stop ongoing tagging operation
/taggingstatus         → View current tagging progress
/taghelp               → Show tagging help
```

**Examples:**
```
/tagall
/tagall Check out the announcement in pinned message!
/tagall Important update from the admin
```

#### Super Admin Only (Private)
```
/tagconfig batchsize 5    → Set members per batch (default: 5)
/tagconfig delay 1.5      → Set delay between batches in seconds
/tagconfig retries 3      → Set max retries per batch
/taghistory [limit]       → View tagging history
```

### How It Works

1. **Admin Command**: Admin uses `/tagall` with optional message
2. **Member Fetching**: Bot retrieves all non-bot group members
3. **Batch Processing**: Members are split into configurable batches (default 5 per batch)
4. **Invisible Mentions**: Each batch message contains:
   - Optional custom message from admin
   - Zero-Width Non-Joiner (ZWNJ) invisible mentions
   - HTML hyperlink mentions for reliability
5. **Notification**: Each mention sends a notification to members
6. **Batch Delay**: Configurable delay between batches to avoid Telegram flood limits
7. **Error Handling**: Failed mentions are retried up to 3 times (configurable)
8. **Session Management**: All tagging sessions are logged and trackable

### Key Features

✅ **Invisible Mentions**
- Uses ZWNJ character (U+200C) for invisible text
- Hyperlink mentions for reliable notification
- Messages appear clean without visible mention lists

✅ **Batch Processing**
- Splits members into small batches (default 5)
- Prevents Telegram flood limits
- Configurable batch size and delays
- Progress tracking during tagging

✅ **Custom Messages**
- Include message text with the tagging
- Example: `/tagall Don't forget the event tonight!`
- HTML formatting supported

✅ **Session Management**
- Start/stop tagging operations
- View tagging status in real-time
- Cancel anytime with `/stoptag`
- Full audit trail in MongoDB

✅ **Error Handling**
- Automatic retries (default 3 times)
- Detailed error reporting
- Graceful degradation on failures
- Success rate calculation

✅ **Admin Controls**
- View all tagging sessions
- Configure batch behavior
- Monitor tagging history
- Performance optimized

### Configuration

Default batch configuration:
- **Batch Size**: 5 members per message
- **Batch Delay**: 1.5 seconds between batches
- **Max Retries**: 3 attempts per batch

Change via super admin commands:
```
/tagconfig batchsize 10    # Larger batches = faster, higher risk
/tagconfig delay 2.0       # Longer delay = safer, slower
/tagconfig retries 5       # More retries = better reliability
```

### Permissions

- ✅ **Group Admin Required**: Admin must be group admin
- ✅ **Bot Admin Required**: Bot must be group admin
- ✅ **Exclude Bots**: Only human members are tagged
- ✅ **Protected**: Max 500 members per tagging session

### Workflow Example

**Step 1: Start Tagging**
```
Admin: /tagall Hey everyone! Check the pinned message!
Bot:   🔄 Fetching group members...
       👥 Found 150 members
       🏷️ Starting tagging process
```

**Step 2: Progress Update**
```
Progress: 2/30
Tagged: 10/150
Failed: 0
Status: Processing batch 2...
```

**Step 3: Completion**
```
✅ Tagging Complete
Total Members: 150
Tagged: 148
Failed: 2
Success Rate: 98.7%
Took 30 batches
```

### Session Management

**View Status**
```
/taggingstatus
Status: 🔄 In Progress
Admin: John
Members: 250
```

**Stop Tagging**
```
/stoptag
⏹️ Tagging Stopped
Tagged: 45/250
```

**View History**
```
/taghistory 20
1. Group: -1001234567890
   Admin: John (148 tagged)
   Success Rate: 98.7%
   Date: 15 Jan 2024 10:30
```

### Performance Optimizations

- ✅ Batch processing avoids Telegram API rate limits
- ✅ Configurable delays prevent flood bans
- ✅ Async/await for non-blocking operations
- ✅ MongoDB indexing for fast queries
- ✅ In-memory session tracking for speed
- ✅ Supports 500+ member groups

### Error Scenarios

**Scenario 1: Bot Not Admin**
```
❌ Bot Permission Error
Bot is not an admin in this group
```

**Solution**: Make bot a group admin

**Scenario 2: Tagging Already Running**
```
⚠️ Tagging Already in Progress
Use /stoptag to cancel
```

**Solution**: Wait or stop with `/stoptag`

**Scenario 3: Failed Members**
```
Tagged: 148/150
Failed: 2
Success Rate: 98.7%
```

**Solution**: Rerun or increase retries

### Invisible Mention Technology

**ZWNJ Character (U+200C)**
- Completely invisible in normal rendering
- Used for inline spacing in Arabic text
- Perfect for hidden mentions in Telegram
- Combined with hyperlinks for reliability

**Implementation**
```
Format: {ZWNJ}<a href='tg://user?id={UID}'>​</a>
Result: Invisible but notifies user
Visual: No visible text or mention list
Effect: User gets notification in their feed
```

### Use Cases

1. **Announcements**: `/tagall Important announcement!`
2. **Events**: `/tagall Don't miss the event at 5 PM!`
3. **Reminders**: `/tagall Reminder: Weekly meeting tonight`
4. **Updates**: `/tagall System update completed`
5. **Discussions**: `/tagall What's your opinion on this?`

### Advantages Over Native Tagging

| Feature | Native | Invisible Tag |
|---------|--------|---------------|
| Visual Spam | ❌ Yes | ✅ No |
| Everyone Notified | ❌ No | ✅ Yes |
| Custom Message | ❌ No | ✅ Yes |
| Clean Message | ❌ No | ✅ Yes |
| Controllable | ❌ No | ✅ Yes |

### Database Schema for Tagging

```javascript
// tagall_sessions Collection
{
  "session_id": "unique_session_id",           // chat_admin_timestamp
  "chat_id": -1001234567890,                  // Group ID
  "admin_id": 123456789,                      // Admin user ID
  "admin_name": "John",                       // Admin name
  "members_count": 250,                       // Total members found
  "custom_msg": "Check the announcement",     // Optional message
  "created_at": ISODate("2024-01-15T10:30:00"),
  "completed_at": ISODate("2024-01-15T10:35:00"),
  "status": "completed",                      // active, completed, failed
  "tagged_count": 245,                        // Successfully tagged
  "failed_count": 5,                          // Failed to tag
  "success_rate": 98.0                        // Percentage
}
```

---

## Files Modified (with Invisible Tagall)

1. **config.py** - MongoDB collections (no changes for tagger)
2. **handlers/group_settings.py** - Group settings (350+ lines)
3. **handlers/groups.py** - Group management (16 lines)
4. **handlers/admin.py** - Admin commands (150 lines)
5. **handlers/tagger.py** - **NEW**: Invisible tagall system (500+ lines)
6. **handlers/__init__.py** - Added tagger import
7. **main.py** - Added tagger import

---

## Support

For issues or questions, contact the admin or check the logging output when features are used.

---

**Version:** 1.0.0
**Date:** January 2024
**Compatibility:** Python 3.8+, Pyrogram 2.0+, MongoDB 4.0+
