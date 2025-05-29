#!/bin/bash
cd $(dirname $(dirname $0))
npx lint-staged
