import Foundation
import XCTest
@testable import StudyPlannerCore

final class PlannerTests: XCTestCase {
    func testTaskValidationAndCompletion() throws {
        XCTAssertThrowsError(try StudyTask(title: "  ", subject: "Math"))
        var planner = PlannerSnapshot()
        let task = try StudyTask(title: "  Review algebra  ", subject: "Math")
        try planner.add(task: task)
        planner.completeTask(id: task.id)
        XCTAssertEqual(planner.tasks.first?.title, "Review algebra")
        XCTAssertEqual(planner.tasks.first?.isComplete, true)
    }

    func testSessionsAreBoundedAndDailyTotalIsCalculated() throws {
        let task = try StudyTask(title: "Reading", subject: "History")
        var planner = PlannerSnapshot()
        try planner.add(task: task)
        let today = Date()
        try planner.record(session: StudySession(taskID: task.id, startedAt: today, durationMinutes: 25))
        try planner.record(session: StudySession(taskID: task.id, startedAt: today.addingTimeInterval(-600), durationMinutes: 30))
        XCTAssertEqual(planner.minutesStudied(on: today), 55)
        XCTAssertThrowsError(try StudySession(durationMinutes: 721))
    }

    func testSnapshotRoundTripsAtomicallyThroughStore() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: directory) }
        let store = PlannerStore(fileURL: directory.appendingPathComponent("planner.json"))
        var planner = PlannerSnapshot()
        try planner.add(task: StudyTask(title: "Read chapter", subject: "Science"))
        try store.save(planner)
        XCTAssertEqual(try store.load(), planner)
    }
}
