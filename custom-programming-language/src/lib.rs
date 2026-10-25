use std::collections::{HashMap, HashSet};
use std::fmt;

const MAX_SOURCE_BYTES: usize = 1_048_576;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct Position {
    line: usize,
    column: usize,
}

#[derive(Clone, Debug, PartialEq, Eq)]
enum Kind {
    Number(i64),
    Name(String),
    Let,
    Int,
    Print,
    Plus,
    Minus,
    Star,
    Slash,
    Equal,
    Colon,
    Semi,
    LParen,
    RParen,
    Eof,
}

#[derive(Clone, Debug)]
struct Token {
    kind: Kind,
    at: Position,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct LangError {
    pub line: usize,
    pub column: usize,
    pub message: String,
}

impl LangError {
    fn at(at: Position, message: impl Into<String>) -> Self {
        Self {
            line: at.line,
            column: at.column,
            message: message.into(),
        }
    }
}

impl fmt::Display for LangError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}:{}: {}", self.line, self.column, self.message)
    }
}

impl std::error::Error for LangError {}

fn lex(source: &str) -> Result<Vec<Token>, LangError> {
    let mut tokens = Vec::new();
    let mut chars = source.char_indices().peekable();
    let mut line = 1;
    let mut column = 1;
    while let Some((index, ch)) = chars.next() {
        let at = Position { line, column };
        if ch == '\n' {
            line += 1;
            column = 1;
            continue;
        }
        if ch.is_whitespace() {
            column += 1;
            continue;
        }
        if ch.is_ascii_digit() {
            let start = index;
            let mut end = index + ch.len_utf8();
            while let Some((next_index, next)) = chars.peek().copied() {
                if !next.is_ascii_digit() {
                    break;
                }
                chars.next();
                end = next_index + next.len_utf8();
                column += 1;
            }
            let value = source[start..end]
                .parse::<i64>()
                .map_err(|_| LangError::at(at, "integer literal exceeds signed 64-bit range"))?;
            tokens.push(Token {
                kind: Kind::Number(value),
                at,
            });
            column += 1;
            continue;
        }
        if ch.is_ascii_alphabetic() || ch == '_' {
            let start = index;
            let mut end = index + ch.len_utf8();
            while let Some((next_index, next)) = chars.peek().copied() {
                if !(next.is_ascii_alphanumeric() || next == '_') {
                    break;
                }
                chars.next();
                end = next_index + next.len_utf8();
                column += 1;
            }
            let word = &source[start..end];
            let kind = match word {
                "let" => Kind::Let,
                "int" => Kind::Int,
                "print" => Kind::Print,
                _ => Kind::Name(word.to_owned()),
            };
            tokens.push(Token { kind, at });
            column += 1;
            continue;
        }
        let kind = match ch {
            '+' => Kind::Plus,
            '-' => Kind::Minus,
            '*' => Kind::Star,
            '/' => Kind::Slash,
            '=' => Kind::Equal,
            ':' => Kind::Colon,
            ';' => Kind::Semi,
            '(' => Kind::LParen,
            ')' => Kind::RParen,
            _ => return Err(LangError::at(at, format!("unexpected character {ch:?}"))),
        };
        tokens.push(Token { kind, at });
        column += 1;
    }
    tokens.push(Token {
        kind: Kind::Eof,
        at: Position { line, column },
    });
    Ok(tokens)
}

#[derive(Clone, Debug)]
enum Expr {
    Number(i64),
    Variable(String, Position),
    UnaryMinus(Box<Expr>, Position),
    Binary(Box<Expr>, Op, Box<Expr>, Position),
}
#[derive(Clone, Copy, Debug)]
enum Op {
    Add,
    Sub,
    Mul,
    Div,
}
#[derive(Clone, Debug)]
enum Statement {
    Let(String, Expr),
    Print(Expr),
}

struct Parser {
    tokens: Vec<Token>,
    index: usize,
    declared: HashSet<String>,
}

