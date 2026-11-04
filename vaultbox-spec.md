# Vaultbox — Especificação para implementação

## Objetivo

Criar uma aplicação pequena, **stateless**, em Python, que use **SOPS + age** para criptografar e descriptografar arquivos dotenv. Substituir o Infisical no homelab (três servidores) sem exigir CLI SOPS/age/Python no host: o deploy existente do GitHub Actions acessa o servidor por SSH e executa `deploy.sh`, que chama a API via `curl` e gera o `.env` para `docker compose up -d`.

Não implementar um gerenciador de secrets completo: sem banco, Redis, contas multiusuário, auditoria avançada, rotação automática ou armazenamento de secrets pela aplicação.

## Arquitetura

- Serviço Docker com **FastAPI**, SOPS e age, empacotados na imagem.
- Duas réplicas independentes (por exemplo, `server1` e `server3`) atrás de proxy HTTPS redundante com health checks.
- Réplicas com **a mesma identidade privada age** e configuração de autenticação equivalente. Não dependem de estado compartilhado.
- Sem instalação de dependências no host além de Docker e `curl` (este já usado no script).
- Container iniciado/configurado manualmente nos servidores; segredos de bootstrap **não vão ao Git**.
- Interface web simples servida pela mesma aplicação; API REST também usada por deploys.

**Limites importantes:** replicação reduz indisponibilidade, mas não elimina dependências de rede/proxy nem substitui backup da chave age. O host/administrador Docker pode acessar variáveis, processos e arquivos do container; “chave dentro do container” não é isolamento criptográfico do host.

## API v1

### `POST /api/v1/encrypt`

- Header: `X-API-Key: <chave>` para clientes automatizados; a UI usa autenticação web própria.
- `Content-Type: text/plain; charset=utf-8`.
- Body: conteúdo completo de um `.env` em texto puro.
- Resposta `200`, `Content-Type: text/plain; charset=utf-8`: dotenv criptografado pelo SOPS com recipient age configurado, incluindo metadados SOPS.
- Não requer chave privada para criptografar.

### `POST /api/v1/decrypt`

- Mesmo contrato de autenticação e formato de entrada/saída.
- Body: conteúdo completo de um `.env.enc` gerado pelo SOPS.
- Resposta `200`: dotenv original em texto puro, sem envelope JSON.
- Usar chave privada age configurada na instância.

### `GET /health`

- Endpoint de liveness sem autenticação, com resposta mínima, sem dados sensíveis. Opcionalmente `/ready` valida a disponibilidade dos binários e configuração necessária sem divulgar chaves.

### Erros e proteção

- `400` para conteúdo vazio/inválido, `401` para credencial ausente/inválida, `413` para payload acima do limite, `415` para tipo de conteúdo não aceito, `422` para entrada incompatível/erro de criptografia e `503` para serviço não configurado.
- Nunca incluir texto enviado, chaves, conteúdo de saída nem stderr potencialmente sensível nas mensagens de erro ou logs.
- Limite de payload (sugestão: 1 MiB), timeout de subprocesso, limite de concorrência, sem shell interpolation (`subprocess.run([...], shell=False)`).
- Evitar arquivos temporários quando possível; avaliar suporte real do SOPS a stdin/stdout para dotenv e testar. Se forem necessários arquivos temporários, usar diretório tmpfs, permissões 0600, exclusão em `finally`, sem persistência.
- `Cache-Control: no-store`, `X-Content-Type-Options: nosniff` e redaction de logs. HTTPS obrigatório via proxy; nunca cachear endpoints.
- Não expor OpenAPI/docs publicamente em produção sem autenticação/restrição.

## Autenticação

### API keys

- Suportar **lista de API keys** independentes para scripts/servidores; todas as réplicas aceitam o mesmo conjunto.
- Configuração por variável de ambiente, sem banco. Preferir hashes verificáveis em vez de armazenar tokens em claro na configuração quando viável; comparar em tempo constante.
- Permitir rotação adicionando chave nova antes de remover a antiga. Retornar `401` genérico.
- Recomendar uma chave por servidor para revogação isolada.

### Interface web

- Usuário e senha fixos configurados por ambiente (não no Git), independentes das API keys.
- Usar autenticação segura (sessão assinada, cookie `HttpOnly`, `Secure`, `SameSite`, segredo de assinatura idêntico nas réplicas; proteção CSRF em operações de sessão). Não expor credenciais em JavaScript.
- Considerar rate limiting no proxy e restrição de acesso à rede interna/VPN.
- Não armazenar dotenv em `localStorage`, cookies, banco, logs ou analytics.

## UI mínima

Página única após login:

```text
┌──────────────────────────┬──────────────────────────┐
│ Plaintext (.env)         │ Encrypted (.env.enc)     │
│                          │                          │
│ [textarea editável]      │ [textarea editável]      │
│                          │                          │
└──────────────────────────┴──────────────────────────┘
       [Encrypt →]             [← Decrypt]
```

- Colar/editar conteúdo em qualquer painel.
- **Encrypt** envia o painel plaintext à API e coloca a resposta no painel encrypted.
- **Decrypt** envia o painel encrypted à API e coloca a resposta no painel plaintext.
- Operações **somente ao clicar**, não automaticamente a cada tecla.
- Botões copiar conteúdo e limpar campos; indicador de operação/erro sem revelar conteúdo.
- Layout responsivo; HTML/CSS/JS simples, sem framework pesado.
- Não salvar conteúdo no servidor ou armazenamento persistente do navegador. Desabilitar cache das páginas autenticadas.

