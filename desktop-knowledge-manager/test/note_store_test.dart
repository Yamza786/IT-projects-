import 'package:desktop_knowledge_manager/data/note_store.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

void main() {
  late NoteStore store;
  setUpAll(sqfliteFfiInit);
  setUp(() async { store = await NoteStore.open(databaseFactoryFfi, inMemoryDatabasePath); });
  tearDown(() => store.close());

  test('saves, searches literal LIKE metacharacters, updates and deletes', () async {
    final id = await store.save(title: 'C++ 100% guide', body: 'Rate _limit behavior');
    await store.save(title: 'Other', body: 'Unrelated');
    expect((await store.list(query: '100%')).map((note) => note.id), [id]);
    expect((await store.list(query: '_limit')).map((note) => note.id), [id]);
    await store.save(id: id, title: 'Updated title', body: 'new text');
    expect((await store.list(query: '100%')), isEmpty);
    expect((await store.list(query: 'Updated')).single.body, 'new text');
    await store.delete(id);
    expect((await store.list()).map((note) => note.title), ['Other']);
  });

  test('validates lengths and rolls back invalid backup replacement', () async {
    await store.save(title: 'Keep this', body: 'existing');
    await expectLater(store.save(title: '  ', body: ''), throwsArgumentError);
    await expectLater(store.replaceAll([{'title': 'valid', 'body': '', 'updated_at': 0}, {'title': '', 'body': '', 'updated_at': 0}]), throwsFormatException);
    expect((await store.list()).single.title, 'Keep this');
  });
}
