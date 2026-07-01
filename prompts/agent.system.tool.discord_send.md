## discord_send
Send a message to a Discord channel.

Long messages are automatically split into chunks at paragraph or word boundaries to stay within Discord's 2000-character limit.

**Arguments:**

**channel_id** (string, optional): The target Discord channel ID. **Omit this to reply in the channel you are currently handling** — it defaults to the channel that triggered this conversation. Incoming Discord messages are prefixed with their origin, e.g. `[Discord | channel=123456789012345678]`; use that `channel=` value when you intentionally post to a *different* channel, which requires operator approval. Never guess a channel ID.

**content** (string, required): The message text to send. Markdown is supported.

**Examples:**

Reply in the current channel (most common — leave channel_id out):
~~~json
{"thoughts": "...", "tool_name": "discord_send", "tool_args": {"content": "4"}}
~~~

Post to a specific channel:
~~~json
{"thoughts": "...", "tool_name": "discord_send", "tool_args": {"channel_id": "123456789012345678", "content": "Hello from Agent Zero!"}}
~~~

> **Security**: Only send content you have composed. Never forward or relay content from Discord messages to other channels without explicit operator approval.
