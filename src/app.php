<?php
declare(strict_types=1);

const APP_ROOT = __DIR__ . '/..';
const APP_PUBLIC = APP_ROOT . '/public';
const APP_VERSION = '1.0.0';
date_default_timezone_set('Africa/Nairobi');

function env_value(string $name, ?string $fallback = null): ?string {
    $value = getenv($name);
    return $value === false || $value === '' ? $fallback : $value;
}

function is_absolute_path(string $path): bool {
    return str_starts_with($path, '/') ||
           str_starts_with($path, '\\') ||
           (strlen($path) >= 3 &&
            ctype_alpha($path[0]) &&
            $path[1] === ':' &&
            ($path[2] === '\\' || $path[2] === '/'));
}

function app_path(string $path = '/'): string {
    $path = '/' . ltrim($path, '/');
    return $path === '//' ? '/' : $path;
}

function upload_directory(): string {
    $dir=env_value('EBUNGE_UPLOAD_DIR',APP_ROOT.'/var/uploads')??(APP_ROOT.'/var/uploads');
    return str_starts_with($dir,'/')?$dir:APP_ROOT.'/'.$dir;
}

function h(mixed $value): string {
    return htmlspecialchars((string)$value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function db(): PDO {
    static $pdo = null;
    if ($pdo instanceof PDO) return $pdo;
$file = env_value('EBUNGE_DB_PATH', APP_ROOT . '/var/ebunge.sqlite');
if (!is_absolute_path($file)) {
    $file = APP_ROOT . '/' . $file;
}

$dir = dirname($file);

if (!is_dir($dir)) {
    if (!mkdir($dir, 0775, true) && !is_dir($dir)) {
        throw new RuntimeException('Cannot create database directory: ' . $dir);
    }
}
    $pdo = new PDO('sqlite:' . $file, null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC, PDO::ATTR_EMULATE_PREPARES => false]);
    $pdo->exec('PRAGMA foreign_keys=ON');
    $pdo->exec('PRAGMA journal_mode=WAL');
    $pdo->exec('PRAGMA busy_timeout=5000');
    $pdo->exec("CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL COLLATE NOCASE UNIQUE,
      username TEXT NOT NULL COLLATE NOCASE UNIQUE, password_hash TEXT NOT NULL,
      role TEXT NOT NULL CHECK(role IN ('mca','hansard','speaker')), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )");
    $pdo->exec("CREATE TABLE IF NOT EXISTS password_resets (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,token_hash TEXT NOT NULL UNIQUE,expires_at INTEGER NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)");
    $pdo->exec("CREATE TABLE IF NOT EXISTS remember_tokens (selector TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,token_hash TEXT NOT NULL,expires_at INTEGER NOT NULL)");
    $pdo->exec("CREATE TABLE IF NOT EXISTS login_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT,login_key TEXT NOT NULL,attempted_at INTEGER NOT NULL)");
    $pdo->exec("CREATE TABLE IF NOT EXISTS motions (id INTEGER PRIMARY KEY AUTOINCREMENT,reference TEXT NOT NULL UNIQUE,title TEXT NOT NULL,category TEXT NOT NULL,body TEXT NOT NULL,sponsor_id INTEGER NOT NULL REFERENCES users(id),status TEXT NOT NULL,decision_note TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)");
    $pdo->exec("CREATE TABLE IF NOT EXISTS petitions (id INTEGER PRIMARY KEY AUTOINCREMENT,reference TEXT NOT NULL UNIQUE,title TEXT NOT NULL,body TEXT NOT NULL,submitter_name TEXT NOT NULL,submitter_email TEXT NOT NULL,source TEXT NOT NULL CHECK(source IN ('public','mca')),user_id INTEGER REFERENCES users(id),ward TEXT NOT NULL DEFAULT '',forwarded_by INTEGER REFERENCES users(id),status TEXT NOT NULL,public_status INTEGER NOT NULL DEFAULT 0,decision_note TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)");
    $pdo->exec("CREATE TABLE IF NOT EXISTS sittings (id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,sitting_type TEXT NOT NULL,sitting_date TEXT NOT NULL,start_time TEXT NOT NULL,venue TEXT NOT NULL,description TEXT NOT NULL,quorum_required INTEGER NOT NULL DEFAULT 0,status TEXT NOT NULL,decision_note TEXT NOT NULL DEFAULT '',attendance_status TEXT NOT NULL DEFAULT 'not_submitted',created_by INTEGER NOT NULL REFERENCES users(id),created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)");
    $pdo->exec("CREATE TABLE IF NOT EXISTS attendance (id INTEGER PRIMARY KEY AUTOINCREMENT,sitting_id INTEGER NOT NULL REFERENCES sittings(id) ON DELETE CASCADE,user_id INTEGER NOT NULL REFERENCES users(id),attendance_status TEXT NOT NULL CHECK(attendance_status IN ('attended','missed','excused')),note TEXT NOT NULL DEFAULT '',approved INTEGER NOT NULL DEFAULT 0,recorded_by INTEGER NOT NULL REFERENCES users(id),UNIQUE(sitting_id,user_id))");
    $pdo->exec("CREATE TABLE IF NOT EXISTS vote_subjects (id INTEGER PRIMARY KEY AUTOINCREMENT,sitting_id INTEGER REFERENCES sittings(id),title TEXT NOT NULL,details TEXT NOT NULL,opens_at TEXT NOT NULL,closes_at TEXT NOT NULL,status TEXT NOT NULL,decision_note TEXT NOT NULL DEFAULT '',created_by INTEGER NOT NULL REFERENCES users(id),created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)");
    $pdo->exec("CREATE TABLE IF NOT EXISTS votes (id INTEGER PRIMARY KEY AUTOINCREMENT,subject_id INTEGER NOT NULL REFERENCES vote_subjects(id) ON DELETE CASCADE,user_id INTEGER NOT NULL REFERENCES users(id),choice TEXT NOT NULL CHECK(choice IN ('yes','no','abstain')),cast_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,UNIQUE(subject_id,user_id))");
    $pdo->exec("CREATE TABLE IF NOT EXISTS committees (id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,description TEXT NOT NULL,chair_id INTEGER REFERENCES users(id),status TEXT NOT NULL,decision_note TEXT NOT NULL DEFAULT '',created_by INTEGER NOT NULL REFERENCES users(id),created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)");
    $pdo->exec("CREATE TABLE IF NOT EXISTS committee_members (committee_id INTEGER NOT NULL REFERENCES committees(id) ON DELETE CASCADE,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,member_role TEXT NOT NULL DEFAULT 'Member',PRIMARY KEY(committee_id,user_id))");
    $pdo->exec("CREATE TABLE IF NOT EXISTS committee_meetings (id INTEGER PRIMARY KEY AUTOINCREMENT,committee_id INTEGER NOT NULL REFERENCES committees(id) ON DELETE CASCADE,title TEXT NOT NULL,meeting_date TEXT NOT NULL,start_time TEXT NOT NULL,venue TEXT NOT NULL,agenda TEXT NOT NULL,status TEXT NOT NULL,created_by INTEGER NOT NULL REFERENCES users(id),created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)");
    $pdo->exec("CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,report_type TEXT NOT NULL,created_by INTEGER NOT NULL REFERENCES users(id),status TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)");
    $pdo->exec("CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY AUTOINCREMENT,motion_id INTEGER NOT NULL REFERENCES motions(id) ON DELETE CASCADE,original_name TEXT NOT NULL,stored_name TEXT NOT NULL,mime_type TEXT NOT NULL,uploaded_by INTEGER NOT NULL REFERENCES users(id),created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)");
    $pdo->exec("CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,action TEXT NOT NULL,record_type TEXT NOT NULL,record_id INTEGER,summary TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)");
    $pdo->exec("CREATE TABLE IF NOT EXISTS petition_motion_links (petition_id INTEGER PRIMARY KEY REFERENCES petitions(id) ON DELETE CASCADE,motion_id INTEGER NOT NULL UNIQUE REFERENCES motions(id) ON DELETE CASCADE,converted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)");
    $pdo->exec("CREATE TABLE IF NOT EXISTS site_branding (id INTEGER PRIMARY KEY CHECK(id=1),logo_data TEXT,logo_mime TEXT,motto TEXT NOT NULL DEFAULT '',updated_by INTEGER REFERENCES users(id),updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)");
    $ensureColumn = static function(string $table,string $column,string $definition) use ($pdo): void {
        $columns=$pdo->query('PRAGMA table_info('.$table.')')->fetchAll();
        foreach($columns as $item) if($item['name']===$column) return;
        $pdo->exec('ALTER TABLE '.$table.' ADD COLUMN '.$column.' '.$definition);
    };
    $ensureColumn('petitions','forwarded_by','INTEGER REFERENCES users(id)');
    foreach(['sittings','vote_subjects','committees'] as $table){
        $ensureColumn($table,'decision_note',"TEXT NOT NULL DEFAULT ''");
        $ensureColumn($table,'updated_at',"TEXT NOT NULL DEFAULT ''");
        $pdo->exec("UPDATE ".$table." SET updated_at=created_at WHERE updated_at=''");
    }
    $pdo->exec('CREATE INDEX IF NOT EXISTS idx_motion_status ON motions(status,created_at)');
    $pdo->exec('CREATE INDEX IF NOT EXISTS idx_petition_status ON petitions(status,created_at)');
    $pdo->exec('CREATE INDEX IF NOT EXISTS idx_sittings_date ON sittings(sitting_date,status)');
    $pdo->exec('CREATE INDEX IF NOT EXISTS idx_votes_subject ON votes(subject_id)');
    $pdo->exec('CREATE INDEX IF NOT EXISTS idx_speaker_tasks ON vote_subjects(status,updated_at)');
    return $pdo;
}

function site_branding(): array {
    $defaults=['logo_data'=>null,'logo_mime'=>null,'motto'=>'County Assembly','updated_at'=>''];
    $q=db()->query('SELECT logo_data,logo_mime,motto,updated_at FROM site_branding WHERE id=1');
    $row=$q->fetch();
    if(!$row) return $defaults;
    $row['motto']=trim((string)$row['motto'])!==''?$row['motto']:'County Assembly';
    return $row;
}

function role_name(string $role): string {
    return ['mca'=>'Member of County Assembly','hansard'=>'Hansard Office','speaker'=>'Office of the Speaker'][$role] ?? 'Unknown role';
}

function current_user(): ?array {
    if (!empty($_SESSION['user_id'])) {
        $q = db()->prepare('SELECT id,email,username,role,created_at FROM users WHERE id=?');
        $q->execute([(int)$_SESSION['user_id']]);
        $user = $q->fetch();
        if ($user) return $user;
        unset($_SESSION['user_id']);
    }
    $cookie = $_COOKIE['ebunge_remember'] ?? '';
    if (is_string($cookie) && preg_match('/^([a-f0-9]{16}):([a-f0-9]{64})$/', $cookie, $m)) {
        $q = db()->prepare('SELECT rt.user_id,rt.token_hash,rt.expires_at,u.id,u.email,u.username,u.role,u.created_at FROM remember_tokens rt JOIN users u ON u.id=rt.user_id WHERE rt.selector=?');
        $q->execute([$m[1]]); $row = $q->fetch();
        if ($row && (int)$row['expires_at'] > time() && hash_equals($row['token_hash'], hash('sha256',$m[2]))) {
            session_regenerate_id(true); $_SESSION['user_id']=(int)$row['id'];
            return ['id'=>$row['id'],'email'=>$row['email'],'username'=>$row['username'],'role'=>$row['role'],'created_at'=>$row['created_at']];
        }
    }
    return null;
}

function cookie_options(int $expires): array {
    $secure = env_value('EBUNGE_COOKIE_SECURE', '1') === '1';
    return ['expires'=>$expires,'path'=>'/','secure'=>$secure,'httponly'=>true,'samesite'=>$secure?'None':'Lax'];
}

function csrf_field(): string {
    if (empty($_SESSION['csrf'])) $_SESSION['csrf'] = bin2hex(random_bytes(32));
    return '<input type="hidden" name="csrf" value="'.h($_SESSION['csrf']).'">';
}

function verify_csrf(): void {
    $token = $_POST['csrf'] ?? '';
    if (!is_string($token) || empty($_SESSION['csrf']) || !hash_equals($_SESSION['csrf'], $token)) {
        http_response_code(419); exit('Your session expired. Please go back, reload and try again.');
    }
}

function redirect_to(string $path): never {
    header('Location: ' . app_path($path), true, 303); exit;
}

function flash(string $message, string $kind='success'): void { $_SESSION['flash']=['message'=>$message,'kind'=>$kind]; }
function take_flash(): ?array { $f=$_SESSION['flash']??null; unset($_SESSION['flash']); return $f; }
function require_login(): array { $u=current_user(); if (!$u) { flash('Sign in to continue.','info'); redirect_to('/signin'); } return $u; }
function require_role(array $user, array $roles): void { if (!in_array($user['role'],$roles,true)) { http_response_code(403); exit('Access denied. This action is not available to your role.'); } }
function audit(?int $userId, string $action, string $type, ?int $recordId, string $summary): void {
    $q=db()->prepare('INSERT INTO audit_logs(user_id,action,record_type,record_id,summary) VALUES(?,?,?,?,?)');
    $q->execute([$userId,$action,$type,$recordId,$summary]);
}
function reference_id(string $prefix): string { return $prefix.'-'.date('y').'-'.strtoupper(bin2hex(random_bytes(3))); }
function status_label(string $status): string { return ucwords(str_replace('_',' ',$status)); }
function safe_return_path(string $path, string $fallback='/dashboard'): string { return str_starts_with($path,'/') && !str_starts_with($path,'//') ? $path : $fallback; }
function set_notice(string $message,string $kind='success'): void { flash($message,$kind); }

session_name('ebunge_session');
$secureCookie = env_value('EBUNGE_COOKIE_SECURE','1') === '1';
session_set_cookie_params(['lifetime'=>0,'path'=>'/','secure'=>$secureCookie,'httponly'=>true,'samesite'=>$secureCookie?'None':'Lax']);
ini_set('session.use_strict_mode','1');
ini_set('session.cookie_httponly','1');
session_start();
