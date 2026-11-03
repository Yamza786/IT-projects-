class Note {
  const Note({required this.id, required this.title, required this.body, required this.updatedAt});

  final int id;
  final String title;
  final String body;
  final DateTime updatedAt;

  Map<String, Object?> toMap() => {
        'id': id,
        'title': title,
        'body': body,
        'updated_at': updatedAt.toUtc().millisecondsSinceEpoch,
      };

  factory Note.fromMap(Map<String, Object?> map) => Note(
        id: map['id']! as int,
        title: map['title']! as String,
        body: map['body']! as String,
        updatedAt: DateTime.fromMillisecondsSinceEpoch(map['updated_at']! as int, isUtc: true),
      );
}
