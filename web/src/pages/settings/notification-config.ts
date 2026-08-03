import type { NotifyType } from "@/types";

export interface NotificationFieldConfig {
  /**
   * 配置字段名。
   */
  key: string;
  /**
   * 字段标签。
   */
  label: string;
  /**
   * 输入框类型。
   */
  type?: "text" | "password";
  /**
   * 占位文案。
   */
  placeholder?: string;
  /**
   * 展示时是否隐藏真实值。
   */
  masked?: boolean;
}

export interface NotificationChannelConfig {
  /**
   * 通知渠道类型。
   */
  type: NotifyType;
  /**
   * 渠道名称。
   */
  title: string;
  /**
   * 渠道说明。
   */
  description: string;
  /**
   * 配置字段。
   */
  fields: NotificationFieldConfig[];
}

export const notificationChannelConfigs: NotificationChannelConfig[] = [
  {
    type: "webhook",
    title: "Webhook",
    description: "配置通用 Webhook 地址",
    fields: [{ key: "url", label: "Webhook URL", placeholder: "https://example.com/webhook" }],
  },
  {
    type: "telegram",
    title: "Telegram",
    description: "配置 Telegram Bot 通知",
    fields: [
      { key: "bot_token", label: "Bot Token", type: "password", placeholder: "123456:ABC-DEF...", masked: true },
      { key: "chat_id", label: "Chat ID", placeholder: "-100123456789" },
    ],
  },
];
