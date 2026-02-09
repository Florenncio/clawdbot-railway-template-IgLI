# Configuração do Google Calendar

Este guia explica como configurar a integração do Google Calendar com o OpenClaw.

## Pré-requisitos

- Conta Google (pessoal ou Workspace)
- Acesso ao Google Cloud Console
- Projeto Railway configurado

## 1. Criar Credenciais OAuth no Google Cloud Console

### Passo 1: Criar Projeto

1. Acesse [Google Cloud Console](https://console.cloud.google.com/)
2. Clique em **Selecionar um projeto** → **Novo projeto**
3. Digite um nome (ex: "OpenClaw Calendar")
4. Clique em **Criar**

### Passo 2: Ativar API Google Calendar

1. No menu lateral, vá em **APIs e Serviços** → **Biblioteca**
2. Procure por "Google Calendar API"
3. Clique em **Ativar**

### Passo 3: Criar Credenciais OAuth 2.0

1. Vá em **APIs e Serviços** → **Credenciais**
2. Clique em **Criar credenciais** → **ID do cliente OAuth**
3. Se solicitado, configure a **Tela de consentimento OAuth**:
   - Tipo: **Externo**
   - Nome do app: "OpenClaw Calendar"
   - Email de suporte: seu email
   - Adicione seu email como **Usuário de teste**
   - Clique em **Salvar e continuar**
   - Em Escopos, adicione: `https://www.googleapis.com/auth/calendar`
   - Clique em **Salvar e continuar**
   - Em Usuários de teste, adicione seu email
   - Clique em **Salvar e continuar**
   - Clique em **Voltar ao painel**

4. Configure o ID do cliente:
   - Tipo de aplicativo: **Aplicativo para computador**
   - Nome: "OpenClaw Calendar"
   - Clique em **Criar**

5. **Copie o Client ID e Client Secret** (você precisará deles)

### Passo 4: Configurar URIs de Redirect (Opcional)

Para aplicativos Desktop, o Google aceita automaticamente `http://localhost` e variações.
Não é necessário configurar URIs específicas, mas se quiser:

- **URIs de redirecionamento autorizadas:** `http://localhost` (ou deixe vazio)

## 2. Configurar Variáveis de Ambiente no Railway

1. No seu projeto Railway, vá em **Variables**
2. Adicione as seguintes variáveis:

   - **Nome:** `GOOGLE_CALENDAR_CLIENT_ID`
   - **Valor:** Cole o Client ID copiado do Google Cloud Console
   - **Tipo:** Plain Text (ou Secret para maior segurança)

   - **Nome:** `GOOGLE_CALENDAR_CLIENT_SECRET`
   - **Valor:** Cole o Client Secret copiado do Google Cloud Console
   - **Tipo:** Secret (recomendado)

3. Clique em **Add** para cada variável

## 3. Primeira Autenticação

### Opção A: Via Bot/Agente (Recomendado)

1. Execute o comando de autenticação através do bot:
   ```bash
   python3 /usr/local/bin/google_calendar.py auth
   ```

2. O bot receberá um JSON com o link:
   ```json
   {
     "step": "authorize",
     "url": "https://accounts.google.com/o/oauth2/v2/auth?...",
     "message": "Por favor, acesse este link para autorizar o aplicativo"
   }
   ```

3. O bot passará o link para você. Acesse o link no seu navegador.

4. Faça login na sua conta Google e autorize o aplicativo.

5. O script continuará e exibirá um código de verificação (o bot passará para você).

6. Digite o código na página do Google.

7. Após autorização, o bot receberá o token completo:
   ```json
   {
     "step": "complete",
     "token": {
       "token": "ya29.a0AfH6SMC...",
       "refresh_token": "1//0gX...",
       ...
     },
     "message": "Autenticação concluída! Copie o token acima e configure GOOGLE_CALENDAR_TOKEN_JSON no Railway"
   }
   ```

8. Copie o JSON completo do token e adicione como variável no Railway:
   - **Nome:** `GOOGLE_CALENDAR_TOKEN_JSON`
   - **Valor:** Cole o JSON completo do token
   - **Tipo:** Secret (recomendado)

### Opção B: Autenticação Local (Desenvolvimento)

Se estiver testando localmente:

1. Configure as variáveis de ambiente localmente:
   ```bash
   export GOOGLE_CALENDAR_CLIENT_ID="seu-client-id"
   export GOOGLE_CALENDAR_CLIENT_SECRET="seu-client-secret"
   ```

2. Execute:
   ```bash
   python3 openclaw-tools/google_calendar.py auth
   ```

3. O navegador abrirá automaticamente para autorização.

4. Após autorização, copie o token JSON exibido e configure no Railway.

## 4. Configurar como Ferramenta no OpenClaw

No OpenClaw, adicione uma ferramenta customizada que execute o script:

**Comando:**
```bash
python3 /usr/local/bin/google_calendar.py [action] [args]
```

**Exemplos de ações:**

- Listar eventos:
  ```bash
  python3 /usr/local/bin/google_calendar.py list --max-results 10
  ```

- Criar evento:
  ```bash
  python3 /usr/local/bin/google_calendar.py create --summary "Reunião" --start-time "2024-01-15T10:00:00-03:00"
  ```

- Atualizar evento:
  ```bash
  python3 /usr/local/bin/google_calendar.py update --event-id "event_id" --summary "Novo título"
  ```

- Deletar evento:
  ```bash
  python3 /usr/local/bin/google_calendar.py delete --event-id "event_id"
  ```

- Obter evento específico:
  ```bash
  python3 /usr/local/bin/google_calendar.py get --event-id "event_id"
  ```

- Listar calendários:
  ```bash
  python3 /usr/local/bin/google_calendar.py list_calendars
  ```

## 5. Formato de Datas

Use formato ISO 8601 para datas/horas:

- Exemplo: `2024-01-15T10:00:00-03:00` (15 de janeiro de 2024, 10:00, fuso horário -03:00)
- Exemplo: `2024-01-15T10:00:00Z` (UTC)

## 6. Renovação Automática de Tokens

O script renova automaticamente tokens expirados. Quando isso acontecer:

1. O script exibirá um JSON com o token renovado
2. Copie o novo token JSON
3. Atualize a variável `GOOGLE_CALENDAR_TOKEN_JSON` no Railway

## Troubleshooting

### Erro: "missing_credentials"

**Causa:** Variáveis `GOOGLE_CALENDAR_CLIENT_ID` ou `GOOGLE_CALENDAR_CLIENT_SECRET` não configuradas.

**Solução:** Configure as variáveis no Railway conforme seção 2.

### Erro: "invalid_token"

**Causa:** Token JSON na variável `GOOGLE_CALENDAR_TOKEN_JSON` está inválido ou corrompido.

**Solução:** 
1. Remova a variável `GOOGLE_CALENDAR_TOKEN_JSON` do Railway
2. Execute autenticação novamente (seção 3)
3. Configure o novo token

### Erro: "oauth_failed"

**Causa:** Erro durante o fluxo OAuth.

**Soluções:**
- Verifique se as credenciais estão corretas
- Verifique se a API Google Calendar está ativada
- Verifique se você está na lista de usuários de teste (se app ainda não está publicado)

### Token expira frequentemente

**Causa:** Token de acesso expira após ~1 hora.

**Solução:** O script renova automaticamente usando o refresh token. Se o refresh token também expirar, faça autenticação novamente.

### Erro ao acessar Calendar API

**Causa:** Permissões insuficientes ou escopo incorreto.

**Solução:**
- Verifique se o escopo `https://www.googleapis.com/auth/calendar` está configurado
- Verifique se você autorizou o aplicativo corretamente
- Para contas Workspace, verifique se o admin aprovou o app (se necessário)

## Notas Importantes

- **Segurança:** Use Railway Secrets para variáveis sensíveis (CLIENT_SECRET e TOKEN_JSON)
- **Workspace:** Se sua conta for Google Workspace, pode ser necessário aprovação do admin
- **Contas pessoais:** Contas @gmail.com não requerem aprovação de admin
- **Tokens:** Tokens são armazenados apenas em variáveis de ambiente, nunca em arquivos

## Suporte

Para mais informações:
- [Documentação Google Calendar API](https://developers.google.com/calendar/api/guides/overview)
- [Documentação OAuth 2.0](https://developers.google.com/identity/protocols/oauth2)

