"""Router for Google OAuth2 login."""

from urllib.parse import urlparse, urlunparse

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse
from starlette.config import Config
from starlette.responses import RedirectResponse

from .auth import UserInfo
from .env import env
from .router_utils import RouteErrorHandler

router = APIRouter(route_class=RouteErrorHandler)

if env('LILAC_AUTH_ENABLED'):
  oauth = OAuth(
    Config(
      environ={
        'GOOGLE_CLIENT_ID': env('GOOGLE_CLIENT_ID'),
        'GOOGLE_CLIENT_SECRET': env('GOOGLE_CLIENT_SECRET'),
      }
    )
  )
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
  userinfo = token['userinfo']
  request.session['user'] = UserInfo(
    id=str(userinfo['sub']),
    email=userinfo['email'],
    name=userinfo['name'],
    given_name=userinfo['given_name'],
    family_name=userinfo['family_name'],
  ).model_dump()

  return RedirectResponse(url='/')


@router.get('/logout')
def logout(request: Request) -> RedirectResponse:
  """Logs the user out."""
  request.session.pop('user', None)
  return RedirectResponse(url='/')
