# TinyLang

TinyLang is a small statically checked integer language and interpreter written in Rust. Programs have typed immutable bindings, arithmetic with conventional precedence, parentheses, and integer output.

```text
let base: int = 6;
let total: int = base * (base + 1);
print(total);
```

## Run

```sh
cargo fmt --check
cargo test
cargo clippy --all-targets -- -D warnings
cargo run -- example.tl
```

The interpreter supports signed 64-bit integer literals, variables declared earlier in the program, unary minus, `+ - * /`, and `print(expression);`. It rejects duplicate or unknown names, unsupported types, malformed syntax, division by zero, and checked arithmetic overflow with line and column diagnostics. Input is capped at 1 MiB.

## Scope

This is a learning-language MVP: there are no functions, mutable variables, booleans, strings, control flow, or external I/O. The parser validates all declarations before evaluation; evaluation produces output only after parsing succeeds. It runs no native code and has no third-party dependencies.
