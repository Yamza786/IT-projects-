# Study Planner

An offline-first SwiftUI study planner. It stores tasks and study-session records as an atomically replaced JSON snapshot in the app's Documents directory, with iOS file protection enabled. It is designed to give students a simple task checklist that works without an account or network connection.

## MVP features

- Validated, bounded task titles and study-session durations.
- Complete/reopen tasks and calculate daily study minutes from recorded sessions.
- Codable domain model separated from the SwiftUI view and persistence adapter.
- VoiceOver labels/hints and native Dynamic Type-friendly list controls.
- Atomic local persistence; no network requests, analytics, or third-party dependencies.

The current SwiftUI screen supports adding and completing tasks. Session recording and reminders are represented by the tested core model but are not yet exposed in the UI. No screenshot is included yet; run the app in an iOS 17+ simulator to capture one.

## Requirements and setup

Requires Xcode 15+, Swift 5.9+, and an iOS 17+ simulator or device. The domain package also targets macOS 14 for command-line unit testing.

```sh
swift test
```

Open `Package.swift` in Xcode, select an iOS simulator destination, and run the `StudyPlannerApp` scheme. The iOS app writes `planner.json` under its sandboxed Documents directory; uninstalling the app removes that local data.

## Architecture and limitations

`StudyPlannerCore` owns validation, completion state, session totals, and the persistence adapter. `StudyPlannerApp` provides the SwiftUI list and accessible controls. XCTest exercises validation, session totals, completion and persistence round-trips. A macOS GitHub Actions workflow runs `swift test`.

This is an MVP: reminders, recurring schedules, subject management, backup/export, cloud sync and app-level data migrations are future work. The JSON snapshot is suitable for this small local dataset, not concurrent multi-device writes. Do not store sensitive personal notes in the demo.

## Contribution

Keep task/session fixtures synthetic. Run `swift test` before submitting changes and add migration coverage before changing the stored snapshot format.
