#!/usr/bin/env python
"""Launcher shim; the app lives in the vkpostscheduler package."""

import sys

from vkpostscheduler.main import main

if __name__ == "__main__":
    sys.exit(main())
