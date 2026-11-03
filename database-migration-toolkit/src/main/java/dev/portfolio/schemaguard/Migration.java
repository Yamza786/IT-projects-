package dev.portfolio.schemaguard;

record Migration(int version, String name, String upSql, String downSql, String checksum) {
    String displayName() {
        return "V%04d__%s".formatted(version, name);
    }
}
