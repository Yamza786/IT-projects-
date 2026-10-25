import 'package:desktop_knowledge_manager/app.dart';
import 'package:desktop_knowledge_manager/data/note_store.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

void main() {
  setUpAll(sqfliteFfiInit);

  testWidgets('renders notes and filters the list accessibly', (tester) async {
    final store = await NoteStore.open(databaseFactoryFfi, inMemoryDatabasePath);
    await store.save(title: 'Release plan', body: 'Prepare the build checklist');
    await store.save(title: 'Garden', body: 'Water plants');
    await tester.pumpWidget(KnowledgeManagerApp(store: store));
    await tester.pumpAndSettle();
    expect(find.text('Release plan'), findsOneWidget);
    expect(find.text('Garden'), findsOneWidget);
    await tester.enterText(find.byType(TextField).first, 'build');
    await tester.pumpAndSettle();
    expect(find.text('Release plan'), findsOneWidget);
    expect(find.text('Garden'), findsNothing);
    await store.close();
  });
}
