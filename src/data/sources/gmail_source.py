"""Gmail source."""
import base64
import os.path
import random
from time import sleep
from typing import Any, Iterable, Optional

from email_reply_parser import EmailReplyParser
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import Field as PydanticField
from typing_extensions import override

from ...schema import Item, field
from ...utils import log
from .source import Source, SourceSchema

# If modifying these scopes, delete the token json file.
_SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
_GMAIL_CONFIG_DIR = '.gmail'
_TOKEN_FILENAME = 'token.json'
_CREDS_FILENAME = 'credentials.json'
_NUM_RETRIES = 5
_MAX_NUM_THREADS = 1_000


class Gmail(Source):
  """Connects to your Gmail and loads the text of your emails.

  **One time setup**

  Download the OAuth credentials file from the
  [Google Cloud Console](https://console.cloud.google.com/apis/credentials) and save it to the
  correct location. See
  [guide](https://developers.google.com/gmail/api/quickstart/python#authorize_credentials_for_a_desktop_application)
  for details.
  """

  name = 'gmail'

  credentials_file = PydanticField(
    description='Path to the OAuth credentials file.',
    default=os.path.join(_GMAIL_CONFIG_DIR, _CREDS_FILENAME))

  _creds: Optional[Credentials] = None

  class Config:
    # Language is required even though it has a default value.
    schema_extra = {'required': ['credentials_file']}

  @override
  def prepare(self) -> None:
    # The token file stores the user's access and refresh tokens, and is created automatically when
    # the authorization flow completes for the first time.
    token_filepath = os.path.join(_GMAIL_CONFIG_DIR, _TOKEN_FILENAME)
    if os.path.exists(token_filepath):
      self._creds = Credentials.from_authorized_user_file(token_filepath, _SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not self._creds or not self._creds.valid:
      if self._creds and self._creds.expired and self._creds.refresh_token:
        self._creds.refresh(Request())
      else:
        if not os.path.exists(self.credentials_file):
          raise ValueError(
            f'Could not find the OAuth credentials file at "{self.credentials_file}". Make sure to '
            'download it from the Google Cloud Console and save it to the correct location.')
        flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, _SCOPES)
        self._creds = flow.run_local_server()

      os.makedirs(os.path.dirname(token_filepath), exist_ok=True)
      # Save the token for the next run.
      with open(token_filepath, 'w') as token:
        token.write(self._creds.to_json())

  @override
  def source_schema(self) -> SourceSchema:
    return SourceSchema(fields={'text': field('string')})

  @override
  def process(self) -> Iterable[Item]:
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
      else:
        text = '\n\n'.join([
          EmailReplyParser.parse_reply(
            base64.urlsafe_b64decode(
              msg['payload']['body']['data'].encode('ascii')).decode('utf-8'))
          for msg in response['messages']
          if 'payload' in msg and 'body' in msg['payload'] and 'data' in msg['payload']['body']
        ])
        thread_batch.append({'text': text})
        if request_id in retry_batch:
          retry_batch.remove(request_id)

    # First request.
    thread_list_req = threads_resource.list(userId='me', includeSpamTrash=False) or None
    thread_list = thread_list_req.execute(num_retries=_NUM_RETRIES) if thread_list_req else None

    while (num_threads_fetched < _MAX_NUM_THREADS and thread_list and thread_list_req):
      batch = service.new_batch_http_request(callback=_thread_fetched)

      for gmail_thread in thread_list['threads']:
        thread_id = gmail_thread['id']
        if not retry_batch or (thread_id in retry_batch):
          batch.add(
            service.users().threads().get(userId='me', id=thread_id, format='full'),
            request_id=thread_id)

      batch.execute()
      num_threads_fetched += len(thread_batch)
      yield from thread_batch
      thread_batch = []

      if retry_batch:
        log(f'Failed to fetch {len(retry_batch)} threads. Retrying...')
        timeout = 2**(num_retries - 1) + random.uniform(0, 1)
        sleep(timeout)
        num_retries += 1
      else:
        retry_batch = set()
        num_retries = 0
        # Fetch next page.
        thread_list_req = threads_resource.list_next(thread_list_req, thread_list)
        thread_list = thread_list_req.execute(num_retries=_NUM_RETRIES) if thread_list_req else None
