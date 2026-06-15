// build.js
import * as esbuild from 'esbuild';
import dotenv from 'dotenv';

// 1. Load the specific .env file
dotenv.config({ path: '.env.production' });

// 2. Prepare the variables you want to inject
// esbuild requires the values in 'define' to be JSON-stringified strings
const url = JSON.stringify(process.env.NEXT_PUBLIC_FRONT_URL || '');

const config: esbuild.BuildOptions = {
  entryPoints: ['scripts/chat-widget.ts'],
  bundle: true,
  minify: true,
  outfile: 'public/chat-widget.js',
  // 3. Define the global variable to replace in your source code
  define: {
    'process.env.NEXT_PUBLIC_FRONT_URL': url,
    // Or you can use a custom global name like:
    // '__FRONT_URL__': url
  },
};
esbuild.build(config).catch(() => process.exit(1));