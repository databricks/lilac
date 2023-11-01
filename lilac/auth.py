"""Authentication and ACL configuration."""

from typing import Optional

from fastapi import Request
from pydantic import BaseModel, ValidationError

from .env import env


class ConceptAuthorizationException(Exception):
  """Authorization exceptions thrown by the concept database."""

  pass


class DatasetUserAccess(BaseModel):
  """User access for datasets."""

  # Whether the user can compute a signal.
  compute_signals: bool
  # Whether the user can delete a dataset.
  delete_dataset: bool
  # Whether the user can delete a signal.
  delete_signals: bool
  # Whether the user can update settings.
  update_settings: bool
  # Whether the user can create a new label type.
  create_label_type: bool
  # Whether the user can add or remove labels.
  edit_labels: bool
  # Whether the user can use the label all feature.
  label_all: bool


class ConceptUserAccess(BaseModel):
  """User access for concepts."""

  # Whether the user can delete any concept (not their own).
  delete_any_concept: bool


class UserAccess(BaseModel):
  """User access."""

  is_admin: bool = False

  create_dataset: bool

  # TODO(nsthorat): Make this keyed to each dataset and concept.
  dataset: DatasetUserAccess
  concept: ConceptUserAccess


class UserInfo(BaseModel):
  """User information."""

  id: str
  email: str
  name: str
  given_name: str
  family_name: str


class AuthenticationInfo(BaseModel):
  """Authentication information for the user."""

  user: Optional[UserInfo] = None
  access: UserAccess
  auth_enabled: bool
  # The HuggingFace space ID if the server is running on a HF space.
  huggingface_space_id: Optional[str] = None


def get_session_user(request: Request) -> Optional[UserInfo]:
  """Get the user from the session."""
  if not env('LILAC_AUTH_ENABLED'):
    return None
  user_info_dict = request.session.get('user', None)
  if user_info_dict:
    try:
      return UserInfo.model_validate(user_info_dict)
    except ValidationError:
      return None
  return None


def get_admin_emails() -> list[str]:
  """Return the admin emails."""
  admin_emails = env('LILAC_AUTH_ADMIN_EMAILS', None)
  if admin_emails:
    return admin_emails.split(',')
  return []


def get_user_access(user_info: Optional[UserInfo]) -> UserAccess:
  """Get the user access."""
  auth_enabled = env('LILAC_AUTH_ENABLED')
  if isinstance(auth_enabled, str):
    auth_enabled = auth_enabled.lower() == 'true'

  admin_emails = get_admin_emails()
  is_admin = not auth_enabled or (user_info is not None and user_info.email in admin_emails)

  if auth_enabled and not is_admin:
    return UserAccess(
      is_admin=is_admin,
      create_dataset=False,
      dataset=DatasetUserAccess(
        compute_signals=False,
        delete_dataset=False,
        delete_signals=False,
        update_settings=False,
        create_label_type=False,
        edit_labels=bool(env('LILAC_AUTH_USER_EDIT_LABELS', False)),
        label_all=not bool(env('LILAC_AUTH_USER_DISABLE_LABEL_ALL', False)),
      ),
      concept=ConceptUserAccess(delete_any_concept=False),
    )

  return UserAccess(
    is_admin=is_admin,
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
  )
