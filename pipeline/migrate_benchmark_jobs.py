"""Copy local research history into configured PostgreSQL without overwrites."""
from utils import benchmark_jobs as jobs


def main():
    if not jobs.database_url():
        raise SystemExit('Set BENCHMARK_DATABASE_URL before migrating.')
    local = jobs.local_connection()
    try:
        rows = local.execute('SELECT * FROM jobs').fetchall()
    finally:
        local.close()
    copied = 0
    with jobs.connect() as target:
        for row in rows:
            status = 'Kesildi' if row['status'] in ('Sırada', 'Araştırılıyor') else row['status']
            copied += target.execute(
                'INSERT INTO jobs(id,brief,prompt,status,progress,result,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING',
                (row['id'], row['brief'], row['prompt'], status, row['progress'], row['result'], row['created_at'], row['updated_at']),
            ).rowcount
    print(f'{copied} research records copied. Existing records were preserved.')


if __name__ == '__main__':
    main()
