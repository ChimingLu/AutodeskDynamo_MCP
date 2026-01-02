# Tests Directory

This directory contains test scripts and temporary files for the AutodeskDynamo_MCP project.

## Directory Structure

- **`archive/`**: Contains old, deprecated, or superseded test scripts. These are kept for reference but should not be actively used.
- **`temp/`**: Contains temporary scripts generated during agent interactions or debugging sessions. These files can be safely deleted if no longer needed.
- **`scripts/`** (Future Use): Intended for permanent, well-structured test scripts that are part of the CI/CD pipeline or regular regression testing.

## Usage

When creating new test scripts:
1. If it's a **temporary** test or experiment, place it in `tests/temp/`.
2. If it's a **permanent** test case, place it in `tests/` (or `tests/scripts/` once established).
3. Do **not** place test scripts in the project root directory.
