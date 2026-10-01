import sys

from google import genai

from services.agent.settings import MODEL, api_key


def main():
    client = genai.Client(api_key=api_key())
    if "--models" in sys.argv:
        for model in client.models.list():
            print(model.name)
        return
    print("model:", MODEL)
    print(client.models.generate_content(model=MODEL, contents="Reply with the word OK").text)


if __name__ == "__main__":
    main()