"""Lilac deployer streamlit UI.

This powers: https://huggingface.co/spaces/lilacai/lilac_deployer
"""

from typing import Literal, Optional, Union

import lilac as ll
import streamlit as st
from datasets import load_dataset_builder

if 'current_page' not in st.session_state:
  st.session_state.current_page = 'dataset'

query_params = st.experimental_get_query_params()
if 'dataset' in query_params:
  st.session_state.hf_dataset_name = query_params['dataset'][0]


def _dataset_page():
  is_valid_dataset = False

  st.header('Deploy Lilac for a HuggingFace dataset to a space', anchor=False)
  st.subheader(
    'Step 1: select a dataset',
    divider='violet',
    anchor=False,
    help='For a list of datasets see: https://huggingface.co/datasets',
  )
  hf_dataset_name = st.text_input(
    'dataset id',
    help='Either in the format `user/dataset` or `dataset`, for example: `Open-Orca/OpenOrca`',
    placeholder='dataset or user/dataset',
    value=st.session_state.get('hf_dataset_name', None),
  )
  with st.expander('advanced options'):
    hf_config_name = st.text_input(
      'config',
      help='Some datasets required this field.',
      placeholder='(optional)',
      value=st.session_state.get('hf_config_name', None),
    )
    hf_split = st.text_input(
      'split',
      help='Loads all splits by default.',
      placeholder='(optional)',
      value=st.session_state.get('hf_split', None),
    )
    sample_size = st.number_input(
      'sample size',
      help='Number of rows to sample from the dataset, for each split.',
      placeholder='(optional)',
      min_value=1,
      step=1,
      key='sample_size',
      value=st.session_state.get('sample_size', None),
    )
    hf_read_token = st.text_input(
      'huggingface [read token](https://huggingface.co/settings/tokens)',
      type='password',
      help='The access token is used to authenticate you with HuggingFace to read the dataset. '
      'https://huggingface.co/docs/hub/security-tokens',
      placeholder='(optional if dataset is public)',
    )

  def _next():
    st.session_state.current_page = 'space'
    st.session_state.hf_dataset_name = hf_dataset_name
    st.session_state.hf_config_name = hf_config_name
    st.session_state.hf_split = hf_split
    st.session_state.sample_size = sample_size

  def _next_button():
    enabled = is_valid_dataset
    return st.button('Next', disabled=not enabled, type='primary', on_click=_next)

  ds_builder = None
  if hf_dataset_name:
    is_valid_dataset = False
    try:
      ds_builder = load_dataset_builder(hf_dataset_name, name=hf_config_name, token=hf_read_token)
      is_valid_dataset = True
    except Exception as e:
      st.session_state.ds_error = e
      st.session_state.ds_loaded = False

  st.session_state.hf_dataset_name = hf_dataset_name

  _next_button()

  if ds_builder:
    st.session_state.ds_loaded = True
    st.session_state.ds_error = None
    st.session_state.ds_dataset_name = ds_builder.info.dataset_name
    st.session_state.ds_description = ds_builder.info.description
    st.session_state.ds_features = ds_builder.info.features
    st.session_state.ds_splits = ds_builder.info.splits
  else:
    st.session_state.ds_loaded = False


