import SwiftUI
import StudyPlannerCore

@main
struct StudyPlannerApp: App {
    var body: some Scene {
        WindowGroup { PlannerView() }
    }
}

struct PlannerView: View {
    @State private var tasks: [StudyTask] = []
    @State private var title = ""
    @State private var errorMessage: String?

    private let store = PlannerStore(fileURL: FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("planner.json"))

    var body: some View {
        NavigationStack {
            List {
                Section("Add a study task") {
                    TextField("Task title", text: $title)
                        .accessibilityLabel("Study task title")
                    Button("Add task", systemImage: "plus") { addTask() }
                        .disabled(title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
                Section("Tasks") {
                    ForEach(tasks) { task in
                        Toggle(isOn: Binding(get: { task.isComplete }, set: { complete(task, $0) })) {
                            VStack(alignment: .leading) {
                                Text(task.title)
                                if !task.subject.isEmpty { Text(task.subject).font(.caption).foregroundStyle(.secondary) }
                            }
                        }
                        .accessibilityHint("Mark this study task complete")
                    }
                }
            }
            .navigationTitle("Study Planner")
            .alert("Could not save", isPresented: Binding(get: { errorMessage != nil }, set: { if !$0 { errorMessage = nil } })) {
                Button("OK", role: .cancel) { errorMessage = nil }
            } message: { Text(errorMessage ?? "Unknown error") }
            .task { load() }
        }
    }

    private func load() {
        do { tasks = try store.load().tasks }
        catch { errorMessage = error.localizedDescription }
    }

    private func addTask() {
        do {
            var snapshot = try store.load()
            try snapshot.add(task: StudyTask(title: title, subject: ""))
            try store.save(snapshot)
            tasks = snapshot.tasks
            title = ""
        } catch { errorMessage = error.localizedDescription }
    }

    private func complete(_ task: StudyTask, _ value: Bool) {
        do {
            var snapshot = try store.load()
            snapshot.completeTask(id: task.id, completed: value)
            try store.save(snapshot)
            tasks = snapshot.tasks
        } catch { errorMessage = error.localizedDescription }
    }
}
