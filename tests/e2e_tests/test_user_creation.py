# SPDX-License-Identifier: LGPL-2.1-or-later
#
# Copyright (C) 2023 Collabora Limited
# Author: Jeny Sadadia <jeny.sadadia@collabora.com>

"""End-to-end test functions for KernelCI API user creation"""

import json
import pytest

from api.models import User, UserGroup, UserProfile
from api.db import Database
from e2e_tests.conftest import db_create


@pytest.mark.dependency(
    depends=["e2e_tests/test_user_group_handler.py::test_create_user_groups"],
    scope="session")
@pytest.mark.dependency()
@pytest.mark.order(2)
@pytest.mark.asyncio
async def test_create_admin_user(test_async_client):
    """
    Test Case : Get hashed password using '/hash' endpoint to create an admin
    user. Create the admin user using database create method.
    Request authentication token using '/token' endpoint for the user and
    store it in pytest global variable 'ADMIN_BEARER_TOKEN'.
    """
    username = 'admin'
    password = 'test'
    response = await test_async_client.post(
        "hash",
        data=json.dumps({'password': password})
    )
    hashed_password = response.json()
    assert response.status_code == 200

    profile = UserProfile(
        username=username,
        hashed_password=hashed_password,
        email='test-admin@kernelci.org',
        groups=[UserGroup(name="admin")]
    )
    obj = await db_create(
            Database.COLLECTIONS[User],
            User(profile=profile)
        )
    assert obj is not None

    response = await test_async_client.post(
        "token",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        },
        data={
            'username': username, 'password': password, 'scope': 'admin users'
        }
    )
    assert response.status_code == 200
    assert response.json().keys() == {
        'access_token',
        'token_type',
    }
    pytest.ADMIN_BEARER_TOKEN = response.json()['access_token']


@pytest.mark.dependency(depends=["test_create_admin_user"])
@pytest.mark.order(3)
@pytest.mark.asyncio
async def test_create_regular_user(test_async_client):
    """
    Test Case : Test KernelCI API '/user' endpoint to create regular user
    when requested with admin user's bearer token. Request '/token' endpoint
    for the user and store it in pytest global variable 'BEARER_TOKEN'.
    """
    username = 'test_user'
    password = 'test'
    email = 'test@kernelci.org'
    response = await test_async_client.post(
        f"user/{username}?email={email}",
        headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {pytest.ADMIN_BEARER_TOKEN}"
            },
        data=json.dumps({'password': password})
    )
    assert response.status_code == 200
    assert ('id', 'active',
            'profile') == tuple(response.json().keys())
    assert ('username', 'hashed_password',
            'groups', 'email') == tuple(response.json()['profile'].keys())

    response = await test_async_client.post(
        "token",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        },
        data={'username': username, 'password': password}
    )
    assert response.status_code == 200
    assert response.json().keys() == {
        'access_token',
        'token_type',
    }
    pytest.BEARER_TOKEN = response.json()['access_token']


@pytest.mark.dependency(depends=["test_create_regular_user"])
def test_whoami(test_client):
    """
    Test Case : Test KernelCI API /whoami endpoint
    Expected Result :
        HTTP Response Code 200 OK
        JSON with 'id', 'username', 'hashed_password'
        and 'active' keys
    """
    response = test_client.get(
        "whoami",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {pytest.BEARER_TOKEN}"
        },
    )
    assert response.status_code == 200
    assert ('id', 'active',
            'profile') == tuple(response.json().keys())
    assert ('username', 'hashed_password',
            'groups', 'email') == tuple(response.json()['profile'].keys())
    assert response.json()['profile']['username'] == 'test_user'


@pytest.mark.dependency(depends=["test_create_regular_user"])
def test_create_user_negative(test_client):
    """
    Test Case : Test KernelCI API /user endpoint when requested
    with regular user's bearer token.
    Expected Result :
        HTTP Response Code 401 Unauthorized
        JSON with 'detail' key denoting 'Access denied' error
    """
    response = test_client.post(
        "user/test",
        headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {pytest.BEARER_TOKEN}"
            },
        data=json.dumps({'password': 'test'})
    )
    assert response.status_code == 401
    assert response.json() == {'detail': 'Access denied'}
