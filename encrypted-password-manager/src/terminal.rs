use crate::crypto::wipe;
use std::io::{self, IsTerminal, Write};
use std::process::{Command, Stdio};

struct EchoGuard;

impl EchoGuard {
    fn disable() -> Result<Self, String> {
        if !io::stdin().is_terminal() {
            return Err("secret input requires an interactive terminal".into());
        }
        let status = Command::new("stty")
            .arg("-echo")
            .stdin(Stdio::inherit())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .map_err(|error| format!("disable terminal echo: {error}"))?;
        if !status.success() {
            return Err("could not disable terminal echo".into());
        }
        Ok(Self)
    }
}

impl Drop for EchoGuard {
    fn drop(&mut self) {
        let _ = Command::new("stty")
            .arg("echo")
            .stdin(Stdio::inherit())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
        println!();
    }
}

pub fn read_secret(prompt: &str, maximum_bytes: usize) -> Result<String, String> {
    print!("{prompt}");
    io::stdout()
        .flush()
        .map_err(|error| format!("write prompt: {error}"))?;
    let _echo = EchoGuard::disable()?;
    read_line(maximum_bytes)
}

pub fn read_text(prompt: &str, maximum_bytes: usize) -> Result<String, String> {
    print!("{prompt}");
    io::stdout()
        .flush()
        .map_err(|error| format!("write prompt: {error}"))?;
    read_line(maximum_bytes)
}

fn read_line(maximum_bytes: usize) -> Result<String, String> {
    let mut value = String::new();
    io::stdin()
        .read_line(&mut value)
        .map_err(|error| format!("read terminal input: {error}"))?;
    if value.ends_with('\n') {
        value.pop();
    }
    if value.ends_with('\r') {
        value.pop();
    }
    if value.len() > maximum_bytes {
        wipe(unsafe { value.as_bytes_mut() });
        return Err(format!("input exceeds {maximum_bytes} bytes"));
    }
    if value.contains('\0') {
        wipe(unsafe { value.as_bytes_mut() });
        return Err("input may not contain NUL".into());
    }
    Ok(value)
}
