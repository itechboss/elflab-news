#!/bin/bash
# assemble.sh — собирает elflab-news.yaml из app/*.py + шаблона
# Запускать из корня репозитория elflab-news/
#
# Результат: k3s/base/elflab-news.yaml (ConfigMap + Deployment + Service + Ingress)

set -euo pipefail

OUTFILE="k3s/base/elflab-news.yaml"
SRCDIR="app"

for f in main.py collectors.py digest.py db.py index.jinja2; do
    if [ ! -f "$SRCDIR/$f" ]; then
        echo "❌ $SRCDIR/$f не найден!"
        exit 1
    fi
done

indent_file() {
    sed 's/^/    /' "$1"
}

echo "📦 Собираю $OUTFILE..."

cat > "$OUTFILE" << 'HEADER'
---
# ============================================================
# elflab-news — DevOps & AI Radar
# Сгенерировано assemble.sh — НЕ РЕДАКТИРОВАТЬ ВРУЧНУЮ
# Редактируй файлы в app/ и запускай ./assemble.sh
# ============================================================
apiVersion: v1
kind: ConfigMap
metadata:
  name: elflab-news-code
  namespace: elflab-news
data:
HEADER

for f in main.py collectors.py digest.py db.py index.jinja2; do
    echo "  $f: |" >> "$OUTFILE"
    indent_file "$SRCDIR/$f" >> "$OUTFILE"
    echo "" >> "$OUTFILE"
done

CODE_HASH=$(cat "$SRCDIR"/main.py "$SRCDIR"/collectors.py "$SRCDIR"/digest.py "$SRCDIR"/db.py "$SRCDIR"/index.jinja2 | sha256sum | cut -c1-16)

cat >> "$OUTFILE" << DEPLOYMENT
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: elflab-news
  namespace: elflab-news
  labels:
    app: elflab-news
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: elflab-news
  template:
    metadata:
      labels:
        app: elflab-news
      annotations:
        checksum/code: "$CODE_HASH"
    spec:
      initContainers:
        - name: install-deps
          image: python:3.12-slim
          command:
            - pip
            - install
            - --target=/deps
            - --no-cache-dir
            - httpx==0.28.1
            - jinja2==3.1.6
            - aiohttp==3.11.18
            - apscheduler==3.10.4
            - feedparser==6.0.11
          volumeMounts:
            - name: deps
              mountPath: /deps
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 256Mi
      containers:
        - name: elflab-news
          image: python:3.12-slim
          command: ["python", "/app/main.py"]
          env:
            - name: PYTHONPATH
              value: "/deps:/app"
            - name: DATA_DIR
              value: "/data"
            - name: APP_DIR
              value: "/app"
            - name: PORT
              value: "8080"
            - name: PYTHONUNBUFFERED
              value: "1"
            - name: GITHUB_TOKEN
              valueFrom:
                secretKeyRef:
                  name: elflab-news-secrets
                  key: GITHUB_TOKEN
                  optional: true
          volumeMounts:
            - name: app-code
              mountPath: /app
            - name: deps
              mountPath: /deps
            - name: data
              mountPath: /data
          ports:
            - containerPort: 8080
              protocol: TCP
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 200m
              memory: 256Mi
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 60
          readinessProbe:
            httpGet:
              path: /healthz
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 15
      restartPolicy: Always
      volumes:
        - name: app-code
          configMap:
            name: elflab-news-code
        - name: deps
          emptyDir: {}
        - name: data
          persistentVolumeClaim:
            claimName: elflab-news-data
DEPLOYMENT

cat >> "$OUTFILE" << 'SERVICE'
---
apiVersion: v1
kind: Service
metadata:
  name: elflab-news
  namespace: elflab-news
spec:
  selector:
    app: elflab-news
  ports:
    - port: 8080
      targetPort: 8080
      protocol: TCP
SERVICE

cat >> "$OUTFILE" << 'INGRESS'
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: elflab-news
  namespace: elflab-news
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - elflab.eu
      secretName: elflab-news-tls
  rules:
    - host: elflab.eu
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: elflab-news
                port:
                  number: 8080
INGRESS

SIZE=$(wc -c < "$OUTFILE")
echo "✅ Готово: $OUTFILE ($SIZE bytes)"
echo ""
echo "Следующие шаги:"
echo "  1. Создай секрет (один раз):"
echo "     kubectl create ns elflab-news"
echo "     kubectl -n elflab-news create secret generic elflab-news-secrets --from-literal=GITHUB_TOKEN=ghp_xxx"
echo "  2. git add k3s/base/elflab-news.yaml && git commit -m 'feat: elflab-news' && git push"
echo "  3. ArgoCD подхватит автоматически"
