"""Authentication and ACL configuration."""

from typing import Optional

from pydantic import BaseModel

from .config import CONFIG


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


class ConceptUserAccess(BaseModel):
  """User access for concepts."""
  # Whether the user can delete any concept (not their own).
  delete_any_concept: bool


class UserAccess(BaseModel):
  """User access."""
  create_dataset: bool

  # TODO(nsthorat): Make this keyed to each dataset and concept.
  dataset: DatasetUserAccess
  concept: ConceptUserAccess


class UserInfo(BaseModel):
  """User information."""
  email: str
  name: str
  given_name: str
  family_name: str


class AuthenticationInfo(BaseModel):
  """Authentication information for the user."""
  user: Optional[UserInfo]
  access: UserAccess
  auth_enabled: bool


def get_user_access() -> UserAccess:
  """Get the user access."""
  auth_enabled = CONFIG.get('LILAC_AUTH_ENABLED', False)
  if isinstance(auth_enabled, str):
    auth_enabled = auth_enabled.lower() == 'true'
  if auth_enabled:
    return UserAccess(
      create_dataset=False,
      dataset=DatasetUserAccess(
        compute_signals=False, delete_dataset=False, delete_signals=False, update_settings=False),
      concept=ConceptUserAccess(delete_any_concept=False))
  return UserAccess(
    create_dataset=True,
    dataset=DatasetUserAccess(
      compute_signals=True, delete_dataset=True, delete_signals=True, update_settings=True),
    concept=ConceptUserAccess(delete_any_concept=True))
