#!/bin/bash
cd $(dirname $(dirname $0))/ui
npx prettier -c -w src --cache --cache-strategy metadata
