import 'package:desktop_knowledge_manager/app.dart';
import 'package:desktop_knowledge_manager/data/note_store.dart';
import 'package:desktop_knowledge_manager/models/note.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeNoteStore implements NoteStore {
  final notes = <Note>[
    Note(id: 1, title: 'Release plan', body: 'Prepare the build checklist', updatedAt: DateTime.utc(2026)),
    Note(id: 2, title: 'Garden', body: 'Water plants', updatedAt: DateTime.utc(2026)),
  ];

  @override
  Future<List<Note>> list({String query = ''}) async => notes.where((note) => '${note.title} ${note.body}'.toLowerCase().contains(query.trim().toLowerCase())).toList();
  @override
  Future<int> save({int? id, required String title, required String body}) async => id ?? notes.length + 1;
  @override
  Future<void> delete(int id) async { notes.removeWhere((note) => note.id == id); }
  @override
  Future<List<Map<String, Object?>>> exportRows() async => [];
  @override
  Future<void> replaceAll(List<Map<String, Object?>> rows) async {}
  @override
  Future<void> close() async {}
}

void main() {
  testWidgets('renders notes and filters the list accessibly', (tester) async {
    final store = FakeNoteStore();
    await tester.pumpWidget(KnowledgeManagerApp(store: store));
    await tester.pump();
    expect(find.text('Release plan'), findsOneWidget);
    expect(find.text('Garden'), findsOneWidget);
    await tester.enterText(find.byType(TextField).first, 'build');
    await tester.pump();
    expect(find.text('Release plan'), findsOneWidget);
    expect(find.text('Garden'), findsNothing);
    await tester.pumpWidget(const SizedBox.shrink());
    await store.close();
  });
}
