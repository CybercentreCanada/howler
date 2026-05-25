#!/bin/bash
cd ${1:-$(pwd)}
poetry check
