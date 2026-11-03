import Foundation

public enum PlannerError: Error, Equatable {
    case emptyTitle
    case invalidDuration
    case duplicateIdentifier
}

public struct StudyTask: Codable, Identifiable, Equatable, Sendable {
    public let id: UUID
    public var title: String
    public var subject: String
    public var dueAt: Date?
    public var isComplete: Bool

    public init(id: UUID = UUID(), title: String, subject: String, dueAt: Date? = nil, isComplete: Bool = false) throws {
        let cleanTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleanTitle.isEmpty, cleanTitle.count <= 160 else { throw PlannerError.emptyTitle }
        guard subject.count <= 80 else { throw PlannerError.emptyTitle }
        self.id = id
        self.title = cleanTitle
        self.subject = subject.trimmingCharacters(in: .whitespacesAndNewlines)
        self.dueAt = dueAt
        self.isComplete = isComplete
    }
}

public struct StudySession: Codable, Identifiable, Equatable, Sendable {
    public let id: UUID
    public let taskID: UUID?
    public let startedAt: Date
    public let durationMinutes: Int
    public let note: String

    public init(id: UUID = UUID(), taskID: UUID? = nil, startedAt: Date = .now, durationMinutes: Int, note: String = "") throws {
        guard (1...720).contains(durationMinutes) else { throw PlannerError.invalidDuration }
        guard note.count <= 500 else { throw PlannerError.invalidDuration }
        self.id = id
        self.taskID = taskID
        self.startedAt = startedAt
        self.durationMinutes = durationMinutes
        self.note = note
    }
}

public struct PlannerSnapshot: Codable, Equatable, Sendable {
    public private(set) var tasks: [StudyTask] = []
    public private(set) var sessions: [StudySession] = []

    public init() {}

    public mutating func add(task: StudyTask) throws {
        guard !tasks.contains(where: { $0.id == task.id }) else { throw PlannerError.duplicateIdentifier }
        tasks.append(task)
        tasks.sort { ($0.dueAt ?? .distantFuture, $0.title) < ($1.dueAt ?? .distantFuture, $1.title) }
    }

    public mutating func completeTask(id: UUID, completed: Bool = true) {
        guard let index = tasks.firstIndex(where: { $0.id == id }) else { return }
        tasks[index].isComplete = completed
    }

    public mutating func record(session: StudySession) throws {
        guard !sessions.contains(where: { $0.id == session.id }) else { throw PlannerError.duplicateIdentifier }
        if let taskID = session.taskID, !tasks.contains(where: { $0.id == taskID }) { return }
        sessions.append(session)
        sessions.sort { $0.startedAt > $1.startedAt }
    }

    public func minutesStudied(on day: Date, calendar: Calendar = .current) -> Int {
        sessions.filter { calendar.isDate($0.startedAt, inSameDayAs: day) }.reduce(0) { $0 + $1.durationMinutes }
    }
}

public struct PlannerStore: Sendable {
    public let fileURL: URL

    public init(fileURL: URL) { self.fileURL = fileURL }

    public func load() throws -> PlannerSnapshot {
        guard FileManager.default.fileExists(atPath: fileURL.path) else { return PlannerSnapshot() }
        let data = try Data(contentsOf: fileURL, options: [.mappedIfSafe])
        return try JSONDecoder().decode(PlannerSnapshot.self, from: data)
    }

    public func save(_ snapshot: PlannerSnapshot) throws {
        let directory = fileURL.deletingLastPathComponent()
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        let data = try encoder.encode(snapshot)
        try data.write(to: fileURL, options: [.atomic, .completeFileProtectionUnlessOpen])
    }
}
