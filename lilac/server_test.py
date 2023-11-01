"""Test our public REST API."""
import os

from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from .auth import (
  AuthenticationInfo,
  ConceptUserAccess,
  DatasetUserAccess,
  UserAccess,
  UserInfo,
  get_session_user,
)
from .server import app

client = TestClient(app)


def test_auth_admin(mocker: MockerFixture) -> None:
  mocker.patch.dict(os.environ, {'LILAC_AUTH_ENABLED': 'True'})
  mocker.patch.dict(os.environ, {'LILAC_AUTH_ADMIN_EMAILS': 'test@test.com,test2@test2.com'})

  # Override the session user so we make them an admin.
  def admin_user() -> UserInfo:
    return UserInfo(
      id='1', email='test@test.com', name='test', given_name='test', family_name='test'
    )

  app.dependency_overrides[get_session_user] = admin_user

  url = '/auth_info'
  response = client.get(url)
  assert response.status_code == 200
  assert AuthenticationInfo.model_validate(response.json()) == AuthenticationInfo(
    user=admin_user(),
    access=UserAccess(
      is_admin=True,
      create_dataset=True,
      dataset=DatasetUserAccess(
        compute_signals=True,
        delete_dataset=True,
        delete_signals=True,
        update_settings=True,
        create_label_type=True,
        edit_labels=True,
        label_all=True,
      ),
      concept=ConceptUserAccess(delete_any_concept=True),
    ),
    auth_enabled=True,
  )


def test_auth_nonadmin(mocker: MockerFixture) -> None:
  mocker.patch.dict(os.environ, {'LILAC_AUTH_ENABLED': 'True'})
  mocker.patch.dict(os.environ, {'LILAC_AUTH_ADMIN_EMAILS': 'test@test.com,test2@test2.com'})

  # Override the session user so we make them an admin.
  def user() -> UserInfo:
    return UserInfo(
      id='1', email='test_user@test.com', name='test', given_name='test', family_name='test'
    )

  app.dependency_overrides[get_session_user] = user

  url = '/auth_info'
  response = client.get(url)
  assert response.status_code == 200
  assert AuthenticationInfo.model_validate(response.json()) == AuthenticationInfo(
    user=user(),
    access=UserAccess(
      is_admin=False,
      create_dataset=False,
      dataset=DatasetUserAccess(
        compute_signals=False,
        delete_dataset=False,
        delete_signals=False,
        update_settings=False,
        create_label_type=False,
        edit_labels=False,
        label_all=True,
      ),
      concept=ConceptUserAccess(delete_any_concept=False),
    ),
    auth_enabled=True,
  )


def test_auth_nonadmin_edit_labels(mocker: MockerFixture) -> None:
  mocker.patch.dict(os.environ, {'LILAC_AUTH_ENABLED': 'True'})
  mocker.patch.dict(os.environ, {'LILAC_AUTH_ADMIN_EMAILS': 'admin@test.com'})
  mocker.patch.dict(os.environ, {'LILAC_AUTH_USER_EDIT_LABELS': 'True'})

  # Override the session user so we make them an admin.
  def user() -> UserInfo:
    return UserInfo(
      id='1', email='test@test.com', name='test', given_name='test', family_name='test'
    )

  app.dependency_overrides[get_session_user] = user

  url = '/auth_info'
  response = client.get(url)
  assert response.status_code == 200
  assert AuthenticationInfo.model_validate(response.json()) == AuthenticationInfo(
    user=user(),
    access=UserAccess(
      is_admin=False,
      create_dataset=False,
      dataset=DatasetUserAccess(
        compute_signals=False,
        delete_dataset=False,
        delete_signals=False,
        update_settings=False,
        create_label_type=False,
        # Users can edit labels (add and remove) but not create label types.
        edit_labels=True,
        label_all=True,
      ),
      concept=ConceptUserAccess(delete_any_concept=False),
    ),
    auth_enabled=True,
  )


def test_auth_nonadmin_label_all(mocker: MockerFixture) -> None:
  mocker.patch.dict(os.environ, {'LILAC_AUTH_ENABLED': 'True'})
  mocker.patch.dict(os.environ, {'LILAC_AUTH_ADMIN_EMAILS': 'admin@test.com'})
  mocker.patch.dict(os.environ, {'LILAC_AUTH_USER_EDIT_LABELS': 'True'})
  mocker.patch.dict(os.environ, {'LILAC_AUTH_USER_DISABLE_LABEL_ALL': 'True'})

  # Override the session user so we make them an admin.
  def user() -> UserInfo:
    return UserInfo(
      id='1', email='test@test.com', name='test', given_name='test', family_name='test'
    )

  app.dependency_overrides[get_session_user] = user

  url = '/auth_info'
  response = client.get(url)
  assert response.status_code == 200
  assert AuthenticationInfo.model_validate(response.json()) == AuthenticationInfo(
    user=user(),
    access=UserAccess(
      is_admin=False,
      create_dataset=False,
      dataset=DatasetUserAccess(
        compute_signals=False,
        delete_dataset=False,
        delete_signals=False,
        update_settings=False,
        create_label_type=False,
        # Users can edit labels (add and remove) but not create label types.
        edit_labels=True,
        # Users cannot use the label all feature.
        label_all=False,
      ),
      concept=ConceptUserAccess(delete_any_concept=False),
    ),
    auth_enabled=True,
  )
