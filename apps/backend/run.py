from app import create_app

app = create_app()


if __name__ == "__main__":
    container = app.extensions["container"]
    settings = container.settings
    app.run(
        host=settings.flask_host,
        port=settings.flask_port,
        debug=settings.flask_debug,
        use_reloader=False,
    )
