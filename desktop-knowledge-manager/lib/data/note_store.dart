import 'package:sqflite_common/sqlite_api.dart';

import '../models/note.dart';

class NoteStore {
  NoteStore(this._database);

  final Database _database;

  static Future<NoteStore> open(DatabaseFactory factory, String path) async {
    final database = await factory.openDatabase(
      path,
      options: OpenDatabaseOptions(
        version: 1,
        onCreate: (db, version) async {
          await db.execute('''CREATE TABLE notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL CHECK(length(trim(title)) BETWEEN 1 AND 160),
            body TEXT NOT NULL CHECK(length(body) <= 20000),
            updated_at INTEGER NOT NULL
          )''');
          await db.execute('CREATE INDEX notes_updated_idx ON notes(updated_at DESC)');
        },
      ),
    );
    return NoteStore(database);
  }

  Future<List<Note>> list({String query = ''}) async {
    final cleaned = query.trim();
    final rows = cleaned.isEmpty
        ? await _database.query('notes', orderBy: 'updated_at DESC, id DESC')
        : await _database.query(
            'notes',
            where: "(title LIKE ? ESCAPE '\\' OR body LIKE ? ESCAPE '\\')",
            whereArgs: ['%${_escapeLike(cleaned)}%', '%${_escapeLike(cleaned)}%'],
            orderBy: 'updated_at DESC, id DESC',
          );
    return rows.map(Note.fromMap).toList(growable: false);
  }

  static String _escapeLike(String value) => value.replaceAll('\\', '\\\\').replaceAll('%', '\\%').replaceAll('_', '\\_');

  Future<int> save({int? id, required String title, required String body}) async {
    final cleanTitle = title.trim();
    if (cleanTitle.isEmpty || cleanTitle.length > 160) throw ArgumentError('Title must contain 1–160 characters');
    if (body.length > 20000) throw ArgumentError('Note body must contain at most 20,000 characters');
    final values = {'title': cleanTitle, 'body': body, 'updated_at': DateTime.now().toUtc().millisecondsSinceEpoch};
    if (id == null) return _database.insert('notes', values);
    final changed = await _database.update('notes', values, where: 'id = ?', whereArgs: [id]);
    if (changed != 1) throw StateError('Note no longer exists');
    return id;
  }

  Future<void> delete(int id) async {
    final count = await _database.delete('notes', where: 'id = ?', whereArgs: [id]);
    if (count != 1) throw StateError('Note no longer exists');
  }

  Future<List<Map<String, Object?>>> exportRows() async => _database.query('notes', orderBy: 'id');

  Future<void> replaceAll(List<Map<String, Object?>> rows) async {
    if (rows.length > 10000) throw ArgumentError('Backup contains too many notes');
    await _database.transaction((transaction) async {
      await transaction.delete('notes');
      for (final row in rows) {
        final title = row['title'];
        final body = row['body'];
        final updatedAt = row['updated_at'];
        if (title is! String || title.trim().isEmpty || title.length > 160 || body is! String || body.length > 20000 || updatedAt is! int) {
          throw const FormatException('Backup contains an invalid note');
        }
        await transaction.insert('notes', {'title': title.trim(), 'body': body, 'updated_at': updatedAt});
      }
    });
  }

  Future<void> close() => _database.close();
}
