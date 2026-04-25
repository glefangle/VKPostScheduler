"""VK-specific part of the error mapping: ApiError codes -> ClientError."""

from vk_api.exceptions import ApiError

from vk_client import PERMANENT_VK_CODES, VKClient


def vk_error(code):
    return ApiError(None, "wall.post", {}, None,
                    {"error_code": code, "error_msg": "test"})


def test_permanent_vk_codes():
    # auth failure, no access, blocked app, access denied, invalid params
    assert PERMANENT_VK_CODES == {5, 7, 8, 15, 100}
    for code in PERMANENT_VK_CODES:
        wrapped = VKClient._wrap(vk_error(code))
        assert wrapped.permanent is True
        assert wrapped.code == code


def test_retryable_vk_codes():
    # captcha, rate limit, flood control
    for code in (6, 9, 14, 29):
        wrapped = VKClient._wrap(vk_error(code))
        assert wrapped.permanent is False
        assert wrapped.code == code


def test_code_fallback_parses_message():
    # no structured payload, only "[7]" in the message
    class UnstructuredVkError(Exception):
        error = None

        def __str__(self):
            return "wall.post failed [7] permission denied"

    wrapped = VKClient._wrap(UnstructuredVkError())
    assert wrapped.code == 7
    assert wrapped.permanent is True
