#!/bin/bash
cd "$(dirname $(dirname $0))/ui"
pnpm tsc --noEmit --incremental
