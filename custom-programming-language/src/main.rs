use std::env;
use std::fs::{self, File};
use std::io::Read;
use std::path::Path;
use tinylang::run;

fn main() {
    let mut args = env::args_os();
    let executable = args.next().unwrap_or_default();
    let Some(path) = args.next() else {
        eprintln!("Usage: {} SOURCE.tl", Path::new(&executable).display());
        std::process::exit(2);
    };
    if args.next().is_some() {
        eprintln!("Usage: {} SOURCE.tl", Path::new(&executable).display());
        std::process::exit(2);
    }
    let path = Path::new(&path);
    match fs::symlink_metadata(path) {
        Ok(metadata) if metadata.file_type().is_file() && metadata.len() <= 1_048_576 => {}
        _ => {
            eprintln!("tinylang: source must be a regular file no larger than 1 MiB");
            std::process::exit(1);
        }
    }
    let file = match File::open(path) {
        Ok(file) => file,
        Err(error) => {
            eprintln!("tinylang: cannot read UTF-8 source: {error}");
            std::process::exit(1);
        }
    };
    match file.metadata() {
        Ok(metadata) if metadata.is_file() && metadata.len() <= 1_048_576 => {}
        _ => {
            eprintln!("tinylang: source must be a regular file no larger than 1 MiB");
            std::process::exit(1);
        }
    }
    let mut bytes = Vec::new();
    if let Err(error) = file.take(1_048_577).read_to_end(&mut bytes) {
        eprintln!("tinylang: cannot read source: {error}");
        std::process::exit(1);
    }
    if bytes.len() > 1_048_576 {
        eprintln!("tinylang: source exceeds 1 MiB");
        std::process::exit(1);
    }
    let source = match String::from_utf8(bytes) {
        Ok(source) => source,
        Err(error) => {
            eprintln!("tinylang: cannot read UTF-8 source: {error}");
            std::process::exit(1);
        }
    };
    match run(&source) {
        Ok(lines) => {
            for value in lines {
                println!("{value}");
            }
        }
        Err(error) => {
            eprintln!("tinylang: {error}");
            std::process::exit(1);
        }
    }
}
