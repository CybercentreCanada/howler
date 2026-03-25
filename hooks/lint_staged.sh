#!/bin/bash
cd $(dirname $(dirname $0))/ui
pwd
npx lint-staged --no-stash
