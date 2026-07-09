#!/bin/bash
cd $(dirname $(dirname $0))
pwd
pnpx oxfmt src
