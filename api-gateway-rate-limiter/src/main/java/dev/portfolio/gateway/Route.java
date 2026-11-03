package dev.portfolio.gateway;

import java.net.URI;

public record Route(String method, String prefix, URI upstream, int requestLimit, long windowMillis) {
    public Route {
        if (method == null || !(method.equals("*") || method.matches("[A-Z]{3,10}"))) {
            throw new IllegalArgumentException("method must be * or an uppercase HTTP method");
        }
        if (prefix == null || !prefix.startsWith("/") || prefix.contains("..") || prefix.contains("?")) {
            throw new IllegalArgumentException("route prefix must be an absolute path without traversal or query");
        }
        if (upstream == null || !("http".equals(upstream.getScheme()) || "https".equals(upstream.getScheme()))
                || upstream.getHost() == null || upstream.getUserInfo() != null || upstream.getQuery() != null
                || upstream.getFragment() != null) {
            throw new IllegalArgumentException("upstream must be an HTTP(S) URL without credentials or query");
        }
        if (requestLimit < 1 || windowMillis < 1) throw new IllegalArgumentException("quota values must be positive");
    }

    public boolean matches(String requestMethod, String path) {
        boolean methodMatches = method.equals("*") || method.equals(requestMethod);
        boolean pathMatches = path.equals(prefix) || path.startsWith(prefix.endsWith("/") ? prefix : prefix + "/");
        return methodMatches && pathMatches;
    }

    public String id() { return method + " " + prefix; }

    public URI target(String path, String rawQuery) {
        String suffix = path.substring(prefix.length());
        String base = upstream.toString();
        if (base.endsWith("/") && suffix.startsWith("/")) suffix = suffix.substring(1);
        String combined = base + suffix;
        return URI.create(rawQuery == null ? combined : combined + "?" + rawQuery);
    }
}
