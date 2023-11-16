"""Gmail source."""
import base64
import dataclasses
import os.path
import random
import re
from datetime import datetime
from time import sleep
from typing import TYPE_CHECKING, Any, ClassVar, Iterable, Optional

from pydantic import ConfigDict
from pydantic import Field as PydanticField
from typing_extensions import override

from ..env import get_project_dir
from ..schema import Item, field
from ..source import Source, SourceSchema
from ..utils import log

if TYPE_CHECKING:
  from google.oauth2.credentials import Credentials

# If modifying these scopes, delete the token json file.
_SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
_TOKEN_FILENAME = 'token.json'
_CREDS_FILENAME = 'credentials.json'
_NUM_RETRIES = 10
_MAX_NUM_THREADS = 30_000

_UNWRAP_PATTERN = re.compile(r'(\S)\n(\S)')
HTTP_PATTERN = re.compile(r'https?://[^\s]+')


def _gmail_config_dir() -> str:
  return os.path.join(get_project_dir(), '.gmail')


class GmailSource(Source):
  """Connects to your Gmail and loads the text of your emails.

  **One time setup**

  Download the OAuth credentials file from the
  [Google Cloud Console](https://console.cloud.google.com/apis/credentials) and save it to the
  correct location. See
  [guide](https://developers.google.com/gmail/api/quickstart/python#authorize_credentials_for_a_desktop_application)
  for details.
  """

  name: ClassVar[str] = 'gmail'

  credentials_file: str = PydanticField(
    description=f'Path to the OAuth credentials file. Defaults to `.gmail/{_CREDS_FILENAME}` in '
    'your Lilac project directory.',
    default_factory=lambda: os.path.join(_gmail_config_dir(), _CREDS_FILENAME),
  )

  _creds: Optional['Credentials'] = None
  model_config = ConfigDict(json_schema_extra={'required': ['credentials_file']})

  @override
  def setup(self) -> None:
    try:
      from google.auth.transport.requests import Request
      from google.oauth2.credentials import Credentials
      from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
      raise ImportError(
        'Could not import dependencies for the "gmail" source. '
        'Please install with pip install lilac[gmail]'
      )

    gmail_config_dir = _gmail_config_dir()
    credentials_file = self.credentials_file or os.path.join(gmail_config_dir, _CREDS_FILENAME)

    # The token file stores the user's access and refresh tokens, and is created automatically when
    # the authorization flow completes for the first time.
    token_filepath = os.path.join(gmail_config_dir, _TOKEN_FILENAME)
    if os.path.exists(token_filepath):
      self._creds = Credentials.from_authorized_user_file(token_filepath, _SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not self._creds or not self._creds.valid:
      if self._creds and self._creds.expired and self._creds.refresh_token:
        self._creds.refresh(Request())
      else:
        if not os.path.exists(credentials_file):
          raise ValueError(
            f'Could not find the OAuth credentials file at "{credentials_file}". Make sure to '
            'download it from the Google Cloud Console and save it to the correct location.'
          )
        flow = InstalledAppFlow.from_client_secrets_file(credentials_file, _SCOPES)
        self._creds = flow.run_local_server()

      os.makedirs(os.path.dirname(token_filepath), exist_ok=True)
      # Save the token for the next run.
      with open(token_filepath, 'w') as token:
        token.write(self._creds.to_json())

  @override
  def source_schema(self) -> SourceSchema:
    return SourceSchema(
      fields={
        'body': field('string'),
        'snippet': field('string'),
        'dates': field(fields=['string']),
        'subject': field('string'),
      }
    )

  @override
  def yield_items(self) -> Iterable[Item]:
    try:
      from email_reply_parser import EmailReplyParser
      from googleapiclient.discovery import build
      from googleapiclient.errors import HttpError
    except ImportError:
      raise ImportError(
        'Could not import dependencies for the "gmail" source. '
        'Please install with pip install lilac[gmail]'
      )

    # Call the Gmail API
    service = build('gmail', 'v1', credentials=self._creds)

    # threads.list API
    threads_resource = service.users().threads()

    thread_batch: list[Item] = []
    retry_batch: set[str] = set()
    num_retries = 0
    num_threads_fetched = 0

    def _thread_fetched(request_id: str, response: Any, exception: Optional[HttpError]) -> None:
      if exception is not None:
        retry_batch.add(request_id)
        return

      replies: list[str] = []
      dates: list[str] = []
      snippets: list[str] = []
      subject: Optional[str] = None

      for msg in response['messages']:
        epoch_sec = int(msg['internalDate']) / 1000.0
        date = datetime.fromtimestamp(epoch_sec).strftime('%Y-%m-%d %H:%M:%S')
        dates.append(date)
        if 'snippet' in msg:
          snippets.append(msg['snippet'])
        email_info = _parse_payload(msg['payload'])
        subject = subject or email_info.subject
        parsed_parts: list[str] = []
        for body in email_info.parts:
          if not body:
            continue
          text = base64.urlsafe_b64decode(body).decode('utf-8')
          text = EmailReplyParser.parse_reply(text)
          # Unwrap text.
          text = _UNWRAP_PATTERN.sub('\\1 \\2', text)
          # Remove URLs.
          text = HTTP_PATTERN.sub('', text)

          if text:
            parsed_parts.append(text)
        if email_info.sender and parsed_parts:
          parsed_parts = [
            f'--------------------{email_info.sender}--------------------',
            *parsed_parts,
          ]
        if parsed_parts:
          replies.append('\n'.join(parsed_parts))

      if replies:
        thread_batch.append(
          {
            'body': '\n\n'.join(replies),
            'snippet': '\n'.join(snippets) if snippets else None,
            'dates': dates,
            'subject': subject,
          }
        )
      if request_id in retry_batch:
        retry_batch.remove(request_id)

    # First request.
    thread_list_req = threads_resource.list(userId='me', includeSpamTrash=False) or None
    thread_list = thread_list_req.execute(num_retries=_NUM_RETRIES) if thread_list_req else None

    while num_threads_fetched < _MAX_NUM_THREADS and thread_list and thread_list_req:
      batch = service.new_batch_http_request(callback=_thread_fetched)

      threads = thread_list['threads'] if 'threads' in thread_list else []
      for gmail_thread in threads:
        thread_id = gmail_thread['id'] if 'id' in gmail_thread else None
        if not thread_id:
          continue
        if not retry_batch or (thread_id in retry_batch):
          batch.add(
            service.users().threads().get(userId='me', id=thread_id, format='full'),
            request_id=thread_id,
          )

      batch.execute()
      num_threads_fetched += len(thread_batch)
      yield from thread_batch
      thread_batch = []

      if retry_batch:
        log(f'Failed to fetch {len(retry_batch)} threads. Retrying...')
        timeout = 2 ** (num_retries - 1) + random.uniform(0, 1)
        sleep(timeout)
        num_retries += 1
      else:
        retry_batch = set()
        num_retries = 0
        # Fetch next page.
        thread_list_req = threads_resource.list_next(thread_list_req, thread_list)
        thread_list = thread_list_req.execute(num_retries=_NUM_RETRIES) if thread_list_req else None


@dataclasses.dataclass
class EmailInfo:
  """Stores parsed information about an email."""

  sender: Optional[str] = None
  subject: Optional[str] = None
  parts: list[bytes] = dataclasses.field(default_factory=list)


def _get_header(payload: Any, name: str) -> Optional[str]:
  if 'headers' not in payload:
    return None
  values = [h['value'] for h in payload['headers'] if h['name'].lower().strip() == name]
  return values[0] if values else None


def _parse_payload(payload: Any) -> EmailInfo:
  sender = _get_header(payload, 'from')
  subject = _get_header(payload, 'subject')
  parts: list[bytes] = []

  # Process the message body.
  if 'mimeType' in payload and 'text/plain' in payload['mimeType']:
    if 'body' in payload and 'data' in payload['body']:
      parts.append(payload['body']['data'].encode('ascii'))

  # Process the message parts.
  for part in payload.get('parts', []):
    email_info = _parse_payload(part)
    sender = sender or email_info.sender
    subject = subject or email_info.subject
    parts.extend(email_info.parts)

  return EmailInfo(sender, subject, parts)
