mod crypto;
mod sqlite;
mod terminal;
mod vault;

use std::env;
use std::io::{self, Write};

fn main() {
    if let Err(error) = run() {
        eprintln!("vaultsmith: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let mut arguments: Vec<String> = env::args().skip(1).collect();
    let database_path = if arguments.first().map(String::as_str) == Some("--db") {
        if arguments.len() < 3 {
            return Err(
                "usage: vaultsmith [--db PATH] <init|add|list|show|remove|export|import> [ENTRY_ID|BACKUP_PATH]".into(),
            );
        }
        let path = arguments.remove(1);
        arguments.remove(0);
        path
    } else {
        vault::database_path_from_environment()
    };
    let Some(action) = arguments.first().map(String::as_str) else {
        return Err("usage: vaultsmith [--db PATH] <init|add|list|show|remove|export|import> [ENTRY_ID|BACKUP_PATH]".into());
    };
    let remaining = &arguments[1..];
    match action {
        "init" => {
            require_argument_count(remaining, 0, "init")?;
            let database = vault::open_database(&database_path)?;
            let mut first = terminal::read_secret("Choose vault passphrase (12+ bytes): ", 1024)?;
            if first.len() < 12 {
                crypto::wipe(unsafe { first.as_bytes_mut() });
                return Err("passphrase must contain at least 12 bytes".into());
            }
            let mut confirmation = match terminal::read_secret("Confirm passphrase: ", 1024) {
                Ok(value) => value,
                Err(error) => {
                    crypto::wipe(unsafe { first.as_bytes_mut() });
                    return Err(error);
                }
            };
            if first != confirmation {
                crypto::wipe(unsafe { first.as_bytes_mut() });
                crypto::wipe(unsafe { confirmation.as_bytes_mut() });
                return Err("passphrases do not match".into());
            }
            let result = vault::create_vault(&database, &first);
            crypto::wipe(unsafe { first.as_bytes_mut() });
            crypto::wipe(unsafe { confirmation.as_bytes_mut() });
            result?;
            println!(
                "{{\"event\":\"vault_initialized\",\"database\":{}}}",
                json_quote(&database_path)
            );
        }
        "add" => {
            require_argument_count(remaining, 0, "add")?;
            let database = vault::open_database(&database_path)?;
            let mut passphrase = terminal::read_secret("Vault passphrase: ", 1024)?;
            let key = vault::unlock(&database, &passphrase);
            crypto::wipe(unsafe { passphrase.as_bytes_mut() });
            let key = key?;
            let service = terminal::read_text("Service label: ", 120)?;
            let username = terminal::read_text("Username: ", 512)?;
            let mut password = terminal::read_secret("Password to store: ", 4096)?;
            let result = vault::add_entry(&database, &key, &service, &username, &password);
            crypto::wipe(unsafe { password.as_bytes_mut() });
            let id = result?;
            println!(
                "{{\"event\":\"entry_added\",\"id\":{},\"service\":{}}}",
                json_quote(&id),
                json_quote(&service)
            );
        }
        "list" => {
            require_argument_count(remaining, 0, "list")?;
            let database = vault::open_database(&database_path)?;
            let mut passphrase = terminal::read_secret("Vault passphrase: ", 1024)?;
            let unlocked = vault::unlock(&database, &passphrase);
            crypto::wipe(unsafe { passphrase.as_bytes_mut() });
            let _key = unlocked?;
            for entry in vault::list_entries(&database)? {
                println!(
                    "{{\"id\":{},\"service\":{},\"created_at\":{}}}",
                    json_quote(&entry.id),
                    json_quote(&entry.service),
                    json_quote(&entry.created_at)
                );
            }
        }
        "show" => {
            require_argument_count(remaining, 1, "show")?;
            let database = vault::open_database(&database_path)?;
            let mut passphrase = terminal::read_secret("Vault passphrase: ", 1024)?;
            let unlocked = vault::unlock(&database, &passphrase);
            crypto::wipe(unsafe { passphrase.as_bytes_mut() });
            let key = unlocked?;
            let mut entry = vault::read_entry(&database, &key, &remaining[0])?;
            let mut serialized = String::from("{\"service\":");
            append_json_string(&mut serialized, &entry.service);
            serialized.push_str(",\"username\":");
            append_json_string(&mut serialized, &entry.username);
            serialized.push_str(",\"password\":");
            append_json_string(&mut serialized, &entry.password);
            serialized.push('}');
            println!("{serialized}");
            crypto::wipe(unsafe { serialized.as_bytes_mut() });
            crypto::wipe(unsafe { entry.username.as_bytes_mut() });
            crypto::wipe(unsafe { entry.password.as_bytes_mut() });
        }
        "remove" => {
            require_argument_count(remaining, 1, "remove")?;
            let database = vault::open_database(&database_path)?;
            let mut passphrase = terminal::read_secret("Vault passphrase: ", 1024)?;
            let unlocked = vault::unlock(&database, &passphrase);
            crypto::wipe(unsafe { passphrase.as_bytes_mut() });
            let _key = unlocked?;
            if !vault::remove_entry(&database, &remaining[0])? {
                return Err("entry not found".into());
            }
            println!(
                "{{\"event\":\"entry_removed\",\"id\":{}}}",
                json_quote(&remaining[0])
            );
        }
        "export" => {
            require_argument_count(remaining, 1, "export")?;
            let database = vault::open_database(&database_path)?;
            let mut passphrase = terminal::read_secret("Vault passphrase: ", 1024)?;
            let unlocked = vault::unlock(&database, &passphrase);
            crypto::wipe(unsafe { passphrase.as_bytes_mut() });
            let key = unlocked?;
            let mut backup_passphrase =
                terminal::read_secret("New backup passphrase (12+ bytes): ", 1024)?;
            let result = vault::export_backup(&database, &key, &backup_passphrase, &remaining[0]);
            crypto::wipe(unsafe { backup_passphrase.as_bytes_mut() });
            let count = result?;
            println!(
                "{{\"event\":\"backup_exported\",\"entries\":{count},\"path\":{}}}",
                json_quote(&remaining[0])
            );
        }
        "import" => {
            require_argument_count(remaining, 1, "import")?;
            let database = vault::open_database(&database_path)?;
            let mut passphrase = terminal::read_secret("Destination vault passphrase: ", 1024)?;
            let unlocked = vault::unlock(&database, &passphrase);
            crypto::wipe(unsafe { passphrase.as_bytes_mut() });
            let key = unlocked?;
            let mut backup_passphrase = terminal::read_secret("Backup passphrase: ", 1024)?;
            let result = vault::import_backup(&database, &key, &backup_passphrase, &remaining[0]);
            crypto::wipe(unsafe { backup_passphrase.as_bytes_mut() });
            let count = result?;
            println!("{{\"event\":\"backup_imported\",\"entries\":{count}}}");
        }
        "help" | "--help" | "-h" => {
            if !remaining.is_empty() {
                return Err("help takes no arguments".into());
            }
            print_help();
        }
        _ => return Err(format!("unknown command {action:?}; use `vaultsmith help`")),
    }
    io::stdout()
        .flush()
        .map_err(|error| format!("flush output: {error}"))?;
    Ok(())
}

fn require_argument_count(
    arguments: &[String],
    expected: usize,
    action: &str,
) -> Result<(), String> {
    if arguments.len() == expected {
        Ok(())
    } else {
        Err(format!(
            "{action} expects {expected} additional argument(s)"
        ))
    }
}

fn print_help() {
    println!("Vaultsmith — local encrypted password vault\n\nUsage:\n  vaultsmith [--db PATH] init\n  vaultsmith [--db PATH] add\n  vaultsmith [--db PATH] list\n  vaultsmith [--db PATH] show ENTRY_ID\n  vaultsmith [--db PATH] remove ENTRY_ID\n  vaultsmith [--db PATH] export BACKUP_PATH\n  vaultsmith [--db PATH] import BACKUP_PATH\n\nBackups use a separate passphrase and AES-256-GCM. The default database is ./vaultsmith.sqlite or VAULTSMITH_DB. Passphrases and stored passwords are read without terminal echo and never accepted as command-line arguments.");
}

fn json_quote(value: &str) -> String {
    let mut output = String::with_capacity(value.len() + 2);
    append_json_string(&mut output, value);
    output
}

fn append_json_string(output: &mut String, value: &str) {
    output.push('"');
    for character in value.chars() {
        match character {
            '"' => output.push_str("\\\""),
            '\\' => output.push_str("\\\\"),
            '\n' => output.push_str("\\n"),
            '\r' => output.push_str("\\r"),
            '\t' => output.push_str("\\t"),
            character if character <= '\u{1f}' => {
                output.push_str(&format!("\\u{:04x}", character as u32))
            }
            character => output.push(character),
        }
    }
    output.push('"');
}
