import 'package:desktop_knowledge_manager/data/encrypted_backup.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  const passphrase = 'correct horse battery staple';
  const notes = [{'title': 'Private note', 'body': 'meeting at 4', 'updated_at': 123}];
  final backup = EncryptedBackup();

  test('encrypts and restores data without exposing plaintext', () async {
    final envelope = await backup.encrypt(notes, passphrase);
    expect(envelope, isNot(contains('Private note')));
    expect(await backup.decrypt(envelope, passphrase), notes);
  });

  test('rejects wrong passphrases and tampered backups', () async {
    final envelope = await backup.encrypt(notes, passphrase);
    await expectLater(backup.decrypt(envelope, 'wrong passphrase value'), throwsFormatException);
    final decoded = envelope.replaceFirst(RegExp(r'"mac":"[^"]+"'), '"mac":"AAAA"');
    await expectLater(backup.decrypt(decoded, passphrase), throwsFormatException);
  });

  test('requires a long passphrase', () async {
    await expectLater(backup.encrypt(notes, 'short'), throwsArgumentError);
  });
}
