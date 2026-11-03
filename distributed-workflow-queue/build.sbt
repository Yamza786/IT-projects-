ThisBuild / scalaVersion := "2.13.15"
ThisBuild / version := "0.1.0"
ThisBuild / organization := "portfolio"

libraryDependencies ++= Seq(
  "org.xerial" % "sqlite-jdbc" % "3.46.0.0",
  "org.scalatest" %% "scalatest" % "3.2.19" % Test
)

Test / parallelExecution := false
