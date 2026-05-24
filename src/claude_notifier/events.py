"""Event type definitions for notification triggers.

Each event maps to a Claude Code hook and carries display data.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EventConfig:
    key: str
    hook_name: str          # Claude Code hook name (Stop, PermissionRequest, …)
    matcher: str | None     # Optional hook matcher ("" = match all, None = no matcher)
    icon: str               # Unicode icon for popup title
    title: str              # Popup title
    message: str            # Popup body text
    category: str           # "success" | "warning" | "info" → drives sound selection
    tts_message: str        # Spoken text for TTS


EVENTS: list[EventConfig] = [
    EventConfig(
        key="stop",
        hook_name="Stop",
        matcher=None,
        icon="✓",
        title="CLAUDE 响应完成",
        message="已处理完你的请求，回来看看吧",
        category="success",
        tts_message="Claude 已完成处理，请回来查看",
    ),
    EventConfig(
        key="notification",
        hook_name="Notification",
        matcher=None,
        icon="🔔",
        title="CLAUDE 通知",
        message="Claude 发来了一条消息",
        category="info",
        tts_message="Claude 发来了一条通知",
    ),
    EventConfig(
        key="permission",
        hook_name="PermissionRequest",
        matcher="",
        icon="⚡",
        title="需要你的确认",
        message="Claude 请求执行操作，请点击确认",
        category="warning",
        tts_message="Claude 需要你的授权确认",
    ),
    EventConfig(
        key="subagent_stop",
        hook_name="SubagentStop",
        matcher=None,
        icon="🤖",
        title="子代理完成",
        message="子代理已完成任务返回",
        category="success",
        tts_message="子代理任务完成",
    ),
    EventConfig(
        key="pre_tool_use",
        hook_name="PreToolUse",
        matcher="",
        icon="🔧",
        title="即将执行工具",
        message="Claude 即将执行工具调用",
        category="info",
        tts_message="Claude 正在执行工具操作",
    ),
    EventConfig(
        key="post_tool_use",
        hook_name="PostToolUse",
        matcher="",
        icon="✓",
        title="工具执行完成",
        message="工具调用已完成",
        category="info",
        tts_message="工具执行完成",
    ),
    EventConfig(
        key="test",
        hook_name="",               # Not a real hook — manual test only
        matcher=None,
        icon="✦",
        title="测试通知",
        message="通知系统工作正常",
        category="success",
        tts_message="通知系统测试正常",
    ),
]

BY_KEY: dict[str, EventConfig] = {e.key: e for e in EVENTS}
