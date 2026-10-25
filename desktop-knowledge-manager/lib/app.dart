import 'dart:io';

import 'package:flutter/material.dart';

import 'data/encrypted_backup.dart';
import 'data/note_store.dart';
import 'models/note.dart';

class KnowledgeManagerApp extends StatelessWidget {
  const KnowledgeManagerApp({super.key, required this.store});
  final NoteStore store;

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'Knowledge Manager',
        theme: ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff315b75)), useMaterial3: true),
        home: NotesPage(store: store),
      );
}

class NotesPage extends StatefulWidget {
  const NotesPage({super.key, required this.store});
  final NoteStore store;

  @override
  State<NotesPage> createState() => _NotesPageState();
}

class _NotesPageState extends State<NotesPage> {
  final _search = TextEditingController();
  final _backup = EncryptedBackup();
  List<Note> _notes = const [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
    _search.addListener(_load);
  }

  @override
  void dispose() {
    _search.removeListener(_load);
    _search.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final notes = await widget.store.list(query: _search.text);
    if (mounted) setState(() { _notes = notes; _loading = false; });
  }

  Future<void> _edit([Note? note]) async {
    final title = TextEditingController(text: note?.title ?? '');
    final body = TextEditingController(text: note?.body ?? '');
    final result = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(note == null ? 'New note' : 'Edit note'),
        content: SizedBox(width: 520, child: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: title, autofocus: true, maxLength: 160, decoration: const InputDecoration(labelText: 'Title', hintText: 'A clear, searchable title')),
          TextField(controller: body, maxLength: 20000, minLines: 6, maxLines: 12, decoration: const InputDecoration(labelText: 'Note', alignLabelWithHint: true)),
        ])),
        actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Save'))],
      ),
    );
    if (result == true) {
      try {
        await widget.store.save(id: note?.id, title: title.text, body: body.text);
        await _load();
      } on ArgumentError catch (error) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(error.message?.toString() ?? 'Invalid note')));
      }
    }
    title.dispose(); body.dispose();
  }

  Future<String?> _ask(String title, String label, {bool secret = false}) async {
    final controller = TextEditingController();
    final result = await showDialog<String>(context: context, builder: (context) => AlertDialog(
      title: Text(title), content: TextField(controller: controller, obscureText: secret, autofocus: true, decoration: InputDecoration(labelText: label)),
      actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.pop(context, controller.text), child: const Text('Continue'))],
    ));
    controller.dispose();
    return result;
  }

  Future<void> _exportBackup() async {
    final path = await _ask('Export encrypted backup', 'Destination file path');
    if (path == null || path.trim().isEmpty) return;
    final passphrase = await _ask('Protect backup', 'Passphrase (12+ characters)', secret: true);
    if (passphrase == null) return;
    try {
      final envelope = await _backup.encrypt(await widget.store.exportRows(), passphrase);
      await File(path).writeAsString(envelope, flush: true);
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Encrypted backup saved')));
    } on Object catch (error) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Backup failed: $error')));
    }
  }

  Future<void> _importBackup() async {
    final path = await _ask('Import encrypted backup', 'Backup file path');
    if (path == null || path.trim().isEmpty) return;
    final passphrase = await _ask('Unlock backup', 'Passphrase', secret: true);
    if (passphrase == null) return;
    final confirmed = await showDialog<bool>(context: context, builder: (context) => AlertDialog(
      title: const Text('Replace all notes?'),
      content: const Text('The unlocked backup will replace the notes currently stored on this device.'),
      actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Replace notes'))],
    ));
    if (confirmed != true) return;
    try {
      final file = File(path);
      if (await file.length() > 64 * 1024 * 1024) throw const FormatException('Backup is too large');
      final rows = await _backup.decrypt(await file.readAsString(), passphrase);
      await widget.store.replaceAll(rows);
      await _load();
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Backup imported')));
    } on Object catch (error) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Import failed: $error')));
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Knowledge Manager'), actions: [
          PopupMenuButton<String>(tooltip: 'Backup options', onSelected: (value) => value == 'export' ? _exportBackup() : _importBackup(), itemBuilder: (context) => const [
            PopupMenuItem(value: 'export', child: Text('Export encrypted backup')),
            PopupMenuItem(value: 'import', child: Text('Import encrypted backup (replace notes)')),
          ]),
        ]),
        body: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 920), child: Column(children: [
          Padding(padding: const EdgeInsets.all(16), child: TextField(controller: _search, decoration: const InputDecoration(prefixIcon: Icon(Icons.search), labelText: 'Search notes', border: OutlineInputBorder()), textInputAction: TextInputAction.search)),
          Expanded(child: _loading ? const Center(child: CircularProgressIndicator()) : _notes.isEmpty
              ? Center(child: Text(_search.text.isEmpty ? 'No notes yet. Create one to get started.' : 'No notes match this search.'))
              : ListView.builder(itemCount: _notes.length, itemBuilder: (context, index) {
                  final note = _notes[index];
                  return ListTile(
                    title: Text(note.title, maxLines: 1, overflow: TextOverflow.ellipsis),
                    subtitle: Text(note.body, maxLines: 2, overflow: TextOverflow.ellipsis),
                    isThreeLine: true,
                    onTap: () => _edit(note),
                    trailing: IconButton(tooltip: 'Delete ${note.title}', icon: const Icon(Icons.delete_outline), onPressed: () async {
                      await widget.store.delete(note.id); await _load();
                    }),
                  );
                })),
          Padding(padding: const EdgeInsets.fromLTRB(16, 4, 16, 16), child: Align(alignment: Alignment.centerLeft, child: Text('${_notes.length} notes', semanticsLabel: '${_notes.length} notes'))),
        ]))),
        floatingActionButton: FloatingActionButton.extended(onPressed: _edit, icon: const Icon(Icons.add), label: const Text('New note')),
      );
}
