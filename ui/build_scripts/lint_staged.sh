#!/bin/bash
cd $(dirname $(dirname $0))
pwd
npx lint-staged --no-stash
