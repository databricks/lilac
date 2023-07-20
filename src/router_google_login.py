"""Router for Google OAuth2 login."""

from urllib.parse import urlparse, urlunparse

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse
from starlette.config import Config
from starlette.responses import RedirectResponse

from .config import CONFIG
from .router_utils import RouteErrorHandler

router = APIRouter(route_class=RouteErrorHandler)

GOOGLE_CLIENT_ID = CONFIG.get('GOOGLE_CLIENT_ID', None)
GOOGLE_CLIENT_SECRET = CONFIG.get('GOOGLE_CLIENT_SECRET', None)
LILAC_AUTH_ENABLED = CONFIG.get('LILAC_AUTH_ENABLED', False)
if LILAC_AUTH_ENABLED:
  if GOOGLE_CLIENT_ID is None or GOOGLE_CLIENT_SECRET is None:
    raise ValueError(
      'Missing `GOOGLE_CLIENT_ID` or `GOOGLE_CLIENT_SECRET` when `LILAC_AUTH_ENABLED=true`')
  SECRET_KEY = CONFIG.get('LILAC_OAUTH_SECRET_KEY', None)
  if not SECRET_KEY:
    raise ValueError('Missing `LILAC_OAUTH_SECRET_KEY` when `LILAC_AUTH_ENABLED=true`')

  # Set up oauth
  oauth = OAuth(
    Config(environ={
      'GOOGLE_CLIENT_ID': GOOGLE_CLIENT_ID,
      'GOOGLE_CLIENT_SECRET': GOOGLE_CLIENT_SECRET
    }))
  oauth.register(
    name='google',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
  )


@router.get('/login')
async def login(request: Request, origin_url: str) -> RedirectResponse:
  """Redirects to Google OAuth login page."""
  auth_path = urlunparse(urlparse(origin_url)._replace(path='/google/auth'))
  return await oauth.google.authorize_redirect(request, auth_path)


@router.get('/auth')
async def auth(request: Request) -> Response:
  """Handles the Google OAuth callback."""
  try:
    token = await oauth.google.authorize_access_token(request)
  except OAuthError as error:
    return HTMLResponse(f'<h1>{error}</h1>')
  request.session['user'] = token['userinfo']
  return RedirectResponse(url='/')


@router.get('/logout')
def logout(request: Request) -> RedirectResponse:
  """Logs the user out."""
  request.session.pop('user', None)
  return RedirectResponse(url='/')