impl Parser {
    fn current(&self) -> &Token {
        &self.tokens[self.index]
    }
    fn advance(&mut self) -> Token {
        let token = self.tokens[self.index].clone();
        if !matches!(token.kind, Kind::Eof) {
            self.index += 1;
        }
        token
    }
    fn consume(&mut self, expected: Kind, description: &str) -> Result<Token, LangError> {
        if std::mem::discriminant(&self.current().kind) == std::mem::discriminant(&expected) {
            Ok(self.advance())
        } else {
            Err(LangError::at(
                self.current().at,
                format!("expected {description}"),
            ))
        }
    }
    fn program(mut self) -> Result<Vec<Statement>, LangError> {
        let mut statements = Vec::new();
        while !matches!(self.current().kind, Kind::Eof) {
            statements.push(self.statement()?);
        }
        Ok(statements)
    }
    fn statement(&mut self) -> Result<Statement, LangError> {
        if matches!(self.current().kind, Kind::Let) {
            self.advance();
            let name_token = self.advance();
            let name = match name_token.kind {
                Kind::Name(name) => name,
                _ => return Err(LangError::at(name_token.at, "expected variable name")),
            };
            if self.declared.contains(&name) {
                return Err(LangError::at(
                    name_token.at,
                    format!("variable {name} is already declared"),
                ));
            }
            self.consume(Kind::Colon, "':' after variable name")?;
            self.consume(Kind::Int, "type 'int'")?;
            self.consume(Kind::Equal, "'='")?;
            let value = self.expression()?;
            self.consume(Kind::Semi, "';' after declaration")?;
            self.declared.insert(name.clone());
            Ok(Statement::Let(name, value))
        } else if matches!(self.current().kind, Kind::Print) {
            self.advance();
            self.consume(Kind::LParen, "'('")?;
            let value = self.expression()?;
            self.consume(Kind::RParen, "')'")?;
            self.consume(Kind::Semi, "';' after print")?;
            Ok(Statement::Print(value))
        } else {
            Err(LangError::at(
                self.current().at,
                "expected 'let' declaration or 'print' statement",
            ))
        }
    }
    fn expression(&mut self) -> Result<Expr, LangError> {
        self.additive()
    }
    fn additive(&mut self) -> Result<Expr, LangError> {
        let mut expression = self.multiplicative()?;
        loop {
            let op = match self.current().kind {
                Kind::Plus => Op::Add,
                Kind::Minus => Op::Sub,
                _ => break,
            };
            let at = self.advance().at;
            expression = Expr::Binary(
                Box::new(expression),
                op,
                Box::new(self.multiplicative()?),
                at,
            );
        }
        Ok(expression)
    }
    fn multiplicative(&mut self) -> Result<Expr, LangError> {
        let mut expression = self.unary()?;
        loop {
            let op = match self.current().kind {
                Kind::Star => Op::Mul,
                Kind::Slash => Op::Div,
                _ => break,
            };
            let at = self.advance().at;
            expression = Expr::Binary(Box::new(expression), op, Box::new(self.unary()?), at);
        }
        Ok(expression)
    }
    fn unary(&mut self) -> Result<Expr, LangError> {
        if matches!(self.current().kind, Kind::Minus) {
            let at = self.advance().at;
            Ok(Expr::UnaryMinus(Box::new(self.unary()?), at))
        } else {
            self.primary()
        }
    }
    fn primary(&mut self) -> Result<Expr, LangError> {
        let token = self.advance();
        match token.kind {
            Kind::Number(value) => Ok(Expr::Number(value)),
            Kind::Name(name) if self.declared.contains(&name) => Ok(Expr::Variable(name, token.at)),
            Kind::Name(name) => Err(LangError::at(
                token.at,
                format!("variable {name} is not declared"),
            )),
            Kind::LParen => {
                let expression = self.expression()?;
                self.consume(Kind::RParen, "')'")?;
                Ok(expression)
            }
            _ => Err(LangError::at(
                token.at,
                "expected integer, variable, or parenthesized expression",
            )),
        }
    }
}

fn evaluate(expression: &Expr, variables: &HashMap<String, i64>) -> Result<i64, LangError> {
    match expression {
        Expr::Number(value) => Ok(*value),
        Expr::Variable(name, at) => variables
            .get(name)
            .copied()
            .ok_or_else(|| LangError::at(*at, format!("variable {name} has no value"))),
        Expr::UnaryMinus(value, at) => evaluate(value, variables)?
            .checked_neg()
            .ok_or_else(|| LangError::at(*at, "integer overflow in negation")),
        Expr::Binary(left, operation, right, at) => {
            let left = evaluate(left, variables)?;
            let right = evaluate(right, variables)?;
            let result = match operation {
                Op::Add => left.checked_add(right),
                Op::Sub => left.checked_sub(right),
                Op::Mul => left.checked_mul(right),
                Op::Div if right == 0 => return Err(LangError::at(*at, "division by zero")),
                Op::Div => left.checked_div(right),
            };
            result.ok_or_else(|| LangError::at(*at, "integer overflow in arithmetic operation"))
        }
    }
}

pub fn run(source: &str) -> Result<Vec<i64>, LangError> {
    if source.len() > MAX_SOURCE_BYTES {
        return Err(LangError::at(
            Position { line: 1, column: 1 },
            "source exceeds 1 MiB",
        ));
    }
    let tokens = lex(source)?;
    let statements = (Parser {
        tokens,
        index: 0,
        declared: HashSet::new(),
    })
    .program()?;
    let mut variables = HashMap::new();
    let mut output = Vec::new();
    for statement in statements {
        match statement {
            Statement::Let(name, value) => {
                variables.insert(name, evaluate(&value, &variables)?);
            }
            Statement::Print(value) => output.push(evaluate(&value, &variables)?),
        }
    }
    Ok(output)
}

#[cfg(test)]
mod tests {
    use super::run;

    #[test]
    fn evaluates_precedence_variables_and_parentheses() {
        let result =
            run("let count: int = 3 + 4 * 2; print(count); print((count - 1) / 2);").unwrap();
        assert_eq!(result, vec![11, 5]);
    }

    #[test]
    fn reports_unknown_and_duplicate_names() {
        assert!(run("print(missing);")
            .unwrap_err()
            .message
            .contains("not declared"));
        assert!(run("let x: int = 1; let x: int = 2;")
            .unwrap_err()
            .message
            .contains("already declared"));
    }

    #[test]
    fn reports_source_locations_and_malformed_programs() {
        let error = run("let x: int = 1;\nprint(x + );").unwrap_err();
        assert_eq!(error.line, 2);
        assert!(error.column > 1);
        assert!(run("let x: bool = 1;").is_err());
    }

    #[test]
    fn checks_division_by_zero_overflow_and_literal_range() {
        assert!(run("print(9 / 0);")
            .unwrap_err()
            .message
            .contains("division by zero"));
        assert!(run("print(9223372036854775807 + 1);")
            .unwrap_err()
            .message
            .contains("overflow"));
        assert!(run("print(999999999999999999999999999999999999);")
            .unwrap_err()
            .message
            .contains("literal"));
    }
}
