"""离线验证 GLaDOS 的请求契约, 业务结果和 Provider 加载流程."""

from __future__ import annotations

import json
import unittest
from unittest.mock import AsyncMock

from curl_cffi import requests
from pydantic import ValidationError

from app.infrastructure.http.requester import Requester
from app.infrastructure.providers.builtin_provider_registry import BuiltinProviderRegistry
from app.infrastructure.providers.code_loader import ProviderCodeLoader
from app.provider_plugins.builtin.glados import GladosAccount, GladosConfig, GladosProvider
from app.provider_plugins.contracts import ProviderContext


ACCOUNT = {
    "base_url": "https://glados.cloud",
    "username": "example@example.com",
    "cookie": "gld:sess=test-session; gld:sess.sig=test-signature",
    "user_agent": "Test Chrome on Windows",
}
"""不包含真实凭据的测试账号."""

CONFIG = {"accounts": [ACCOUNT]}
"""使用账号列表的 Provider 配置."""

SUCCESS = {
    "code": 0,
    "message": "Checkin! Got 12 Points",
    "list": [{"balance": "407", "change": "12", "business": "checkin"}],
}
"""参考实现中的积分签到响应."""

STATUS = {"code": 0, "data": {"leftDays": "528.125"}}
"""包含小数天数的账号状态响应."""


def response(payload: object, status: int = 200) -> requests.Response:
    """构造真实响应类型, 同时支持 JSON 和网关文本."""
    result = requests.Response()
    result.status_code = status
    result.ok = 200 <= status < 400
    result.url = "https://glados.cloud/api/user/checkin"
    result.content = (payload if isinstance(payload, str) else json.dumps(payload)).encode()
    return result


