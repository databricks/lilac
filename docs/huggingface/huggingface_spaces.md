# Duplicate the HuggingFace demo

Lilac hosts a [HuggingFace spaces demo](https://lilacai-lilac.hf.space/) so you can try Lilac before
installing it.

Thanks to HuggingFace, this space can be duplicated and customized with your own data. You can
decide to make your duplicated private for use with private or sensitive data.

To duplicate the space, click the hamburger menu in the top-right of the space and click **Duplicate
this Space**:

<img width=480 src="../_static/huggingface/huggingface_duplicate_space.png"></img>

This will open a modal which allows to to determine the machine. We recommend using persistent
storage as it will allow you to save results of computations permanently (loading datasets, making
concepts, computing signals and concepts). However, if you decide not to pay for persistent storage,
you can still use Lilac, but results of computations will lost when the image reboots.

<img src="../_static/huggingface/huggingface_duplicate_space_machine.png"></img>

The modal also contains options for environment variables.

<img src="../_static/huggingface/huggingface_duplicate_space_variables.png"></img>

**Secrets**:

- `HF_ACCESS_TOKEN`: If your space is private or reads from private data hosted on HuggingFace, set
  this to a HuggingFace access token with read permissions, allowing the space to download the
  datasets upon boot. See
  [HuggingFace User access tokens](https://huggingface.co/docs/hub/security-tokens) for more
  details.
- `GOOGLE_CLIENT_SECRET`: If you wish to enable authentication on your server, define this variable
  to be the client secret of a Google Application you create. You should also define
  `GOOGLE_CLIENT_ID`. Details can be found at
  [Using Oauth 2.0 to Access Google APIs](https://developers.google.com/identity/protocols/oauth2).
- `LILAC_OAUTH_SECRET_KEY`: If you wish to enable authentication on your server, this should be
  defined as a random string. Details in the Oauth link above.

**Space variables**:

- `LILAC_AUTH_ENABLED`: Whether to enable Google authentication on your duplicated server. Set this
  to `false`, or delete it, to disable Google authentication. If your HuggingFace space is private,
  you can set this to `false` and rely on HuggingFace space authentication.
- `DUCKDB_USE_VIEWS`: Whether DuckDB uses views (1), or DuckDB tables (0). Views allow for much less
  RAM consumption, with a runtime query penalty. When using DuckDB tables (0), demos will take more
  RAM but be much faster.
- `HF_HOME`: This should be kept `/data/.huggingface` if you plan on using Persistent Storage. This
  allows the HuggingFace cache to be persistent. If you are not, you should remove this variable
  entirely.
- `LILAC_PROJECT_DIR`: The path where data for datasets, concept models and Lilac caches are stored.
  This should be kept `/data` if you plan on using Persistent Storage. If you are not, this should
  be set to the relative path `./data` which lives ephemerally in the docker image. It is important
  to use `./data` because it has been given writen permissions by the docker image. See
  [HuggingFace Disk usage on Spaces](https://huggingface.co/docs/hub/spaces-storage) for
  documentation on Persistent Storage.
- `LILAC_DATA_PATH`: Deprecated in favor of `LILAC_PROJECT_DIR`.
- `GOOGLE_ANALYTICS_ENABLED`: Set this to "false" to disable our Google Analytics tracking on the
  HuggingFace demo. We use this just to track basic session information on the public demo.

After you click the duplicate space button, the space will be duplicated and start building the
docker image in your own space.

Once the image is built, your space is now running a personalized Lilac instance!

For more details on environment variables, see [Environment Variables](../environment/variables.md).

### Removing datasets

You'll notice that the demo will try to load the same datasets from the lilacai/lilac space. This
may lead to an out of memory error when cloning locally.

To remove these, edit the `README.md` on the space and delete the datasets under the linked
`datasets` field for the HuggingFace space configuration. The space will restart.

If these datasets were synced in the process, you can delete them from the UI.

<img src="../_static/huggingface/huggingface_space_readme_datasets.png"></img>
