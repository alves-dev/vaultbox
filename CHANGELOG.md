# Changelog

Todas as mudanças relevantes do Vaultbox serão documentadas neste arquivo.

## [0.2.0] - 2026-11-04

### Adicionado

- Suporte à publicação de imagens Docker para `linux/amd64` e `linux/arm64`.
- Validação do checksum do binário `age` para a arquitetura ARM64.
- Documentação para geração segura dos segredos de produção.

### Alterado

- Versão do pacote atualizada de `0.1.0` para `0.2.0`.
- Configuração do Compose ajustada para o fluxo de publicação multi-arquitetura.

### Verificação

- Suíte de testes validada com 3 testes aprovados.
