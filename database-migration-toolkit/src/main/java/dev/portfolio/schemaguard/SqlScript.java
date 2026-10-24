package dev.portfolio.schemaguard;

import java.util.ArrayList;
import java.util.List;

final class SqlScript {
    private SqlScript() {}

    static List<String> statements(String script) {
        List<String> statements = new ArrayList<>();
        StringBuilder current = new StringBuilder();
        char quote = 0;
        boolean lineComment = false;
        boolean blockComment = false;

        for (int index = 0; index < script.length(); index++) {
            char character = script.charAt(index);
            char next = index + 1 < script.length() ? script.charAt(index + 1) : 0;
            if (lineComment) {
                current.append(character);
                if (character == '\n') lineComment = false;
            } else if (blockComment) {
                current.append(character);
                if (character == '*' && next == '/') {
                    current.append(next);
                    index++;
                    blockComment = false;
                }
            } else if (quote != 0) {
                current.append(character);
                if (character == quote) {
                    if (next == quote) {
                        current.append(next);
                        index++;
                    } else quote = 0;
                }
            } else if (character == '-' && next == '-') {
                current.append(character).append(next);
                index++;
                lineComment = true;
            } else if (character == '/' && next == '*') {
                current.append(character).append(next);
                index++;
                blockComment = true;
            } else if (character == '\'' || character == '"' || character == '`') {
                quote = character;
                current.append(character);
            } else if (character == ';') {
                addIfNotBlank(statements, current);
            } else {
                current.append(character);
            }
        }
        if (quote != 0 || blockComment) throw new IllegalArgumentException("Unterminated SQL quote or block comment");
        addIfNotBlank(statements, current);
        return List.copyOf(statements);
    }

    private static void addIfNotBlank(List<String> statements, StringBuilder current) {
        String statement = current.toString().trim();
        if (!statement.isEmpty() && !statement.matches("(?s)(--[^\\n]*\\s*)+")) statements.add(statement);
        current.setLength(0);
    }
}
