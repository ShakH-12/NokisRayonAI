import os

path = os.listdir()

if "db.sqlite3" in path:
    os.remove("db.sqlite3")

apps = ["apps/ai", "web_view"]

for app in apps:
    path = os.listdir(app)
    if "migrations" in path:
        os.chdir(f"{app}/migrations/")
        print(f"{app} found: {os.listdir()}")
        files = os.listdir()

        for file in files:
            if file not in ["__pycache__", "__init__.py"]:
                os.remove(file)
        print(f"{app} then: {os.listdir()}")
        print("\n" * 2)

    os.chdir("../..")

print(os.listdir())