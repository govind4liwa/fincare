# FinCare Technology and Port Matrix

FinCare is project code **5** in the shared local Docker allocation.

## Port allocation

| Service | Host port | Container port | Local URL / connection |
|---|---:|---:|---|
| PostgreSQL | 55432 | 5432 | `localhost:55432` |
| Redis | 56379 | 6379 | `localhost:56379` |
| Django API | 8005 | 8000 | `http://localhost:8005` |
| Next.js frontend | 3005 | 3000 | `http://localhost:3005` |

Container-to-container connections continue to use `db:5432`, `redis:6379`,
and `web:8000`. Host ports must not be used in Docker service URLs.

## Version baseline and targets

| Component | Current FinCare baseline | Portfolio draft target | Decision |
|---|---|---|---|
| Python | 3.12 | `14.2.x` | Target is ambiguous and must be corrected before upgrade |
| PostgreSQL | 16 | 18.4 | Separate database upgrade and restore rehearsal required |
| Django | 5.0.6 | 6.x | Separate framework upgrade after dependency compatibility review |
| Next.js | Not installed | 16+ | Use 16+ when the frontend is created |
| Redis server | 7 | 8.8+ | Separate cache/broker compatibility upgrade required |
| TypeScript | Not installed | 7.x | Validate availability and Next.js compatibility at frontend bootstrap |
| Tailwind CSS | Not installed | 4.x | Use 4.x at frontend bootstrap |

Major runtime upgrades are not part of a port-alignment change. They require CI,
dependency, migration, backup/restore, Celery, and deployment verification before
the baseline is changed.

## Environment variables

The default host mappings can be overridden in `.env`:

```dotenv
POSTGRES_HOST_PORT=55432
REDIS_HOST_PORT=56379
BACKEND_HOST_PORT=8005
FRONTEND_HOST_PORT=3005
CORS_ALLOWED_ORIGINS=http://localhost:3005
CSRF_TRUSTED_ORIGINS=http://localhost:3005
```

