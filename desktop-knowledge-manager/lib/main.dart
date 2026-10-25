import 'dart:io';

import 'package:flutter/material.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import 'app.dart';
import 'data/note_store.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  sqfliteFfiInit();
  databaseFactory = databaseFactoryFfi;
  final base = Platform.isWindows
      ? (Platform.environment['APPDATA'] ?? Platform.environment['USERPROFILE'] ?? Directory.current.path)
      : (Platform.environment['XDG_DATA_HOME'] ?? '${Platform.environment['HOME'] ?? Directory.current.path}/.local/share');
  final directory = Directory('$base/PortfolioKnowledgeManager');
  await directory.create(recursive: true);
  final store = await NoteStore.open(databaseFactory, '${directory.path}/notes.sqlite');
  runApp(KnowledgeManagerApp(store: store));
}