## Configuração de runtime

Variáveis sugeridas:

```dotenv
VAULTBOX_AGE_KEY=<AGE-SECRET-KEY-...>
VAULTBOX_AGE_RECIPIENT=age1...
VAULTBOX_API_KEYS=<configuração de múltiplas chaves>
VAULTBOX_WEB_USERNAME=<usuário>
VAULTBOX_WEB_PASSWORD=<senha>
VAULTBOX_SESSION_SECRET=<segredo compartilhado entre réplicas>
```

- Definir e documentar o formato exato de `VAULTBOX_API_KEYS` (ex.: JSON ou lista delimitada), sem ambiguidades.
- Para SOPS, mapear a chave privada para `SOPS_AGE_KEY` no subprocesso ou mecanismo oficialmente suportado; evitar escrevê-la em disco.
- Validar configuração obrigatória na inicialização (fail fast), sem imprimir valores.
- Variáveis serão fornecidas manualmente ao iniciar os containers; documentar que `docker inspect` pode revelar env vars. Oferecer opcionalmente `env_file` local protegido ou Docker secrets como melhoria futura, sem exigir no MVP.
- Configuração idêntica nas duas réplicas. Chave privada age deve ter backup seguro fora do Git.

## Container

- Imagem Python slim com binários SOPS e age instalados e versões fixadas; verificar checksums no build.
- Build para `linux/amd64` e, se possível, `linux/arm64`.
- Executar como usuário não root; filesystem read-only e `/tmp` em tmpfs quando necessário; `no-new-privileges`, sem Docker socket e sem `privileged`.
- Health check e encerramento gracioso.
- Publicar imagem versionada no GHCR; evitar `latest` nos deploys de produção.
- Não incluir segredos no Dockerfile, build args, camadas ou imagem.

## Integração com deploy.sh

O repositório de stacks versiona somente `.env.enc`, nunca `.env` plaintext. No servidor, `VAULTBOX_API_KEY` é configurada localmente para o script, sem passar o segredo por argumentos de linha de comando ou por GitHub Actions se puder ser evitado.

Exemplo ilustrativo (executar a partir do diretório da stack):

```bash
#!/usr/bin/env bash
set -euo pipefail
umask 077

: "${VAULTBOX_API_KEY:?VAULTBOX_API_KEY não configurada}"

TMP_ENV="$(mktemp ./.env.XXXXXX)"
trap 'rm -f "$TMP_ENV"' EXIT

curl --fail --silent --show-error \
  --connect-timeout 5 --max-time 30 --retry 2 \
  -X POST 'https://vaultbox.internal.alves-dev.com/api/v1/decrypt' \
  -H "X-API-Key: ${VAULTBOX_API_KEY}" \
  -H 'Content-Type: text/plain' \
  --data-binary @.env.enc \
  --output "$TMP_ENV"

# Só substitui o .env após resposta HTTP de sucesso.
mv -f "$TMP_ENV" .env

docker compose up -d
```

- O proxy precisa de TLS confiável; não usar `curl -k`.
- O arquivo temporário deve ser criado no mesmo filesystem do destino para `mv` atômico.
- Em falha de decrypt, manter `.env` anterior intacto e não executar o compose.
- O `.env` fica no host após deploy para uso do Compose; restringir permissões e adicioná-lo ao `.gitignore`. Se a política exigir remoção, avaliar cuidadosamente o impacto em recriações do Compose.
- A disponibilidade da API não é necessária para containers já em execução; é necessária para deploys que precisam regenerar `.env`.

## Critérios de aceitação / testes

1. Encrypt/decrypt round-trip preserva o dotenv original, incluindo comentários, aspas, `=`, caracteres Unicode, linhas em branco e newline final, dentro dos limites suportados pelo SOPS.
2. Arquivo `.env.enc` criptografado na réplica A pode ser descriptografado na B e vice-versa.
3. API keys válidas funcionam; ausentes/revogadas falham sem revelar informação.
4. Login web funciona atrás do proxy com duas réplicas e sessões compatíveis.
5. UI permite colar, criptografar, descriptografar, copiar e limpar, sem persistência.
6. Falha HTTP, timeout ou erro de SOPS nunca sobrescreve `.env` existente no deploy.
7. Nenhum segredo aparece em logs, respostas de erro, imagem Docker ou repositório.
8. Testes automatizados para endpoints, autenticação, limites, falhas e fluxo real com binário SOPS.
9. Documentar instalação local, geração de chave age, backup/recuperação, execução manual em dois hosts, proxy e uso via cURL.

## Fora do escopo do MVP

- Banco de dados, gerenciamento de usuários, histórico/auditoria de secrets, rotação automática, sincronização de arquivos, armazenamento de `.env` no Vaultbox, integração direta com GitHub, UI de múltiplos projetos e CLI própria.

## Orientação ao agente

Implemente de forma incremental: (1) estrutura/configuração/container; (2) serviço SOPS+age; (3) endpoints e testes; (4) autenticação web; (5) UI; (6) documentação e exemplo de deploy. Confirme comandos e formatos do SOPS contra a versão instalada, em vez de assumir que stdin/stdout funcionam de determinada maneira. Priorize segurança, simplicidade e compatibilidade entre réplicas.
