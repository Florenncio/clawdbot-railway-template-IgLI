#!/usr/bin/env python3
"""
Script para acessar Google Calendar via OAuth 2.0
Funciona sem necessidade de acesso de admin - usa autenticação do usuário
Suporta fluxo OAuth em três etapas para integração com bot/agente
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print(
        json.dumps(
            {
                "status": "error",
                "error": "missing_dependencies",
                "message": "Bibliotecas do Google não instaladas. Execute: pip install -r requirements.txt",
            }
        ),
        file=sys.stderr,
    )
    sys.exit(1)

# Escopos necessários para acessar o Calendar
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_client_config():
    """Constrói configuração OAuth a partir de variáveis de ambiente."""
    client_id = os.getenv("GOOGLE_CALENDAR_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CALENDAR_CLIENT_SECRET")

    if not client_id or not client_secret:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": "missing_credentials",
                    "message": "Variáveis de ambiente GOOGLE_CALENDAR_CLIENT_ID e GOOGLE_CALENDAR_CLIENT_SECRET são necessárias",
                    "instructions": "Configure essas variáveis no Railway antes de usar o script",
                }
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "redirect_uris": ["http://localhost"],
        }
    }


def get_credentials_from_env():
    """Tenta carregar credenciais da variável de ambiente."""
    token_json = os.getenv("GOOGLE_CALENDAR_TOKEN_JSON")
    if not token_json:
        return None

    try:
        token_data = json.loads(token_json)
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        return creds
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": "invalid_token",
                    "message": f"Token JSON inválido na variável GOOGLE_CALENDAR_TOKEN_JSON: {e}",
                }
            ),
            file=sys.stderr,
        )
        return None


def authenticate_oauth_flow():
    """
    Realiza autenticação OAuth em três etapas.
    Retorna credenciais após autorização completa.
    """
    client_config = get_client_config()

    # Detecta ambiente headless
    is_headless = not sys.stdin.isatty() or os.getenv("RAILWAY_ENVIRONMENT") is not None

    if is_headless:
        # Device flow para ambiente headless
        # Etapa 1: Gerar e exibir URL
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        authorization_url, _ = flow.authorization_url(
            prompt="consent", access_type="offline", redirect_uri="http://localhost"
        )

        print(
            json.dumps(
                {
                    "step": "authorize",
                    "url": authorization_url,
                    "message": "Por favor, acesse este link para autorizar o aplicativo",
                }
            )
        )
        sys.stdout.flush()

        # Etapa 2 e 3: run_console() vai exibir código e obter token
        # Nota: run_console() exibe URL e código juntos, mas já exibimos URL acima
        # O código será exibido pelo run_console() em formato texto normal
        # Para melhorar isso no futuro, precisaríamos implementar device flow manualmente
        try:
            creds = flow.run_console()
            return creds
        except Exception as e:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "error": "oauth_failed",
                        "message": f"Erro no fluxo OAuth: {e}",
                    }
                ),
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        # Local server para ambiente interativo
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True)
        return creds


def get_credentials():
    """Obtém credenciais válidas, fazendo OAuth se necessário."""
    # Tenta carregar token da variável de ambiente
    creds = get_credentials_from_env()

    if creds and creds.valid:
        return creds

    # Se token expirado, tenta renovar
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Token renovado - exibir para usuário atualizar variável
            token_json = json.dumps(json.loads(creds.to_json()), indent=2)
            print(
                json.dumps(
                    {
                        "step": "token_refreshed",
                        "token": json.loads(creds.to_json()),
                        "message": "Token renovado automaticamente. Atualize GOOGLE_CALENDAR_TOKEN_JSON no Railway com o token acima.",
                    }
                )
            )
            return creds
        except Exception as e:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "error": "refresh_failed",
                        "message": f"Erro ao renovar token: {e}. É necessário fazer autenticação novamente.",
                    }
                ),
                file=sys.stderr,
            )
            creds = None

    # Precisa fazer OAuth
    if not creds:
        creds = authenticate_oauth_flow()

        # Após autenticação bem-sucedida, exibir token para usuário copiar
        token_data = json.loads(creds.to_json())
        print(
            json.dumps(
                {
                    "step": "complete",
                    "token": token_data,
                    "message": "Autenticação concluída! Copie o token acima e configure GOOGLE_CALENDAR_TOKEN_JSON no Railway",
                }
            )
        )

    return creds


def list_events(max_results=10, time_min=None, time_max=None):
    """Lista eventos do calendário."""
    try:
        creds = get_credentials()
        service = build("calendar", "v3", credentials=creds)

        calendar_id = "primary"
        now = datetime.utcnow().isoformat() + "Z"
        if time_min:
            try:
                time_min_dt = datetime.fromisoformat(time_min.replace("Z", "+00:00"))
                time_min = time_min_dt.isoformat() + "Z"
            except ValueError:
                time_min = now
        else:
            time_min = now

        if time_max:
            try:
                time_max_dt = datetime.fromisoformat(time_max.replace("Z", "+00:00"))
                time_max = time_max_dt.isoformat() + "Z"
            except ValueError:
                time_max = None

        events_result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])

        result = {"status": "success", "count": len(events), "events": []}

        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            result["events"].append(
                {
                    "id": event.get("id"),
                    "summary": event.get("summary", "(Sem título)"),
                    "start": start,
                    "end": event["end"].get("dateTime", event["end"].get("date")),
                    "location": event.get("location", ""),
                    "description": (event.get("description", "") or "")[:200],
                }
            )

        return json.dumps(result, indent=2, ensure_ascii=False)

    except HttpError as error:
        return json.dumps(
            {
                "status": "error",
                "error": str(error),
                "message": f"Erro ao acessar Google Calendar: {error}",
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "message": f"Erro inesperado: {e}"},
            ensure_ascii=False,
        )


def create_event(summary, start_time, end_time=None, location=None, description=None):
    """Cria um novo evento no calendário."""
    try:
        creds = get_credentials()
        service = build("calendar", "v3", credentials=creds)

        # Parse dos tempos
        if not end_time:
            # Se não especificado, assume 1 hora de duração
            try:
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                end_dt = start_dt + timedelta(hours=1)
                end_time = end_dt.isoformat()
            except ValueError:
                return json.dumps(
                    {
                        "status": "error",
                        "error": "invalid_time_format",
                        "message": "Formato de data/hora inválido. Use ISO format (ex: 2024-01-15T10:00:00-03:00)",
                    },
                    ensure_ascii=False,
                )

        event = {
            "summary": summary,
            "start": {
                "dateTime": start_time,
                "timeZone": "America/Sao_Paulo",
            },
            "end": {
                "dateTime": end_time,
                "timeZone": "America/Sao_Paulo",
            },
        }

        if location:
            event["location"] = location
        if description:
            event["description"] = description

        created_event = (
            service.events().insert(calendarId="primary", body=event).execute()
        )

        return json.dumps(
            {
                "status": "success",
                "message": "Evento criado com sucesso",
                "event": {
                    "id": created_event.get("id"),
                    "summary": created_event.get("summary"),
                    "start": created_event["start"].get("dateTime"),
                    "end": created_event["end"].get("dateTime"),
                    "htmlLink": created_event.get("htmlLink"),
                },
            },
            indent=2,
            ensure_ascii=False,
        )

    except HttpError as error:
        return json.dumps(
            {
                "status": "error",
                "error": str(error),
                "message": f"Erro ao criar evento: {error}",
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "message": f"Erro inesperado: {e}"},
            ensure_ascii=False,
        )


def update_event(
    event_id,
    summary=None,
    start_time=None,
    end_time=None,
    location=None,
    description=None,
):
    """Atualiza um evento existente."""
    try:
        creds = get_credentials()
        service = build("calendar", "v3", credentials=creds)

        # Busca evento existente
        event = service.events().get(calendarId="primary", eventId=event_id).execute()

        # Atualiza campos fornecidos
        if summary:
            event["summary"] = summary
        if start_time:
            event["start"] = {
                "dateTime": start_time,
                "timeZone": "America/Sao_Paulo",
            }
        if end_time:
            event["end"] = {
                "dateTime": end_time,
                "timeZone": "America/Sao_Paulo",
            }
        if location is not None:
            event["location"] = location
        if description is not None:
            event["description"] = description

        updated_event = (
            service.events()
            .update(calendarId="primary", eventId=event_id, body=event)
            .execute()
        )

        return json.dumps(
            {
                "status": "success",
                "message": "Evento atualizado com sucesso",
                "event": {
                    "id": updated_event.get("id"),
                    "summary": updated_event.get("summary"),
                    "start": updated_event["start"].get("dateTime"),
                    "end": updated_event["end"].get("dateTime"),
                    "htmlLink": updated_event.get("htmlLink"),
                },
            },
            indent=2,
            ensure_ascii=False,
        )

    except HttpError as error:
        return json.dumps(
            {
                "status": "error",
                "error": str(error),
                "message": f"Erro ao atualizar evento: {error}",
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "message": f"Erro inesperado: {e}"},
            ensure_ascii=False,
        )


def delete_event(event_id):
    """Deleta um evento do calendário."""
    try:
        creds = get_credentials()
        service = build("calendar", "v3", credentials=creds)

        service.events().delete(calendarId="primary", eventId=event_id).execute()

        return json.dumps(
            {"status": "success", "message": f"Evento {event_id} deletado com sucesso"},
            indent=2,
            ensure_ascii=False,
        )

    except HttpError as error:
        return json.dumps(
            {
                "status": "error",
                "error": str(error),
                "message": f"Erro ao deletar evento: {error}",
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "message": f"Erro inesperado: {e}"},
            ensure_ascii=False,
        )


def get_event(event_id):
    """Obtém detalhes de um evento específico."""
    try:
        creds = get_credentials()
        service = build("calendar", "v3", credentials=creds)

        event = service.events().get(calendarId="primary", eventId=event_id).execute()

        return json.dumps(
            {
                "status": "success",
                "event": {
                    "id": event.get("id"),
                    "summary": event.get("summary", "(Sem título)"),
                    "start": event["start"].get("dateTime", event["start"].get("date")),
                    "end": event["end"].get("dateTime", event["end"].get("date")),
                    "location": event.get("location", ""),
                    "description": event.get("description", ""),
                    "htmlLink": event.get("htmlLink"),
                },
            },
            indent=2,
            ensure_ascii=False,
        )

    except HttpError as error:
        return json.dumps(
            {
                "status": "error",
                "error": str(error),
                "message": f"Erro ao obter evento: {error}",
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "message": f"Erro inesperado: {e}"},
            ensure_ascii=False,
        )


def list_calendars():
    """Lista calendários disponíveis."""
    try:
        creds = get_credentials()
        service = build("calendar", "v3", credentials=creds)

        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get("items", [])

        result = {"status": "success", "count": len(calendars), "calendars": []}

        for calendar in calendars:
            result["calendars"].append(
                {
                    "id": calendar.get("id"),
                    "summary": calendar.get("summary"),
                    "description": calendar.get("description", ""),
                    "timeZone": calendar.get("timeZone", ""),
                }
            )

        return json.dumps(result, indent=2, ensure_ascii=False)

    except HttpError as error:
        return json.dumps(
            {
                "status": "error",
                "error": str(error),
                "message": f"Erro ao listar calendários: {error}",
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "message": f"Erro inesperado: {e}"},
            ensure_ascii=False,
        )


def main():
    parser = argparse.ArgumentParser(description="Acessa Google Calendar via OAuth 2.0")
    parser.add_argument(
        "action",
        choices=["list", "create", "update", "delete", "get", "list_calendars", "auth"],
        help="Ação a executar",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        help="Número máximo de eventos para listar",
    )
    parser.add_argument("--time-min", help="Data/hora mínima (ISO format)")
    parser.add_argument("--time-max", help="Data/hora máxima (ISO format)")
    parser.add_argument("--summary", help="Título do evento")
    parser.add_argument("--start-time", help="Data/hora de início (ISO format)")
    parser.add_argument("--end-time", help="Data/hora de fim (ISO format)")
    parser.add_argument("--location", help="Localização do evento")
    parser.add_argument("--description", help="Descrição do evento")
    parser.add_argument("--event-id", help="ID do evento")

    args = parser.parse_args()

    if args.action == "auth":
        # Apenas faz autenticação
        try:
            creds = get_credentials()
            # get_credentials() já exibe o JSON apropriado
            # Se chegou aqui sem erro, autenticação foi bem-sucedida
            if not os.getenv("GOOGLE_CALENDAR_TOKEN_JSON"):
                # Token foi gerado mas ainda não está na variável
                # get_credentials() já exibiu o JSON com o token
                pass
        except Exception as e:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "error": str(e),
                        "message": f"Erro na autenticação: {e}",
                    }
                ),
                file=sys.stderr,
            )
            sys.exit(1)

    elif args.action == "list":
        print(list_events(args.max_results, args.time_min, args.time_max))

    elif args.action == "create":
        if not args.summary or not args.start_time:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "message": "É necessário fornecer --summary e --start-time",
                    }
                ),
                file=sys.stderr,
            )
            sys.exit(1)
        print(
            create_event(
                args.summary,
                args.start_time,
                args.end_time,
                args.location,
                args.description,
            )
        )

    elif args.action == "update":
        if not args.event_id:
            print(
                json.dumps(
                    {"status": "error", "message": "É necessário fornecer --event-id"}
                ),
                file=sys.stderr,
            )
            sys.exit(1)
        print(
            update_event(
                args.event_id,
                args.summary,
                args.start_time,
                args.end_time,
                args.location,
                args.description,
            )
        )

    elif args.action == "delete":
        if not args.event_id:
            print(
                json.dumps(
                    {"status": "error", "message": "É necessário fornecer --event-id"}
                ),
                file=sys.stderr,
            )
            sys.exit(1)
        print(delete_event(args.event_id))

    elif args.action == "get":
        if not args.event_id:
            print(
                json.dumps(
                    {"status": "error", "message": "É necessário fornecer --event-id"}
                ),
                file=sys.stderr,
            )
            sys.exit(1)
        print(get_event(args.event_id))

    elif args.action == "list_calendars":
        print(list_calendars())


if __name__ == "__main__":
    main()
