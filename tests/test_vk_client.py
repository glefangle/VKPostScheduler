"""VK-specific part of the error mapping: ApiError codes -> ClientError."""

import pytest
from vk_api.exceptions import ApiError

from vkpostscheduler.vk_client import PERMANENT_VK_CODES, VKClient

# auth failure, no access, blocked app, access denied, invalid params
NEVER_RETRY_CODES = [5, 7, 8, 15, 100]
# captcha, rate limit, flood control
RETRYABLE_CODES = [6, 9, 14, 29]


def vk_error(code):
    return ApiError(None, "wall.post", {}, None,
                    {"error_code": code, "error_msg": "test"})


def test_permanent_vk_codes_are_exactly_the_documented_ones():
    assert PERMANENT_VK_CODES == set(NEVER_RETRY_CODES)


@pytest.mark.parametrize("code", NEVER_RETRY_CODES)
def test_vk_error_code_fails_the_post_without_retry(code):
    wrapped = VKClient._wrap(vk_error(code))
    assert wrapped.permanent is True
    assert wrapped.code == code


@pytest.mark.parametrize("code", RETRYABLE_CODES)
def test_vk_error_code_leaves_room_for_a_retry(code):
    wrapped = VKClient._wrap(vk_error(code))
    assert wrapped.permanent is False
    assert wrapped.code == code


def test_vk_error_without_payload_still_gets_its_code():
    # no structured payload, only "[7]" in the message
    class UnstructuredVkError(Exception):
        error = None

        def __str__(self):
            return "wall.post failed [7] permission denied"

    wrapped = VKClient._wrap(UnstructuredVkError())
    assert wrapped.code == 7
    assert wrapped.permanent is True
