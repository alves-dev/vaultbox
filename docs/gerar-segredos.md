# Gerar segredos para produção

Este tutorial mostra como gerar os valores usados no `.env.vaultbox`. Execute
os comandos em uma máquina confiável e não versione o arquivo de ambiente.

## Chave age

Instale o `age` e gere uma identidade:

```bash
age-keygen -o age.key
chmod 600 age.key
```

Obtenha a chave privada e o recipient público:

```bash
grep '^AGE-SECRET-KEY-' age.key
grep '^# public key:' age.key | awk '{print $4}'
```

Preencha o `.env.vaultbox` com os valores retornados:

```dotenv
VAULTBOX_AGE_KEY=AGE-SECRET-KEY-...
VAULTBOX_AGE_RECIPIENT=age1...
```

`VAULTBOX_AGE_KEY` é a chave privada. Faça backup seguro de `age.key`: sem
ela, os arquivos já criptografados não poderão ser descriptografados.

## Segredo da sessão

Gere um valor aleatório de 32 bytes em hexadecimal:

```bash
openssl rand -hex 32
```

Use o resultado em:

```dotenv
VAULTBOX_SESSION_SECRET=...
```

## API key

Gere um token aleatório:

```bash
openssl rand -hex 32
```

Configure-o como uma lista JSON:

```dotenv
VAULTBOX_API_KEYS=["token-gerado-aqui"]
```

É possível armazenar somente o hash no servidor. Gere o token e seu hash:

```bash
TOKEN="$(openssl rand -hex 32)"
printf 'Token: %s\n' "$TOKEN"
printf 'Hash: sha256:%s\n' "$(printf %s "$TOKEN" | sha256sum | awk '{print $1}')"
```

Nesse caso, coloque apenas o hash no `.env.vaultbox`:

```dotenv
VAULTBOX_API_KEYS=["sha256:..."]
```

O cliente deve enviar o token original no header `X-API-Key`; o valor com
`sha256:` é apenas a representação armazenada no servidor.

## Permissões e validação

Proteja o arquivo de ambiente e inicie o serviço:

```bash
chmod 600 .env.vaultbox age.key
docker compose up --build -d
docker compose logs --tail=100 vaultbox
```

Não publique `age.key`, `.env.vaultbox`, tokens ou segredos em Git, logs,
issues ou mensagens. Em produção, mantenha `VAULTBOX_COOKIE_SECURE=true` e
exponha a aplicação somente via HTTPS.
