#!/bin/bash
cd $(dirname $(dirname $0))
pwd
pnpx oxlint --fix src
