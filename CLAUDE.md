# elflab-news — Контекст для Claude Code

## Что это

Curated DevOps/AI/Infra news feed для elflab.eu.
Коллекторы: GitHub Trending, Hacker News, RSS (CNCF, K8s, Lobste.rs, TheNewStack, InfoQ).
Статический HTML + RSS feed. K3s deployment через ConfigMap pattern.

## Правила

- При каждом коммите обновляй CHANGELOG.md — секцию [Unreleased] в том же коммите, что и код
- Не `git add -A` — добавляй файлы по имени
- Не `kubectl apply` — git push → ArgoCD
- Не Docker build — ConfigMap pattern (assemble.sh)
- Документация на русском

## Деплой

```bash
# Редактируй app/*.py → упакуй → запуш
./assemble.sh
git add k3s/base/elflab-news.yaml ...
git commit -m "feat: ..."
git push
# ArgoCD подхватит автоматически
```

## Структура

- `app/` — Python исходники (main.py, collectors.py, digest.py, db.py, index.jinja2)
- `k3s/base/` — Kustomize манифесты (elflab-news.yaml генерируется assemble.sh)
- `argocd/` — ArgoCD Application
- `assemble.sh` — упаковывает app/* в ConfigMap YAML