def _space_page():
  session = dict(st.session_state)

  def _back():
    st.session_state.hf_space_name = hf_space_name
    st.session_state.hf_storage = hf_storage
    st.session_state.hf_access_token = hf_access_token
    st.session_state.current_page = 'dataset'

  hf_space_name = st.session_state.get('hf_space_name', None)
  hf_storage = st.session_state.get('hf_storage', None)
  hf_access_token = st.session_state.get('hf_access_token', None)

  def _back_button():
    return st.button('⬅ Back', on_click=_back)

  _back_button()
  st.subheader(
    'Step 2: create huggingface space',
    divider='violet',
    anchor=False,
    help='See HuggingFace Spaces [documentation](https://huggingface.co/docs/hub/spaces-overview)',
  )
  if session.get('hf_config_name', None):
    st.write(f'Config: {session["hf_config_name"]}')
  if st.session_state.get('hf_split', None):
    st.write(f'Split: {session["hf_split"]}')
  if st.session_state.get('sample_size', None):
    st.write(f'Sample size: {session["sample_size"]}')

  hf_space_name = st.text_input(
    'space id',
    help='This space will be created if it does not exist',
    placeholder='org/name',
    value=hf_space_name,
  )
  hf_access_token = st.text_input(
    'huggingface [write token](https://huggingface.co/settings/tokens)',
    type='password',
    help='The access token is used to authenticate you with HuggingFace to create the space. '
    'https://huggingface.co/docs/hub/security-tokens',
    value=hf_access_token,
  )
  storage_options = ['None', 'small', 'medium', 'large']
  hf_storage = st.selectbox(
    'persistent storage',
    ['None', 'small', 'medium', 'large'],
    help='Persistent storage is required if you want data to persist past the lifetime of the '
    'space docker image. This is recommended when running computations like signals or embeddings,'
    'or if you want labels to persist. You will get charged for persistent storage. See '
    'https://huggingface.co/docs/hub/spaces-storage',
    index=storage_options.index(hf_storage if hf_storage else 'None'),
  )

  def _deploy_button():
    enabled = hf_access_token and hf_space_name
    return st.button('Deploy', disabled=not enabled, on_click=_deploy)

  def _deploy():
    hf_dataset_name = st.session_state['hf_dataset_name']
    assert hf_space_name and hf_access_token and hf_dataset_name

    hf_config_name = st.session_state.get('hf_config_name', None)
    hf_split = st.session_state.get('hf_split', None)
    sample_size = st.session_state.get('sample_size', None)

    hf_space_storage: Optional[Union[Literal['small'], Literal['medium'], Literal['large']]]
    if hf_storage == 'None':
      hf_space_storage = None
    else:
      assert hf_storage == 'small' or hf_storage == 'medium' or hf_storage == 'large'
      hf_space_storage = hf_storage

    try:
      space_link = ll.deploy_config(
        hf_space=hf_space_name,
        create_space=True,
        hf_space_storage=hf_space_storage,
        config=ll.Config(
          datasets=[
            ll.DatasetConfig(
              namespace='local',
              name=hf_dataset_name.replace('/', '_'),
              source=ll.HuggingFaceSource(
                dataset_name=hf_dataset_name,
                config_name=hf_config_name,
                split=hf_split,
                sample_size=int(sample_size) if sample_size else None,
                token=hf_access_token,
              ),
            )
          ]
        ),
        hf_token=hf_access_token,
      )
      st.session_state.space_link = space_link
      st.session_state.current_page = 'success'
    except Exception as e:
      st.subheader('Deployment failed!', divider='red')
      st.error(e)

  _deploy_button()


def _success_page():
  space_link = st.session_state.space_link

  st.subheader('Success!', divider='green')
  st.subheader(f'[Visit your HuggingFace space ↗]({space_link})')
  st.write(
    'Spaces are private by default. '
    f'To make them public, visit the [Space settings]({space_link}/settings). '
  )


if st.session_state.current_page == 'dataset':
  _dataset_page()
elif st.session_state.current_page == 'space':
  _space_page()
elif st.session_state.current_page == 'success':
  _success_page()

# Sidebar content.
dataset_name = st.session_state.get('ds_dataset_name', None) or st.session_state.get(
  'hf_dataset_name', None
)
if st.session_state.get('ds_loaded', False):
  st.sidebar.header(
    f'[{dataset_name}](https://huggingface.co/datasets/{dataset_name})',
    divider='rainbow',
    anchor=False,
    help='Dataset information from HuggingFace datasets.',
  )

  st.sidebar.write(st.session_state.get('ds_description', None))

  st.sidebar.write('##### Features')
  st.sidebar.table(st.session_state.get('ds_features', {}))

  st.sidebar.write('##### Splits')
  st.sidebar.table(st.session_state.get('ds_splits', {}))
else:
  if st.session_state.get('ds_error', None):
    st.sidebar.subheader(f'Error loading `{dataset_name}`', divider='red', anchor=False)
    st.sidebar.error(st.session_state.get('ds_error', None))
    st.sidebar.write(
      'If the dataset is private, make sure to enter a HuggingFace '
      'token that has access to the dataset.'
    )
  else:
    st.sidebar.write('Choose a dataset to see more info..')
