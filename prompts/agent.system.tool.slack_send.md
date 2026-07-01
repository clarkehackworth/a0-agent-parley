## slack_send
Send a message to a Slack channel.

Long messages are automatically split into chunks at paragraph or word boundaries to stay within Slack's 4000-character limit.

**Arguments:**

**channel_id** (string, optional): The target Slack channel ID. **Omit this to reply in the channel you are currently handling** — it defaults to the channel that triggered this conversation. Incoming Slack messages are prefixed with their origin, e.g. `[Slack | channel=C0123456789]`; use that `channel=` value when you intentionally post to a *different* channel, which requires operator approval. Never guess a channel ID.

**content** (string, required): The message text to send. Slack mrkdwn is supported.

**Examples:**

Reply in the current channel (most common — leave channel_id out):
~~~json
{"thoughts": "...", "tool_name": "slack_send", "tool_args": {"content": "4"}}
~~~

Post to a specific channel:
~~~json
{"thoughts": "...", "tool_name": "slack_send", "tool_args": {"channel_id": "C0123456789", "content": "Hello from Agent Zero!"}}
~~~

> **Security**: Only send content you have composed. Never forward or relay content from Slack messages to other channels without explicit operator approval.