class GladosProviderTests(unittest.IsolatedAsyncioTestCase):
    """通过共享 Requester 验证签到与状态查询, 禁止连接真实账号."""

    def setUp(self) -> None:
        """使用模拟 HTTP 会话和零延迟重试初始化执行环境."""
        self.client = AsyncMock(spec=requests.AsyncSession)
        self.requester = Requester(
            client=self.client,
            retry_attempts=3,
            retry_delay_seconds=0,
        )
        self.provider = GladosProvider(requester=self.requester)
        self.context = ProviderContext(task_id=1, task_name="glados", trigger_type="manual")

    async def test_checkin_status_and_headers(self) -> None:
        """确认签到后只读查询状态, 域名, token 和设备标识保持一致."""
        self.client.request.side_effect = [response(SUCCESS), response(STATUS)]
        result = await self.provider.run(CONFIG, self.context)
        self.assertTrue(result.success, result.message)
        self.assertEqual(result.data["targets"][0]["points"], 12)
        self.assertEqual(result.data["targets"][0]["balance"], 407)
        self.assertEqual(result.data["targets"][0]["left_days"], 528.125)
        calls = self.client.request.await_args_list
        self.assertEqual([call.args for call in calls], [
            ("POST", "https://glados.cloud/api/user/checkin"),
            ("GET", "https://glados.cloud/api/user/status"),
        ])
        self.assertEqual(calls[0].kwargs["json"], {"token": "glados.cloud"})
        self.assertNotIn("json", calls[1].kwargs)
        for call in calls:
            self.assertEqual(call.kwargs["headers"]["User-Agent"], ACCOUNT["user_agent"])
            self.assertEqual(call.kwargs["headers"]["Cookie"], "gld:sess=test-session; gld:sess.sig=test-signature")
            self.assertEqual(call.kwargs["headers"]["Origin"], "https://glados.cloud")
            self.assertEqual(call.kwargs["headers"]["Referer"], "https://glados.cloud/console/checkin")
            self.assertFalse(call.kwargs["allow_redirects"])
        self.assertNotIn("test-session", result.model_dump_json())

    async def test_multiple_accounts_keep_independent_credentials(self) -> None:
        """同一次执行中的各账号独立使用域名, token, Cookie 和设备标识."""
        second_account = {
            **ACCOUNT,
            "username": "second@example.com",
            "base_url": "https://glados.one",
            "token": "custom-token",
            "cookie": "gld:sess=second-session",
            "user_agent": "Test Safari on Mac",
        }
        self.client.request.side_effect = [response(SUCCESS), response(STATUS)] * 2
        result = await self.provider.run({"accounts": [ACCOUNT, second_account]}, self.context)
        self.assertTrue(result.success, result.message)
        targets = result.data["targets"]
        self.assertEqual([target["username"] for target in targets], [ACCOUNT["username"], second_account["username"]])
        self.assertTrue(all(target["success"] for target in targets))
        self.assertEqual([target["left_days"] for target in targets], [528.125, 528.125])
        calls = self.client.request.await_args_list
        self.assertEqual([call.args[0] for call in calls], ["POST", "GET", "POST", "GET"])
        self.assertEqual(calls[0].kwargs["json"], {"token": "glados.cloud"})
        self.assertEqual(calls[2].kwargs["json"], {"token": "custom-token"})
        for account, account_calls in [(ACCOUNT, calls[:2]), (second_account, calls[2:])]:
            for call in account_calls:
                self.assertTrue(call.args[1].startswith(account["base_url"] + "/api/"))
                self.assertEqual(call.kwargs["headers"]["Cookie"], account["cookie"])
                self.assertEqual(call.kwargs["headers"]["User-Agent"], account["user_agent"])
        self.assertEqual(len(result.logs), 6)
        self.assertNotIn("test-session", result.model_dump_json())
        self.assertNotIn("second-session", result.model_dump_json())

    async def test_failed_account_does_not_stop_remaining_accounts(self) -> None:
        """账号业务失败后继续后续账号, 保留各自结果并将整体标记失败."""
        self.client.request.side_effect = [
            response({"code": -2, "message": "没有权限"}),
            response(SUCCESS),
            response(STATUS),
            response({"code": 1, "message": GladosProvider.REPEAT_MESSAGE}),
            response(STATUS),
        ]
        accounts = [{**ACCOUNT, "username": name} for name in ("first", "second", "third")]
        result = await self.provider.run({"accounts": accounts}, self.context)
        self.assertFalse(result.success)
        targets = result.data["targets"]
        self.assertEqual([target["username"] for target in targets], ["first", "second", "third"])
        self.assertEqual([target["success"] for target in targets], [False, True, True])
        self.assertIn("重新登录", targets[0]["message"])
        self.assertEqual(targets[1]["points"], 12)
        self.assertEqual(targets[2]["status"], "今日已签到")
        self.assertEqual(self.client.request.await_count, 5)

    async def test_network_failure_does_not_stop_next_account(self) -> None:
        """首个账号耗尽网络重试后继续处理第二个账号."""
        self.client.request.side_effect = [requests.RequestsError("connection reset")] * 3 + [
            response(SUCCESS), response(STATUS),
        ]
        result = await self.provider.run({"accounts": [ACCOUNT, {**ACCOUNT, "username": "second"}]}, self.context)
        self.assertFalse(result.success)
        self.assertEqual([target["success"] for target in result.data["targets"]], [False, True])
        self.assertEqual(self.client.request.await_count, 5)

    async def test_current_success_points_and_repeated_messages(self) -> None:
        """支持当前观察记录, 积分字段及明确的重复签到响应."""
        for payload, expected in [
            ({"code": 0, "message": "Today's observation logged. Return tomorrow for more points."}, "今日观察已记录"),
            ({"code": "0", "message": "ok", "points": "1.5"}, "获得 1.5 积分"),
            ({"code": 0, "message": GladosProvider.REPEAT_MESSAGE}, "今日已签到"),
            ({"code": 1, "message": GladosProvider.REPEAT_MESSAGE}, "今日已签到"),
        ]:
            with self.subTest(payload=payload):
                self.client.request.side_effect = [response(payload), response(STATUS)]
                result = await self.provider.run(CONFIG, self.context)
                self.assertTrue(result.success, result.message)
                self.assertIn(expected, result.data["targets"][0]["message"])

    async def test_business_rejections_never_retry_or_succeed(self) -> None:
        """登录失效和设备拒绝不能因积分字段而被判成功或触发重试."""
        for payload, expected in [
            ({"code": -2, "message": "没有权限"}, "重新登录"),
            ({"code": 0, "message": "Unauthorized"}, "重新登录"),
            ({"code": 4, "reason": "device-mismatch"}, "device-mismatch"),
            ({"code": 4, "message": "Automated check-in detected"}, "重新登录"),
            ({"code": 0, "message": "Automated check-in detected"}, "重新登录"),
            ({**SUCCESS, "code": 5}, "业务失败"),
            ({"code": 5, "message": GladosProvider.REPEAT_MESSAGE}, "业务失败"),
            ({"code": 0, "message": "Please Try Tomorrow"}, "请明天再试"),
        ]:
            with self.subTest(payload=payload):
                self.client.request.reset_mock()
                self.client.request.side_effect = [response({**payload, "points": 12})]
                result = await self.provider.run(CONFIG, self.context)
                self.assertFalse(result.success)
                self.assertIn(expected, result.data["targets"][0]["message"])
                self.assertEqual(self.client.request.await_count, 1)

    async def test_invalid_json_and_unknown_results_fail(self) -> None:
        """缺失业务状态, 非对象 JSON 和无法识别的签到消息必须失败."""
        for payload in ["<html>login</html>", "", [], None, {}, {"code": False, "points": 12}, {"code": 0, "message": "unexpected"}]:
            with self.subTest(payload=payload):
                self.client.request.reset_mock()
                self.client.request.side_effect = [response(payload)]
                result = await self.provider.run(CONFIG, self.context)
                self.assertFalse(result.success)
                self.assertEqual(self.client.request.await_count, 1)

    async def test_http_auth_and_redirect_fail_without_retry(self) -> None:
        """未授权响应不重试, 重定向不能被当成成功结果."""
        for status in [301, 302, 401, 403]:
            with self.subTest(status=status):
                self.client.request.reset_mock()
                self.client.request.side_effect = [response("login required", status)]
                result = await self.provider.run(CONFIG, self.context)
                self.assertFalse(result.success)
                self.assertIn(str(status), result.data["targets"][0]["message"])
                self.assertEqual(self.client.request.await_count, 1)

    async def test_temporary_gateway_errors_keep_same_device(self) -> None:
        """HTTP 网关故障沿用共享 Requester 重试, 保持相同请求."""
        self.client.request.side_effect = [
            response("error code: 502", 502),
            response("error code: 503", 503),
            response(SUCCESS),
            response(STATUS),
        ]
        result = await self.provider.run(CONFIG, self.context)
        self.assertTrue(result.success, result.message)
        calls = self.client.request.await_args_list
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[0], calls[1])
        self.assertEqual(calls[1], calls[2])

    async def test_gateway_errors_only_use_requester_retries(self) -> None:
        """HTTP 200 网关正文直接失败, HTTP 错误仅使用共享 Requester 重试."""
        for status, attempts in [(200, 1), (504, 3)]:
            with self.subTest(status=status, attempts=attempts):
                self.client.request.reset_mock()
                self.client.request.side_effect = [response("error code: 504", status)] * attempts
                result = await self.provider.run(CONFIG, self.context)
                self.assertFalse(result.success)
                self.assertIn("504", result.data["targets"][0]["message"])
                self.assertEqual(self.client.request.await_count, attempts)

    async def test_network_error_retries(self) -> None:
        """网络异常沿用项目 HTTP 重试策略并可恢复."""
        self.client.request.side_effect = [requests.RequestsError("connection reset"), response(SUCCESS), response(STATUS)]
        result = await self.provider.run(CONFIG, self.context)
        self.assertTrue(result.success, result.message)
        self.assertEqual(self.client.request.await_count, 3)

    async def test_status_failure_preserves_completed_checkin(self) -> None:
        """查询失败不能伪造剩余天数, 同时保留已经完成的签到结果."""
        for payload in [
            {"code": -2, "message": "没有权限"},
            {"code": 5, "data": {"leftDays": 528}},
            {"code": 0, "data": {}},
            {"code": 0, "data": {"leftDays": "NaN"}},
            {"code": 0, "data": {"leftDays": True}},
        ]:
            with self.subTest(payload=payload):
                self.client.request.side_effect = [response(SUCCESS), response(payload)]
                result = await self.provider.run(CONFIG, self.context)
                self.assertFalse(result.success)
                self.assertIn("状态查询失败", result.data["targets"][0]["message"])
                self.assertEqual(result.data["targets"][0]["points"], 12)
                self.assertNotIn("left_days", result.data["targets"][0])

    async def test_invalid_config_never_sends_request(self) -> None:
        """缺少账号列表, 空列表或缺少必填凭据时均在配置阶段失败."""
        for config in [{}, {"accounts": []}, {"accounts": [{"username": "example"}]}]:
            with self.subTest(config=config):
                result = await self.provider.run(config, self.context)
                self.assertFalse(result.success)
                self.client.request.assert_not_awaited()

    def test_account_defaults_and_unmodified_text(self) -> None:
        """保留现有域名与设备默认值, 账号文本不再由自定义校验器修改."""
        config = GladosConfig.model_validate({"accounts": [{"username": "example", "cookie": "session=value"}]})
        account = config.accounts[0]
        self.assertIsInstance(account, GladosAccount)
        self.assertEqual(account.base_url, "https://glados.one")
        self.assertIn("Chrome/153.0.0.0", account.user_agent)
        self.assertIsNone(account.token)
        original = {**ACCOUNT, "base_url": "custom-value", "username": " example ", "cookie": "Cookie: session=value"}
        self.assertEqual(GladosAccount.model_validate(original).model_dump(exclude={"token"}), original)
        with self.assertRaises(ValidationError):
            GladosConfig.model_validate({"accounts": []})

    async def test_builtin_discovery_and_sandbox_source_loading(self) -> None:
        """自动发现与数据库源码加载均应得到可运行的 glados Provider."""
        registry = BuiltinProviderRegistry()
        self.assertIn("glados", registry.load_providers())
        self.assertIs(registry.get("glados"), GladosProvider)
        loader = ProviderCodeLoader(sandbox_enabled=True)
        source = loader.source_code_for_provider_class(GladosProvider)
        provider_class = loader.load_provider_class_from_code("glados", source)
        self.assertEqual(provider_class.name, "glados")
        schema = provider_class.config_schema.model_json_schema()
        self.assertEqual(schema["required"], ["accounts"])
        self.assertEqual(schema["$defs"]["GladosAccount"]["required"], ["username", "cookie"])
        self.client.request.side_effect = [response(SUCCESS), response(STATUS)]
        result = await provider_class(requester=self.requester).run(CONFIG, self.context)
        self.assertTrue(result.success, result.message)


if __name__ == "__main__":
    unittest.main()
