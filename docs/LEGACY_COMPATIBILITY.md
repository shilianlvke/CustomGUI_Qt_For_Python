# Legacy Compatibility Plan

Last Updated: 2026-03-19

## Current Legacy Entry Points

None.

## Canonical Replacements

1. AppCore.get_app_context().settings / AppCore.AppSettings
2. GUI.windows.loading_window.ui_main

## Removed Legacy Entry Points

1. AppCore.SYS.module.languge_module -> AppCore.SYS.module.language_module
2. GUI.windows.loading_window.ui_mian -> GUI.windows.loading_window.ui_main
3. AppCore.SYS.module.config_module -> AppCore.get_app_context().settings / AppCore.AppSettings

## Runtime Status

1. Runtime code currently does not depend on legacy entry points.
2. Legacy imports are only retained in compatibility wrappers and dedicated tests.

## Removal Window Strategy

1. Stage 1 (now): keep compatibility wrappers and emit deprecation warning where available.
2. Stage 2 (next minor): block new legacy imports in CI and keep migration docs.
3. Stage 3 (next major): remove legacy wrappers and compatibility tests.

## Guardrails

1. tests/test_legacy_import_policy.py enforces no new runtime legacy imports.
2. CI runs the legacy import policy test on every push and pull request.
