#!/bin/bash
cd $(dirname $(dirname $0))
pwd
npx prettier -c -w src --cache
