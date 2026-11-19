# Habit Pulse Application Specification

Source: requirements.md and scripts/01_schema.sql (executed successfully on APEX 26.1.6).
App path: applications/habit-pulse. New app ID:110. Workspace: existing user-scoped workspace.
Compiler truth: SQLcl26.3 apexlang-compiler.jar build26.2.0+3479 metadataHash863417236b69.

## Application Composition Plan

Five functional pages plus scaffold login/global. Full-page detail deliberately selected for beginner tutorial traceability.
Page1 TODAY: breadcrumb 今日(root); metrics metricCard SQL count/done/rate; native cards active habits → Page10 P10_ID=HABIT_ID; add button → Page10 cleared.
Page2 DASHBOARD: breadcrumb 振り返り(parent1); native line chart daily completion percentage last7days; native habit cards summary.
Page3 HABITS: breadcrumb 習慣管理(parent1); active/all select; cards → Page10; add button.
Page4 HISTORY: breadcrumb 履歴(parent1); interactive report read-only joined checkins owner-filtered; native report date/name filters.
Page10 HABIT: breadcrumb 習慣を編集(parent3); fields NAME,DESCRIPTION,COLOR,ICON,ORDER,NOTE; hidden ID checksum protected; save/process, record/process, undo/process, archive/process; return Today after successful write.

## Rich UI Pattern Plan

Native metricCard, Cards, chart, interactiveReport. White/forest green CSS; no custom web rendering of native data components.
Native static LOVs COLOR(green,blue,orange,purple),ICON(fa-check-circle,fa-book,fa-heart,fa-bicycle).

## Behavior and Security

HT_API derives uppercase authenticated APP_USER. Every write asserts parent ownership; only active habits writable. Records today JST only, unique by habit/day; merge idempotent, parent row locked. Archived habits keep history. Detail load is ownership-filtered. Hidden ID checksum. All user data escaped by native components.
Save NAME required and max80; DESCRIPTION/NOTE max500; color/icon allowlisted by constraints. Start today server-only. No physical deletion. Login requires APEX accounts.
All pages use direct navigation; detail is full page therefore no modal refresh dependency.

## Test Plan

Native compile; live validate/import; owner API isolation; same-day uniqueness; check/undo/archive semantics; SQL/chart equality; PC and mobile screenshots.
