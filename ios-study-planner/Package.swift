// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "StudyPlanner",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [.library(name: "StudyPlannerCore", targets: ["StudyPlannerCore"]), .executable(name: "StudyPlannerApp", targets: ["StudyPlannerApp"])],
    targets: [
        .target(name: "StudyPlannerCore"),
        .executableTarget(name: "StudyPlannerApp", dependencies: ["StudyPlannerCore"]),
        .testTarget(name: "StudyPlannerCoreTests", dependencies: ["StudyPlannerCore"])
    ]
)
