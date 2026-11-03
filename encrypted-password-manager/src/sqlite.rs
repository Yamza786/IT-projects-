use std::ffi::{c_char, c_int, c_void, CStr, CString};
use std::ptr;
use std::slice;

const SQLITE_OK: c_int = 0;
const SQLITE_ROW: c_int = 100;
const SQLITE_DONE: c_int = 101;
const SQLITE_OPEN_READWRITE: c_int = 0x0000_0002;
const SQLITE_OPEN_CREATE: c_int = 0x0000_0004;
const SQLITE_OPEN_FULLMUTEX: c_int = 0x0001_0000;
const SQLITE_OPEN_NOFOLLOW: c_int = 0x0100_0000;

#[repr(C)]
struct SqliteHandle {
    _private: [u8; 0],
}
#[repr(C)]
struct StatementHandle {
    _private: [u8; 0],
}

type Destructor = Option<unsafe extern "C" fn(*mut c_void)>;

#[link(name = "sqlite3")]
unsafe extern "C" {
    fn sqlite3_open_v2(
        filename: *const c_char,
        database: *mut *mut SqliteHandle,
        flags: c_int,
        vfs: *const c_char,
    ) -> c_int;
    fn sqlite3_close_v2(database: *mut SqliteHandle) -> c_int;
    fn sqlite3_errmsg(database: *mut SqliteHandle) -> *const c_char;
    fn sqlite3_exec(
        database: *mut SqliteHandle,
        sql: *const c_char,
        callback: *mut c_void,
        argument: *mut c_void,
        error_message: *mut *mut c_char,
    ) -> c_int;
    fn sqlite3_free(pointer: *mut c_void);
    fn sqlite3_prepare_v2(
        database: *mut SqliteHandle,
        sql: *const c_char,
        length: c_int,
        statement: *mut *mut StatementHandle,
        tail: *mut *const c_char,
    ) -> c_int;
    fn sqlite3_finalize(statement: *mut StatementHandle) -> c_int;
    fn sqlite3_step(statement: *mut StatementHandle) -> c_int;
    fn sqlite3_bind_text(
        statement: *mut StatementHandle,
        index: c_int,
        value: *const c_char,
        length: c_int,
        destructor: Destructor,
    ) -> c_int;
    fn sqlite3_bind_blob(
        statement: *mut StatementHandle,
        index: c_int,
        value: *const c_void,
        length: c_int,
        destructor: Destructor,
    ) -> c_int;
    fn sqlite3_column_text(statement: *mut StatementHandle, column: c_int) -> *const u8;
    fn sqlite3_column_blob(statement: *mut StatementHandle, column: c_int) -> *const c_void;
    fn sqlite3_column_bytes(statement: *mut StatementHandle, column: c_int) -> c_int;
    fn sqlite3_column_int64(statement: *mut StatementHandle, column: c_int) -> i64;
    fn sqlite3_busy_timeout(database: *mut SqliteHandle, milliseconds: c_int) -> c_int;
    fn sqlite3_changes(database: *mut SqliteHandle) -> c_int;
}

pub struct Connection {
    handle: *mut SqliteHandle,
}

impl Connection {
    pub fn open(path: &str) -> Result<Self, String> {
        let filename = CString::new(path).map_err(|_| "database path contains a NUL byte")?;
        let mut handle = ptr::null_mut();
        let flags = SQLITE_OPEN_READWRITE
            | SQLITE_OPEN_CREATE
            | SQLITE_OPEN_FULLMUTEX
            | SQLITE_OPEN_NOFOLLOW;
        let result = unsafe { sqlite3_open_v2(filename.as_ptr(), &mut handle, flags, ptr::null()) };
        if result != SQLITE_OK {
            let message = if handle.is_null() {
                format!("SQLite open failed ({result})")
            } else {
                error_text(handle)
            };
            if !handle.is_null() {
                unsafe { sqlite3_close_v2(handle) };
            }
            return Err(message);
        }
        if unsafe { sqlite3_busy_timeout(handle, 5_000) } != SQLITE_OK {
            let message = error_text(handle);
            unsafe { sqlite3_close_v2(handle) };
            return Err(message);
        }
        let connection = Self { handle };
        connection.execute("PRAGMA foreign_keys=ON; PRAGMA secure_delete=ON; PRAGMA journal_mode=DELETE; PRAGMA synchronous=FULL; PRAGMA trusted_schema=OFF; PRAGMA temp_store=MEMORY;")?;
        Ok(connection)
    }

