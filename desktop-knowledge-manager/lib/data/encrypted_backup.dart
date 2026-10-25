import 'dart:convert';
import 'dart:math';

import 'package:cryptography/cryptography.dart';

class EncryptedBackup {
  static const _iterations = 210000;
  final Pbkdf2 _kdf = Pbkdf2(macAlgorithm: Hmac.sha256(), iterations: _iterations, bits: 256);
  final AesGcm _cipher = AesGcm.with256bits();

  Future<String> encrypt(List<Map<String, Object?>> notes, String passphrase) async {
    if (passphrase.length < 12) throw ArgumentError('Backup passphrase must contain at least 12 characters');
    if (notes.length > 10000) throw ArgumentError('Backup contains too many notes');
    final random = Random.secure();
    final salt = List<int>.generate(16, (_) => random.nextInt(256), growable: false);
    final key = await _kdf.deriveKey(secretKey: SecretKey(utf8.encode(passphrase)), nonce: salt);
    final plaintext = utf8.encode(jsonEncode({'version': 1, 'notes': notes}));
    final box = await _cipher.encrypt(plaintext, secretKey: key, nonce: _cipher.newNonce(), aad: utf8.encode('portfolio-notes-v1'));
    return jsonEncode({
      'format': 'portfolio-notes-encrypted',
      'version': 1,
      'salt': base64Encode(salt),
      'nonce': base64Encode(box.nonce),
      'ciphertext': base64Encode(box.cipherText),
      'mac': base64Encode(box.mac.bytes),
    });
  }

  Future<List<Map<String, Object?>>> decrypt(String envelope, String passphrase) async {
    if (passphrase.length < 12 || envelope.length > 64 * 1024 * 1024) throw const FormatException('Invalid backup or passphrase');
    try {
      final outer = jsonDecode(envelope) as Map<String, dynamic>;
      if (outer['format'] != 'portfolio-notes-encrypted' || outer['version'] != 1) throw const FormatException('Unsupported backup format');
      final salt = base64Decode(outer['salt'] as String);
      final nonce = base64Decode(outer['nonce'] as String);
      final ciphertext = base64Decode(outer['ciphertext'] as String);
      final mac = Mac(base64Decode(outer['mac'] as String));
      if (salt.length != 16 || nonce.length != 12 || ciphertext.length > 48 * 1024 * 1024 || mac.bytes.length != 16) {
        throw const FormatException('Invalid backup fields');
      }
      final key = await _kdf.deriveKey(secretKey: SecretKey(utf8.encode(passphrase)), nonce: salt);
      final plaintext = await _cipher.decrypt(SecretBox(ciphertext, nonce: nonce, mac: mac), secretKey: key, aad: utf8.encode('portfolio-notes-v1'));
      final payload = jsonDecode(utf8.decode(plaintext)) as Map<String, dynamic>;
      if (payload['version'] != 1 || payload['notes'] is! List) throw const FormatException('Invalid backup payload');
      return (payload['notes'] as List).map((item) => Map<String, Object?>.from(item as Map)).toList(growable: false);
    } on Object catch (error) {
      throw FormatException('Backup authentication or parsing failed: $error');
    }
  }
}
