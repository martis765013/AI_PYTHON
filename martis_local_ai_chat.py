#!/usr/bin/env python3
"""
Martis Local AI Chat
Jednoduchý terminálový chat pro Ollama API.
Vyžaduje Python 3.9+ a běžící Ollamu na http://localhost:11434.
Používá pouze standardní knihovny Pythonu.
"""

import json
import urllib.error
import urllib.request

OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"


def api_request(path, payload=None, timeout=180):
    """Provede HTTP požadavek na lokální Ollama API."""
    url = OLLAMA_URL + path
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"} if data else {}
    request = urllib.request.Request(url, data=data, headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP chyba {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            "Nelze se připojit k Ollamě. Ověř, že Ollama běží "
            "a API je dostupné na http://localhost:11434."
        ) from exc


def list_models():
    result = api_request("/api/tags")
    return [item["name"] for item in result.get("models", [])]


def ask_number(prompt, current, minimum, maximum):
    raw = input(f"{prompt} [{current}]: ").strip()
    if not raw:
        return current
    try:
        value = float(raw)
        if not minimum <= value <= maximum:
            raise ValueError
        return value
    except ValueError:
        print(f"Neplatná hodnota. Zadej číslo od {minimum} do {maximum}.")
        return current


def settings_menu(settings):
    """Umožní změnit parametry; změny se projeví na dalších zprávách."""
    while True:
        print("\n--- Nastavení ---")
        print(f"1. Model             : {settings['model']}")
        print(f"2. Temperature       : {settings['temperature']}")
        print(f"3. System prompt     : {settings['system'] or '(prázdný)'}")
        print(f"4. Max. tokenů       : {settings['num_predict']}")
        print(f"5. Top-p             : {settings['top_p']}")
        print(f"6. Top-k             : {settings['top_k']}")
        print(f"7. Resetovat historii: {'ano' if settings['reset_on_change'] else 'ne'}")
        print("8. Zpět do chatu")

        choice = input("Vyber možnost: ").strip()

        if choice == "1":
            try:
                models = list_models()
                if not models:
                    print("Ollama nevrátila žádné stažené modely.")
                    continue
                print("\nDostupné modely:")
                for i, name in enumerate(models, 1):
                    print(f"{i}. {name}")
                selected = input("Číslo modelu nebo přesný název: ").strip()
                if selected.isdigit() and 1 <= int(selected) <= len(models):
                    settings["model"] = models[int(selected) - 1]
                elif selected in models:
                    settings["model"] = selected
                else:
                    print("Model nebyl nalezen v seznamu.")
            except (RuntimeError, KeyError) as exc:
                print(exc)

        elif choice == "2":
            settings["temperature"] = ask_number(
                "Temperature (0 = méně náhodné, 2 = více náhodné)",
                settings["temperature"], 0, 2
            )
        elif choice == "3":
            print("Zadej nový system prompt. Prázdný vstup jej smaže.")
            settings["system"] = input("> ").strip()
        elif choice == "4":
            settings["num_predict"] = int(ask_number(
                "Maximální počet generovaných tokenů",
                settings["num_predict"], 1, 32768
            ))
        elif choice == "5":
            settings["top_p"] = ask_number(
                "Top-p", settings["top_p"], 0, 1
            )
        elif choice == "6":
            settings["top_k"] = int(ask_number(
                "Top-k", settings["top_k"], 1, 100
            ))
        elif choice == "7":
            settings["reset_on_change"] = not settings["reset_on_change"]
            print("Reset historie při změně modelu: "
                  + ("zapnutý" if settings["reset_on_change"] else "vypnutý"))
        elif choice == "8":
            return
        else:
            print("Neznámá možnost.")


def chat():
    print("=" * 48)
    print(" MARTIS LOCAL AI CHAT")
    print(" Příkazy: /help, /settings, /clear, /exit")
    print("=" * 48)

    settings = {
        "model": DEFAULT_MODEL,
        "temperature": 0.7,
        "system": "Jsi užitečný, přesný a přátelský asistent.",
        "num_predict": 512,
        "top_p": 0.9,
        "top_k": 40,
        "reset_on_change": True,
    }
    history = []
    last_model = settings["model"]

    # Ověření připojení a výběr dostupného výchozího modelu
    try:
        models = list_models()
        if not models:
            print("Nemáš stažený žádný model. Stáhni si například:")
            print("  ollama pull qwen2.5:1.5b")
            return
        if settings["model"] not in models:
            settings["model"] = models[0]
            print(f"Výchozí model nebyl nalezen; používám {models[0]}.")
        print(f"Model: {settings['model']}")
    except RuntimeError as exc:
        print(exc)
        return

    while True:
        try:
            user_text = input("\nTy: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nUkončuji chat.")
            break

        if not user_text:
            continue

        command = user_text.lower()
        if command in ("/exit", "/quit", "/q"):
            print("Ahoj!")
            break
        if command == "/help":
            print("Příkazy:")
            print("  /settings  otevře nastavení")
            print("  /clear     smaže historii konverzace")
            print("  /exit      ukončí program")
            print("Nastavení můžeš měnit i během konverzace.")
            continue
        if command == "/settings":
            old_model = settings["model"]
            settings_menu(settings)
            if settings["model"] != old_model and settings["reset_on_change"]:
                history.clear()
                print("Model změněn; historie byla vymazána.")
            continue
        if command == "/clear":
            history.clear()
            print("Historie konverzace byla vymazána.")
            continue

        messages = []
        if settings["system"]:
            messages.append({"role": "system", "content": settings["system"]})
        messages.extend(history)
        messages.append({"role": "user", "content": user_text})

        payload = {
            "model": settings["model"],
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": settings["temperature"],
                "num_predict": settings["num_predict"],
                "top_p": settings["top_p"],
                "top_k": settings["top_k"],
            },
        }

        print("\nAI: přemýšlím…")
        try:
            result = api_request("/api/chat", payload)
            answer = result.get("message", {}).get("content", "").strip()
            if not answer:
                print("Model vrátil prázdnou odpověď.")
                continue

            print(f"\nAI ({settings['model']}):\n{answer}")
            history.append({"role": "user", "content": user_text})
            history.append({"role": "assistant", "content": answer})

            # Historii necháváme pro jednoduchost celou. /clear ji vymaže.
            # U velkých konverzací může být vhodné ji omezit.
            if result.get("done_reason") == "length":
                print("\n[Odpověď dosáhla limitu tokenů.]")

        except (RuntimeError, TimeoutError) as exc:
            print(f"\nChyba: {exc}")


if __name__ == "__main__":
    chat()