    pub fn execute(&self, sql: &str) -> Result<(), String> {
        let sql = CString::new(sql).map_err(|_| "SQL contains a NUL byte")?;
        let mut error = ptr::null_mut();
        let result = unsafe {
            sqlite3_exec(
                self.handle,
                sql.as_ptr(),
                ptr::null_mut(),
                ptr::null_mut(),
                &mut error,
            )
        };
        if result == SQLITE_OK {
            return Ok(());
        }
        let message = if error.is_null() {
            error_text(self.handle)
        } else {
            let text = unsafe { CStr::from_ptr(error) }
                .to_string_lossy()
                .into_owned();
            unsafe { sqlite3_free(error.cast()) };
            text
        };
        Err(message)
    }

    pub fn prepare(&self, sql: &str) -> Result<Statement<'_>, String> {
        let sql = CString::new(sql).map_err(|_| "SQL contains a NUL byte")?;
        let mut statement = ptr::null_mut();
        let result = unsafe {
            sqlite3_prepare_v2(
                self.handle,
                sql.as_ptr(),
                -1,
                &mut statement,
                ptr::null_mut(),
            )
        };
        if result != SQLITE_OK {
            return Err(error_text(self.handle));
        }
        if statement.is_null() {
            return Err("SQLite returned an empty statement".into());
        }
        Ok(Statement {
            connection: self,
            handle: statement,
        })
    }

    pub fn user_version(&self) -> Result<i64, String> {
        let mut query = self.prepare("PRAGMA user_version")?;
        if !query.step()? {
            return Err("SQLite did not return user_version".into());
        }
        Ok(query.integer(0))
    }

    pub fn changes(&self) -> i32 {
        unsafe { sqlite3_changes(self.handle) }
    }
}

impl Drop for Connection {
    fn drop(&mut self) {
        unsafe { sqlite3_close_v2(self.handle) };
    }
}

pub struct Statement<'connection> {
    connection: &'connection Connection,
    handle: *mut StatementHandle,
}

impl Statement<'_> {
    pub fn bind_text(&mut self, index: c_int, value: &str) -> Result<(), String> {
        let length =
            c_int::try_from(value.len()).map_err(|_| "text value is too large for SQLite")?;
        let transient =
            unsafe { std::mem::transmute::<isize, unsafe extern "C" fn(*mut c_void)>(-1) };
        let result = unsafe {
            sqlite3_bind_text(
                self.handle,
                index,
                value.as_ptr().cast(),
                length,
                Some(transient),
            )
        };
        self.check(result)
    }

    pub fn bind_blob(&mut self, index: c_int, value: &[u8]) -> Result<(), String> {
        let length =
            c_int::try_from(value.len()).map_err(|_| "binary value is too large for SQLite")?;
        let transient =
            unsafe { std::mem::transmute::<isize, unsafe extern "C" fn(*mut c_void)>(-1) };
        let result = unsafe {
            sqlite3_bind_blob(
                self.handle,
                index,
                value.as_ptr().cast(),
                length,
                Some(transient),
            )
        };
        self.check(result)
    }

    pub fn step(&mut self) -> Result<bool, String> {
        match unsafe { sqlite3_step(self.handle) } {
            SQLITE_ROW => Ok(true),
            SQLITE_DONE => Ok(false),
            _ => Err(error_text(self.connection.handle)),
        }
    }

    pub fn text(&self, column: c_int) -> Result<String, String> {
        let pointer = unsafe { sqlite3_column_text(self.handle, column) };
        let length = unsafe { sqlite3_column_bytes(self.handle, column) };
        if pointer.is_null() || length < 0 {
            return Err("SQLite returned invalid text data".into());
        }
        let bytes = unsafe { slice::from_raw_parts(pointer, length as usize) };
        String::from_utf8(bytes.to_vec()).map_err(|_| "SQLite text is not valid UTF-8".into())
    }

    pub fn blob(&self, column: c_int) -> Result<Vec<u8>, String> {
        let pointer = unsafe { sqlite3_column_blob(self.handle, column) };
        let length = unsafe { sqlite3_column_bytes(self.handle, column) };
        if length < 0 || (pointer.is_null() && length > 0) {
            return Err("SQLite returned invalid binary data".into());
        }
        if length == 0 {
            return Ok(Vec::new());
        }
        Ok(unsafe { slice::from_raw_parts(pointer.cast(), length as usize) }.to_vec())
    }

    pub fn integer(&self, column: c_int) -> i64 {
        unsafe { sqlite3_column_int64(self.handle, column) }
    }

    fn check(&self, result: c_int) -> Result<(), String> {
        if result == SQLITE_OK {
            Ok(())
        } else {
            Err(error_text(self.connection.handle))
        }
    }
}

impl Drop for Statement<'_> {
    fn drop(&mut self) {
        unsafe { sqlite3_finalize(self.handle) };
    }
}

fn error_text(database: *mut SqliteHandle) -> String {
    let pointer = unsafe { sqlite3_errmsg(database) };
    if pointer.is_null() {
        "unknown SQLite error".into()
    } else {
        unsafe { CStr::from_ptr(pointer) }
            .to_string_lossy()
            .into_owned()
    }
}
