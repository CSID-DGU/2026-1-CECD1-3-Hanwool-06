"""Local operator tools. Passwords are read from a terminal, never command arguments."""
import argparse
import getpass
import sqlite3
from pathlib import Path
from . import auth, config, db


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('backup').add_argument('destination', type=Path)
    commands.add_parser('reset-password').add_argument('email')
    args = parser.parse_args()
    if not config.APP_DB_PATH.is_file():
        parser.error('운영 DB가 없습니다. API를 먼저 실행하세요.')
    if args.command == 'backup':
        target = args.destination.expanduser().resolve()
        if target.exists():
            parser.error('기존 파일을 덮어쓸 수 없습니다. 다른 백업 파일명을 선택하세요.')
        target.parent.mkdir(parents=True, exist_ok=True)
        with db.connect() as source, sqlite3.connect(target) as destination:
            source.backup(destination)
        target.chmod(0o600)
        print(f'백업 완료: {target}')
        return
    with db.connect() as c:
        row = c.execute('SELECT id FROM users WHERE email=?', (args.email.strip().lower(),)).fetchone()
        if not row:
            parser.error('등록된 사용자가 없습니다.')
        password = getpass.getpass('새 비밀번호 (12~128자): ')
        if password != getpass.getpass('새 비밀번호 확인: '):
            parser.error('입력한 비밀번호가 다릅니다.')
        try:
            hashed = auth.hash_password(password)
        except ValueError as error:
            parser.error(str(error))
        c.execute('UPDATE users SET password_hash=?,must_change_password=1 WHERE id=?', (hashed, row['id']))
        c.execute('DELETE FROM sessions WHERE user_id=?', (row['id'],))
        db.audit(c, None, 'operator_password_reset', row['id'])
    print('비밀번호를 변경하고 기존 세션을 만료했습니다.')


if __name__ == '__main__':
    main()
