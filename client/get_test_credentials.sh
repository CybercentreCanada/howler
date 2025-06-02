#!/bin/bash

echo "This script allows you to set environment variables before running the Howler Client integration tests."
echo "This will allow the test to connect to your local howler client using either OBO Authentication, or"
echo "a user/API key pair."
echo ""

        export HOWLER_USERNAME="user"
        export HOWLER_API_KEY="devkey:user"

        echo "HOWLER_USERNAME and HOWLER_API_KEY set. Your tests will be run using API key authentication."
