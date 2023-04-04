import CopyPlugin from 'copy-webpack-plugin';
import HtmlWebpackPlugin from 'html-webpack-plugin';
import open from 'open';
import * as path from 'path';
import {Compiler, Configuration as WebpackConfiguration} from 'webpack';
import {Configuration as WebpackDevServerConfiguration} from 'webpack-dev-server';

// We use require() here because this module has no typings.
// eslint-disable-next-line @typescript-eslint/no-var-requires
const WriteFilePlugin = require('write-file-webpack-plugin');

const WEBPACK_DEVSERVER_PORT = 9000;

const SERVER_PORT = 5432;

const DIST_PATH = path.join(__dirname, '..', '..', 'dist');
const DIST_STATIC_PATH = path.join(DIST_PATH, 'static');

export const INDEX_HTML_OPTIONS: HtmlWebpackPlugin.Options = {
  title: 'Lilac',
  publicPath: '/',
  template: path.join(__dirname, 'src/index.html'),
};

export const WEBPACK_DEVSERVER_CONFIG: WebpackDevServerConfiguration = {
  port: WEBPACK_DEVSERVER_PORT,
  // Gzip compress all assets.
  compress: true,
  // Automatically refresh pages when typescript changes.
  hot: true,
  devMiddleware: {
    // Writes files to dist so we can serve them statically from express.
    writeToDisk: true,
  },
  watchFiles: [path.join(__dirname, 'web', 'src')],
};

interface Configuration extends WebpackConfiguration {
  devServer?: WebpackDevServerConfiguration;
}

let hasOpened = false;
export const WEBPACK_CONFIG: Configuration = {
  mode: 'development',
  devtool: 'source-map',
  module: {
    rules: [
      {
        test: /\.(ts|tsx)$/,
        // Only compile the browser typescript code.
        include: [path.resolve('src/'), path.resolve('fastapi_client/')],
        use: [{loader: 'ts-loader'}],
      },
      {
        test: /\.css$/i,
        use: ['style-loader', 'css-loader', 'postcss-loader'],
      },
    ],
  },
  resolve: {
    modules: ['node_modules'],
    extensions: ['.ts', '.tsx', '.js', '.jsx'],
  },
  entry: {
    demo: './src/index.tsx',
  },
  output: {
    path: DIST_PATH,
    filename: 'static/bundle.js',
    hotUpdateChunkFilename: 'hot/hot-update.js',
    hotUpdateMainFilename: 'hot/hot-update.json',
  },
  plugins: [
    new HtmlWebpackPlugin(INDEX_HTML_OPTIONS),
    new WriteFilePlugin(),
    // Manually copy the duckdb wasm files to the static folder.
    new CopyPlugin({
      patterns: [
        // Copy Shoelace assets to dist/shoelace
        {
          from: path.resolve(__dirname, 'node_modules/@shoelace-style/shoelace/dist/assets'),
          to: path.resolve(DIST_STATIC_PATH, 'shoelace/assets'),
        },
      ],
    }),
    {
      apply: (compiler: Compiler) => {
        compiler.hooks.afterEmit.tap('AfterEmitPlugin', () => {
          if (!hasOpened) {
            // Opens the browser window to this URL automatically when the first build completes.
            open(`http://localhost:${SERVER_PORT}`);
            hasOpened = true;
          }
        });
      },
    },
  ],
  devServer: WEBPACK_DEVSERVER_CONFIG,
};

export default WEBPACK_CONFIG;
