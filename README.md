# Ritmo

Sua rotina em blocos: planeje o dia em blocos de tempo, veja as horas líquidas dedicadas a
cada área e receba lembretes antes de cada compromisso.

## Rodando

```bash
cp .env.example .env
make run
```

- Frontend: http://localhost:3000
- API: http://localhost:8000 (docs em `/docs`, saúde em `/saude` e `/saude/banco`)

Desenvolvimento sem Docker para API/front: `make db`, depois `make run-api` e `make run-front`.

## Verificação

```bash
make check   # ruff, mypy, pytest, eslint, nuxt typecheck
```

Detalhes de arquitetura e convenções em [CLAUDE.md](CLAUDE.md).
